"""X-ray display of point clouds and Gaussian splats.

Every point adds a little light and hides nothing: an Add Shader of Transparent and Emission, blended. Where many
points line up along the view (a wall seen edge-on, a vault, the far side of a building) the light adds up, so the
structure reads through itself, as on a radiograph. Ordinary transparency does not do this: it fades everything
to an even fog.

It is a material effect: one shared shader group, "OGC3D X-ray", sits in front of the Material Output of every
point tile and mixes its usual shader with the X-ray one ("On", "Strength", "Tint", "Tint Amount" are its values).
Points keep the shape their geometry nodes give them (points, tetrahedra, discs).

Gaussian splats are the exception: Blender draws them with its own splat renderer, which ignores the material, so
while X-ray is on their Splats modifier is given the "OGC3D X-ray Points" geometry group, which turns them into
plain points of "Splat radius" carrying the "OGC3D X-ray" material. The look needs a dark background.
"""
from __future__ import annotations

import bpy

GROUP = "OGC3D X-ray"                   # shared shader group
POINTS_GROUP = "OGC3D X-ray Points"     # geometry group of splat tiles while X-ray is on
MATERIAL = "OGC3D X-ray"                # material of those points
NODE = "OGC3D X-ray"                    # the group node in a tile material
MARK = "ogc3d_xray"                     # on a splat tile object while it is shown as points
METHOD = "ogc3d_xray_method"            # a material's render method before X-ray


def group():
    """The shared shader group: Shader and Color in, the shader or its X-ray out."""
    ng = bpy.data.node_groups.get(GROUP)
    if ng is not None and ng.bl_idname == "ShaderNodeTree":
        return ng
    if ng is not None:                                  # the geometry group of a development build
        ng.name = GROUP + " (old)"
    ng = bpy.data.node_groups.new(GROUP, "ShaderNodeTree")
    iface = ng.interface
    iface.new_socket("Shader", in_out="INPUT", socket_type="NodeSocketShader")
    iface.new_socket("Color", in_out="INPUT", socket_type="NodeSocketColor").default_value = (1, 1, 1, 1)
    iface.new_socket("Shader", in_out="OUTPUT", socket_type="NodeSocketShader")
    N, L = ng.nodes.new, ng.links.new
    gin, gout = N("NodeGroupInput"), N("NodeGroupOutput")

    def value(name, v):
        n = N("ShaderNodeValue")
        n.name = n.label = name
        n.outputs[0].default_value = v
        return n
    on, strength, amount = value("On", 0.0), value("Strength", 0.3), value("Tint Amount", 0.0)
    tint = N("ShaderNodeRGB")
    tint.name = tint.label = "Tint"
    tint.outputs[0].default_value = (0.55, 0.8, 1.0, 1.0)
    mix = N("ShaderNodeMix")
    mix.data_type = "RGBA"
    glow, clear, add, pick = N("ShaderNodeEmission"), N("ShaderNodeBsdfTransparent"), N("ShaderNodeAddShader"), \
        N("ShaderNodeMixShader")
    L(amount.outputs[0], mix.inputs[0])
    L(gin.outputs["Color"], mix.inputs[6])
    L(tint.outputs[0], mix.inputs[7])
    L(mix.outputs[2], glow.inputs["Color"])
    L(strength.outputs[0], glow.inputs["Strength"])
    L(clear.outputs[0], add.inputs[0])
    L(glow.outputs[0], add.inputs[1])
    L(on.outputs[0], pick.inputs["Fac"])
    L(gin.outputs["Shader"], pick.inputs[1])
    L(add.outputs[0], pick.inputs[2])
    L(pick.outputs[0], gout.inputs["Shader"])
    try:
        from .node_layout import arrange
        arrange(ng)
    except Exception:                                   # noqa: BLE001
        pass
    return ng


def material():
    """Material of splat tiles shown as X-ray points: the group alone, on."""
    m = bpy.data.materials.get(MATERIAL)
    if m is not None:
        return m
    m = bpy.data.materials.new(MATERIAL)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    col = nt.nodes.new("ShaderNodeAttribute")
    col.attribute_name = "Col"
    g = nt.nodes.new("ShaderNodeGroup")
    g.node_tree = group()
    g.name = g.label = NODE
    nt.links.new(col.outputs["Color"], g.inputs["Color"])
    nt.links.new(g.outputs["Shader"], out.inputs["Surface"])
    col.location, g.location, out.location = (-400, 0), (-150, 0), (100, 0)
    _set_blended(m, True)
    m.use_backface_culling = False
    return m


