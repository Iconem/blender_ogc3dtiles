"""Terrain blending (beta): a detailed dataset shown over a terrain or a globe.

The two overlap: the terrain pokes through the dataset, and the dataset ends on a hard edge. With
*Blend datasets into this terrain* ticked on a background tileset (a globe, a terrain layer, Google or
Bing 3D Tiles), the footprint of every other tileset, seen from above, is kept as a small raster,
the **coverage**: metres from each covered ground cell to the nearest uncovered one, and the datasets'
lowest height there. Tile materials read it:

  * the terrain's tiles become transparent under the datasets (from *Terrain inset* metres inside the
    footprint, over *Terrain fade* metres), except where the terrain lies under the datasets' lowest
    point there (*Keep terrain below*): it then stays, as the ground seen through a sparse point cloud
    or under a dataset that floats;
  * the datasets' tiles fade in over their first *Dataset fade* metres, so their border dissolves
    into the terrain.

The coverage is made from the tiles shown (blend_raster), one tile at a time and kept per tile, in the
frame of an Empty placed at the datasets (east, north, up there) that rides the first dataset's root.
One coverage for the scene: every blended terrain reads the same one.

Both fades are one Mix Shader with a Transparent BSDF, behind the clipping mixes, driven by the shared
group ``OGC3D Blend``. Its numbers are custom properties of the scene, read by Attribute nodes
(shader_params): a slider, or a coverage made again, touches no node tree. (As Value nodes of the group,
each write re-evaluated every tile material: seconds of frozen viewport with a thousand tiles.)
"""
from __future__ import annotations

import math
import time

import bpy
import numpy as np

from . import blend_raster as br
from . import shader_params as sp

PREF = "beta_terrain_blend"
FRAME = "OGC3D Blend Frame"
IMAGE = "OGC3D Blend Coverage"
GROUP = "OGC3D Blend"
MIX = "OGC3D Blend Mix"
TRANSPARENT = "OGC3D Blend Transparent"
KEEP = "OGC3D Blend Keep"
OUTPUTS = {"terrain": "Terrain Keep", "dataset": "Dataset Keep"}
OUT = "Keep"                 # what a tile material reads: all there, or one of the two above, by the tile's role
ROLE = "ogc3d_blend_role"    # on a tile object, read by the group: 0 takes no part, 1 terrain, 2 dataset
ROLES = {None: 0, "terrain": 1, "dataset": 2}
GLOBAL_RADIUS_M = 1.0e6
DATASET_CENTRE_M = 6.3e6     # a dataset's centre is at least this far from the Earth's: under 70 km deep
SCAN_PERIOD_S = 0.25
CELLS_BUDGET_S = 0.015      # rasterising new tiles, per tick
MATS_BUDGET_S = 0.008       # material edits, per tick
MATS_BACKLOG = 24           # more tiles than this waiting for their mix: the wider budget
MATS_BACKLOG_S = 0.05
REBUILD_PERIOD_S = 3.0      # the coverage follows the tiles shown at most this often (at once in a render)
AUTO_SHARE = 0.05           # Auto: the dataset fades over this share of the smallest dataset's width

_state = {"cells": {}, "boxes": {}, "cell": None, "sig": None, "frame_ecef": None, "frame_sig": None,
          "done": {}, "t_scan": 0.0, "vis": {}, "info": "", "build_ms": 0.0, "t_build": -1e9, "now": False,
          "auto": False}


def enabled() -> bool:
    from .io import addon_pref
    return bool(addon_pref(PREF, False))


def _is_aggregate(st) -> bool:
    """Do this stream's tiles come from datasets of a tileset of tilesets? A dataset has a place on the
    surface. Google pages its own hierarchy through external files: those "datasets" are regions so wide
    that their centres lie 150 km and more under the surface (a 1000 km wide country: 20 km), and do not
    count."""
    seen = getattr(st.get("backend"), "tile_dataset", None)
    if not seen:
        return False
    memo = st.get("blend_aggregate")
    if memo is None or memo[0] != len(seen):
        local = False
        for v in {id(v): v for v in list(seen.values()) if v}.values():
            try:
                local = float(np.linalg.norm(np.asarray(v[1], np.float64)[:3])) > DATASET_CENTRE_M
            except Exception:                        # noqa: BLE001
                local = False
            if local:
                break
        memo = st["blend_aggregate"] = (len(seen), local)
    return memo[1]


