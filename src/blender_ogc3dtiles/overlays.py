"""Raster overlays on tile materials.

cesium-native tells us (through the native backend's raster hooks) which
raster image covers a tile for overlay texture-coordinate set ``tex_id``,
with the ``translation`` / ``scale`` that map the tile's
``_CESIUMOVERLAY_<id>`` UVs into that raster. Per tile material we insert:

    UV Map(_CESIUMOVERLAY_<id>) → Mapping(translation, scale) → Image Texture
        → Mix(RGBA, factor = opacity × raster alpha) over the material's
          current colour → every consumer of that colour (Principled Base
          Color / Emission, the Relight group's Albedo, ...)

Overlays chain: a second overlay mixes over the first mix's result. Detach
restores the previous links, so the material is left as it was built.
"""
from __future__ import annotations

import bpy

from .io import OVERLAY_UV_PREFIX

NODE_TAG = "OGC3D Overlay"
ORDER_PROP = "ogc_order"


def _names(uid):
    b = f"{NODE_TAG} {uid}"
    return {"uv": b + " UV", "map": b + " Map", "tex": b + " Tex", "mix": b + " Mix",
            "alpha": b + " Alpha", "fac": b + " Factor"}


def _overlay_mixes(nt):
    return [n for n in nt.nodes
            if n.name.startswith(NODE_TAG) and n.name.endswith(" Mix") and n.type == "MIX"]


def _color_source(nt):
    """Socket carrying the material's own colour (the image texture, else a
    RGB node of the base colour)."""
    for n in nt.nodes:
        if n.type == "TEX_IMAGE" and n.image is not None and not n.name.startswith(NODE_TAG):
            return n.outputs["Color"]
    bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    rgb = nt.nodes.get(NODE_TAG + " Base") or nt.nodes.new("ShaderNodeRGB")
    rgb.name = rgb.label = NODE_TAG + " Base"
    rgb.location = (-900, 300)
    if bsdf is not None:
        rgb.outputs[0].default_value = bsdf.inputs["Base Color"].default_value
    return rgb.outputs[0]


def _insert_mix(nt, mix) -> None:
    """Put a new overlay mix in the chain by layer order, bottom layer first:
    material colour → mix → mix → every consumer of the colour."""
    others = [m for m in _overlay_mixes(nt) if m != mix]    # bpy wrappers: not "is"
    if others:
        ordered = sorted(others, key=lambda m: m.get(ORDER_PROP, 0))
        src = ordered[0].inputs[6].links[0].from_socket
        dst = [lk.to_socket for lk in ordered[-1].outputs[2].links]
    else:
        src = _color_source(nt)
        dst = [lk.to_socket for lk in src.links]
        if not dst:
            # untextured material: the base colour was a plain value, feed the BSDF
            bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
            dst = [bsdf.inputs["Base Color"]] if bsdf is not None else []
    acc = src
    for m in sorted(others + [mix], key=lambda m: m.get(ORDER_PROP, 0)):
        nt.links.new(acc, m.inputs[6])
        acc = m.outputs[2]
    for sock in dst:
        nt.links.new(acc, sock)


