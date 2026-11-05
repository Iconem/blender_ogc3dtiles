"""
materials.py — "Relight" node group for photogrammetry tiles.

Photogrammetry textures carry the capture lighting. This module builds ONE
shared, user-editable node group ("OGC3D Relight") that derives roughness,
a gold/metal mask and a shadow lift from the albedo, and swaps every tile
material's Principled BSDF for it (the Image Texture node stays).

Everything tunable lives in Value nodes inside the group (named, so the
sidebar can show them as sliders); because the group is shared, editing it
once — in the panel or in the Shader Editor — changes every tile.
"""
from __future__ import annotations

import colorsys

import bpy
from bpy.types import Operator

from .tileset.feature_meta import MAX_CLASSES, REGISTRY, attribute_name

GROUP_NAME = "OGC3D Relight"
TUNABLES = (
    # (node name, default, min, max, description)
    ("Albedo Strength", 1.0, 0.0, 1.0, "1 = photo albedo, 0 = pure clay (the 'Clay Color' RGB node "
                                       "in the group)"),
    ("Shadow Lift", 1.3, 0.5, 3.0, "Gamma on the albedo: >1 lifts baked shadows"),
    ("Saturation", 1.1, 0.0, 2.0, "Albedo saturation"),
    ("Baked Light", 0.5, 0.0, 1.0, "0 = fully lit Principled BSDF, 1 = unlit albedo. Photogrammetry "
                                  "already carries its lighting; higher values also hide "
                                  "shading seams between tiles"),
    ("Roughness Dark", 0.95, 0.0, 1.0, "Roughness for dark albedo"),
    ("Roughness Bright", 0.55, 0.0, 1.0, "Roughness for bright albedo"),
    ("Gold Hue", 0.11, 0.0, 1.0, "Hue centre of the metal mask (0.11 ≈ gold)"),
    ("Gold Range", 0.06, 0.005, 0.5, "Hue half-width of the metal mask"),
    ("Gold Min Saturation", 0.25, 0.0, 1.0, "Below this saturation nothing counts as gold"),
    ("Gold Metallic", 0.9, 0.0, 1.0, "Metallic applied inside the mask"),
    ("Gold Roughness", 0.25, 0.0, 1.0, "Roughness inside the mask"),
    ("Gold Boost", 0.35, 0.0, 2.0, "Extra brightness inside the mask"),
    ("Specular", 0.3, 0.0, 1.0, "Specular IOR level outside the mask"),
)
HIDDEN_TUNABLES = (("Gold Enable", 0.0),)     # driven by scene props, not sliders

# ── viewport clipping region → shader ────────────────────────────────────────
# EEVEE (Material Preview / Rendered) ignores Blender's clipping region
# (Alt+B); Solid honours it.  With "Clip to viewport region" on, the region's
# planes are copied into this shared group every tick and every tile
# material mixes to a Transparent BSDF where any plane says "outside".
CLIP_GROUP = "OGC3D Clip"
CLIP_ENABLE = "Clip Enable"
CLIP_MIX = "OGC3D Clip Mix"
CLIP_TRANSPARENT = "OGC3D Clip Transparent"
CLIP_PLANES = 6                                # RegionView3D.clip_planes
_last_clip = [None]
GROUP_VERSION_NODE = "Clay Color"             # presence marks an up-to-date group


def _value_node(ng, name, default):
    n = ng.nodes.new("ShaderNodeValue")
    n.name = n.label = name
    n.outputs[0].default_value = default
    return n


def ensure_relight_group():
    ng = bpy.data.node_groups.get(GROUP_NAME)
    if ng is not None:
        if ng.nodes.get(GROUP_VERSION_NODE) is not None:
            return ng
        # older group from a previous version: rebuild the nodes in place.
        # The interface sockets are kept (removing them would drop the links
        # of every material using the group → black tiles).
        for n in list(ng.nodes):
            ng.nodes.remove(n)
    else:
        ng = bpy.data.node_groups.new(GROUP_NAME, "ShaderNodeTree")
    _build_relight_group(ng)
    return ng


