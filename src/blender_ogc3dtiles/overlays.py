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


def _names(tex_id):
    b = f"{NODE_TAG} {tex_id}"
    return {"uv": b + " UV", "map": b + " Map", "tex": b + " Tex", "mix": b + " Mix",
            "alpha": b + " Alpha", "fac": b + " Factor"}


def _color_source(nt):
    """Socket carrying the material's current colour (the topmost overlay
    mix, else the image texture, else a RGB node of the base colour)."""
    best = None
    for n in nt.nodes:
        if n.name.startswith(NODE_TAG) and n.name.endswith(" Mix") and n.type == "MIX":
            best = n if best is None or n.location.x > best.location.x else best
    if best is not None:
        return best.outputs[2]
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


def attach(mat, tex_id, image_name, translation, scale, alpha=1.0) -> bool:
    if mat is None or not mat.use_nodes or mat.node_tree is None:
        return False
    img = bpy.data.images.get(image_name)
    if img is None:
        return False
    nt = mat.node_tree
    nm = _names(tex_id)
    tex = nt.nodes.get(nm["tex"])
    mp = nt.nodes.get(nm["map"])
    if tex is not None and mp is not None:          # re-attach: finer raster for the same set
        tex.image = img
        mp.inputs["Location"].default_value = (translation[0], translation[1], 0.0)
        mp.inputs["Scale"].default_value = (scale[0], scale[1], 1.0)
        return True
    src = _color_source(nt)
    x0 = src.node.location.x
    uv = nt.nodes.new("ShaderNodeUVMap")
    uv.name = uv.label = nm["uv"]
    uv.uv_map = f"{OVERLAY_UV_PREFIX}{tex_id}"
    uv.location = (x0 - 300, 700 + 120 * tex_id)
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.name = mp.label = nm["map"]
    mp.vector_type = "POINT"
    mp.inputs["Location"].default_value = (translation[0], translation[1], 0.0)
    mp.inputs["Scale"].default_value = (scale[0], scale[1], 1.0)
    mp.location = (x0 - 100, 700 + 120 * tex_id)
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.name = tex.label = nm["tex"]
    tex.image = img
    tex.extension = "EXTEND"
    tex.interpolation = "Linear"
    tex.location = (x0 + 150, 700 + 120 * tex_id)
    fac = nt.nodes.new("ShaderNodeMath")
    fac.name = fac.label = nm["fac"]
    fac.operation = "MULTIPLY"
    fac.inputs[0].default_value = float(alpha)
    fac.location = (x0 + 450, 850 + 120 * tex_id)
    mix = nt.nodes.new("ShaderNodeMix")
    mix.name = mix.label = nm["mix"]
    mix.data_type = "RGBA"
    mix.blend_type = "MIX"
    mix.location = (x0 + 450, 500 + 120 * tex_id)
    nt.links.new(uv.outputs["UV"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], tex.inputs["Vector"])
    nt.links.new(tex.outputs["Alpha"], fac.inputs[1])
    nt.links.new(fac.outputs[0], mix.inputs[0])
    # consumers of the previous colour now read the mix
    for link in list(src.links):
        nt.links.new(mix.outputs[2], link.to_socket)
    if not mix.outputs[2].links:
        # untextured material: the base colour was a plain value, feed the BSDF
        bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if bsdf is not None:
            nt.links.new(mix.outputs[2], bsdf.inputs["Base Color"])
    nt.links.new(src, mix.inputs[6])
    nt.links.new(tex.outputs["Color"], mix.inputs[7])
    return True


def detach(mat, tex_id) -> bool:
    """cesium-native detaches a raster when a finer one replaces it (and when
    an overlay is removed). Keep the nodes and only drop the image: an Image
    Texture without image reads alpha 0, so the mix shows the material's own
    colour, and the next attach is a cheap image / mapping update instead of
    a rebuilt node graph (which also made EEVEE recompile the material)."""
    if mat is None or not mat.use_nodes or mat.node_tree is None:
        return False
    tex = mat.node_tree.nodes.get(_names(tex_id)["tex"])
    if tex is None:
        return False
    tex.image = None
    return True


def set_alpha(mat, tex_id, alpha) -> bool:
    n = mat.node_tree.nodes.get(_names(tex_id)["fac"]) if mat and mat.node_tree else None
    if n is None:
        return False
    n.inputs[0].default_value = float(alpha)
    return True


def set_overlay_alpha(uid, alpha) -> int:
    """Live opacity: every tile material carrying this overlay (matched by
    the tex id the tile object recorded for the uid)."""
    n = 0
    for o in bpy.data.objects:
        ids = o.get("overlay_ids")
        if not ids or o.type != "MESH":
            continue
        tid = ids.get(uid) if hasattr(ids, "get") else None
        if tid is None:
            continue
        for m in o.data.materials:
            if set_alpha(m, int(tid), alpha):
                n += 1
    return n


# ── clipping volumes ─────────────────────────────────────────────────────────
# Note: cesium-native gives all overlays sharing a projection the same
# texture coordinate set, so clip nodes are keyed by overlay uid, not by set.
# Every clipping volume of a mesh tile is one "term" node in its material,
# 1 where the per-volume condition holds (inside, or outside, see
# clipping.MODE_OPS):
#
#   prism (uid ``clip_...``, a cesium mask):  UV → Mapping → Image → Term
#   box   (clip_nodes.set_box_terms):  Texture Coordinate (Object) → … → Term
#
#   Terms → MAX / MIN chain → Greater Than 0.5 → Mix Shader(surface, Transparent)
#
# The op is stored on the material (``ogc_clip_op``). A detached mask's nodes
# are removed (a stale term would bias the MIN chain), and the whole chain
# goes when no term is left.