def attach(mat, tex_id, uid, image_name, translation, scale, alpha=1.0, order=0) -> bool:
    """Overlays sharing a projection share a texture coordinate set, so the
    nodes are keyed by overlay uid. ``order``: position in the overlay list,
    later layers mix over earlier ones."""
    if mat is None or not mat.use_nodes or mat.node_tree is None:
        return False
    img = bpy.data.images.get(image_name)
    if img is None:
        return False
    nt = mat.node_tree
    nm = _names(uid)
    tex = nt.nodes.get(nm["tex"])
    mp = nt.nodes.get(nm["map"])
    if tex is not None and mp is not None:          # re-attach: finer raster for the same layer
        tex.image = img
        mp.inputs["Location"].default_value = (translation[0], translation[1], 0.0)
        mp.inputs["Scale"].default_value = (scale[0], scale[1], 1.0)
        uv = nt.nodes.get(nm["uv"])
        if uv is not None and uv.uv_map != f"{OVERLAY_UV_PREFIX}{tex_id}":
            uv.uv_map = f"{OVERLAY_UV_PREFIX}{tex_id}"
        return True
    y = 700 + 260 * order
    uv = nt.nodes.new("ShaderNodeUVMap")
    uv.name = uv.label = nm["uv"]
    uv.uv_map = f"{OVERLAY_UV_PREFIX}{tex_id}"
    uv.location = (-800, y)
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.name = mp.label = nm["map"]
    mp.vector_type = "POINT"
    mp.inputs["Location"].default_value = (translation[0], translation[1], 0.0)
    mp.inputs["Scale"].default_value = (scale[0], scale[1], 1.0)
    mp.location = (-600, y)
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.name = tex.label = nm["tex"]
    tex.image = img
    tex.extension = "EXTEND"
    tex.interpolation = "Linear"
    tex.location = (-350, y)
    fac = nt.nodes.new("ShaderNodeMath")
    fac.name = fac.label = nm["fac"]
    fac.operation = "MULTIPLY"
    fac.inputs[0].default_value = float(alpha)
    fac.location = (-50, y + 150)
    mix = nt.nodes.new("ShaderNodeMix")
    mix.name = mix.label = nm["mix"]
    mix.data_type = "RGBA"
    mix.blend_type = "MIX"
    mix.location = (-50, y - 100)
    mix[ORDER_PROP] = int(order)
    nt.links.new(uv.outputs["UV"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], tex.inputs["Vector"])
    nt.links.new(tex.outputs["Alpha"], fac.inputs[1])
    nt.links.new(fac.outputs[0], mix.inputs[0])
    nt.links.new(tex.outputs["Color"], mix.inputs[7])
    _insert_mix(nt, mix)
    return True


def detach(mat, uid) -> bool:
    """cesium-native detaches a raster when a finer one replaces it (and when
    an overlay is removed). Keep the nodes and only drop the image: an Image
    Texture without image reads alpha 0, so the mix shows the colour below,
    and the next attach is a cheap image / mapping update instead of a
    rebuilt node graph (which also made EEVEE recompile the material)."""
    if mat is None or not mat.use_nodes or mat.node_tree is None:
        return False
    tex = mat.node_tree.nodes.get(_names(uid)["tex"])
    if tex is None:
        return False
    tex.image = None
    return True


def set_alpha(mat, uid, alpha) -> bool:
    n = mat.node_tree.nodes.get(_names(uid)["fac"]) if mat and mat.node_tree else None
    if n is None:
        return False
    n.inputs[0].default_value = float(alpha)
    return True


def set_overlay_alpha(uid, alpha) -> int:
    """Live opacity: every tile material carrying this overlay."""
    n = 0
    for o in bpy.data.objects:
        ids = o.get("overlay_ids")
        if not ids or o.type != "MESH" or uid not in ids:
            continue
        for m in o.data.materials:
            if set_alpha(m, uid, alpha):
                n += 1
    return n


# ── clipping volumes ─────────────────────────────────────────────────────────
# Note: cesium-native gives all overlays sharing a projection the same
# texture coordinate set, so clip nodes are keyed by overlay uid, not by set.
# Every clipping volume of a mesh tile is one "term" node in its material, 1
# inside the volume:
#
#   polygon (uid ``clip_...``, a cesium mask):  UV → Mapping → Image → Term
#   volumes (clip_nodes.set_volumes_term):  the tileset's shared group → Term
#
#   Terms → MAX chain ┐
#   Terms → MIN chain ┴ Mix (attribute "any") → |x - attribute "invert"|
#     → Greater Than 0.5 → Mix Shader(surface, Transparent)
#
# The two attributes are view-layer attributes (custom properties on the
# scene, clip_nodes.set_mode), so a mode switch recompiles no material. The
# structure only changes when a volume is added or removed. A mask detached
# for a finer raster keeps its nodes for the same reason.

