"""X-ray display of point clouds, Gaussian splats and, as an option, meshes.

Every point adds a little light and hides nothing: an Add Shader of Transparent and Emission, blended. Where many
points line up along the view (a wall seen edge-on, a vault, the far side of a building) the light adds up, so the
structure reads through itself, as on a radiograph. Ordinary transparency does not do this: it fades everything
to an even fog.

It is a material effect: one shared shader group, "OGC3D X-ray", sits in front of the Material Output of every
point tile and mixes its usual shader with the X-ray one ("On", "Strength", "Tint", "Tint Amount" are its values).
Points keep the shape their geometry nodes give them (points, tetrahedra, discs).

Meshes ("Meshes" on): the same group on mesh tile materials, its "Mesh" input at 1. Every face adds its texture
colour as light, front and back faces alike, so rooms and corridors show through the walls. "Mesh Edge" weights
the light by how much a face is seen edge-on (0: every face the same; higher: outlines and walls stand out, floors
and facades seen straight on fade), "Mesh Strength" is the light of a face seen edge-on.

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


VERSION_NODE = "Mesh Edge"
MESH_GAIN = 5.0                 # one Strength for all: a face seen edge-on adds this many times a point's light              # presence marks an up-to-date group


def group():
    """The shared shader group: Shader, Color and Mesh (0 a point material, 1 a mesh one) in, the shader or its
    X-ray out. A group of an older version is rebuilt in place: materials keep their links and the values stay."""
    ng = bpy.data.node_groups.get(GROUP)
    if ng is not None and ng.bl_idname != "ShaderNodeTree":     # the geometry group of a development build
        ng.name = GROUP + " (old)"
        ng = None
    kept = {}
    if ng is not None:
        if ng.nodes.get(VERSION_NODE) is not None:
            return ng
        kept = {n.name: tuple(n.outputs[0].default_value) if n.bl_idname == "ShaderNodeRGB"
                else n.outputs[0].default_value
                for n in ng.nodes if n.bl_idname in ("ShaderNodeValue", "ShaderNodeRGB")}
        for n in list(ng.nodes):
            ng.nodes.remove(n)
    else:
        ng = bpy.data.node_groups.new(GROUP, "ShaderNodeTree")
    _build(ng)
    for name, v in kept.items():
        n = ng.nodes.get(name)
        if n is not None:
            n.outputs[0].default_value = v
    return ng


def _build(ng) -> None:
    iface = ng.interface
    have = {it.name for it in iface.items_tree if getattr(it, "item_type", "") == "SOCKET"}
    if "Shader" not in have:
        iface.new_socket("Shader", in_out="INPUT", socket_type="NodeSocketShader")
        iface.new_socket("Shader", in_out="OUTPUT", socket_type="NodeSocketShader")
    if "Color" not in have:
        iface.new_socket("Color", in_out="INPUT", socket_type="NodeSocketColor").default_value = (1, 1, 1, 1)
    if "Mesh" not in have:
        sock = iface.new_socket("Mesh", in_out="INPUT", socket_type="NodeSocketFloat")
        sock.default_value, sock.min_value, sock.max_value = 0.0, 0.0, 1.0
    N, L = ng.nodes.new, ng.links.new
    gin, gout = N("NodeGroupInput"), N("NodeGroupOutput")

    def value(name, v):
        n = N("ShaderNodeValue")
        n.name = n.label = name
        n.outputs[0].default_value = v
        return n

    def feed(sockets, values):
        for sock, v in zip(sockets, values):
            if isinstance(v, (int, float)):
                sock.default_value = v
            else:
                L(v, sock)

    def math(op, a, b, clamp=False):
        n = N("ShaderNodeMath")
        n.operation = op
        n.use_clamp = clamp
        feed(n.inputs, (a, b))
        return n.outputs[0]

    def pick_float(fac, a, b):                          # a where fac is 0, b where it is 1
        n = N("ShaderNodeMix")
        n.data_type = "FLOAT"
        feed((n.inputs[0], n.inputs[2], n.inputs[3]), (fac, a, b))
        return n.outputs[0]

    on, strength, amount = value("On", 0.0), value("Strength", 0.3), value("Tint Amount", 0.0)
    meshes, mesh_strength, mesh_edge = value("Meshes", 0.0), value("Mesh Strength", 0.5), value(VERSION_NODE, 1.0)
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
    # the light of a face: Mesh Strength x (how much it is seen edge-on) ^ Mesh Edge; of a point: Strength
    facing = N("ShaderNodeLayerWeight")
    facing.inputs["Blend"].default_value = 0.5
    edge = math("POWER", math("MAXIMUM", facing.outputs["Facing"], 0.0001), mesh_edge.outputs[0], clamp=True)
    face_light = math("MULTIPLY", mesh_strength.outputs[0], edge)
    L(pick_float(gin.outputs["Mesh"], strength.outputs[0], face_light), glow.inputs["Strength"])
    L(clear.outputs[0], add.inputs[0])
    L(glow.outputs[0], add.inputs[1])
    # on: On for a point material, On x Meshes for a mesh one
    L(math("MULTIPLY", on.outputs[0], pick_float(gin.outputs["Mesh"], 1.0, meshes.outputs[0])), pick.inputs["Fac"])
    L(gin.outputs["Shader"], pick.inputs[1])
    L(add.outputs[0], pick.inputs[2])
    L(pick.outputs[0], gout.inputs["Shader"])
    try:
        from .node_layout import arrange
        arrange(ng)
    except Exception:                                   # noqa: BLE001
        pass


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
    """On, strength, tint, the mesh values and splat radius, live: values of the shared groups."""
    ng = group()
    for name, v in (("On", 1.0 if props.xray else 0.0), ("Strength", props.xray_strength),
                    ("Tint Amount", props.xray_tint_amount), ("Meshes", 1.0 if props.xray_meshes else 0.0),
                    ("Mesh Strength", props.xray_strength * MESH_GAIN), (VERSION_NODE, props.xray_mesh_edge)):
        ng.nodes[name].outputs[0].default_value = float(v)
    ng.nodes["Tint"].outputs[0].default_value = (*props.xray_tint, 1.0)
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
    """The socket that gives a material its colour, wherever it is linked now: what feeds the shared shader
    nodes' Albedo, else the Principled surface or light colour (the Col lookup of points, the texture of a mesh)."""
    from .materials import GROUP_NAME
    relit = next((n for n in nt.nodes if n.type == "GROUP" and n.node_tree is not None
                  and n.node_tree.name == GROUP_NAME), None)
    if relit is not None and relit.inputs["Albedo"].links:
        return relit.inputs["Albedo"].links[0].from_socket
    bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED" and not n.mute), None) \
        or next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf is not None:
        for name in ("Base Color", "Emission Color"):
            if bsdf.inputs[name].links:
                return bsdf.inputs[name].links[0].from_socket
    tex = next((n for n in nt.nodes if n.type == "TEX_IMAGE" and n.image is not None), None)
    if tex is not None:
        return tex.outputs["Color"]
    col = next((n for n in nt.nodes if n.type == "ATTRIBUTE" and n.attribute_name == "Col"), None)
    return col.outputs["Color"] if col is not None else None