def is_background(item, st) -> bool:
    """A globe, a terrain layer, or a tileset that spans the planet (Google, Bing). A tileset of tilesets is
    never one, however wide its datasets are spread."""
    if item.kind in ("GLOBE", "TERRAIN"):
        return True
    if item.kind == "AGGREGATE":
        return False
    if st and _is_aggregate(st):
        return False
    b = st.get("backend") if st else None
    r = b.root_radius_m() if b is not None and hasattr(b, "root_radius_m") else None
    if r is None:
        return item.kind == "ION" and st is None     # not known yet: an ion asset may be Cesium World Terrain
    return r >= GLOBAL_RADIUS_M


def wanted(props) -> bool:
    return enabled() and any(it.use_blend for it in props.tilesets)


def roles(props, streams) -> dict:
    """{tileset uid: "terrain" | "dataset"} of the running streams."""
    out = {}
    if not wanted(props):
        return out
    from .ui import _stream_hidden
    live = [(it, streams.get(it.uid)) for it in props.tilesets if it.uid]
    live = [(it, st) for it, st in live if st is not None and st.get("backend") is not None
            and st.get("mode") == "native"]
    for it, st in live:
        if it.use_blend:
            out[it.uid] = "terrain"
    if not out:
        return {}
    for it, st in live:
        if it.uid not in out and not is_background(it, st) and not _stream_hidden(st):
            out[it.uid] = "dataset"
    return out


# ── shader ───────────────────────────────────────────────────────────────────
PARAM = "blend "             # scene properties: ogc3d_blend_<name>
# written when the group is made. A scene without the properties reads 0 everywhere: nothing covered, no
# fade, the tiles whole
DEFAULTS = {"Range": 0.0, "Low Range": 1.0, "Low Min": 0.0, "Below Margin": 2.0, "Keep Below": 1.0,
            "Terrain Inset": 10.0, "Terrain Fade": 10.0, "Dataset Fade": 20.0,
            "Place Scale": (1.0, 1.0, 1.0), "Place Location": (0.0, 0.0, 0.0),
            "Frame X": (1.0, 0.0, 0.0), "Frame Y": (0.0, 1.0, 0.0), "Frame Z": (0.0, 0.0, 1.0), "Frame T": (0.0, 0.0, 0.0)}


def _write(values, only_missing=False) -> bool:
    return sp.write({PARAM + k: v for k, v in values.items()}, only_missing=only_missing)