def points_group():
    ng = bpy.data.node_groups.get(POINTS_GROUP)
    if ng is not None:
        return ng
    ng = bpy.data.node_groups.new(POINTS_GROUP, "GeometryNodeTree")
    ng.is_modifier = True
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    N, L = ng.nodes.new, ng.links.new
    gin, gout = N("NodeGroupInput"), N("NodeGroupOutput")
    pts = N("GeometryNodeMeshToPoints")
    radius = N("ShaderNodeValue")
    radius.name = radius.label = "Radius"
    radius.outputs[0].default_value = 0.05
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
    """On, strength, tint and splat radius, live: values of the shared groups."""
    ng = group()
    ng.nodes["On"].outputs[0].default_value = 1.0 if props.xray else 0.0
    ng.nodes["Strength"].outputs[0].default_value = float(props.xray_strength)
    ng.nodes["Tint"].outputs[0].default_value = (*props.xray_tint, 1.0)
    ng.nodes["Tint Amount"].outputs[0].default_value = float(props.xray_tint_amount)
    pg = bpy.data.node_groups.get(POINTS_GROUP)
    if pg is not None:
        pg.nodes["Radius"].outputs[0].default_value = float(props.xray_radius)


def _set_blended(mat, on: bool) -> None:
    """X-ray needs the blended render method (additive light, no depth write); the material gets its own back."""
    try:
        if on:
            if METHOD not in mat:
                mat[METHOD] = mat.surface_render_method
            mat.surface_render_method = "BLENDED"
        elif METHOD in mat:
            mat.surface_render_method = mat[METHOD]
            del mat[METHOD]
    except Exception:                                   # noqa: BLE001 — before Blender 4.2
        if on:
            if METHOD not in mat:
                mat[METHOD] = mat.blend_method
            mat.blend_method = "BLEND"
        elif METHOD in mat:
            mat.blend_method = mat[METHOD]
            del mat[METHOD]


def _colour_source(nt):
    """The socket that gives a point material its colour (the Col lookup), wherever it is linked now."""
    bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf is not None:
        for name in ("Base Color", "Emission Color"):
            if bsdf.inputs[name].links:
                return bsdf.inputs[name].links[0].from_socket
    col = next((n for n in nt.nodes if n.type == "ATTRIBUTE" and n.attribute_name == "Col"), None)
    return col.outputs["Color"] if col is not None else None


def insert(mat) -> bool:
    """Put the shared group in front of a point material's output (once), and set the render method."""
    if mat is None or not mat.use_nodes or mat.node_tree is None or mat.name == MATERIAL:
        return False
    from .materials import surface_target
    nt = mat.node_tree
    tgt = surface_target(nt)
    if tgt is None:
        return False
    node = nt.nodes.get(NODE)
    if node is None:
        node = nt.nodes.new("ShaderNodeGroup")
        node.node_tree = group()
        node.name = node.label = NODE
        node.location = (tgt.node.location.x - 220, tgt.node.location.y - 260)
        src = _colour_source(nt)
        if src is not None:
            nt.links.new(src, node.inputs["Color"])
    if not (tgt.links and tgt.links[0].from_node == node):
        if tgt.links and tgt.links[0].from_node != node:      # something was linked in front since: go after it
            nt.links.new(tgt.links[0].from_socket, node.inputs["Shader"])
        nt.links.new(node.outputs["Shader"], tgt)
    return True


def point_tile(o) -> bool:
    return (o.type == "MESH" and "tile_url" in o and o.modifiers.get("Points") is not None
            and not (o.get("splats") and o.modifiers.get("Splats") is not None))


def show(obj) -> bool:
    """A tile built while X-ray is on: point tiles through their material, splat tiles as points."""
    if obj.type != "MESH" or "tile_url" not in obj:
        return False
    mod = obj.modifiers.get("Splats")
    if mod is not None and mod.type == "NODES":
        mod.node_group = points_group()
        obj[MARK] = True
        return True
    if obj.modifiers.get("Points") is None:
        return False
    for m in obj.data.materials:
        if insert(m):
            _set_blended(m, True)
    return True


def apply(scene) -> int:
    """Turn the mode on or off for every point and splat tile of the scene."""
    props = scene.ogc3dtiles
    update_params(props)
    n = 0
    if props.xray:
        for o in bpy.data.objects:
            n += bool(show(o))
        return n
    from . import io
    seen = set()
    for o in bpy.data.objects:
        if o.type != "MESH":
            continue
        if o.get(MARK):
            del o[MARK]
            mod = o.modifiers.get("Splats")
            if mod is not None:
                mod.node_group = io._splats_nodegroup()
                o.update_tag()
            n += 1
        for m in (o.data.materials if o.modifiers.get("Points") is not None else ()):
            if m is not None and m.name not in seen:
                seen.add(m.name)
                _set_blended(m, False)
                n += 1
    return n