CLIP_PREFIX = "clip_"
POLY_TAG = "OGC3D PolyClip"
POLY_MIX = POLY_TAG + " Mix"
POLY_TRANSPARENT = POLY_TAG + " Transparent"
POLY_MODE = POLY_TAG + " Mode"
MODE_GROUP_PREFIX = "OGC3D Clip Mode "
CLIP_UID_PROP = "ogc_clip_uid"


def clip_attr_base(tileset_uid) -> str:
    """Start of the names of a tileset's scene custom properties."""
    return "ogc_clip_" + "".join(c if c.isalnum() else "_" for c in str(tileset_uid))


def clip_attr_names(tileset_uid) -> tuple:
    """Scene custom property names of a tileset's mode: (any, invert)."""
    b = clip_attr_base(tileset_uid)
    return b + "_any", b + "_invert"


def _mode_group(tileset_uid):
    """Group (Min, Max → Cut) applying the tileset's mode, shared by its tiles."""
    name = f"{MODE_GROUP_PREFIX}{tileset_uid}"
    ng = bpy.data.node_groups.get(name)
    if ng is not None:
        return ng
    ng = bpy.data.node_groups.new(name, "ShaderNodeTree")
    for k in ("Min", "Max"):
        ng.interface.new_socket(k, in_out="INPUT", socket_type="NodeSocketFloat")
    ng.interface.new_socket("Cut", in_out="OUTPUT", socket_type="NodeSocketFloat")
    N, L = ng.nodes.new, ng.links.new

    def math(op):
        n = N("ShaderNodeMath")
        n.operation = op
        return n

    gi, go = N("NodeGroupInput"), N("NodeGroupOutput")
    any_name, inv_name = clip_attr_names(tileset_uid)
    a_any, a_inv = N("ShaderNodeAttribute"), N("ShaderNodeAttribute")
    a_any.attribute_type = a_inv.attribute_type = "VIEW_LAYER"
    a_any.attribute_name, a_inv.attribute_name = any_name, inv_name
    sel = N("ShaderNodeMix")
    sel.data_type = "FLOAT"
    sub, ab, step = math("SUBTRACT"), math("ABSOLUTE"), math("GREATER_THAN")
    step.inputs[1].default_value = 0.5
    L(a_any.outputs["Fac"], sel.inputs[0])
    L(gi.outputs[0], sel.inputs[2])
    L(gi.outputs[1], sel.inputs[3])
    L(sel.outputs[0], sub.inputs[0])
    L(a_inv.outputs["Fac"], sub.inputs[1])
    L(sub.outputs[0], ab.inputs[0])
    L(ab.outputs[0], step.inputs[0])
    L(step.outputs[0], go.inputs[0])
    return ng


def tileset_uid_of_mask(uid) -> str:
    """clip_<tileset uid>_<p0 | u> → the tileset uid."""
    return str(uid)[len(CLIP_PREFIX):].rsplit("_", 1)[0]


def is_clip_uid(uid) -> bool:
    return str(uid).startswith(CLIP_PREFIX)


def _poly_names(uid):
    b = f"{POLY_TAG} {uid}"
    return {"uv": b + " UV", "map": b + " Map", "tex": b + " Tex", "term": b + " Term"}


def _ensure_poly_mix(nt, tileset_uid):
    """Mix Shader between the material's shader and a Transparent BSDF, put
    in front of the viewport-region clip mix when that one exists, with the
    mode logic ahead of it."""
    from . import materials
    mix = nt.nodes.get(POLY_MIX)
    if mix is not None:
        return mix
    target = materials.surface_target(nt, include_poly=False)
    if target is None or not target.links:
        return None
    src = target.links[0].from_socket
    x, y = target.node.location
    N, L = nt.nodes.new, nt.links.new

    def named(node, name, dx, dy):
        node.name = node.label = name
        node.location = (x + dx, y + dy)
        return node

    tr = named(N("ShaderNodeBsdfTransparent"), POLY_TRANSPARENT, -420, -420)
    mode = named(N("ShaderNodeGroup"), POLY_MODE, -420, -250)
    mode.node_tree = _mode_group(tileset_uid)
    mix = named(N("ShaderNodeMixShader"), POLY_MIX, -200, 0)
    L(mode.outputs[0], mix.inputs["Fac"])
    L(src, mix.inputs[1])
    L(tr.outputs[0], mix.inputs[2])
    L(mix.outputs[0], target)
    return mix


