"""Color correction per tileset, and Match Colors.

A tileset with *Color correction* ticked gets one small shader group of its own, ``OGC3D Color <uid>``, put
in every tile material between the tile's color (its texture, or the point colors) and what uses it:

    color → ^ Gamma (per channel) → × Gain (per channel) × 2^Exposure → Saturation → Contrast

The numbers are custom properties of the scene, read by Attribute nodes of that group (shader_params): a
slider touches no node tree. (As nodes of the group, each slider step re-evaluated every tile material of
the tileset.) It sits before the metadata colors (*Color tiles by*), which are not corrected.

*Match Colors* fills Gain and Gamma from another tileset: both are sampled where they overlap, from above,
one mean color per ground cell each (color_match fits the numbers). The samples are the raw colors of the
tiles shown: points on a mesh looked up in its texture and in the raster overlays drawn over it (a terrain
with imagery is read as its imagery), or the point colors. Terrain blending hides nothing from it: the
whole tiles are read, not what the fade leaves visible.
"""
from __future__ import annotations

import time

import bpy
import numpy as np

from . import blend_raster as br
from . import color_match as cm
from . import shader_params as sp

NODE = "OGC3D Color"
MARK = "ogc3d_color"
SCAN_PERIOD_S = 0.5
RECHECK_PER_TICK = 6        # tiles looked at again each tick, in turn: a material another feature rebuilt gets the
                            # node back. (Starting over every 3 s never reached the tiles at the end of a long list.)
BUDGET_S = 0.006
SAMPLES_PER_TILE = 3000
MAX_TILES = 600
MAX_PIXELS = 4096 * 4096
FAR_BELOW_M = 100_000.0

_state = {"done": {}, "t_scan": 0.0, "vis": {}, "strip": set(), "cursor": {}}


def group_name(item) -> str:
    return f"{NODE} {item.uid[:8]}"


def _param(item, name) -> str:
    return f"color {item.uid[:8]} {name}"


def ensure_group(item):
    name = group_name(item)
    ng = bpy.data.node_groups.get(name)
    if ng is not None and sp.is_param(ng.nodes.get("Contrast")):
        return ng
    ng = ng or bpy.data.node_groups.new(name, "ShaderNodeTree")
    ng.nodes.clear()                                 # an older group (numbers in nodes) is made again; its
    have = {(it.name, it.in_out) for it in ng.interface.items_tree if hasattr(it, "in_out")}
    for in_out in ("INPUT", "OUTPUT"):               # sockets stay, so the tile materials keep their links
        if ("Color", in_out) not in have:
            ng.interface.new_socket("Color", in_out=in_out, socket_type="NodeSocketColor")
    N, L = ng.nodes.new, ng.links.new

    def math_(op, a, b=None, value=None):
        n = N("ShaderNodeMath")
        n.operation = op
        L(a, n.inputs[0])
        if b is not None:
            L(b, n.inputs[1])
        if value is not None:
            n.inputs[1].default_value = value
        return n.outputs[0]

    def number(key):                                 # stored as its offset from 1: a missing property changes nothing
        return math_("ADD", sp.socket(ng, key, _param(item, key)), value=1.0)

    gin, gout = N("NodeGroupInput"), N("NodeGroupOutput")
    sep_c, sep_gamma, sep_gain = N("ShaderNodeSeparateColor"), N("ShaderNodeSeparateXYZ"), N("ShaderNodeSeparateXYZ")
    L(gin.outputs[0], sep_c.inputs[0])
    L(sp.socket(ng, "Gamma", _param(item, "Gamma"), vector=True), sep_gamma.inputs[0])
    L(sp.socket(ng, "Gain", _param(item, "Gain"), vector=True), sep_gain.inputs[0])
    exposure = number("Exposure Gain")
    comb = N("ShaderNodeCombineColor")
    for i in range(3):
        pos = math_("MAXIMUM", sep_c.outputs[i], value=0.0)      # a negative color has no power
        pw = math_("POWER", pos, math_("ADD", sep_gamma.outputs[i], value=1.0))
        mul = math_("MULTIPLY", pw, math_("ADD", sep_gain.outputs[i], value=1.0))
        L(math_("MULTIPLY", mul, exposure), comb.inputs[i])
    hsv = N("ShaderNodeHueSaturation")
    L(comb.outputs[0], hsv.inputs["Color"])
    L(number("Saturation"), hsv.inputs["Saturation"])
    bc = N("ShaderNodeBrightContrast")
    L(hsv.outputs[0], bc.inputs["Color"])
    L(sp.socket(ng, "Contrast", _param(item, "Contrast")), bc.inputs["Contrast"])
    L(bc.outputs[0], gout.inputs[0])
    from .node_layout import arrange
    arrange(ng)
    set_params(item)
    return ng


