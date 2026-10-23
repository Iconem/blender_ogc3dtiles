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
    if mat is None or not mat.use_nodes or mat.node_tree is None:
        return False
    nt = mat.node_tree
    nm = _names(tex_id)
    mix = nt.nodes.get(nm["mix"])
    if mix is None:
        return False
    prev = mix.inputs[6].links[0].from_socket if mix.inputs[6].links else None
    for link in list(mix.outputs[2].links):
        if prev is not None:
            nt.links.new(prev, link.to_socket)
        else:
            nt.links.remove(link)
    for k in ("uv", "map", "tex", "fac", "mix"):
        n = nt.nodes.get(nm[k])
        if n is not None:
            nt.nodes.remove(n)
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


def apply_event(obj, ev, alpha_for_uid) -> None:
    """An ("attach"/"detach") event from the native backend on a tile object."""
    if ev[0] == "attach":
        _, key, tid, uid, image, tr, sc = ev
        ids = dict(obj.get("overlay_ids") or {})
        ids[uid] = tid
        obj["overlay_ids"] = ids
        for m in obj.data.materials:
            attach(m, tid, image, tr, sc, alpha_for_uid(uid))
    elif ev[0] == "detach":
        _, key, tid = ev
        for m in obj.data.materials:
            detach(m, tid)
