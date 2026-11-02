"""Clipping volumes in Blender nodes (see clipping.py for the modes).

* Mesh tile materials: one node group per tileset, shared by its tiles, holds
  every volume: boxes test the shading point in the box's space, polygons edge by
  edge in the tileset frame. Everything that moves is a view-layer attribute
  (scene custom properties), including the transforms: changing one recompiles
  nothing, where a value in a node or an object in a Texture Coordinate node
  regenerates the shader of every material using it (15-30 s with 3000 tiles).
  Keyframes reach the attributes through a frame change handler (ui).
  When the volumes change shape, a new version of the group and of its attributes
  takes over tile by tile, a few per tick, so the regeneration is spread out; the
  old version keeps its values until no tile uses it.
* Point and splat tiles: one Geometry Nodes group per tileset (modifier
  "OGC3D Clip", first in the stack) deletes the cut vertices. Boxes test the
  vertex in the box's space; polygons cast a vertical ray onto a hidden helper
  mesh holding the flattened, filled outlines in the tileset frame (face
  attribute ``clip_poly`` = polygon index).
* Mesh tiles with Cut Geometry: the same test in a second group deletes the
  faces whose vertices are all cut; the shader still trims the faces across
  the boundary. Solid view, exports and snapping then see the cut.

The per-tileset settings live on the tileset's root Empty (``ogc_clip``) so
tiles built later pick them up (io._new_tile_hooks → apply_to_tile).
"""
from __future__ import annotations

import time

import bpy
from mathutils import Matrix

from .clipping import edge_slots, padded_edges
from .overlays import MODE_GROUP_PREFIX, POLY_TAG, clip_attr_base, clip_attr_names, relink_clip_chain

CFG_PROP = "ogc_clip"
GN_MOD = "OGC3D Clip"
GN_PREFIX = "OGC3D Clip "
GN_FACES_PREFIX = "OGC3D Clip Faces "
HELPER_PREFIX = "OGC3D Clip Polygons "
VOLUMES_PREFIX = "OGC3D Clip Volumes "
VOLUMES_TERM = POLY_TAG + " volumes Term"
POLY_ATTR = "clip_poly"
RAY_Z = 1.0e5
TILES_PER_TICK_S = 0.1      # clip nodes on existing tiles: this long per tick


# ── config on the root Empty ─────────────────────────────────────────────────
def make_cfg(uid, op, outside, boxes, n_polygons, helper_name, masks=(), geometry=False,
             volumes="") -> dict:
    """boxes: [(object name, centre xyz, half size xyz)]; masks: uids of the
    tileset's cesium masks; geometry: Cut Geometry on mesh tiles; volumes: the
    tiles' shared shader group."""
    return {"uid": uid, "op": op, "outside": bool(outside), "n_polygons": int(n_polygons),
            "helper": helper_name or "", "masks": list(masks), "geometry": bool(geometry),
            "volumes": volumes,
            "boxes": [{"obj": n, "c": list(c), "h": list(h)} for n, c, h in boxes]}


def _cfg(root):
    cfg = root.get(CFG_PROP) if root is not None else None
    cfg = cfg.to_dict() if hasattr(cfg, "to_dict") else cfg
    if cfg and "n_prisms" in cfg:                    # saved by an earlier version
        cfg["n_polygons"] = cfg["n_prisms"]
    return cfg


def _is_point_tile(obj) -> bool:
    return obj.type == "MESH" and (obj.modifiers.get("Points") is not None
                                   or obj.modifiers.get("Splats") is not None
                                   or (len(obj.data.vertices) and not len(obj.data.polygons)))


# ── the volumes group of mesh tile materials ─────────────────────────────────
def _write_attrs(scene, values) -> None:
    """Set a tileset's volume attributes (name → xyz) and drop its old ones."""
    changed = False
    for k, v in values.items():
        old = scene.get(k)
        if old is None or any(abs(a - b) > 1e-6 * max(1.0, abs(b)) for a, b in zip(old, v)):
            scene[k] = v
            changed = True
    if changed:
        scene.update_tag()


def _obj_matrix(obj, depsgraph):
    return (obj.evaluated_get(depsgraph) if depsgraph is not None else obj).matrix_world