def set_params(item) -> None:
    """The tileset's numbers, as scene properties its group reads (live, no node is touched). Box off:
    the numbers that change nothing."""
    if not item.use_color:
        sp.write({_param(item, k): v for k, v in (("Gamma", (0, 0, 0)), ("Gain", (0, 0, 0)), ("Exposure Gain", 0.0),
                                                  ("Saturation", 0.0), ("Contrast", 0.0))})
        return
    sp.write({_param(item, "Gamma"): [v - 1.0 for v in item.color_gamma],
              _param(item, "Gain"): [v - 1.0 for v in item.color_gain],
              _param(item, "Exposure Gain"): 2.0 ** item.color_exposure - 1.0,
              _param(item, "Saturation"): item.color_saturation - 1.0,
              _param(item, "Contrast"): item.color_contrast})


# ── tile materials ───────────────────────────────────────────────────────────
def _ours(nt):
    return [n for n in nt.nodes if n.type == "GROUP" and n.get(MARK)]


def _targets(mat) -> list:
    """The inputs the tile's own color reaches: behind the metadata colors, which stay as they are."""
    from .materials import META_NODE, _color_target, _emission_target
    out = []
    for t in (_color_target(mat), _emission_target(mat)):
        while t is not None and t.links and t.links[0].from_node.name.startswith(META_NODE):
            t = t.links[0].from_node.inputs[0]
        if t is not None and t.links:
            out.append(t)
    return out


def _remove(nt) -> bool:
    found = False
    for n in _ours(nt):
        src = n.inputs[0].links[0].from_socket if n.inputs[0].links else None
        dst = [lk.to_socket for lk in n.outputs[0].links]
        nt.nodes.remove(n)
        if src is not None:
            for s in dst:
                nt.links.new(src, s)
        found = True
    return found


def apply_material(mat, ng) -> bool:
    """Put the tileset's color group in a tile material (``ng`` None takes it out). True when it changed."""
    if mat is None or mat.node_tree is None:
        return False
    nt = mat.node_tree
    if ng is None:
        return _remove(nt)
    changed = False
    for target in _targets(mat):
        src_node = target.links[0].from_node
        if src_node.type == "GROUP" and src_node.get(MARK):
            if src_node.node_tree != ng:
                src_node.node_tree = ng
                changed = True
            continue
        src = target.links[0].from_socket
        node = next((lk.to_node for lk in src.links if lk.to_node.type == "GROUP" and lk.to_node.get(MARK)), None)
        if node is None:
            node = nt.nodes.new("ShaderNodeGroup")
            node.node_tree = ng
            node.name = node.label = NODE
            node[MARK] = True
            node.location = (target.node.location.x - 220, target.node.location.y + 420)
            nt.links.new(src, node.inputs[0])
        nt.links.new(node.outputs[0], target)
        changed = True
    return changed


def _stream_objects(st, visible_only=True):
    objs = bpy.data.objects
    for rec in st["tiles"].values():
        if visible_only and not rec.visible:
            continue
        o = objs.get(rec.holder)
        if o is None:
            continue
        if o.type == "MESH":
            yield o
        else:
            yield from (c for c in o.children if c.type == "MESH")