def ensure_group():
    ng = bpy.data.node_groups.get(GROUP)
    if (ng is not None and sp.is_param(ng.nodes.get("Low Range")) and sp.is_param(ng.nodes.get("Frame T"))
            and ng.nodes.get("Role") is not None):
        return ng
    ng = ng or bpy.data.node_groups.new(GROUP, "ShaderNodeTree")
    ng.nodes.clear()                                 # an older group (numbers in Value nodes) is made again; its
    have = {it.name for it in ng.interface.items_tree if getattr(it, "in_out", "") == "OUTPUT"}
    for name in (OUT, *OUTPUTS.values()):            # outputs stay, so the tile materials keep their links
        if name not in have:
            ng.interface.new_socket(name, in_out="OUTPUT", socket_type="NodeSocketFloat")

    def _value(ng, name, _default=None):
        return sp.socket(ng, name, PARAM + name)
    N, L = ng.nodes.new, ng.links.new

    def math_(op, a=None, b=None, value=None):
        n = N("ShaderNodeMath")
        n.operation = op
        for i, s in enumerate((a, b)):
            if s is not None:
                L(s, n.inputs[i])
        if value is not None:
            n.inputs[1].default_value = value
        return n.outputs[0]

    out = N("NodeGroupOutput")
    # the surface point in the coverage's frame: the world position through a matrix kept as scene properties.
    # (A Texture Coordinate node set on the frame's Empty did the same, but each move of that Empty
    # re-evaluated every tile material: 3 s for 1,400 of them.)
    geo = N("ShaderNodeNewGeometry")
    comb = N("ShaderNodeCombineXYZ")
    for i, axis in enumerate("XYZ"):
        dot = N("ShaderNodeVectorMath")
        dot.operation = "DOT_PRODUCT"
        L(geo.outputs["Position"], dot.inputs[0])
        L(sp.socket(ng, "Frame " + axis, PARAM + "Frame " + axis, vector=True), dot.inputs[1])
        L(dot.outputs["Value"], comb.inputs[i])
    moved = N("ShaderNodeVectorMath")
    moved.operation = "ADD"
    L(comb.outputs[0], moved.inputs[0])
    L(sp.socket(ng, "Frame T", PARAM + "Frame T", vector=True), moved.inputs[1])
    in_frame = moved.outputs[0]
    mp = N("ShaderNodeMapping")
    mp.name = "Place"
    mp.vector_type = "POINT"
    tex = N("ShaderNodeTexImage")
    tex.name = "Coverage"
    tex.interpolation = "Linear"
    tex.extension = "CLIP"
    L(in_frame, mp.inputs["Vector"])
    L(sp.socket(ng, "Place Scale", PARAM + "Place Scale", vector=True), mp.inputs["Scale"])
    L(sp.socket(ng, "Place Location", PARAM + "Place Location", vector=True), mp.inputs["Location"])
    L(mp.outputs[0], tex.inputs["Vector"])
    rng = _value(ng, "Range", 1.0)                   # the image holds 0..1: metres inside / Range
    sep = N("ShaderNodeSeparateColor")
    L(tex.outputs["Color"], sep.inputs[0])
    inside = math_("MULTIPLY", sep.outputs[0], rng)
    # green: the datasets' lowest height in the cell, 0..1 over Low Min .. Low Min + Low Range
    low = math_("ADD", math_("MULTIPLY", sep.outputs[1], _value(ng, "Low Range", 1.0)),
                _value(ng, "Low Min", 0.0))
    xyz = N("ShaderNodeSeparateXYZ")
    L(in_frame, xyz.inputs[0])
    under = N("ShaderNodeMapRange")                  # 1 where the surface is Margin under the datasets
    L(math_("SUBTRACT", low, xyz.outputs["Z"]), under.inputs["Value"])
    margin = _value(ng, "Below Margin", 2.0)
    L(margin, under.inputs["From Min"])
    L(math_("ADD", margin, value=1.0), under.inputs["From Max"])
    below = math_("MULTIPLY", under.outputs[0], _value(ng, "Keep Below", 1.0))
    inset, t_fade, d_fade = (_value(ng, k, v) for k, v in (("Terrain Inset", 10.0), ("Terrain Fade", 10.0),
                                                           ("Dataset Fade", 20.0)))
    # terrain: all there up to Inset metres inside the footprint, gone Fade metres further
    t_to = math_("ADD", inset, math_("MAXIMUM", t_fade, value=0.01))
    mr = N("ShaderNodeMapRange")
    mr.interpolation_type = "SMOOTHSTEP"
    L(inside, mr.inputs["Value"])
    L(inset, mr.inputs["From Min"])
    L(t_to, mr.inputs["From Max"])
    mr.inputs["To Min"].default_value, mr.inputs["To Max"].default_value = 1.0, 0.0
    k_terrain = math_("MAXIMUM", mr.outputs[0], below)
    L(k_terrain, out.inputs[OUTPUTS["terrain"]])
    # datasets: nothing at their border, all there Fade metres inside; Fade 0: all there
    md = N("ShaderNodeMapRange")
    md.interpolation_type = "SMOOTHSTEP"
    L(inside, md.inputs["Value"])
    md.inputs["From Min"].default_value = 0.0
    L(math_("MAXIMUM", d_fade, value=0.01), md.inputs["From Max"])
    off = math_("LESS_THAN", d_fade, value=0.005)
    k_dataset = math_("MAXIMUM", md.outputs[0], off)
    L(k_dataset, out.inputs[OUTPUTS["dataset"]])
    # the tile's own role, a property of its object: switching a tileset in or out of the blend writes the
    # property, and no material changes
    role = N("ShaderNodeAttribute")
    role.name = role.label = "Role"
    role.attribute_type = "OBJECT"
    role.attribute_name = ROLE
    r = role.outputs["Fac"]
    is_d = math_("GREATER_THAN", r, value=1.5)
    is_t = math_("SUBTRACT", math_("GREATER_THAN", r, value=0.5), is_d)
    gone = math_("ADD", math_("MULTIPLY", is_t, math_("SUBTRACT", is_t, k_terrain)),
                 math_("MULTIPLY", is_d, math_("SUBTRACT", is_d, k_dataset)))
    one = N("ShaderNodeMath")
    one.operation = "SUBTRACT"
    one.inputs[0].default_value = 1.0
    L(gone, one.inputs[1])
    L(one.outputs[0], out.inputs[OUT])
    from .node_layout import arrange
    arrange(ng)
    _write(DEFAULTS, only_missing=True)
    # the image is in the group from the start: assigning it later is a write to a node of the group, which
    # re-evaluates every tile material that already holds it
    tex.image = _coverage_image()
    return ng