def _rows(base, m) -> dict:
    """A matrix's upper 3 x 4 as attributes: three rows and the translation."""
    return {f"{base}_r{i}": tuple(m[i][:3]) for i in range(3)} | {
        f"{base}_t": (m[0][3], m[1][3], m[2][3])}


def _volume_attrs(base, frame, loops, boxes, depsgraph=None) -> dict:
    root = bpy.data.objects.get(frame)
    out = {}
    if root is not None and loops:
        out = _rows(base + "_f", _obj_matrix(root, depsgraph).inverted_safe())
    for i, loop in enumerate(loops):
        for e, edge in enumerate(padded_edges(loop)):
            out[f"{base}_p{i}_{e}"] = edge
    for i, (name, c, h) in enumerate(boxes):
        obj = bpy.data.objects.get(name)
        if obj is not None:
            unit = Matrix.Diagonal((*(1.0 / v for v in h), 1.0)) @ Matrix.Translation(
                (-c[0], -c[1], -c[2]))
            out |= _rows(f"{base}_b{i}", unit @ _obj_matrix(obj, depsgraph).inverted_safe())
    return out


def _volumes_sig(loops, boxes) -> str:
    return repr(([edge_slots(len(lp)) for lp in loops], len(boxes)))


def _build_volumes(name, base, loops, boxes):
    """Group (→ Min, Max) over every volume's "inside"."""
    ng = bpy.data.node_groups.new(name, "ShaderNodeTree")
    for k in ("Min", "Max"):
        ng.interface.new_socket(k, in_out="OUTPUT", socket_type="NodeSocketFloat")
    N, L = ng.nodes.new, ng.links.new

    def math(op):
        n = N("ShaderNodeMath")
        n.operation = op
        return n

    def attr(attr_name):
        n = N("ShaderNodeAttribute")
        n.attribute_type = "VIEW_LAYER"
        n.attribute_name = attr_name
        return n.outputs["Vector"]

    world = N("ShaderNodeNewGeometry").outputs["Position"]

    def transformed(attr_base, axes):
        """The shading point's coordinates through _rows' matrix."""
        t = N("ShaderNodeSeparateXYZ")
        L(attr(attr_base + "_t"), t.inputs[0])
        out = []
        for i in axes:
            dot = N("ShaderNodeVectorMath")
            dot.operation = "DOT_PRODUCT"
            L(world, dot.inputs[0])
            L(attr(f"{attr_base}_r{i}"), dot.inputs[1])
            add = math("ADD")
            L(dot.outputs["Value"], add.inputs[0])
            L(t.outputs[i], add.inputs[1])
            out.append(add.outputs[0])
        return out

    terms = []
    if loops:
        px, py = transformed(base + "_f", (0, 1))
    for p, loop in enumerate(loops):
        above = []
        for e in range(edge_slots(len(loop))):
            xyk = N("ShaderNodeSeparateXYZ")
            L(attr(f"{base}_p{p}_{e}"), xyk.inputs[0])
            d = math("SUBTRACT")
            L(py, d.inputs[0])
            L(xyk.outputs[1], d.inputs[1])
            g = math("GREATER_THAN")
            L(d.outputs[0], g.inputs[0])
            g.inputs[1].default_value = 0.0
            xi = math("MULTIPLY_ADD")               # the edge's x at the point's y
            L(d.outputs[0], xi.inputs[0])
            L(xyk.outputs[2], xi.inputs[1])
            L(xyk.outputs[0], xi.inputs[2])
            above.append((g.outputs[0], xi.outputs[0]))
        acc = None
        for e, (g, xi) in enumerate(above):
            left = math("LESS_THAN")
            L(px, left.inputs[0])
            L(xi, left.inputs[1])
            cross = math("SUBTRACT")                # +1 / -1 where the edge crosses y
            L(g, cross.inputs[0])
            L(above[(e + 1) % len(above)][0], cross.inputs[1])
            add = math("MULTIPLY_ADD")
            L(cross.outputs[0], add.inputs[0])
            L(left.outputs[0], add.inputs[1])
            if acc is None:
                add.inputs[2].default_value = 0.0
            else:
                L(acc, add.inputs[2])
            acc = add.outputs[0]
        ab = math("ABSOLUTE")
        L(acc, ab.inputs[0])
        inside = math("GREATER_THAN")
        L(ab.outputs[0], inside.inputs[0])
        inside.inputs[1].default_value = 0.5
        terms.append(inside.outputs[0])
    for i in range(len(boxes)):
        acc = None
        for v in transformed(f"{base}_b{i}", (0, 1, 2)):
            ab = math("ABSOLUTE")
            L(v, ab.inputs[0])
            if acc is None:
                acc = ab.outputs[0]
            else:
                mx = math("MAXIMUM")
                L(acc, mx.inputs[0])
                L(ab.outputs[0], mx.inputs[1])
                acc = mx.outputs[0]
        term = math("LESS_THAN")
        L(acc, term.inputs[0])
        term.inputs[1].default_value = 1.0
        terms.append(term.outputs[0])
    go = N("NodeGroupOutput")
    for op, out in (("MINIMUM", go.inputs[0]), ("MAXIMUM", go.inputs[1])):
        acc = terms[0]
        for t in terms[1:]:
            comb = math(op)
            L(acc, comb.inputs[0])
            L(t, comb.inputs[1])
            acc = comb.outputs[0]
        L(acc, out)
    return ng