def _strip(st) -> None:
    for o in _stream_objects(st, visible_only=False):
        for m in o.data.materials:
            apply_material(m, None)


def tick(props, streams, now) -> bool:
    """One step, from the streaming tick: the tiles that came in get their tileset's group."""
    changed = False
    for uid in list(_state["strip"]):
        _state["strip"].discard(uid)
        _state["done"].pop(uid, None)
        st = streams.get(uid)
        if st is not None and st.get("backend") is not None:
            _strip(st)
            changed = True
    items = [it for it in props.tilesets if it.use_color and it.uid and streams.get(it.uid) is not None
             and streams[it.uid].get("backend") is not None]
    if not items:
        return changed
    if now - _state["t_scan"] >= SCAN_PERIOD_S or changed:
        _state["t_scan"] = now
        _state["vis"] = {it.uid: [o.name for o in _stream_objects(streams[it.uid])] for it in items}
    t0 = time.perf_counter()
    objs = bpy.data.objects
    for it in items:                                 # first the tiles not corrected yet, all of them over the ticks
        ng = None
        done = _state["done"].setdefault(it.uid, set())
        for name in _state["vis"].get(it.uid, ()):
            if name in done:
                continue
            o = objs.get(name)
            if o is not None and o.data is not None:
                ng = ng or ensure_group(it)
                for m in o.data.materials:
                    changed |= apply_material(m, ng)
            done.add(name)
            if time.perf_counter() - t0 > BUDGET_S:
                return True
    for it in items:                                 # then a few of the others again, in turn
        names = _state["vis"].get(it.uid, ())
        if not names:
            continue
        ng = None
        at = _state["cursor"].get(it.uid, 0)
        for k in range(min(RECHECK_PER_TICK, len(names))):
            o = objs.get(names[(at + k) % len(names)])
            if o is not None and o.data is not None:
                ng = ng or ensure_group(it)
                for m in o.data.materials:
                    changed |= apply_material(m, ng)
        _state["cursor"][it.uid] = (at + RECHECK_PER_TICK) % len(names)
    return changed


def new_tile(props, st, obj) -> None:
    """A tile just built: its tileset's group at once, so it never shows uncorrected."""
    if obj is None:
        return
    it = next((x for x in props.tilesets if x.uid == st.get("key")), None)
    if it is None or not (it.use_color or props.tile_shaders == "ALWAYS"):
        return
    ng = ensure_group(it)
    for o in ([obj] if obj.type == "MESH" else [c for c in obj.children if c.type == "MESH"]):
        if o.data is not None:
            for m in o.data.materials:
                apply_material(m, ng)


def apply_all(item) -> int:
    """The box was just ticked: every tile the tileset has loaded gets the group now, shown or not, so that
    none shows uncorrected later. (Left to the streaming tick it took one tile per tick: over a minute on a
    scene at rest, with the tiles changing color one by one.) Returns the number of materials changed."""
    try:
        from .ui import _state as ui_state
        st = ui_state["streams"].get(item.uid)
    except Exception:                                # noqa: BLE001
        st = None
    if st is None or st.get("backend") is None:
        return 0
    ng = ensure_group(item)
    done = _state["done"].setdefault(item.uid, set())
    n = 0
    for o in _stream_objects(st, visible_only=False):
        if o.data is not None:
            for m in o.data.materials:
                n += bool(apply_material(m, ng))
        done.add(o.name)
    return n


def on_change(item, context) -> None:
    """The checkbox or a slider of a tileset's color correction."""
    try:
        if item.use_color:
            # a slider moved while the box was off (Match Colors fills them first) asked for the groups to be
            # taken out: not any more, or the next tick removed them from every tile just corrected
            _state["strip"].discard(item.uid)
            ensure_group(item)
            set_params(item)
            _state["done"].pop(item.uid, None)
        elif context.scene.ogc3dtiles.tile_shaders == "ALWAYS":
            set_params(item)                         # Instant switches: the group stays in the tiles, neutral
        else:
            _state["strip"].add(item.uid)
    except Exception as e:                           # noqa: BLE001
        print(f"[3DTiles] color correction: {e}")