def _frame_object():
    frame = bpy.data.objects.get(FRAME)
    if frame is None:
        frame = bpy.data.objects.new(FRAME, None)
        frame.empty_display_type = "PLAIN_AXES"
        frame.empty_display_size = 1.0
        frame.hide_viewport = frame.hide_render = True
        frame.hide_select = True
    return frame


def _coverage_image(w=2, h=2):
    img = bpy.data.images.get(IMAGE)
    if img is None:
        img = bpy.data.images.new(IMAGE, w, h, alpha=False, float_buffer=True, is_data=True)
    return img


def set_params(props) -> None:
    """The sliders, as scene properties the shared group reads (live, no node is touched)."""
    _write({"Terrain Inset": props.blend_terrain_inset, "Terrain Fade": props.blend_terrain_fade,
            "Dataset Fade": props.blend_dataset_fade, "Keep Below": 1.0 if props.blend_keep_below else 0.0,
            "Below Margin": props.blend_below_margin})


def _remove_nodes(nt) -> bool:
    mix = nt.nodes.get(MIX)
    src = mix.inputs[2].links[0].from_socket if mix is not None and mix.inputs[2].links else None
    dst = [lk.to_socket for lk in mix.outputs[0].links] if mix is not None else []
    found = False
    for name in (MIX, TRANSPARENT, KEEP):
        n = nt.nodes.get(name)
        if n is not None:
            nt.nodes.remove(n)
            found = True
    if src is not None:
        for s in dst:
            nt.links.new(src, s)
    return found


def apply_material(mat, on) -> bool:
    """Put the blend mix in a tile material (``on`` false takes it out). What it does is the tile's role."""
    if mat is None or mat.node_tree is None:
        return False
    nt = mat.node_tree
    mix = nt.nodes.get(MIX)
    if not on:
        return _remove_nodes(nt)
    keep = nt.nodes.get(KEEP)
    if mix is not None and keep is not None and mix.outputs[0].links and mix.inputs[2].links:
        want = keep.outputs.get(OUT)
        if want is not None and not any(lk.from_socket == want for lk in mix.inputs[0].links):
            nt.links.new(want, mix.inputs[0])        # a material from before the roles: one link, once
        return False
    _remove_nodes(nt)
    from .materials import surface_target
    target = surface_target(nt, include_poly=True, behind_xray=False)
    if target is None or not target.links:
        return False
    src = target.links[0].from_socket
    x, y = target.node.location
    keep = nt.nodes.new("ShaderNodeGroup")
    keep.name = keep.label = KEEP
    keep.node_tree = ensure_group()
    keep.location = (x - 620, y - 560)
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    tr.name = tr.label = TRANSPARENT
    tr.location = (x - 620, y - 700)
    mix = nt.nodes.new("ShaderNodeMixShader")
    mix.name = mix.label = MIX
    mix.location = (x - 400, y - 560)
    nt.links.new(keep.outputs[OUT], mix.inputs[0])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(src, mix.inputs[2])
    nt.links.new(mix.outputs[0], target)
    return True