def _current_volumes(uid):
    """The newest version of a tileset's volumes group, or None."""
    prefix = f"{VOLUMES_PREFIX}{uid} v"
    groups = [g for g in bpy.data.node_groups if g.name.startswith(prefix)]
    return max(groups, key=lambda g: g.get("v", 0), default=None)


def _version_base(uid, version) -> str:
    return f"{clip_attr_base(uid)}_v{version}"


def update_volumes(scene, uid, frame, loops, boxes) -> str:
    """Bring a tileset's attributes and shared group up to date; returns the
    group's name ("": no volumes). Only a change of shape makes a new group:
    another outline or box, or an outline outgrowing its slots. ``frame``: the
    object whose space the outlines are in."""
    if not loops and not boxes:
        return ""
    ng = _current_volumes(uid)
    sig = _volumes_sig(loops, boxes)
    if ng is None or ng.get("sig") != sig:
        v = ng.get("v", 0) + 1 if ng is not None else 1
        ng = _build_volumes(f"{VOLUMES_PREFIX}{uid} v{v}", _version_base(uid, v), loops, boxes)
        ng["sig"], ng["v"] = sig, v
    _write_attrs(scene, _volume_attrs(_version_base(uid, ng["v"]), frame, loops, boxes))
    return ng.name


def update_volume_values(scene, uid, frame, loops, boxes, depsgraph=None) -> bool:
    """The attributes alone, while an object is being dragged or animated. False
    when its shape changed, which takes update_volumes."""
    ng = _current_volumes(uid)
    if ng is None or ng.get("sig") != _volumes_sig(loops, boxes):
        return False
    _write_attrs(scene, _volume_attrs(_version_base(uid, ng["v"]), frame, loops, boxes, depsgraph))
    return True


def set_animated_deps(scene, uid, objs) -> None:
    """Keep keyframed volumes in the render's depsgraph: one hidden from render is
    otherwise left out of it and keeps its old transform. A driver reading its
    location creates that dependency; its value isn't used."""
    base = clip_attr_base(uid) + "_dep"
    ad = scene.animation_data
    have = [fc for fc in ad.drivers if fc.data_path.startswith(f'["{base}')] if ad else []
    if [fc.driver.variables[0].targets[0].id for fc in have] == list(objs):
        return
    for fc in have:
        scene.driver_remove(fc.data_path)
    for k in [k for k in scene.keys() if k.startswith(base)]:
        del scene[k]
    for i, o in enumerate(objs):
        key = f"{base}{i}"
        scene[key] = 0.0
        d = scene.driver_add(f'["{key}"]').driver
        v = d.variables.new()
        v.name, v.type = "x", "TRANSFORMS"
        v.targets[0].id = o
        v.targets[0].transform_type = "LOC_X"
        d.expression = "x"