def reset(item) -> None:
    item.color_gain = (1.0, 1.0, 1.0)
    item.color_gamma = (1.0, 1.0, 1.0)
    item.color_exposure = 0.0
    item.color_saturation = 1.0
    item.color_contrast = 0.0


# ── Match Colors ─────────────────────────────────────────────────────────────
def _texture(mat):
    """(image, UV map name or "") a tile material takes its color from."""
    if mat is None or mat.node_tree is None:
        return None, ""
    from .overlays import NODE_TAG
    for n in mat.node_tree.nodes:
        img = n.image if n.type == "TEX_IMAGE" and not n.name.startswith(NODE_TAG) else None
        if img is None or img.colorspace_settings.name == "Non-Color" or img.channels < 3 or not n.outputs["Color"].links:
            continue
        uv = n.inputs["Vector"].links[0].from_node if n.inputs["Vector"].links else None
        return img, (uv.uv_map if uv is not None and uv.type == "UVMAP" else "")
    return None, ""


def _pixels(img, cache):
    if img.name not in cache:
        w, h = img.size
        px = None
        if w and h and w * h <= MAX_PIXELS:
            buf = np.empty(w * h * img.channels, np.float32)
            img.pixels.foreach_get(buf)
            px = buf.reshape(h, w, img.channels)
        cache[img.name] = px
    return cache[img.name]