def _is_splat(o) -> bool:
    return bool(o.get("splats")) or o.modifiers.get("Splats") is not None


def prewired() -> bool:
    """Tile materials: Instant switches. Every tile carries the mix from the start."""
    try:
        return bpy.context.scene.ogc3dtiles.tile_shaders == "ALWAYS"
    except Exception:                                # noqa: BLE001
        return False


def _set_role(o, role) -> None:
    code = ROLES[role]
    if int(o.get(ROLE, 0)) != code:
        o[ROLE] = code
        o.update_tag(refresh={"OBJECT"})


def _apply_object(o, role) -> None:
    if o is None or o.type != "MESH" or o.data is None:
        return
    if role == "dataset" and _is_splat(o):           # splats add up their own way: they only count in the coverage
        role = None
    _set_role(o, role)
    if role is not None or not prewired():
        for m in o.data.materials:
            apply_material(m, role is not None)


def new_tile(obj) -> None:
    """A tile just built, with Instant switches: the mix from the start, taking no part until it has a role."""
    if obj is None or not enabled() or not prewired():
        return
    for o in ([obj] if obj.type == "MESH" else [c for c in obj.children if c.type == "MESH"]):
        if o.data is not None and not _is_splat(o):
            for m in o.data.materials:
                apply_material(m, True)


def teardown() -> None:
    """Blending switched off: every tile material loses its mix."""
    from .io import tile_mesh_objects
    for o in list(tile_mesh_objects()):
        _apply_object(o, None)
    _state.update(cells={}, boxes={}, cell=None, sig=None, frame_ecef=None, frame_sig=None, done={}, vis={}, info="")


# ── coverage ─────────────────────────────────────────────────────────────────
def _tile_objects(st, shown_only=True):
    """Mesh objects of the tiles a stream shows."""
    objs = bpy.data.objects
    for rec in st["tiles"].values():
        if shown_only and not rec.visible:
            continue
        o = objs.get(rec.holder)
        if o is None:
            continue
        if o.type in ("MESH", "POINTCLOUD"):
            yield o
        else:
            yield from (c for c in o.children if c.type in ("MESH", "POINTCLOUD"))


def _np(m) -> np.ndarray:
    return np.array(m, np.float64)


def _ensure_frame(props, st, objs):
    """The Empty the coverage is drawn in: east, north, up at the datasets, child of the first dataset's root.
    Its place on Earth is fixed once; a scene origin that moves only changes its matrix."""
    from .tile_bounds import _ecef_to_world
    from .ui import _enu_from_ecef
    root = bpy.data.objects.get(st.get("root_obj") or "")
    if root is None:
        return None
    if _state["frame_ecef"] is not None and _far_from_frame(st, objs):
        _state["frame_ecef"] = None                  # the datasets are somewhere else now
    if _state["frame_ecef"] is None:
        pts = np.array([_np(o.matrix_world) @ (*c, 1.0) for o in objs for c in (o.bound_box[0], o.bound_box[6])])
        if not len(pts):
            return None
        centre = np.linalg.inv(_ecef_to_world(st)) @ ((pts.min(0) + pts.max(0)) / 2)
        up = centre[:3] / np.linalg.norm(centre[:3])
        east = np.cross((0.0, 0.0, 1.0), up)
        east /= np.linalg.norm(east) or 1.0
        m = np.eye(4)
        m[:3, 0], m[:3, 1], m[:3, 2], m[:3, 3] = east, np.cross(up, east), up, centre[:3]
        _state["frame_ecef"] = m
        _state["cells"].clear()
    frame = _frame_object()
    for coll in root.users_collection[:1]:
        if coll.objects.get(frame.name) is None:
            for c in frame.users_collection:
                c.objects.unlink(frame)
            coll.objects.link(frame)
    local = np.asarray(_enu_from_ecef(props, st), np.float64) @ _state["frame_ecef"]
    sig = (root.name, tuple(np.round(local, 4).ravel()))
    if sig != _state["frame_sig"]:
        from mathutils import Matrix
        frame.parent = root
        frame.matrix_parent_inverse = Matrix.Identity(4)
        frame.matrix_basis = Matrix(local.tolist())
        _state["frame_sig"] = sig
    ensure_group()
    world = root.matrix_world @ frame.matrix_basis   # where the frame is now, without waiting for the depsgraph
    inv = np.linalg.inv(_np(world))
    _write({"Frame X": inv[0, :3].tolist(), "Frame Y": inv[1, :3].tolist(), "Frame Z": inv[2, :3].tolist(),
            "Frame T": inv[:3, 3].tolist()})
    return world