def _plain_colour(mat):
    """Colour of a material without a texture: the Principled base colour (its light colour under Shadeless)."""
    bsdf = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf is None:
        return (0.8, 0.8, 0.8, 1.0)
    name = "Emission Color" if mat.get("ogc3d_shadeless") and "Emission Color" in bsdf.inputs else "Base Color"
    return tuple(bsdf.inputs[name].default_value)


def insert(mat, mesh: bool = False) -> bool:
    """Put the shared group in front of a tile material's output (once)."""
    if mat is None or not mat.use_nodes or mat.node_tree is None or mat.name == MATERIAL:
        return False
    from .materials import surface_target
    nt = mat.node_tree
    tgt = surface_target(nt, behind_xray=False)
    if tgt is None:
        return False
    ng = group()                                        # first: a group of an older version gets its Mesh input
    node = nt.nodes.get(NODE)
    if node is None:
        node = nt.nodes.new("ShaderNodeGroup")
        node.node_tree = ng
        node.name = node.label = NODE
        node.location = (tgt.node.location.x - 220, tgt.node.location.y - 260)
        src = _colour_source(nt)
        if src is not None:
            nt.links.new(src, node.inputs["Color"])
        elif mesh:
            node.inputs["Color"].default_value = _plain_colour(mat)
    node.inputs["Mesh"].default_value = 1.0 if mesh else 0.0
    if not (tgt.links and tgt.links[0].from_node == node):
        if tgt.links and tgt.links[0].from_node != node:      # something was linked in front since: go after it
            nt.links.new(tgt.links[0].from_socket, node.inputs["Shader"])
        nt.links.new(node.outputs["Shader"], tgt)
    return True


