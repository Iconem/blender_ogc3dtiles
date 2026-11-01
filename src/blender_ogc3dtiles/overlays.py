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


# ── clipping polygons ────────────────────────────────────────────────────────
# A clipping overlay (uid ``clip_...``, see ui.clip_specs) is a one-channel
# mask, 1 where the tile is cut away. Per material:
#
#     UV Map → Mapping → Image Texture (mask) × Valid ─┐
#     ... other clip masks (MAX for "inside any", MIN for "inside all") ─┤
#         → Greater Than 0.5 → Mix Shader(surface, Transparent BSDF)
#
# "Valid" drops to 0 on detach (an Image Texture without image reads pink, so
# 1 in the red channel, which would cut the whole tile).

CLIP_PREFIX = "clip_"
POLY_TAG = "OGC3D PolyClip"
POLY_MIX = POLY_TAG + " Mix"
POLY_STEP = POLY_TAG + " Step"
POLY_TRANSPARENT = POLY_TAG + " Transparent"


def is_clip_uid(uid) -> bool:
    return str(uid).startswith(CLIP_PREFIX)


def _poly_names(tex_id):
    b = f"{POLY_TAG} {tex_id}"
    return {"uv": b + " UV", "map": b + " Map", "tex": b + " Tex", "valid": b + " Valid",
            "comb": b + " Combine"}


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


def _relink_poly_chain(nt, op):
    """Combine every clip mask of the material into the step node."""
    step = nt.nodes.get(POLY_STEP)
    if step is None:
        return
    valids = sorted((n for n in nt.nodes if n.name.startswith(POLY_TAG) and n.name.endswith(" Valid")),
                    key=lambda n: n.name)
    for n in [n for n in nt.nodes if n.name.startswith(POLY_TAG) and n.name.endswith(" Combine")]:
        nt.nodes.remove(n)
    if not valids:
        return
    acc = valids[0].outputs[0]
    for v in valids[1:]:
        comb = nt.nodes.new("ShaderNodeMath")
        comb.name = comb.label = v.name[: -len(" Valid")] + " Combine"
        comb.operation = op
        comb.location = (v.location.x + 200, v.location.y)
        nt.links.new(acc, comb.inputs[0])
        nt.links.new(v.outputs[0], comb.inputs[1])
        acc = comb.outputs[0]
    nt.links.new(acc, step.inputs[0])


def attach_clip(mat, tex_id, image_name, translation, scale, op="MAXIMUM") -> bool:
    if mat is None or not mat.use_nodes or mat.node_tree is None:
        return False
    img = bpy.data.images.get(image_name)
    if img is None:
        return False
    if img.colorspace_settings.name != "Non-Color":
        img.colorspace_settings.name = "Non-Color"
    nt = mat.node_tree
    nm = _poly_names(tex_id)
    tex, mp, valid = nt.nodes.get(nm["tex"]), nt.nodes.get(nm["map"]), nt.nodes.get(nm["valid"])
    if tex is None or mp is None or valid is None:
        mix = _ensure_poly_mix(nt)
        if mix is None:
            return False
        x0, y0 = mix.location.x - 1300, mix.location.y - 700 - 160 * tex_id
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
        valid = nt.nodes.new("ShaderNodeMath")
        valid.name = valid.label = nm["valid"]
        valid.operation = "MULTIPLY"
        valid.location = (x0 + 750, y0)
        nt.links.new(uv.outputs["UV"], mp.inputs["Vector"])
        nt.links.new(mp.outputs["Vector"], tex.inputs["Vector"])
        nt.links.new(tex.outputs["Color"], valid.inputs[0])
        _relink_poly_chain(nt, op)
    tex.image = img
    mp.inputs["Location"].default_value = (translation[0], translation[1], 0.0)
    mp.inputs["Scale"].default_value = (scale[0], scale[1], 1.0)
    valid.inputs[1].default_value = 1.0
    return True


def detach_clip(mat, tex_id) -> bool:
    if mat is None or not mat.use_nodes or mat.node_tree is None:
        return False
    nm = _poly_names(tex_id)
    valid, tex = mat.node_tree.nodes.get(nm["valid"]), mat.node_tree.nodes.get(nm["tex"])
    if valid is None:
        return False
    valid.inputs[1].default_value = 0.0
    if tex is not None:
        tex.image = None
    return True


def remove_poly_clip(mat) -> bool:
    """Take the clipping nodes out of a material (clipping switched off)."""
    if mat is None or not mat.use_nodes or mat.node_tree is None:
        return False
    nt = mat.node_tree
    mix = nt.nodes.get(POLY_MIX)
    if mix is None:
        return False
    src = mix.inputs[1].links[0].from_socket if mix.inputs[1].links else None
    dst = [lk.to_socket for lk in mix.outputs[0].links]
    for n in [n for n in nt.nodes if n.name.startswith(POLY_TAG)]:
        nt.nodes.remove(n)
    if src is not None:
        for s in dst:
            nt.links.new(src, s)
    return True


def apply_event(obj, ev, alpha_for_uid) -> None:
    """An ("attach"/"detach") event from the native backend on a tile object."""
    if ev[0] == "attach":
        _, key, tid, uid, image, tr, sc = ev
        ids = dict(obj.get("overlay_ids") or {})
        ids[uid] = tid
        obj["overlay_ids"] = ids
        if is_clip_uid(uid):
            clips = set(obj.get("clip_tex_ids") or [])
            clips.add(int(tid))
            obj["clip_tex_ids"] = sorted(clips)
            op = "MINIMUM" if "_all_" in uid else "MAXIMUM"
            for m in obj.data.materials:
                attach_clip(m, tid, image, tr, sc, op)
            return
        if int(tid) in set(obj.get("clip_tex_ids") or []):    # set reused by an imagery overlay
            obj["clip_tex_ids"] = [t for t in obj["clip_tex_ids"] if t != int(tid)]
        for m in obj.data.materials:
            attach(m, tid, image, tr, sc, alpha_for_uid(uid))
    elif ev[0] == "detach":
        _, key, tid = ev
        if int(tid) in set(obj.get("clip_tex_ids") or []):
            for m in obj.data.materials:
                detach_clip(m, tid)
            return
        for m in obj.data.materials:
            detach(m, tid)