FRAME_REACH_M = 200_000.0    # a frame further than this from the datasets is made again there


def _far_from_frame(st, objs) -> bool:
    from .tile_bounds import _ecef_to_world
    o = next(iter(objs), None)
    if o is None:
        return False
    p = np.linalg.inv(_ecef_to_world(st)) @ (_np(o.matrix_world) @ (*o.bound_box[0], 1.0))
    return float(np.linalg.norm(p[:3] - _state["frame_ecef"][:3, 3])) > FRAME_REACH_M


def _xyz(o, to_frame):
    data = o.data
    pts = data.points if o.type == "POINTCLOUD" else data.vertices
    co = np.empty(len(pts) * 3, np.float32)
    pts.foreach_get("co", co)
    m = to_frame @ _np(o.matrix_world)
    return co.reshape(-1, 3).astype(np.float64) @ m[:3, :3].T + m[:3, 3]


def _tile_cells(o, to_frame, cell, box=None, z_min=-math.inf):
    """The ground cells a tile covers. ``box`` (lo, hi in the frame): only the part of the tile over it and
    above ``z_min``, for a terrain tile far wider than the dataset it is compared with."""
    xy = _xyz(o, to_frame)
    if not len(xy):
        return br.EMPTY
    if box is not None:
        if o.type != "POINTCLOUD" and len(o.data.polygons):
            o.data.calc_loop_triangles()
            tris = np.empty(len(o.data.loop_triangles) * 3, np.int32)
            o.data.loop_triangles.foreach_get("vertices", tris)
            return br.cells_of_triangles_in(xy, tris, cell, *box, z_min=z_min)
        xy = xy[((xy[:, :2] >= box[0]) & (xy[:, :2] <= box[1])).all(1) & (xy[:, 2] >= z_min)]
        if not len(xy):
            return br.EMPTY
    span = xy.max(0) - xy.min(0)
    spacing = math.sqrt(max(span[0] * span[1], 1e-9) / len(xy))
    me = o.data
    if o.type == "POINTCLOUD" or not len(me.polygons):
        return br.cells_of_points(xy, cell, spacing)
    # always the triangles: a tile dense on a building and flat beside it has few vertices on the flat part,
    # whatever its mean spacing says. Vertices alone left holes there, and the dataset faded around them.
    me.calc_loop_triangles()
    tris = np.empty(len(me.loop_triangles) * 3, np.int32)
    me.loop_triangles.foreach_get("vertices", tris)
    return br.cells_of_triangles(xy, tris, cell)


def _upload(dist, low, x0, y0, c, max_m) -> None:
    h, w = dist.shape
    img = _coverage_image(w, h)
    if tuple(img.size) != (w, h):
        img.scale(w, h)
    px = np.empty((h, w, 4), np.float32)
    z0, z1 = float(low.min()), float(low.max())
    px[..., 0] = np.clip(dist / max_m, 0.0, 1.0)
    px[..., 1] = (low - z0) / max(z1 - z0, 1e-3)
    px[..., 2] = 0.0
    px[..., 3] = 1.0
    img.pixels.foreach_set(px.ravel())
    img.update()
    img.pack()                                       # kept in the .blend: a saved scene keeps its fades
    ng = ensure_group()
    if ng.nodes["Coverage"].image != img:            # written only when it changes: a write to a node of the
        ng.nodes["Coverage"].image = img             # group re-evaluates every tile material
    _write({"Place Scale": (1.0 / (w * c), 1.0 / (h * c), 1.0), "Place Location": (-x0 / (w * c), -y0 / (h * c), 0.0),
            "Range": max_m, "Low Min": z0, "Low Range": max(z1 - z0, 1e-3)})