CLIP_PREFIX = "clip_"
POLY_TAG = "OGC3D PolyClip"
POLY_MIX = POLY_TAG + " Mix"
POLY_STEP = POLY_TAG + " Step"
POLY_TRANSPARENT = POLY_TAG + " Transparent"
CLIP_OP_PROP = "ogc_clip_op"


def is_clip_uid(uid) -> bool:
    return str(uid).startswith(CLIP_PREFIX)


def _poly_names(uid):
    b = f"{POLY_TAG} {uid}"
    return {"uv": b + " UV", "map": b + " Map", "tex": b + " Tex", "term": b + " Term"}


def _ensure_poly_mix(nt):
    """Mix Shader between the material's shader and a Transparent BSDF, put
    in front of the viewport-region clip mix when that one exists."""
    from . import materials
    mix = nt.nodes.get(POLY_MIX)
    if mix is not None:
        return mix
    target = materials.surface_target(nt, include_poly=False)
    if target is None or not target.links:
        return None
    src = target.links[0].from_socket
    x, y = target.node.location
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    tr.name = tr.label = POLY_TRANSPARENT
    tr.location = (x - 420, y - 420)
    step = nt.nodes.new("ShaderNodeMath")
    step.name = step.label = POLY_STEP
    step.operation = "GREATER_THAN"
    step.inputs[1].default_value = 0.5
    step.location = (x - 420, y - 250)
    mix = nt.nodes.new("ShaderNodeMixShader")
    mix.name = mix.label = POLY_MIX
    mix.location = (x - 200, y)
    nt.links.new(step.outputs[0], mix.inputs["Fac"])
    nt.links.new(src, mix.inputs[1])
    nt.links.new(tr.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], target)
    return mix


def _is_term(n) -> bool:
    return n.name.startswith(POLY_TAG) and n.name.endswith(" Term")


def relink_clip_chain(mat, op=None) -> None:
    """Combine every term of the material with ``op`` (MAXIMUM / MINIMUM;
    default: the stored one) into the step node; no term: no clipping."""
    if mat is None or mat.node_tree is None:
        return
    if op is not None:
        mat[CLIP_OP_PROP] = op
    op = mat.get(CLIP_OP_PROP, "MAXIMUM")
    nt = mat.node_tree
    for n in [n for n in nt.nodes if n.name.startswith(POLY_TAG) and n.name.endswith(" Combine")]:
        nt.nodes.remove(n)
    terms = sorted((n for n in nt.nodes if _is_term(n)), key=lambda n: n.name)
    if not terms:
        remove_poly_clip(mat)
        return
    if _ensure_poly_mix(nt) is None:
        return
    step = nt.nodes.get(POLY_STEP)
    acc = terms[0].outputs[0]
    for t in terms[1:]:
        comb = nt.nodes.new("ShaderNodeMath")
        comb.name = comb.label = t.name[: -len(" Term")] + " Combine"
        comb.operation = op
        comb.location = (t.location.x + 200, t.location.y)
        nt.links.new(acc, comb.inputs[0])
        nt.links.new(t.outputs[0], comb.inputs[1])
        acc = comb.outputs[0]
    nt.links.new(acc, step.inputs[0])


def attach_clip(mat, tex_id, uid, image_name, translation, scale, op=None) -> bool:
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
        mix = _ensure_poly_mix(nt)
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
        relink_clip_chain(mat, op)
    elif op is not None and mat.get(CLIP_OP_PROP) != op:
        relink_clip_chain(mat, op)
    uvn = nt.nodes.get(nm["uv"])
    if uvn is not None and uvn.uv_map != f"{OVERLAY_UV_PREFIX}{tex_id}":
        uvn.uv_map = f"{OVERLAY_UV_PREFIX}{tex_id}"
    tex.image = img
    mp.inputs["Location"].default_value = (translation[0], translation[1], 0.0)
    mp.inputs["Scale"].default_value = (scale[0], scale[1], 1.0)
    return True


def detach_clip(mat, uid) -> bool:
    if mat is None or not mat.use_nodes or mat.node_tree is None:
        return False
    nt = mat.node_tree
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


def _clip_op_for(obj):
    root = obj.parent
    cfg = root.get("ogc_clip") if root is not None else None
    return cfg.get("op") if cfg else None


def _shader_clipped(obj) -> bool:
    """Mesh tiles with faces; point / splat tiles are clipped by Geometry
    Nodes (their vertex-only mesh has no overlay UVs)."""
    return obj.type == "MESH" and len(obj.data.polygons) > 0


def apply_event(obj, ev, alpha_for_uid) -> None:
    """An ("attach"/"detach") event from the native backend on a tile object."""
    if ev[0] == "attach":
        _, key, tid, uid, image, tr, sc = ev
        ids = dict(obj.get("overlay_ids") or {})
        ids[uid] = tid
        obj["overlay_ids"] = ids
        if is_clip_uid(uid):
            if _shader_clipped(obj):
                op = _clip_op_for(obj)
                for m in obj.data.materials:
                    attach_clip(m, tid, uid, image, tr, sc, op)
            return
        for m in obj.data.materials:
            attach(m, tid, image, tr, sc, alpha_for_uid(uid))
    elif ev[0] == "detach":
        tid, uid = ev[2], (ev[3] if len(ev) > 3 else "")
        if is_clip_uid(uid):
            ids = dict(obj.get("overlay_ids") or {})
            ids.pop(uid, None)
            obj["overlay_ids"] = ids
            for m in obj.data.materials:
                detach_clip(m, uid)
            return
        for m in obj.data.materials:
            detach(m, tid)