def tile_samples(o, to_frame, rng, cache, box=None):
    """(positions N x 3 in the frame, linear colors N x 3) of some points of a tile; None without colors.
    ``box`` (lo, hi in the frame): the points are taken on the triangles that reach into it, so a coarse tile
    far wider than the area compared still gives some there."""
    me = o.data
    m = to_frame @ np.array(o.matrix_world, np.float64)
    n_v = len(me.vertices)
    if not n_v:
        return None
    co = np.empty(n_v * 3, np.float32)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3).astype(np.float64)
    n_p = len(me.polygons)
    if n_p and me.uv_layers and len(me.loops) == 3 * n_p:
        # points spread over the triangles by their area seen from above: a coarse tile is a few large triangles
        vi = np.empty(3 * n_p, np.int32)
        me.loops.foreach_get("vertex_index", vi)
        vi = vi.reshape(-1, 3)
        mi = np.zeros(n_p, np.int32)
        me.polygons.foreach_get("material_index", mi)
        pos = co @ m[:3, :3].T + m[:3, 3]
        a, b, c = pos[vi[:, 0]], pos[vi[:, 1]], pos[vi[:, 2]]
        area = np.abs((b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) - (b[:, 1] - a[:, 1]) * (c[:, 0] - a[:, 0])) + 1e-9
        if box is not None:
            t_lo = np.minimum(np.minimum(a, b), c)[:, :2]
            t_hi = np.maximum(np.maximum(a, b), c)[:, :2]
            hit = (t_hi >= box[0]).all(1) & (t_lo <= box[1]).all(1) & (np.maximum(np.maximum(a[:, 2], b[:, 2]), c[:, 2]) > -FAR_BELOW_M)
            if not hit.any():
                return None
            area = np.where(hit, area, 0.0)
        tri = rng.choice(n_p, SAMPLES_PER_TILE, p=area / area.sum())
        u, v = rng.random(SAMPLES_PER_TILE), rng.random(SAMPLES_PER_TILE)
        flip = u + v > 1.0
        u[flip], v[flip] = 1.0 - u[flip], 1.0 - v[flip]
        w = np.stack([1.0 - u - v, u, v], 1)
        from . import overlays as ovl
        xyz, rgb = [], []

        def lookup(img, layer, sel, place=None):
            """(colors, alpha) of an image at the sample points of ``sel``, None when it cannot be read."""
            px = _pixels(img, cache) if img is not None and layer is not None else None
            if px is None:
                return None
            uv = np.empty(6 * n_p, np.float32)
            layer.data.foreach_get("uv", uv)
            uv = (uv.reshape(-1, 3, 2)[tri[sel]] * w[sel][:, :, None]).sum(1)
            h, wd = px.shape[:2]
            if place is None:                        # the tile's own texture repeats
                uv = uv % 1.0
            else:                                    # an overlay: placed by its Mapping node, clamped at its edges
                uv = uv * np.array(place[1]) + np.array(place[0])
            x = np.clip((uv[:, 0] * wd).astype(np.int64), 0, wd - 1)
            y = np.clip((uv[:, 1] * h).astype(np.int64), 0, h - 1)
            col = px[y, x, :3]
            if not img.is_float and img.colorspace_settings.name == "sRGB":
                col = cm.srgb_to_linear(col)
            return col, (px[y, x, 3] if px.shape[2] > 3 else np.ones(len(col), np.float32))

        for slot, mat in enumerate(me.materials):
            sel = mi[tri] == slot
            if mat is None or mat.node_tree is None or not sel.any():
                continue
            img, uv_name = _texture(mat)
            got = lookup(img, me.uv_layers.get(uv_name) if uv_name else me.uv_layers.get("UVMap") or me.uv_layers[0], sel)
            col = got[0] if got is not None else None
            for o_img, o_uv, loc, scale, opacity in ovl.layers(mat.node_tree):     # as drawn: mixed over, in order
                got = lookup(o_img, me.uv_layers.get(o_uv), sel, place=(loc, scale))
                if got is None:
                    continue
                if col is None:
                    col = np.tile(np.array(ovl.base_color(mat.node_tree), np.float32), (int(sel.sum()), 1))
                a = (got[1] * opacity)[:, None]
                col = col * (1.0 - a) + got[0] * a
            if col is None:
                continue
            xyz.append((pos[vi[tri[sel]]] * w[sel][:, :, None]).sum(1))
            rgb.append(col)
        if xyz:
            return np.concatenate(xyz), np.concatenate(rgb)
    col = me.color_attributes.get("Col")
    if col is not None and col.domain == "POINT":
        c = np.empty(n_v * 4, np.float32)
        col.data.foreach_get("color", c)
        pick = rng.choice(n_v, min(SAMPLES_PER_TILE, n_v), replace=False)
        return co[pick] @ m[:3, :3].T + m[:3, 3], c.reshape(-1, 4)[pick, :3]
    return None


def _cell_colors(objs, to_frame, cell, rng, box=None):
    cache, keys, rgb = {}, [], []
    for o in objs:
        if box is not None:
            p = np.array([(*c, 1.0) for c in o.bound_box]) @ (to_frame @ np.array(o.matrix_world, np.float64))[:2].T
            if (p.max(0) < box[0]).any() or (p.min(0) > box[1]).any():
                continue
        try:
            s = tile_samples(o, to_frame, rng, cache, box)
        except Exception as e:                       # noqa: BLE001
            print(f"[3DTiles] color match: {o.name}: {e}")
            s = None
        if s is None:
            continue
        near = s[0][:, 2] > -FAR_BELOW_M             # a globe's far side is under every place, seen from above
        if not near.all():
            s = (s[0][near], s[1][near])
        if not len(s[0]):
            continue
        ij = np.floor(s[0][:, :2] / cell).astype(np.int64)
        keys.append(br.pack(ij[:, 0], ij[:, 1]))
        rgb.append(s[1])
    if not keys:
        return cm.cell_means(np.empty(0, np.int64), np.empty((0, 3)))
    return cm.cell_means(np.concatenate(keys), np.concatenate(rgb))


def _extent(objs) -> float:
    pts = np.array([np.array(o.matrix_world, np.float64) @ (*c, 1.0) for o in objs for c in (o.bound_box[0], o.bound_box[6])])
    return float((pts.max(0) - pts.min(0))[:3].max())