def _clear_coverage() -> bool:
    """No dataset is shown any more (hidden, stopped, removed): the terrain is whole again. Without this the
    last coverage stays, and the terrain keeps a hole where a dataset was. The frame is let go too: the next
    dataset may be on the other side of the planet."""
    if _state.get("empty"):
        return False
    _write({"Range": 0.0})                           # every cell reads 0 m inside: outside every footprint
    _state.update(cells={}, boxes={}, cell=None, sig=None, frame_ecef=None, frame_sig=None, info="", empty=True)
    return True


def mark_dirty() -> None:
    _state["sig"] = None
    _state["now"] = True


def _rendering() -> bool:
    """A render is waiting for its tiles: the coverage must be the frame's, not three seconds old."""
    if bpy.app.background:
        return True
    try:
        from .ui import _state as ui_state
        return ui_state.get("render_req") is not None or bool(ui_state.get("render_hold"))
    except Exception:                                # noqa: BLE001
        return False


def _auto_distances(props, vis, rl, boxes) -> None:
    """Auto: the three distances from the size of the smallest dataset shown."""
    sizes = []
    for uid, names in vis.items():
        b = np.array([boxes[n] for n in names if n in boxes]) if rl[uid] == "dataset" else np.empty((0, 4))
        if len(b):
            sizes.append(min(b[:, 2].max() - b[:, 0].min(), b[:, 3].max() - b[:, 1].min()))
    if not sizes:
        return
    fade = float(np.clip(round(AUTO_SHARE * min(sizes), 1), 0.5, 500.0))
    if abs(fade - props.blend_dataset_fade) <= 0.1 * fade:
        return                                       # close enough: tiles refining must not make it flicker
    _state["auto"] = True                            # these writes are ours, not the user's
    try:
        props.blend_dataset_fade = fade
        props.blend_terrain_inset = fade / 2
        props.blend_terrain_fade = fade / 2
    finally:
        _state["auto"] = False