def _build_relight_group(ng):
    iface = ng.interface
    have = {it.name for it in iface.items_tree if getattr(it, "item_type", "") == "SOCKET"}
    if "Albedo" not in have:
        iface.new_socket("Albedo", in_out="INPUT", socket_type="NodeSocketColor")
    if "Alpha" not in have:
        iface.new_socket("Alpha", in_out="INPUT", socket_type="NodeSocketFloat").default_value = 1.0
    if "BSDF" not in have:
        iface.new_socket("BSDF", in_out="OUTPUT", socket_type="NodeSocketShader")
    nodes, links = ng.nodes, ng.links
    n_in = nodes.new("NodeGroupInput")
    n_out = nodes.new("NodeGroupOutput")
    n_in.location = (-1400, 0)
    n_out.location = (900, 0)

    vals = {}
    for i, (name, default, *_rest) in enumerate(TUNABLES + HIDDEN_TUNABLES):
        v = _value_node(ng, name, default)
        v.location = (-1400, -250 - 110 * i)
        vals[name] = v

    # albedo → gamma (shadow lift) → saturation
    gamma = nodes.new("ShaderNodeGamma")
    gamma.location = (-1100, 100)
    links.new(n_in.outputs["Albedo"], gamma.inputs["Color"])
    links.new(vals["Shadow Lift"].outputs[0], gamma.inputs["Gamma"])
    hsv = nodes.new("ShaderNodeHueSaturation")
    hsv.location = (-900, 100)
    links.new(gamma.outputs["Color"], hsv.inputs["Color"])
    links.new(vals["Saturation"].outputs[0], hsv.inputs["Saturation"])

    # albedo ↔ clay
    clay = nodes.new("ShaderNodeRGB")
    clay.name = clay.label = "Clay Color"
    clay.location = (-900, 350)
    clay.outputs[0].default_value = (0.55, 0.52, 0.48, 1.0)
    albedo_mix = nodes.new("ShaderNodeMix")
    albedo_mix.data_type = "RGBA"
    albedo_mix.blend_type = "MIX"
    albedo_mix.label = "albedo strength"
    albedo_mix.location = (-750, 200)
    links.new(vals["Albedo Strength"].outputs[0], albedo_mix.inputs["Factor"])
    links.new(clay.outputs[0], albedo_mix.inputs[6])           # A: clay
    links.new(hsv.outputs["Color"], albedo_mix.inputs[7])      # B: processed albedo
    hsv_out = albedo_mix.outputs[2]

    # luminance → roughness ramp
    bw = nodes.new("ShaderNodeRGBToBW")
    bw.location = (-700, -100)
    links.new(hsv_out, bw.inputs["Color"])
    rough = nodes.new("ShaderNodeMapRange")
    rough.location = (-450, -100)
    rough.label = "Roughness from luminance"
    rough.inputs["From Min"].default_value = 0.0
    rough.inputs["From Max"].default_value = 1.0
    links.new(bw.outputs["Val"], rough.inputs["Value"])
    links.new(vals["Roughness Dark"].outputs[0], rough.inputs["To Min"])
    links.new(vals["Roughness Bright"].outputs[0], rough.inputs["To Max"])

    # gold mask from hue / saturation
    sep = nodes.new("ShaderNodeSeparateColor")
    sep.mode = "HSV"
    sep.location = (-700, -350)
    links.new(hsv.outputs["Color"], sep.inputs["Color"])
    hue_d = nodes.new("ShaderNodeMath")
    hue_d.operation = "SUBTRACT"
    hue_d.location = (-500, -350)
    links.new(sep.outputs["Red"], hue_d.inputs[0])
    links.new(vals["Gold Hue"].outputs[0], hue_d.inputs[1])
    hue_abs = nodes.new("ShaderNodeMath")
    hue_abs.operation = "ABSOLUTE"
    hue_abs.location = (-350, -350)
    links.new(hue_d.outputs[0], hue_abs.inputs[0])
    hue_mask = nodes.new("ShaderNodeMapRange")
    hue_mask.location = (-200, -350)
    hue_mask.label = "hue → mask"
    hue_mask.inputs["To Min"].default_value = 1.0
    hue_mask.inputs["To Max"].default_value = 0.0
    hue_mask.inputs["From Min"].default_value = 0.0
    links.new(hue_abs.outputs[0], hue_mask.inputs["Value"])
    links.new(vals["Gold Range"].outputs[0], hue_mask.inputs["From Max"])
    sat_mask = nodes.new("ShaderNodeMath")
    sat_mask.operation = "GREATER_THAN"
    sat_mask.location = (-350, -550)
    links.new(sep.outputs["Green"], sat_mask.inputs[0])
    links.new(vals["Gold Min Saturation"].outputs[0], sat_mask.inputs[1])
    mask0 = nodes.new("ShaderNodeMath")
    mask0.operation = "MULTIPLY"
    mask0.label = "gold mask"
    mask0.location = (0, -400)
    links.new(hue_mask.outputs["Result"], mask0.inputs[0])
    links.new(sat_mask.outputs[0], mask0.inputs[1])
    mask = nodes.new("ShaderNodeMath")          # × Gold Enable (0/1 from the panel toggle)
    mask.operation = "MULTIPLY"
    mask.label = "gold mask (enabled)"
    mask.location = (100, -500)
    links.new(mask0.outputs[0], mask.inputs[0])
    links.new(vals["Gold Enable"].outputs[0], mask.inputs[1])

    # metallic / roughness / specular / colour from the mask
    metallic = nodes.new("ShaderNodeMath")
    metallic.operation = "MULTIPLY"
    metallic.location = (200, -300)
    links.new(mask.outputs[0], metallic.inputs[0])
    links.new(vals["Gold Metallic"].outputs[0], metallic.inputs[1])
    rough_mix = nodes.new("ShaderNodeMix")
    rough_mix.data_type = "FLOAT"
    rough_mix.location = (200, -100)
    links.new(mask.outputs[0], rough_mix.inputs["Factor"])
    links.new(rough.outputs["Result"], rough_mix.inputs[2])      # A (float)
    links.new(vals["Gold Roughness"].outputs[0], rough_mix.inputs[3])  # B (float)
    boost = nodes.new("ShaderNodeMath")
    boost.operation = "MULTIPLY_ADD"
    boost.location = (200, -500)
    links.new(mask.outputs[0], boost.inputs[0])
    links.new(vals["Gold Boost"].outputs[0], boost.inputs[1])
    boost.inputs[2].default_value = 1.0
    color = nodes.new("ShaderNodeMix")
    color.data_type = "RGBA"
    color.blend_type = "MULTIPLY"
    color.location = (400, 100)
    color.inputs["Factor"].default_value = 1.0
    links.new(hsv_out, color.inputs[6])                         # A (color)
    links.new(boost.outputs[0], color.inputs[7])                 # B (color from float)

    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (650, 0)
    links.new(color.outputs[2], bsdf.inputs["Base Color"])
    links.new(rough_mix.outputs[0], bsdf.inputs["Roughness"])
    links.new(metallic.outputs[0], bsdf.inputs["Metallic"])
    if "Specular IOR Level" in bsdf.inputs:
        links.new(vals["Specular"].outputs[0], bsdf.inputs["Specular IOR Level"])
    links.new(n_in.outputs["Alpha"], bsdf.inputs["Alpha"])
    # baked-light mix: unlit albedo (emission) vs the lit BSDF
    emis = nodes.new("ShaderNodeEmission")
    emis.location = (650, -350)
    links.new(color.outputs[2], emis.inputs["Color"])
    emis.inputs["Strength"].default_value = 1.0
    transp = nodes.new("ShaderNodeBsdfTransparent")
    transp.location = (650, -500)
    emis_a = nodes.new("ShaderNodeMixShader")     # alpha for the unlit branch
    emis_a.location = (850, -400)
    links.new(n_in.outputs["Alpha"], emis_a.inputs["Fac"])
    links.new(transp.outputs[0], emis_a.inputs[1])
    links.new(emis.outputs[0], emis_a.inputs[2])
    mixsh = nodes.new("ShaderNodeMixShader")
    mixsh.location = (1050, 0)
    links.new(vals["Baked Light"].outputs[0], mixsh.inputs["Fac"])
    links.new(bsdf.outputs["BSDF"], mixsh.inputs[1])
    links.new(emis_a.outputs[0], mixsh.inputs[2])
    n_out.location = (1250, 0)
    links.new(mixsh.outputs[0], n_out.inputs["BSDF"])
    return ng