def _is_term(n) -> bool:
    return n.name.startswith(POLY_TAG) and n.name.endswith(" Term")


def relink_clip_chain(mat, tileset_uid=None) -> None:
    """Rebuild the MAX and MIN chains over the material's terms; no term: no
    clipping. Only needed when a term comes or goes."""
    if mat is None or mat.node_tree is None:
        return
    if tileset_uid is not None:
        mat[CLIP_UID_PROP] = tileset_uid
    tileset_uid = mat.get(CLIP_UID_PROP, "")
    nt = mat.node_tree
    for n in [n for n in nt.nodes if n.name.startswith(POLY_TAG) and " Combine" in n.name]:
        nt.nodes.remove(n)
    terms = sorted((n for n in nt.nodes if _is_term(n)), key=lambda n: n.name)
    if not terms:
        remove_poly_clip(mat)
        return
    if _ensure_poly_mix(nt, tileset_uid) is None:
        return
    mode = nt.nodes.get(POLY_MODE)
    for op, sock, dy, out in (("MINIMUM", mode.inputs[0], 0, "Min"),
                              ("MAXIMUM", mode.inputs[1], 120, "Max")):
        def value(t):       # the volumes group has both; a mask one value
            return t.outputs.get(out) or t.outputs[0]

        acc = value(terms[0])
        for t in terms[1:]:
            comb = nt.nodes.new("ShaderNodeMath")
            comb.name = comb.label = f"{t.name[: -len(' Term')]} Combine {op}"
            comb.operation = op
            comb.location = (t.location.x + 200, t.location.y + dy)
            nt.links.new(acc, comb.inputs[0])
            nt.links.new(value(t), comb.inputs[1])
            acc = comb.outputs[0]
        nt.links.new(acc, sock)


def attach_clip(mat, tex_id, uid, image_name, translation, scale) -> bool:
    if mat is None or not mat.use_nodes or mat.node_tree is None:
        return False
    img = bpy.data.images.get(image_name)
    if img is None:
        return False
    if img.colorspace_settings.name != "Non-Color":
        img.colorspace_settings.name = "Non-Color"
    nt = mat.node_tree
    nm = _poly_names(uid)
    tex, mp, term = nt.nodes.get(nm["tex"]), nt.nodes.get(nm["map"]), nt.nodes.get(nm["term"])
    if tex is None or mp is None or term is None:
        tileset_uid = tileset_uid_of_mask(uid)
        mix = _ensure_poly_mix(nt, tileset_uid)
        if mix is None:
            return False
        n_terms = sum(1 for n in nt.nodes if _is_term(n))
        x0, y0 = mix.location.x - 1300, mix.location.y - 700 - 160 * n_terms
        uv = nt.nodes.new("ShaderNodeUVMap")
        uv.name = uv.label = nm["uv"]
        uv.uv_map = f"{OVERLAY_UV_PREFIX}{tex_id}"
        uv.location = (x0, y0)
        mp = nt.nodes.new("ShaderNodeMapping")
        mp.name = mp.label = nm["map"]
        mp.vector_type = "POINT"
        mp.location = (x0 + 200, y0)
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.name = tex.label = nm["tex"]
        tex.extension = "EXTEND"
        tex.interpolation = "Linear"
        tex.location = (x0 + 450, y0)
        term = nt.nodes.new("ShaderNodeMath")       # pass-through, the chain's handle
        term.name = term.label = nm["term"]
        term.operation = "ADD"
        term.inputs[1].default_value = 0.0
        term.location = (x0 + 750, y0)
        nt.links.new(uv.outputs["UV"], mp.inputs["Vector"])
        nt.links.new(mp.outputs["Vector"], tex.inputs["Vector"])
        nt.links.new(tex.outputs["Color"], term.inputs[0])
        relink_clip_chain(mat, tileset_uid)
    uvn = nt.nodes.get(nm["uv"])
    if uvn is not None and uvn.uv_map != f"{OVERLAY_UV_PREFIX}{tex_id}":
        uvn.uv_map = f"{OVERLAY_UV_PREFIX}{tex_id}"
    tex.image = img
    mp.inputs["Location"].default_value = (translation[0], translation[1], 0.0)
    mp.inputs["Scale"].default_value = (scale[0], scale[1], 1.0)
    return True