def set_volumes_term(mat, group, tileset_uid) -> None:
    """Make the material use this version of the tileset's volumes group ("" :
    none). Relinks only when the term comes or goes."""
    if mat is None or not mat.use_nodes or mat.node_tree is None:
        return
    nt = mat.node_tree
    n = nt.nodes.get(VOLUMES_TERM)
    if group and n is None:
        n = nt.nodes.new("ShaderNodeGroup")
        n.name = n.label = VOLUMES_TERM
        n.location = (-1900.0, -2600.0)
        n.node_tree = bpy.data.node_groups.get(group)
        relink_clip_chain(mat, tileset_uid)
    elif group and (n.node_tree is None or n.node_tree.name != group):
        n.node_tree = bpy.data.node_groups.get(group)
    elif not group and n is not None:
        nt.nodes.remove(n)
        relink_clip_chain(mat)


# ── polygon helper mesh ────────────────────────────────────────────────────────
def update_helper(uid, root, loops_local, coll):
    """Hidden mesh with one flat (z = 0) n-gon per polygon outline, in the
    tileset frame (object matrix = the root's). None without polygons."""
    name = HELPER_PREFIX + uid
    ob = bpy.data.objects.get(name)
    if not loops_local:
        if ob is not None:
            me = ob.data
            bpy.data.objects.remove(ob)
            if me is not None and me.users == 0:
                bpy.data.meshes.remove(me)
        return None
    verts, faces = [], []
    for loop in loops_local:
        base = len(verts)
        verts.extend((p[0], p[1], 0.0) for p in loop)
        faces.append(list(range(base, base + len(loop))))
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    a = me.attributes.new(POLY_ATTR, "INT", "FACE")
    a.data.foreach_set("value", list(range(len(faces))))
    me.update()
    if ob is None:
        ob = bpy.data.objects.new(name, me)
        coll.objects.link(ob)
        ob.hide_select = True
        ob.display_type = "WIRE"
    else:
        old = ob.data
        ob.data = me
        if old is not None and old.users == 0:
            bpy.data.meshes.remove(old)
    ob.hide_viewport = True
    ob.hide_render = True
    ob.matrix_world = root.matrix_world.copy()
    return ob


# ── Geometry Nodes group for point / splat tiles ─────────────────────────────
def _gn_signature(cfg, faces) -> str:
    return repr((cfg["op"], cfg["outside"], cfg["n_polygons"], cfg["helper"], faces,
                 [(b["obj"], [round(v, 6) for v in b["c"]], [round(v, 6) for v in b["h"]])
                  for b in cfg["boxes"]]))