def set_gold_enabled(enabled: bool) -> None:
    ng = bpy.data.node_groups.get(GROUP_NAME)
    node = ng.nodes.get("Gold Enable") if ng else None
    if node is not None:
        node.outputs[0].default_value = 1.0 if enabled else 0.0


def ensure_clip_group():
    ng = bpy.data.node_groups.get(CLIP_GROUP)
    if ng is None:
        ng = bpy.data.node_groups.new(CLIP_GROUP, "ShaderNodeTree")
        ng.interface.new_socket("Clip", in_out="OUTPUT", socket_type="NodeSocketFloat")
        _build_clip_group(ng)
    return ng


def _build_clip_group(ng):
    """Clip = Enable × (min_i(N_i · P + D_i) < 0), P = world position.
    Blender's convention: a point is inside the region when N·P + D >= 0 for
    every plane; unused planes are (0,0,0) / D = 1 so they never clip."""
    nodes, links = ng.nodes, ng.links
    nodes.clear()
    out = nodes.new("NodeGroupOutput")
    out.location = (900, 0)
    geo = nodes.new("ShaderNodeNewGeometry")
    geo.location = (-600, 0)
    enable = _value_node(ng, CLIP_ENABLE, 0.0)
    enable.location = (500, -200)
    prev = None
    for i in range(CLIP_PLANES):
        dot = nodes.new("ShaderNodeVectorMath")
        dot.operation = "DOT_PRODUCT"
        dot.name = dot.label = f"Plane {i}"
        dot.location = (-350, 200 - 150 * i)
        dot.inputs[1].default_value = (0.0, 0.0, 0.0)
        links.new(geo.outputs["Position"], dot.inputs[0])
        d = _value_node(ng, f"Plane {i} D", 1.0)
        d.location = (-350, 130 - 150 * i)
        add = nodes.new("ShaderNodeMath")
        add.operation = "ADD"
        add.location = (-150, 200 - 150 * i)
        links.new(dot.outputs["Value"], add.inputs[0])
        links.new(d.outputs[0], add.inputs[1])
        if prev is None:
            prev = add
        else:
            mn = nodes.new("ShaderNodeMath")
            mn.operation = "MINIMUM"
            mn.location = (50 + 60 * i, 200 - 150 * i)
            links.new(prev.outputs[0], mn.inputs[0])
            links.new(add.outputs[0], mn.inputs[1])
            prev = mn
    lt = nodes.new("ShaderNodeMath")
    lt.operation = "LESS_THAN"
    lt.location = (500, 0)
    lt.inputs[1].default_value = 0.0
    links.new(prev.outputs[0], lt.inputs[0])
    mul = nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    mul.location = (700, 0)
    links.new(lt.outputs[0], mul.inputs[0])
    links.new(enable.outputs[0], mul.inputs[1])
    links.new(mul.outputs[0], out.inputs[0])