def point_tile(o) -> bool:
    return (o.type == "MESH" and "tile_url" in o and o.modifiers.get("Points") is not None
            and not (o.get("splats") and o.modifiers.get("Splats") is not None))


def mesh_tile(o) -> bool:
    """A tile drawn as a surface: neither points nor splats (the meshes of a glTF tile hang under its holder)."""
    if o.type != "MESH" or o.data is None or o.modifiers.get("Points") is not None \
            or o.modifiers.get("Splats") is not None:
        return False
    from .materials import _is_tile_object
    return _is_tile_object(o)


def _set_mesh(mat, on: bool, backface_mode: str = "DOUBLE") -> bool:
    """A mesh material in or out of X-ray: blended, and no face culled while it is on (the far walls and the
    inside of a room are back faces)."""
    if mat is None or mat.name == MATERIAL:
        return False
    from .materials import BACKFACE_ORIGINAL, apply_backface
    if on:
        if not insert(mat, mesh=True):
            return False
        _set_blended(mat, True)
        if BACKFACE_ORIGINAL not in mat:
            mat[BACKFACE_ORIGINAL] = int(mat.use_backface_culling)
        mat.use_backface_culling = False
        return True
    if METHOD not in mat:
        return False
    _set_blended(mat, False)
    apply_backface(mat, backface_mode)
    return True


def show(obj, meshes: bool = False) -> bool:
    """A tile built while X-ray is on: point tiles through their material, splat tiles as points, and mesh
    tiles through their material when ``meshes``."""
    if obj.type != "MESH":
        return False
    mod = obj.modifiers.get("Splats")
    if mod is not None and mod.type == "NODES" and "tile_url" in obj:
        mod.node_group = points_group()
        obj[MARK] = True
        return True
    if obj.modifiers.get("Points") is None:
        if not (meshes and mesh_tile(obj)):
            return False
        return any([_set_mesh(m, True) for m in obj.data.materials])
    if "tile_url" not in obj:
        return False
    for m in obj.data.materials:
        if insert(m):
            _set_blended(m, True)
    return True


def new_tiles(scene, objs) -> None:
    """Tiles that were just built: call last, so the group goes in front of whatever the other hooks put
    before the output."""
    props = scene.ogc3dtiles
    if not getattr(props, "xray", False):
        return
    for o in objs:
        if o is not None:
            show(o, bool(getattr(props, "xray_meshes", False)))


def apply(scene) -> int:
    """Turn the mode on or off for every point and splat tile of the scene, and for the mesh tiles when Meshes
    is on."""
    props = scene.ogc3dtiles
    update_params(props)
    n = 0
    meshes = bool(props.xray and props.xray_meshes)
    if not meshes:                                      # mesh materials that were in X-ray go back
        seen = set()
        for o in bpy.data.objects:
            if mesh_tile(o):
                for m in o.data.materials:
                    if m is not None and m.name not in seen:
                        seen.add(m.name)
                        n += bool(_set_mesh(m, False, props.backface_mode))
    if props.xray:
        for o in bpy.data.objects:
            n += bool(show(o, meshes))
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