def build_group(cfg, faces=False):
    """(Re)build the tileset's clip group, deleting points, or with ``faces``
    the faces whose points are all cut; returns it (None: nothing to clip)."""
    name = (GN_FACES_PREFIX if faces else GN_PREFIX) + cfg["uid"]
    ng = bpy.data.node_groups.get(name)
    if not cfg["boxes"] and not cfg["n_polygons"]:
        return None
    sig = _gn_signature(cfg, faces)
    if ng is not None and ng.get("sig") == sig:
        return ng
    if ng is None:
        ng = bpy.data.node_groups.new(name, "GeometryNodeTree")
        ng.is_modifier = True
        ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
        ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    for n in list(ng.nodes):
        ng.nodes.remove(n)
    N, L = ng.nodes.new, ng.links.new
    gi, go = N("NodeGroupInput"), N("NodeGroupOutput")
    gi.location, go.location = (-1400, 300), (1200, 300)

    def obj_info(obj):
        oi = N("GeometryNodeObjectInfo")
        oi.transform_space = "ORIGINAL"
        oi.inputs["Object"].default_value = obj
        return oi

    def inv(m):
        n = N("FunctionNodeInvertMatrix")
        L(m, n.inputs[0])
        return n.outputs[0]

    def xform(m, v):
        n = N("FunctionNodeTransformPoint")
        L(v, n.inputs["Vector"])
        L(m, n.inputs["Transform"])
        return n.outputs[0]

    def math(op, a, b=None, bval=None):
        n = N("ShaderNodeMath")
        n.operation = op
        L(a, n.inputs[0])
        if b is not None:
            L(b, n.inputs[1])
        elif bval is not None:
            n.inputs[1].default_value = bval
        return n.outputs[0]

    selfo = N("GeometryNodeSelfObject")
    self_info = N("GeometryNodeObjectInfo")
    self_info.transform_space = "ORIGINAL"
    L(selfo.outputs[0], self_info.inputs["Object"])
    pos = N("GeometryNodeInputPosition")
    world = xform(self_info.outputs["Transform"], pos.outputs[0])
    terms = []
    for b in cfg["boxes"]:
        ob = bpy.data.objects.get(b["obj"])
        if ob is None:
            continue
        local = xform(inv(obj_info(ob).outputs["Transform"]), world)
        sub = N("ShaderNodeVectorMath")
        sub.operation = "SUBTRACT"
        L(local, sub.inputs[0])
        sub.inputs[1].default_value = b["c"]
        div = N("ShaderNodeVectorMath")
        div.operation = "DIVIDE"
        L(sub.outputs[0], div.inputs[0])
        div.inputs[1].default_value = b["h"]
        ab = N("ShaderNodeVectorMath")
        ab.operation = "ABSOLUTE"
        L(div.outputs[0], ab.inputs[0])
        sep = N("ShaderNodeSeparateXYZ")
        L(ab.outputs[0], sep.inputs[0])
        m = math("MAXIMUM", math("MAXIMUM", sep.outputs[0], sep.outputs[1]), sep.outputs[2])
        terms.append(math("GREATER_THAN" if cfg["outside"] else "LESS_THAN", m, bval=1.0))
    helper = bpy.data.objects.get(cfg["helper"]) if cfg["n_polygons"] else None
    if helper is not None:
        hi = obj_info(helper)
        hl = xform(inv(hi.outputs["Transform"]), world)
        sep = N("ShaderNodeSeparateXYZ")
        L(hl, sep.inputs[0])
        src = N("ShaderNodeCombineXYZ")
        L(sep.outputs[0], src.inputs[0])
        L(sep.outputs[1], src.inputs[1])
        src.inputs[2].default_value = RAY_Z
        attr = N("GeometryNodeInputNamedAttribute")
        attr.data_type = "INT"
        attr.inputs["Name"].default_value = POLY_ATTR
        for i in range(cfg["n_polygons"]):
            cmp = N("FunctionNodeCompare")
            cmp.data_type = "INT"
            cmp.operation = "EQUAL"
            a_in, b_in = (cmp.inputs[2], cmp.inputs[3]) if len(cmp.inputs) > 2 else                 (cmp.inputs[0], cmp.inputs[1])          # Blender < 4.x kept every type's sockets
            L(attr.outputs[0], a_in)
            b_in.default_value = i
            sg = N("GeometryNodeSeparateGeometry")
            sg.domain = "FACE"
            L(hi.outputs["Geometry"], sg.inputs["Geometry"])
            L(cmp.outputs[0], sg.inputs["Selection"])
            rc = N("GeometryNodeRaycast")
            L(sg.outputs[0], rc.inputs["Target Geometry"])
            L(src.outputs[0], rc.inputs["Source Position"])
            rc.inputs["Ray Direction"].default_value = (0.0, 0.0, -1.0)
            rc.inputs["Ray Length"].default_value = 2.0 * RAY_Z
            hit = rc.outputs["Is Hit"]
            terms.append(math("LESS_THAN", hit, bval=0.5) if cfg["outside"]
                         else math("ADD", hit, bval=0.0))
    if not terms:
        L(gi.outputs[0], go.inputs[0])
    else:
        acc = terms[0]
        for t in terms[1:]:
            acc = math(cfg["op"], acc, t)
        cut = math("GREATER_THAN", acc, bval=0.5)
        dg = N("GeometryNodeDeleteGeometry")
        dg.domain = "FACE" if faces else "POINT"
        L(gi.outputs[0], dg.inputs["Geometry"])
        if faces:
            # a boolean point field read on faces is true when all points are
            on_pts = N("GeometryNodeFieldOnDomain")
            on_pts.data_type = "BOOLEAN"
            on_pts.domain = "POINT"
            L(cut, on_pts.inputs[0])
            cut = on_pts.outputs[0]
        L(cut, dg.inputs["Selection"])
        L(dg.outputs[0], go.inputs[0])
    ng["sig"] = sig
    return ng