def tick(scene, props, streams, now) -> bool:
    """One step, from the streaming tick. True while the coverage or the materials are still changing."""
    if not wanted(props):
        if _state["done"] or _state["frame_ecef"] is not None:
            teardown()
            return True
        return False
    rl = roles(props, streams)
    if not rl:
        return False
    changed = False
    if _state.pop("strip", False):                   # a tileset that no longer takes part loses its mix
        for uid, st in streams.items():
            if uid not in rl and st.get("backend") is not None:
                for o in _tile_objects(st, shown_only=False):    # the hidden ones too: they may show again
                    _apply_object(o, None)
    if now - _state["t_scan"] >= SCAN_PERIOD_S or _state["sig"] is None:
        _state["t_scan"] = now
        _state["vis"] = {uid: [o.name for o in _tile_objects(streams[uid])] for uid in rl}
    vis = _state["vis"]
    # materials of the tiles that came in
    # Switched on, or a setting edited: every tile shown gets it in this one tick. Left to the budget, a
    # thousand Google tiles took minutes on a scene at rest, and the terrain stayed in front of the dataset
    # meanwhile. Tiles that stream in afterwards go by the budget, wider while many wait.
    t0 = time.perf_counter()
    objs = bpy.data.objects
    catch_up = _state.pop("catch_up", False)
    waiting = sum(1 for uid, names in vis.items() for n in names if n not in _state["done"].get(uid, ()))
    budget = math.inf if catch_up else MATS_BACKLOG_S if waiting > MATS_BACKLOG else MATS_BUDGET_S
    for uid, names in vis.items():
        done = _state["done"].setdefault(uid, set())
        for name in names:
            if name in done:
                continue
            _apply_object(objs.get(name), rl[uid])
            done.add(name)
            changed = True
            if time.perf_counter() - t0 > budget:
                break
        if len(done) > 4 * len(names) + 64:
            done.intersection_update(names)
    # the coverage of the datasets' tiles
    data = [n for uid, names in vis.items() if rl[uid] == "dataset" for n in names]
    first = next((streams[uid] for uid in rl if rl[uid] == "dataset"), None)
    if first is None or not data:
        return _clear_coverage() or changed
    tiles = [o for o in (objs.get(n) for n in data) if o is not None]
    _state["empty"] = False
    frame_world = _ensure_frame(props, first, tiles)
    if frame_world is None:
        return changed
    to_frame = np.linalg.inv(_np(frame_world))
    max_m = max(props.blend_terrain_inset + props.blend_terrain_fade, props.blend_dataset_fade, 1.0)
    # a dataset moved against the frame (its root Empty dragged): its cells are stale
    moved = tuple(tuple(np.round(to_frame @ _np(r.matrix_world), 2).ravel())
                  for r in (objs.get(streams[uid].get("root_obj") or "") for uid in rl if rl[uid] == "dataset")
                  if r is not None)
    sig = (frozenset(data), moved, round(max_m, 2))
    if sig == _state["sig"]:
        return changed
    if now - _state["t_build"] < REBUILD_PERIOD_S and not _state["now"] and not _rendering():
        return True                                  # the tiles changed: the coverage follows a little later
    if _state.get("moved") != moved:
        _state["cells"].clear()
        _state["boxes"].clear()
        _state["moved"] = moved
    boxes = _state["boxes"]
    for o in tiles:
        if o.name not in boxes:
            p = np.array([(*c, 1.0) for c in o.bound_box]) @ (to_frame @ _np(o.matrix_world))[:2].T
            boxes[o.name] = (*p.min(0), *p.max(0))
    b = np.array([boxes[o.name] for o in tiles])
    cell = br.cell_size(float(max(b[:, 2].max() - b[:, 0].min(), b[:, 3].max() - b[:, 1].min())))
    if cell != _state["cell"]:
        _state["cells"].clear()
        _state["cell"] = cell
    cells = _state["cells"]
    if props.blend_auto:
        _auto_distances(props, vis, rl, boxes)
        max_m = max(props.blend_terrain_inset + props.blend_terrain_fade, props.blend_dataset_fade, 1.0)
        sig = (sig[0], sig[1], round(max_m, 2))
    t0 = time.perf_counter()
    for o in tiles:
        if o.name in cells:
            continue
        try:
            cells[o.name] = _tile_cells(o, to_frame, cell)
        except Exception as e:                       # noqa: BLE001
            print(f"[3DTiles] blend: {o.name}: {e}")
            cells[o.name] = br.EMPTY
        if time.perf_counter() - t0 > CELLS_BUDGET_S:
            return True                              # the rest at the next ticks
    t0 = time.perf_counter()
    cov = br.coverage([cells[o.name] for o in tiles], cell, max_m)
    if cov is not None:
        _upload(*cov, max_m)
        set_params(props)
        _state["build_ms"] = (time.perf_counter() - t0) * 1000.0
        _state["info"] = (f"{len(tiles)} tiles, {cov[0].shape[1]} x {cov[0].shape[0]} cells of "
                          f"{cov[4]:g} m, {_state['build_ms']:.0f} ms")
    for k in [k for k in cells if k not in sig[0]]:
        del cells[k]
        boxes.pop(k, None)
    _state["sig"] = sig
    _state["t_build"] = now
    _state["now"] = False
    return True


def on_change(self, context) -> None:
    """A blend setting edited."""
    if _state["auto"]:
        return
    try:
        props = context.scene.ogc3dtiles
        set_params(props)
        mark_dirty()
        _state["done"].clear()                       # roles may have changed: look at every tile again
        _state["strip"] = True
        _state["catch_up"] = True
        if not wanted(props):
            teardown()
    except Exception as e:                           # noqa: BLE001
        print(f"[3DTiles] blend: {e}")