def detach_clip(mat, uid, keep=False) -> bool:
    """``keep``: the overlay stays, cesium-native is swapping in a finer
    raster; only drop the image. Otherwise the term goes (a stale term would
    bias the MIN chain)."""
    if mat is None or not mat.use_nodes or mat.node_tree is None:
        return False
    nt = mat.node_tree
    if keep:
        tex = nt.nodes.get(_poly_names(uid)["tex"])
        if tex is not None:
            tex.image = None
        return tex is not None
    nodes = [nt.nodes.get(n) for n in _poly_names(uid).values()]
    if not any(nodes):
        return False
    for n in nodes:
        if n is not None:
            nt.nodes.remove(n)
    relink_clip_chain(mat)
    return True


def remove_poly_clip(mat) -> bool:
    """Take the clipping nodes out of a material (clipping switched off)."""
    if mat is None or not mat.use_nodes or mat.node_tree is None:
        return False
    nt = mat.node_tree
    mix = nt.nodes.get(POLY_MIX)
    src = mix.inputs[1].links[0].from_socket if mix is not None and mix.inputs[1].links else None
    dst = [lk.to_socket for lk in mix.outputs[0].links] if mix is not None else []
    tagged = [n for n in nt.nodes if n.name.startswith(POLY_TAG)]
    for n in tagged:
        nt.nodes.remove(n)
    if src is not None:
        for s in dst:
            nt.links.new(src, s)
    return bool(tagged)


def _mask_in_use(obj, uid) -> bool:
    root = obj.parent
    cfg = root.get("ogc_clip") if root is not None else None
    return bool(cfg) and uid in list(cfg.get("masks") or [])


def _shader_clipped(obj) -> bool:
    """Mesh tiles with faces; point / splat tiles are clipped by Geometry
    Nodes (their vertex-only mesh has no overlay UVs)."""
    return obj.type == "MESH" and len(obj.data.polygons) > 0


def apply_event(obj, ev, alpha_for_uid, order_for_uid=None) -> None:
    """An ("attach"/"detach") event from the native backend on a tile object."""
    if ev[0] == "attach":
        _, key, tid, uid, image, tr, sc = ev
        ids = dict(obj.get("overlay_ids") or {})
        ids[uid] = tid
        obj["overlay_ids"] = ids
        if is_clip_uid(uid):
            if _shader_clipped(obj):
                for m in obj.data.materials:
                    attach_clip(m, tid, uid, image, tr, sc)
            return
        order = order_for_uid(uid) if order_for_uid is not None else 0
        for m in obj.data.materials:
            attach(m, tid, uid, image, tr, sc, alpha_for_uid(uid), order)
    elif ev[0] == "detach":
        uid = ev[3] if len(ev) > 3 else ""
        if is_clip_uid(uid):
            keep = _mask_in_use(obj, uid)
            if not keep:
                ids = dict(obj.get("overlay_ids") or {})
                ids.pop(uid, None)
                obj["overlay_ids"] = ids
            for m in obj.data.materials:
                detach_clip(m, uid, keep)
            return
        for m in obj.data.materials:
            detach(m, uid)