def _set_gn(obj, ng) -> None:
    mod = obj.modifiers.get(GN_MOD)
    if ng is None:
        if mod is not None:
            obj.modifiers.remove(mod)
        return
    if mod is None:
        mod = obj.modifiers.new(GN_MOD, "NODES")
        idx = obj.modifiers.find(GN_MOD)
        if idx > 0:
            obj.modifiers.move(idx, 0)
    if mod.node_group is not ng:
        mod.node_group = ng


# ── applying ─────────────────────────────────────────────────────────────────
def set_mode(scene, uid, any_, invert) -> None:
    """The two attributes the tile materials read; no material is touched."""
    any_name, inv_name = clip_attr_names(uid)
    scene[any_name], scene[inv_name] = float(any_), float(invert)
    scene.update_tag()


def _tile_group(prefix, cfg, faces):
    return bpy.data.node_groups.get(prefix + cfg["uid"]) or build_group(cfg, faces)


def apply_to_tile(obj, cfg=None) -> None:
    """Bring one tile in line with its tileset's clip config."""
    if obj is None or obj.type != "MESH":
        return
    cfg = _cfg(obj.parent) if cfg is None else cfg
    if _is_point_tile(obj):
        _set_gn(obj, _tile_group(GN_PREFIX, cfg, False) if cfg else None)
        return
    _set_gn(obj, _tile_group(GN_FACES_PREFIX, cfg, True) if cfg and cfg.get("geometry") else None)
    for m in obj.data.materials:
        set_volumes_term(m, (cfg.get("volumes") or "") if cfg else "", cfg["uid"] if cfg else None)


def apply_to_tiles(names) -> list:
    """Bring these tiles (object names) in line with their tileset's config, for
    at most TILES_PER_TICK_S; returns the rest. Editing a material's links takes
    milliseconds, which adds up to a minute over thousands of tiles."""
    t0 = time.perf_counter()
    for i, name in enumerate(names):
        o = bpy.data.objects.get(name)
        if o is not None:
            try:
                apply_to_tile(o)
            except Exception as e:                   # noqa: BLE001
                print(f"[3DTiles] clip {name}: {e}")
        if time.perf_counter() - t0 > TILES_PER_TICK_S:
            return names[i + 1:]
    return []


def _drop_volumes(uid, keep="") -> None:
    """Remove the versions of the volumes group no tile uses, and their attributes."""
    scene = bpy.context.scene
    for ng in list(bpy.data.node_groups):
        if ng.name.startswith(f"{VOLUMES_PREFIX}{uid} v") and ng.users == 0 and ng.name != keep:
            base = _version_base(uid, ng.get("v", 0)) + "_"
            for k in [k for k in scene.keys() if k.startswith(base)]:
                del scene[k]
            bpy.data.node_groups.remove(ng)


def prune_groups(root) -> None:
    """Remove the groups no tile uses any more."""
    uid = root.get("ogc_clip_uid") if root is not None else None
    if not uid:
        return
    cfg = _cfg(root)
    _drop_volumes(uid, (cfg.get("volumes") or "") if cfg else "")
    if cfg:
        return
    forget_groups(uid)


def forget_groups(uid) -> None:
    """A tileset's tiles are gone: its groups go too."""
    _drop_volumes(uid)
    set_animated_deps(bpy.context.scene, uid, [])
    for name in (GN_PREFIX + uid, GN_FACES_PREFIX + uid, MODE_GROUP_PREFIX + uid):
        ng = bpy.data.node_groups.get(name)
        if ng is not None and ng.users == 0:
            bpy.data.node_groups.remove(ng)


def apply_to_tileset(root, cfg) -> list:
    """Store ``cfg`` (None = no clipping) on the root and update its tiles,
    visible ones first; returns the tiles left for later (apply_to_tiles)."""
    if root is None:
        return []
    if cfg is None:
        if CFG_PROP in root:
            del root[CFG_PROP]
    else:
        root[CFG_PROP] = cfg
        root["ogc_clip_uid"] = cfg["uid"]
        try:
            build_group(cfg)
            if cfg.get("geometry"):
                build_group(cfg, True)
        except Exception as e:                       # noqa: BLE001
            print(f"[3DTiles] clip group: {e}")
    tiles = sorted((o for o in root.children if "tile_url" in o), key=lambda o: o.hide_viewport)
    left = apply_to_tiles([o.name for o in tiles])
    if not left:
        prune_groups(root)
    return left