def surface_target(nt, include_poly=True):
    """Socket a material's final shader should feed: the polygon clip mix,
    else the viewport-region clip mix, else the Material Output surface."""
    if include_poly:
        from .overlays import POLY_MIX
        mix = nt.nodes.get(POLY_MIX)
        if mix is not None:
            return mix.inputs[1]
    mix = nt.nodes.get(CLIP_MIX)
    if mix is not None:
        return mix.inputs[1]
    out = next((n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"), None)
    return out.inputs["Surface"] if out is not None else None


def apply_clip(mat) -> bool:
    if mat is None or not mat.use_nodes or mat.node_tree is None:
        return False
    nt = mat.node_tree
    if nt.nodes.get(CLIP_MIX) is not None:
        return False
    out = next((n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"), None)
    if out is None or not out.inputs["Surface"].links:
        return False
    src = out.inputs["Surface"].links[0].from_socket
    grp = nt.nodes.new("ShaderNodeGroup")
    grp.node_tree = ensure_clip_group()
    grp.name = grp.label = CLIP_GROUP
    grp.location = (out.location.x - 400, out.location.y - 250)
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    tr.name = tr.label = CLIP_TRANSPARENT
    tr.location = (out.location.x - 400, out.location.y - 400)
    mix = nt.nodes.new("ShaderNodeMixShader")
    mix.name = mix.label = CLIP_MIX
    mix.location = (out.location.x - 180, out.location.y)
    out.location.x += 60
    nt.links.new(grp.outputs[0], mix.inputs["Fac"])
    nt.links.new(src, mix.inputs[1])
    nt.links.new(tr.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    return True


def remove_clip(mat) -> bool:
    if mat is None or not mat.use_nodes or mat.node_tree is None:
        return False
    nt = mat.node_tree
    mix = nt.nodes.get(CLIP_MIX)
    if mix is None:
        return False
    src = mix.inputs[1].links[0].from_socket if mix.inputs[1].links else None
    out = next((n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"), None)
    for name in (CLIP_MIX, CLIP_TRANSPARENT, CLIP_GROUP):
        n = nt.nodes.get(name)
        if n is not None:
            nt.nodes.remove(n)
    if src is not None and out is not None:
        nt.links.new(src, out.inputs["Surface"])
    return True


BACKFACE_ORIGINAL = "ogc3d_backface"       # material custom prop: imported culling flag


def set_backface_mode(mode: str) -> int:
    """DOUBLE / SINGLE force the culling flag on every tile material (EEVEE
    and Cycles); MATERIAL restores what the tile declared."""
    n = 0
    for m in tile_materials():
        apply_backface(m, mode)
        n += 1
    return n


def apply_backface(mat, mode: str) -> None:
    if mat is None:
        return
    if BACKFACE_ORIGINAL not in mat:
        mat[BACKFACE_ORIGINAL] = int(mat.use_backface_culling)
    if mode == "DOUBLE":
        cull = False
    elif mode == "SINGLE":
        cull = True
    else:
        cull = bool(mat[BACKFACE_ORIGINAL])
    mat.use_backface_culling = cull
    if hasattr(mat, "use_backface_culling_shadow"):
        mat.use_backface_culling_shadow = cull


def set_clip_materials(enabled: bool) -> int:
    """Apply / remove the clip mix on every tile material; returns the count."""
    n = 0
    for m in tile_materials():
        n += bool(apply_clip(m) if enabled else remove_clip(m))
    if enabled:
        update_clip_planes(force=True)
    return n


def update_clip_planes(force=False):
    """Copy the first 3D viewport's clipping region (Alt+B) into the group:
    Clip Enable follows ``use_clip_planes``, so Alt+B toggles the effect."""
    ng = bpy.data.node_groups.get(CLIP_GROUP)
    if ng is None:
        return
    from .camera import find_view3d
    r3d, _ = find_view3d()
    if r3d is None:
        return
    on = bool(r3d.use_clip_planes)
    planes = [tuple(p) for p in r3d.clip_planes] if on else []
    key = (on, tuple(round(v, 4) for p in planes for v in p))
    if key == _last_clip[0] and not force:
        return
    _last_clip[0] = key
    en = ng.nodes.get(CLIP_ENABLE)
    if en is not None:
        en.outputs[0].default_value = 1.0 if on else 0.0
    for i in range(CLIP_PLANES):
        dot, d = ng.nodes.get(f"Plane {i}"), ng.nodes.get(f"Plane {i} D")
        if dot is None or d is None:
            continue
        p = planes[i] if i < len(planes) else (0.0, 0.0, 0.0, 1.0)
        if any(abs(v) > 1e-12 for v in p[:3]) and all(v == v for v in p):   # used, no NaN
            dot.inputs[1].default_value = p[:3]
            d.outputs[0].default_value = p[3]
        else:
            dot.inputs[1].default_value = (0.0, 0.0, 0.0)
            d.outputs[0].default_value = 1.0


def _albedo_socket(mat):
    """Find the colour source of a material: Image Texture colour output, or a
    plain RGB from the Principled base colour."""
    nt = mat.node_tree
    for n in nt.nodes:
        if n.type == "TEX_IMAGE" and n.image is not None:
            return n.outputs["Color"], (n.outputs["Alpha"] if n.image.alpha_mode != "NONE" else None)
    bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    rgb = nt.nodes.new("ShaderNodeRGB")
    rgb.location = (-600, 300)
    if bsdf is not None:
        rgb.outputs[0].default_value = bsdf.inputs["Base Color"].default_value
    return rgb.outputs[0], None


def apply_relight(mat) -> bool:
    if mat is None or not mat.use_nodes or mat.node_tree is None:
        return False
    nt = mat.node_tree
    if any(n.type == "GROUP" and n.node_tree and n.node_tree.name == GROUP_NAME for n in nt.nodes):
        return False
    recolor = remove_metadata(mat)       # goes back on the new colour input below
    out = next((n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"), None)
    if out is None:
        return False
    albedo, alpha = _albedo_socket(mat)
    for n in [n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"]:
        n.mute = True
        n.hide = True
        n.location.y -= 400
    grp = nt.nodes.new("ShaderNodeGroup")
    grp.node_tree = ensure_relight_group()
    grp.name = grp.label = GROUP_NAME
    grp.location = (out.location.x - 300, out.location.y)
    nt.links.new(albedo, grp.inputs["Albedo"])
    if alpha is not None:
        nt.links.new(alpha, grp.inputs["Alpha"])
    nt.links.new(grp.outputs["BSDF"], surface_target(nt))
    if recolor:
        apply_metadata(mat)
    return True


def set_relight(enabled: bool) -> int:
    """The Relight group on, or off, every tile material."""
    if enabled:
        ensure_relight_group()
    return sum(1 for m in list(tile_materials()) if (apply_relight(m) if enabled else remove_relight(m)))


def reset_relight_group():
    """Default nodes again, in place: materials keep pointing at the group."""
    ng = bpy.data.node_groups.get(GROUP_NAME)
    if ng is None:
        return ensure_relight_group()
    for n in list(ng.nodes):
        ng.nodes.remove(n)
    _build_relight_group(ng)
    return ng


def reset_metadata_group(scene):
    """Default nodes and ramp again. The group's sockets are rebuilt, so the tile
    materials are taken off it first and put back."""
    props = scene.ogc3dtiles
    was = props.meta_color
    if was:
        props.meta_color = False
    ng = bpy.data.node_groups.get(META_GROUP)
    if ng is not None:
        ng.nodes.clear()
        ng.interface.clear()
    update_metadata_group(scene)
    if was:
        props.meta_color = True


def remove_relight(mat) -> bool:
    if mat is None or not mat.use_nodes or mat.node_tree is None:
        return False
    nt = mat.node_tree
    grp = next((n for n in nt.nodes if n.type == "GROUP" and n.node_tree
                and n.node_tree.name == GROUP_NAME), None)
    if grp is None:
        return False
    recolor = remove_metadata(mat)
    bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    nt.nodes.remove(grp)
    if bsdf is not None:
        bsdf.mute = False
        bsdf.hide = False
        bsdf.location.y += 400
        tgt = surface_target(nt)
        if tgt is not None:
            nt.links.new(bsdf.outputs["BSDF"], tgt)
    if recolor:
        apply_metadata(mat)
    return True


def _is_tile_object(o) -> bool:
    """Direct-mesh tiles carry ``tile_url`` themselves; glTF-imported tiles are
    meshes parented under an Empty holder that carries it."""
    p = o
    for _ in range(4):
        if p is None:
            return False
        if "tile_url" in p:
            return True
        p = p.parent
    return False


def tile_materials():
    seen = set()
    for o in bpy.data.objects:
        if o.type == "MESH" and o.data is not None and _is_tile_object(o):
            for m in o.data.materials:
                if m is not None and m.name not in seen:
                    seen.add(m.name)
                    yield m


# ── feature metadata → colors ────────────────────────────────────────────────
# One shared group reads the chosen meta_<column> attribute. Text columns are
# integer class codes that index a palette image: editing a color or meeting a
# new class only rewrites pixels, no shader is recompiled. Number columns go
# through a Color Ramp between the column's min and max.
META_GROUP = "OGC3D Metadata"
META_NODE = "OGC3D Metadata Color"
META_PALETTE = "OGC3D Metadata Palette"
_PALETTE_SIZE = MAX_CLASSES + 1          # pixel 0 is transparent: no class
_meta_seen = [-1]


# usual LiDAR viewer colors of the LAS classes, by class number
_LAS_COLORS = {
    1: (0.6, 0.6, 0.6), 2: (0.55, 0.4, 0.25), 3: (0.6, 0.85, 0.4), 4: (0.3, 0.7, 0.3),
    5: (0.1, 0.45, 0.15), 6: (0.85, 0.3, 0.25), 7: (0.9, 0.1, 0.9), 9: (0.2, 0.45, 0.9),
    10: (0.35, 0.3, 0.45), 11: (0.3, 0.3, 0.3), 17: (0.9, 0.75, 0.3), 18: (0.9, 0.1, 0.9),
}


def _class_color(code, column=""):
    """Distinct default colors: the golden angle around the hue circle. LAS point
    classes get the colors LiDAR viewers use (``code`` is the class number + 1)."""
    from .tileset.feature_meta import LAS_COLUMN
    if column == LAS_COLUMN and code - 1 in _LAS_COLORS:
        return _LAS_COLORS[code - 1]
    return tuple(colorsys.hsv_to_rgb((code * 0.61803398875) % 1.0, 0.75, 0.9))


def _palette_image():
    img = bpy.data.images.get(META_PALETTE)
    if img is None:
        img = bpy.data.images.new(META_PALETTE, _PALETTE_SIZE, 1, alpha=True, float_buffer=True)
        img.colorspace_settings.name = "Non-Color"
        img.use_fake_user = True
    return img


def write_palette(scene):
    """Class colors of the active column into the palette image."""
    props = scene.ogc3dtiles
    px = [0.0] * (_PALETTE_SIZE * 4)
    for item in props.meta_classes:
        if item.column == props.meta_column and 0 < item.code < _PALETTE_SIZE:
            px[item.code * 4:item.code * 4 + 4] = (*item.color, 1.0)
    img = _palette_image()
    img.pixels.foreach_set(px)
    img.update()
    img.pack()
    from . import phases
    phases.apply_year(scene)


# node name -> place on the canvas, left to right: inputs, the class palette on
# top, the number ramp below, then the mix with the tile's own color
_META_LAYOUT = {
    "Group Input": (-1400, 300), "Column": (-1400, 100), "Is Number": (-1400, -200),
    "Min": (-1400, -320), "Max": (-1400, -440), "Strength": (-1400, -560),
    "Column Value": (-1150, 200),
    "Math.001": (-900, 420), "Math": (-700, 420), "Combine XYZ": (-500, 420),
    "Palette": (-300, 480),
    "Map Range": (-700, 100), "Ramp": (-450, 120),
    "Math.003": (-900, -320), "Math.002": (-700, -320),
    "Mix": (50, 300), "Mix.001": (50, -150), "Math.004": (250, -150),
    "Mix.002": (450, 250), "Group Output": (650, 250),
}


def _layout_metadata_group(ng, only_if_stacked=False):
    if only_if_stacked and any(n.location.x or n.location.y for n in ng.nodes):
        return                               # laid out already, or by hand
    for name, xy in _META_LAYOUT.items():
        node = ng.nodes.get(name)
        if node is not None:
            node.location = xy


def ensure_metadata_group():
    ng = bpy.data.node_groups.get(META_GROUP)
    if ng is not None and "Texel" in ng.interface.items_tree:
        return ng
    if ng is None:
        ng = bpy.data.node_groups.new(META_GROUP, "ShaderNodeTree")
    else:                    # a file from before texture metadata: same group, current nodes
        ng.nodes.clear()
        ng.interface.clear()
    ng.interface.new_socket("Color", in_out="INPUT", socket_type="NodeSocketColor")
    ng.interface.new_socket("Texel", in_out="INPUT", socket_type="NodeSocketFloat")
    ng.interface.new_socket("Color", in_out="OUTPUT", socket_type="NodeSocketColor")
    nodes, links = ng.nodes, ng.links
    gin, gout = nodes.new("NodeGroupInput"), nodes.new("NodeGroupOutput")
    attr = nodes.new("ShaderNodeAttribute")
    attr.name = "Column"
    attr.attribute_type = "GEOMETRY"
    # a tile has its column as an attribute or in a texture, the other one reads 0
    column = nodes.new("ShaderNodeMath")
    column.name = "Column Value"
    links.new(attr.outputs["Fac"], column.inputs[0])
    links.new(gin.outputs["Texel"], column.inputs[1])
    strength = _value_node(ng, "Strength", 1.0)
    numeric = _value_node(ng, "Is Number", 0.0)
    lo, hi = _value_node(ng, "Min", 0.0), _value_node(ng, "Max", 1.0)

    # classes: code -> centre of its palette pixel
    u = nodes.new("ShaderNodeMath")
    u.operation = "DIVIDE"
    u.inputs[1].default_value = float(_PALETTE_SIZE)
    shift = nodes.new("ShaderNodeMath")
    shift.inputs[1].default_value = 0.5
    links.new(column.outputs[0], shift.inputs[0])
    links.new(shift.outputs[0], u.inputs[0])
    uv = nodes.new("ShaderNodeCombineXYZ")
    uv.inputs[1].default_value = 0.5
    links.new(u.outputs[0], uv.inputs[0])
    tex = nodes.new("ShaderNodeTexImage")
    tex.name = "Palette"
    tex.image = _palette_image()
    tex.interpolation = "Closest"
    tex.extension = "EXTEND"
    links.new(uv.outputs[0], tex.inputs["Vector"])

    # numbers: min..max -> ramp, no data (0 below the range) stays uncolored
    span = nodes.new("ShaderNodeMapRange")
    links.new(column.outputs[0], span.inputs["Value"])
    links.new(lo.outputs[0], span.inputs["From Min"])
    links.new(hi.outputs[0], span.inputs["From Max"])
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.name = "Ramp"
    els = ramp.color_ramp.elements
    els[0].color = (0.05, 0.03, 0.4, 1.0)
    els[1].color = (0.98, 0.9, 0.15, 1.0)
    els.new(0.5).color = (0.1, 0.6, 0.5, 1.0)
    links.new(span.outputs[0], ramp.inputs["Fac"])
    above = nodes.new("ShaderNodeMath")
    above.operation = "GREATER_THAN"
    links.new(column.outputs[0], above.inputs[0])
    low = nodes.new("ShaderNodeMath")
    low.operation = "SUBTRACT"
    low.inputs[1].default_value = 1e-3
    links.new(lo.outputs[0], low.inputs[0])
    links.new(low.outputs[0], above.inputs[1])

    pick = nodes.new("ShaderNodeMix")
    pick.data_type = "RGBA"
    links.new(numeric.outputs[0], pick.inputs[0])
    links.new(tex.outputs["Color"], pick.inputs[6])
    links.new(ramp.outputs["Color"], pick.inputs[7])
    has = nodes.new("ShaderNodeMix")
    has.data_type = "FLOAT"
    links.new(numeric.outputs[0], has.inputs[0])
    links.new(tex.outputs["Alpha"], has.inputs[2])
    links.new(above.outputs[0], has.inputs[3])
    fac = nodes.new("ShaderNodeMath")
    fac.operation = "MULTIPLY"
    links.new(strength.outputs[0], fac.inputs[0])
    links.new(has.outputs[0], fac.inputs[1])
    out = nodes.new("ShaderNodeMix")
    out.data_type = "RGBA"
    links.new(fac.outputs[0], out.inputs[0])
    links.new(gin.outputs[0], out.inputs[6])
    links.new(pick.outputs[2], out.inputs[7])
    links.new(out.outputs[2], gout.inputs[0])
    _layout_metadata_group(ng)
    return ng


def update_metadata_group(scene):
    """Point the shared group at the active column."""
    props = scene.ogc3dtiles
    ng = ensure_metadata_group()
    col = REGISTRY.get(props.meta_column) if props.meta_column else None
    attr = attribute_name(props.meta_column) if props.meta_column else ""
    nodes = ng.nodes
    if nodes["Column"].attribute_name != attr:
        nodes["Column"].attribute_name = attr
    nodes["Strength"].outputs[0].default_value = props.meta_strength
    is_number = col is not None and col.kind == "number"
    nodes["Is Number"].outputs[0].default_value = 1.0 if is_number else 0.0
    if is_number and col.hi >= col.lo:
        lo, hi = (props.meta_range_min, props.meta_range_max) if props.meta_range_custom else (col.lo, col.hi)
        nodes["Min"].outputs[0].default_value = lo
        nodes["Max"].outputs[0].default_value = max(hi, lo + 1e-6)
    write_palette(scene)


def sync_metadata(scene, force=False):
    """Mirror what the workers found into the panel. Costs nothing until a new
    column, class or range shows up."""
    if not force and REGISTRY.version == _meta_seen[0]:
        return False
    _meta_seen[0] = REGISTRY.version
    props = scene.ogc3dtiles
    columns = REGISTRY.columns()
    known = {c.name for c in props.meta_columns}
    wanted = {c[0] for c in columns}
    if known != wanted:
        props.meta_columns.clear()
        for name, kind, *_rest in columns:
            item = props.meta_columns.add()
            item.name, item.kind = name, kind
    have = {(c.column, c.code) for c in props.meta_classes}
    for name, kind, *_rest in columns:
        if kind != "class":
            continue
        for text, code in REGISTRY.classes(name):
            if (name, code) not in have:
                item = props.meta_classes.add()
                item.name, item.column, item.code = text, name, code
                item["color"] = _class_color(code, name)
    if props.meta_column not in wanted and columns:
        props["meta_column"] = REGISTRY.best_column()
        from .io import refresh_feature_attributes
        refresh_feature_attributes(scene)
    update_metadata_group(scene)
    return True


def metadata_columns(props):
    """Columns the tiles keep as attributes."""
    if props.meta_all_columns:
        return [c.name for c in props.meta_columns]
    return [props.meta_column] if props.meta_column else []


VOXEL_VOLUME_MAT = "OGC3D Voxel Volume"


def voxel_volume_material(scene):
    """Shared by all voxel Volumes: the metadata group sets the color, from the
    meta_<column> grid, so the panel's column and palette apply as on meshes."""
    mat = bpy.data.materials.get(VOXEL_VOLUME_MAT)
    if mat is None:
        mat = bpy.data.materials.new(VOXEL_VOLUME_MAT)
        mat.use_nodes = True
        nt = mat.node_tree
        nt.nodes.clear()
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        vol = nt.nodes.new("ShaderNodeVolumePrincipled")
        vol.name = "Volume"
        vol.inputs["Density Attribute"].default_value = "density"
        # self-lit: thick parts reach the class color, scattering would wash it to white.
        # Emission is per metre, not scaled by density: the same density makes it level off
        vol.inputs["Color"].default_value = (0.0, 0.0, 0.0, 1.0)
        opacity = nt.nodes.new("ShaderNodeValue")
        opacity.name = "Opacity"
        nt.links.new(opacity.outputs[0], vol.inputs["Density"])
        amount = nt.nodes.new("ShaderNodeAttribute")
        amount.attribute_name = "density"
        emission = nt.nodes.new("ShaderNodeMath")
        emission.operation = "MULTIPLY"
        nt.links.new(amount.outputs["Fac"], emission.inputs[0])
        nt.links.new(opacity.outputs[0], emission.inputs[1])
        nt.links.new(emission.outputs[0], vol.inputs["Emission Strength"])
        colors = nt.nodes.new("ShaderNodeAttribute")
        colors.attribute_name = "color"
        group = nt.nodes.new("ShaderNodeGroup")
        group.node_tree = ensure_metadata_group()
        nt.links.new(colors.outputs["Color"], group.inputs[0])
        nt.links.new(group.outputs[0], vol.inputs["Emission Color"])
        nt.links.new(vol.outputs[0], out.inputs["Volume"])
    update_voxel_volume_material(scene)
    return mat


def update_voxel_volume_material(scene):
    mat = bpy.data.materials.get(VOXEL_VOLUME_MAT)
    if mat is not None:
        mat.node_tree.nodes["Opacity"].outputs[0].default_value = scene.ogc3dtiles.voxel_opacity


def _color_target(mat):
    """Input a tile's color ends in: the Relight group's, else the Principled's."""
    nt = mat.node_tree
    grp = next((n for n in nt.nodes if n.type == "GROUP" and n.node_tree
                and n.node_tree.name == GROUP_NAME), None)
    if grp is not None:
        return grp.inputs["Albedo"]
    bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED" and not n.mute), None)
    return bsdf.inputs["Base Color"] if bsdf is not None else None


def _emission_target(mat):
    """Input of an unlit point material's own color, which would show under the
    metadata colors."""
    bsdf = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED" and not n.mute), None)
    if bsdf is None or "Emission Color" not in bsdf.inputs:
        return None
    socket = bsdf.inputs["Emission Color"]
    return socket if socket.links else None


TEXEL_NODE = "OGC3D Metadata Texel"


def _insert_metadata_node(nt, name, target):
    node = nt.nodes.new("ShaderNodeGroup")
    node.node_tree = ensure_metadata_group()
    node.name = node.label = name
    texel = nt.nodes.get(TEXEL_NODE)
    if texel is not None:
        nt.links.new(texel.outputs["Color"], node.inputs["Texel"])
    node.location = (target.node.location.x - 220, target.node.location.y + 260)
    if target.links:
        nt.links.new(target.links[0].from_socket, node.inputs[0])
    else:
        node.inputs[0].default_value = target.default_value
    nt.links.new(node.outputs[0], target)


def apply_metadata(mat) -> bool:
    if mat is None or not mat.use_nodes or mat.node_tree is None:
        return False
    nt = mat.node_tree
    if nt.nodes.get(META_NODE) is not None:
        return False
    target = _color_target(mat)
    if target is None:
        return False
    _insert_metadata_node(nt, META_NODE, target)
    emission = _emission_target(mat)
    if emission is not None:
        _insert_metadata_node(nt, META_NODE + " Emission", emission)
    return True


def remove_metadata(mat) -> bool:
    if mat is None or not mat.use_nodes or mat.node_tree is None:
        return False
    nt = mat.node_tree
    removed = False
    for name in (META_NODE, META_NODE + " Emission"):
        node = nt.nodes.get(name)
        if node is None:
            continue
        source = node.inputs[0].links[0].from_socket if node.inputs[0].links else None
        targets = [l.to_socket for l in node.outputs[0].links]
        nt.nodes.remove(node)
        if source is not None:
            for t in targets:
                nt.links.new(source, t)
        removed = True
    return removed


def set_metadata_colors(scene) -> int:
    """Follow the panel's checkbox on the tiles already loaded."""
    enabled = scene.ogc3dtiles.meta_color
    if enabled:
        sync_metadata(scene, force=True)
        from .io import refresh_feature_attributes
        refresh_feature_attributes(scene)
    return sum(bool(apply_metadata(m) if enabled else remove_metadata(m)) for m in tile_materials())


class OGC3D_OT_RelightApply(Operator):
    """Swap every tile material's BSDF for the shared "OGC3D Relight" node group"""
    bl_idname = "ogc3dtiles.relight_apply"
    bl_label = "Apply Relight to Tiles"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        ensure_relight_group()                 # also upgrades a group from an older version
        n = sum(1 for m in tile_materials() if apply_relight(m))
        if not context.scene.ogc3dtiles.auto_relight:
            context.scene.ogc3dtiles.auto_relight = True
        self.report({"INFO"}, f"Relight applied to {n} materials")
        return {"FINISHED"}


class OGC3D_OT_RelightRemove(Operator):
    """Restore the plain Principled material on every tile"""
    bl_idname = "ogc3dtiles.relight_remove"
    bl_label = "Remove Relight"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        n = sum(1 for m in tile_materials() if remove_relight(m))
        if context.scene.ogc3dtiles.auto_relight:
            context.scene.ogc3dtiles.auto_relight = False
        self.report({"INFO"}, f"Relight removed from {n} materials")
        return {"FINISHED"}


def draw_panel(layout, props):
    """Body of the collapsible "Materials" sub-panel."""
    from . import node_rows
    relit = node_rows.draw(layout, props, "auto_relight", "Shared shader nodes", "RELIGHT")
    row = layout.row(align=True)
    row.prop(props, "clip_materials", text="Clip to viewport region (Alt+B)")
    layout.prop(props, "backface_mode", text="Faces")
    if props.clip_materials:
        from .camera import find_view3d
        r3d, _ = find_view3d()
        on = bool(r3d is not None and r3d.use_clip_planes)
        layout.label(text="Region active (Alt+B clears it)" if on
                     else "No region: drag one with Alt+B", icon="MOD_BOOLEAN" if on else "INFO")
    from .io import addon_pref
    ng = bpy.data.node_groups.get(GROUP_NAME)
    if ng is not None and relit and addon_pref("beta_material_controls", False):
        col = layout.column(align=True)
        for name, *_rest in TUNABLES:
            if name == "Gold Hue":
                col.separator()
                col.prop(props, "relight_gold", text="Gold transfer", toggle=True)
            if name.startswith("Gold") and not props.relight_gold:
                continue
            n = ng.nodes.get(name)
            if n is not None:
                col.prop(n.outputs[0], "default_value", text=name)


_MAX_LEGEND_ROWS = 32


def draw_metadata_panel(layout, props):
    """Body of the collapsible "Metadata" sub-panel."""
    layout.prop(props, "voxel_display")
    if props.voxel_display == "VOLUME":
        layout.prop(props, "voxel_opacity")
    if props.voxel_display == "PROJECT":
        layout.prop(props, "voxel_mix")
        layout.prop(props, "voxel_cut")
    else:
        layout.prop(props, "voxel_exaggeration")
    from .tileset.feature_meta import TILESET_METADATA
    if TILESET_METADATA.tileset:
        box = layout.column(align=True)
        box.label(text="Tileset", icon="INFO")
        for name, value in sorted(TILESET_METADATA.tileset.items()):
            box.label(text=f"{name}: {value}")
    layout.prop(props, "read_metadata")
    if not props.read_metadata:
        return
    if not props.meta_columns:
        layout.label(text="No metadata column loaded yet", icon="INFO")
        return
    from . import node_rows
    node_rows.draw(layout, props, "meta_color", "Color tiles by", "METADATA")
    layout.prop_search(props, "meta_column", props, "meta_columns", text="Column")
    layout.prop(props, "meta_strength")
    layout.prop(props, "meta_all_columns")
    col = REGISTRY.get(props.meta_column)
    if col is None:
        return
    if col.kind == "number":
        layout.label(text=f"{col.lo:g} to {col.hi:g}", icon="IPO_LINEAR")
        ng = bpy.data.node_groups.get(META_GROUP)
        ramp = ng.nodes.get("Ramp") if ng is not None else None
        if ramp is not None:        # the group's own Color Ramp: edits are kept
            layout.template_color_ramp(ramp, "color_ramp", expand=True)
        layout.prop(props, "meta_range_custom")
        if props.meta_range_custom:
            row = layout.row(align=True)
            row.prop(props, "meta_range_min")
            row.prop(props, "meta_range_max")
        return
    box = layout.column(align=True)
    rows = [c for c in props.meta_classes if c.column == props.meta_column]
    for item in rows[:_MAX_LEGEND_ROWS]:
        row = box.row(align=True)
        row.prop(item, "color", text="")
        row.label(text=item.name)
    if len(rows) > _MAX_LEGEND_ROWS:
        layout.label(text=f"+ {len(rows) - _MAX_LEGEND_ROWS} more classes")


_classes = [OGC3D_OT_RelightApply, OGC3D_OT_RelightRemove]


def _persistent(fn):
    """bpy.app.handlers.persistent, tolerant of the test stub without bpy.app."""
    app = getattr(bpy, "app", None)
    return app.handlers.persistent(fn) if app is not None else fn


@_persistent
def _upgrade_group_on_load(_dummy=None):
    """Files saved with an older "OGC3D Relight" group get the current nodes
    (materials keep pointing at the same group datablock)."""
    try:
        if bpy.data.node_groups.get(GROUP_NAME) is not None:
            ensure_relight_group()
        meta = bpy.data.node_groups.get(META_GROUP)
        if meta is not None:                 # files from when its nodes were all at 0, 0
            _layout_metadata_group(meta, only_if_stacked=True)
        # scene toggles that are on (by default or saved) must hold for the
        # tiles already in the file; property defaults fire no update
        for scene in bpy.data.scenes:
            props = getattr(scene, "ogc3dtiles", None)
            if props is None:
                continue
            if props.clip_materials:
                set_clip_materials(True)
            if props.meta_classes:
                write_palette(scene)     # a generated image's pixels need a refresh
            set_backface_mode(props.backface_mode)
            if props.tile_geometry:
                from .io import set_tile_geometry
                set_tile_geometry(True)
            from . import compositor         # files from before the checkbox
            if compositor.is_built(scene) and not props.comp_enabled:
                props.comp_enabled = True
            break
    except Exception as e:                        # noqa: BLE001
        print(f"[3DTiles] relight group upgrade failed: {e}")


def register():
    for c in _classes:
        bpy.utils.register_class(c)
    handlers = getattr(getattr(bpy, "app", None), "handlers", None)
    if handlers is not None and _upgrade_group_on_load not in handlers.load_post:
        handlers.load_post.append(_upgrade_group_on_load)


def unregister():
    handlers = getattr(getattr(bpy, "app", None), "handlers", None)
    if handlers is not None and _upgrade_group_on_load in handlers.load_post:
        handlers.load_post.remove(_upgrade_group_on_load)
    for c in reversed(_classes):
        bpy.utils.unregister_class(c)
