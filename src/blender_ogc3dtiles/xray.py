"""X-ray display of point clouds and Gaussian splats.

Every point adds a little light and hides nothing: Transparent + Emission through an Add Shader, on points
made from the tile's vertices. Where many points line up along the view (a wall seen edge-on, a vault, the
far side of a building) the light adds up, so the structure reads through itself, as on a radiograph.
Ordinary transparency does not do this: it fades everything to an even fog.

On: the tile's Points or Splats modifier is given the "OGC3D X-ray" node group. Off: it gets its own group
back. The look needs a dark background, and Eevee (Cycles shows it too, more slowly).
"""
from __future__ import annotations

import bpy

GROUP = "OGC3D X-ray"
MATERIAL = "OGC3D X-ray"
MARK = "ogc3d_xray"                     # on a tile object while it is shown as X-ray
MODIFIERS = ("Points", "Splats")


def material():
    m = bpy.data.materials.get(MATERIAL)
    if m is not None:
        return m
    m = bpy.data.materials.new(MATERIAL)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    N, L = nt.nodes.new, nt.links.new
    out = N("ShaderNodeOutputMaterial")
    add = N("ShaderNodeAddShader")
    clear = N("ShaderNodeBsdfTransparent")
    glow = N("ShaderNodeEmission")
    col = N("ShaderNodeAttribute")
    col.attribute_name = "Col"
    tint = N("ShaderNodeRGB")
    tint.name = tint.label = "Tint"
    mix = N("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.name = mix.label = "Tint Amount"
    strength = N("ShaderNodeValue")
    strength.name = strength.label = "Strength"
    L(col.outputs["Color"], mix.inputs[6])
    L(tint.outputs[0], mix.inputs[7])
    L(mix.outputs[2], glow.inputs["Color"])
    L(strength.outputs[0], glow.inputs["Strength"])
    L(clear.outputs[0], add.inputs[0])
    L(glow.outputs[0], add.inputs[1])
    L(add.outputs[0], out.inputs["Surface"])
    for i, n in enumerate((col, tint, mix, strength, clear, glow, add, out)):
        n.location = (220 * min(i, 4) + 220 * max(0, i - 4), -160 * (i % 4))
    try:
        m.surface_render_method = "BLENDED"
    except Exception:                               # noqa: BLE001 — before Blender 4.2
        m.blend_method = "BLEND"
    m.use_backface_culling = False
    return m


def group():
    ng = bpy.data.node_groups.get(GROUP)
    if ng is not None:
        return ng
    ng = bpy.data.node_groups.new(GROUP, "GeometryNodeTree")
    ng.is_modifier = True
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    N, L = ng.nodes.new, ng.links.new
    gin, gout = N("NodeGroupInput"), N("NodeGroupOutput")
    pts = N("GeometryNodeMeshToPoints")
    radius = N("ShaderNodeValue")
    radius.name = radius.label = "Radius"
    mat = N("GeometryNodeSetMaterial")
    mat.inputs["Material"].default_value = material()
    L(gin.outputs[0], pts.inputs["Mesh"])
    L(radius.outputs[0], pts.inputs["Radius"])
    L(pts.outputs[0], mat.inputs[0])
    L(mat.outputs[0], gout.inputs[0])
    for i, n in enumerate((gin, radius, pts, mat, gout)):
        n.location = (200 * i, 0)
    return ng


def update_params(props) -> None:
    """Strength, tint and point size, live."""
    m, ng = material(), group()
    nt = m.node_tree
    nt.nodes["Strength"].outputs[0].default_value = float(props.xray_strength)
    nt.nodes["Tint"].outputs[0].default_value = (*props.xray_tint, 1.0)
    nt.nodes["Tint Amount"].inputs[0].default_value = float(props.xray_tint_amount)
    ng.nodes["Radius"].outputs[0].default_value = float(props.xray_radius)


def _modifier(obj):
    if obj.type != "MESH" or "tile_url" not in obj:
        return None
    return next((obj.modifiers[n] for n in MODIFIERS if n in obj.modifiers), None)


def show(obj) -> bool:
    """Give one tile the X-ray group (a tile built while the mode is on)."""
    mod = _modifier(obj)
    if mod is None or mod.type != "NODES":
        return False
    mod.node_group = group()
    obj[MARK] = True
    return True


def apply(scene) -> int:
    """Turn the mode on or off for every point and splat tile of the scene."""
    props = scene.ogc3dtiles
    n = 0
    if props.xray:
        update_params(props)
        for o in bpy.data.objects:
            n += bool(show(o))
        return n
    from . import io
    for o in bpy.data.objects:
        if not o.get(MARK):
            continue
        del o[MARK]
        mod = _modifier(o)
        if mod is None:
            continue
        if mod.name == "Splats":
            mod.node_group = io._splats_nodegroup()
        else:
            mod.node_group = None                   # apply_point_display gives it its group and inputs again
        o.update_tag()
        n += 1
    io.apply_point_display(props.point_display)
    return n