def _boxes(objs, to_frame) -> np.ndarray:
    """Per tile: x min, y min, x max, y max in the frame."""
    out = np.empty((len(objs), 4))
    for i, o in enumerate(objs):
        p = np.array([(*c, 1.0) for c in o.bound_box]) @ (to_frame @ np.array(o.matrix_world, np.float64))[:2].T
        out[i] = (*p.min(0), *p.max(0))
    return out


def _nearest(objs, boxes, lo, hi) -> list:
    """The tiles that reach into the area lo..hi, at most MAX_TILES of them, the smallest (finest) first."""
    inside = (boxes[:, 2:] >= lo).all(1) & (boxes[:, :2] <= hi).all(1)
    idx = np.flatnonzero(inside)
    size = (boxes[idx, 2:] - boxes[idx, :2]).max(1)
    return [objs[i] for i in idx[np.argsort(size)][:MAX_TILES]]


def graded(rgb, item) -> np.ndarray:
    """Colors as a tileset's own correction shows them (gamma, gain, exposure, saturation; not contrast)."""
    out = cm.apply(rgb, np.array(item.color_gain) * 2.0 ** item.color_exposure, item.color_gamma)
    grey = out @ np.array([0.2126, 0.7152, 0.0722])
    return np.maximum(grey[:, None] + (out - grey[:, None]) * item.color_saturation, 0.0)


def match(props, streams, item) -> int:
    """Fill ``item``'s Gain and Gamma so its colors match its reference tileset's where they overlap.
    Returns the number of ground cells compared; RuntimeError says why it could not."""
    from .height_match import local_frame
    ref = next((it for it in props.tilesets if it.name == item.color_ref and it.uid != item.uid), None)
    if ref is None:
        raise RuntimeError("Pick the tileset to match to")
    st, st_ref = streams.get(item.uid), streams.get(ref.uid)
    if st is None or st_ref is None or st.get("backend") is None or st_ref.get("backend") is None:
        raise RuntimeError("Both tilesets have to be streaming")
    mine, theirs = list(_stream_objects(st)), list(_stream_objects(st_ref))
    if not mine or not theirs:
        raise RuntimeError(f"{(item if not mine else ref).name}: no tile shown")
    # the smaller of the two decides where to look: its tiles give the frame and the area compared
    small, small_st = (mine, st) if _extent(mine) <= _extent(theirs) else (theirs, st_ref)
    frame = local_frame(small_st, small)
    to_frame = np.linalg.inv(frame)
    box_a, box_b = _boxes(mine, to_frame), _boxes(theirs, to_frame)
    lo = np.maximum(box_a[:, :2].min(0), box_b[:, :2].min(0))      # the overlap of the two tilesets
    hi = np.minimum(box_a[:, 2:].max(0), box_b[:, 2:].max(0))
    if (hi <= lo).any():
        raise RuntimeError(f"No overlap with {ref.name} among the tiles shown")
    cell = 2.0 * br.cell_size(float((hi - lo).max()))
    rng = np.random.default_rng(0)
    k_a, c_a = _cell_colors(_nearest(mine, box_a, lo, hi), to_frame, cell, rng, box=(lo, hi))
    k_b, c_b = _cell_colors(_nearest(theirs, box_b, lo, hi), to_frame, cell, rng, box=(lo, hi))
    a, b = cm.shared(k_a, c_a, k_b, c_b)
    if ref.use_color:                                # match what the reference looks like, its own correction included
        b = graded(b, ref)
    res = cm.fit(a, b)
    if res is None:
        raise RuntimeError(f"Too little overlap with {ref.name}: {len(a)} ground cells with colors in both. "
                           "Wait for its tiles under this one to load, or zoom in")
    item.color_exposure, item.color_saturation, item.color_contrast = 0.0, 1.0, 0.0   # the fit starts from the raw colors
    item.color_gain, item.color_gamma = res[0].tolist(), res[1].tolist()
    if not item.use_color:
        item.use_color = True
    return len(a)
