"""Demo graphs for the shared 'OGC3D Tile Geometry' group, and an atmosphere preset.

Each demo replaces the nodes of the shared group, so it applies to every tile,
loaded or streamed later. They are starting points to edit, not finished
effects: the Value nodes at the left carry the settings.
"""
from __future__ import annotations

import math

import bpy
from bpy.types import Operator

SUZANNE = "OGC3D Suzanne"
SUN = "OGC3D Sun"


def _suzanne():
    obj = bpy.data.objects.get(SUZANNE)
    if obj is not None:
        return obj
    import bmesh
    bm = bmesh.new()
    bmesh.ops.create_monkey(bm)
    me = bpy.data.meshes.new(SUZANNE)
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(SUZANNE, me)      # in no collection: only instanced by the nodes
    obj.use_fake_user = True
    return obj


def _value(ng, name, default):
    n = ng.nodes.new("ShaderNodeValue")
    n.name = n.label = name
    n.outputs[0].default_value = default
    return n


def _math(ng, operation, a=None, b=None):
    n = ng.nodes.new("ShaderNodeMath")
    n.operation = operation
    for socket, source in zip(n.inputs, (a, b)):
        if source is None:
            continue
        if isinstance(source, (int, float)):
            socket.default_value = source
        else:
            ng.links.new(source, socket)
    return n.outputs[0]


def _shown(sockets):
    """The socket in use: Random Value has one per data type, or a single one."""
    return next(s for s in sockets if s.enabled)


def _world_position(ng):
    """Position in the scene rather than in the tile: each tile has its own origin."""
    position = ng.nodes.new("GeometryNodeInputPosition").outputs[0]
    try:
        me = ng.nodes.new("GeometryNodeSelfObject")
        info = ng.nodes.new("GeometryNodeObjectInfo")
        to_world = ng.nodes.new("FunctionNodeTransformPoint")
        ng.links.new(me.outputs[0], info.inputs[0])
        ng.links.new(info.outputs["Transform"], to_world.inputs["Transform"])
        ng.links.new(position, to_world.inputs["Vector"])
        return to_world.outputs[0]
    except (RuntimeError, KeyError):              # before the matrix nodes: tile space
        return position


def _suzanne_on_points(ng, gin, gout):
    share = _value(ng, "Share Of Points", 0.0005)
    size = _value(ng, "Size", 5.0)
    points = ng.nodes.new("GeometryNodeMeshToPoints")
    pick = ng.nodes.new("FunctionNodeRandomValue")
    pick.data_type = "BOOLEAN"
    info = ng.nodes.new("GeometryNodeObjectInfo")
    info.inputs[0].default_value = _suzanne()
    spin = ng.nodes.new("FunctionNodeRandomValue")
    spin.data_type = "FLOAT_VECTOR"
    next(i for i in spin.inputs if i.enabled and i.name == "Max").default_value = (0.0, 0.0, math.tau)
    instance = ng.nodes.new("GeometryNodeInstanceOnPoints")
    join = ng.nodes.new("GeometryNodeJoinGeometry")
    links = ng.links
    links.new(gin.outputs[0], points.inputs["Mesh"])
    links.new(share.outputs[0], pick.inputs["Probability"])
    links.new(_shown(pick.outputs), points.inputs["Selection"])
    links.new(points.outputs[0], instance.inputs["Points"])
    links.new(info.outputs["Geometry"], instance.inputs["Instance"])
    links.new(_shown(spin.outputs), instance.inputs["Rotation"])
    links.new(size.outputs[0], instance.inputs["Scale"])
    links.new(instance.outputs[0], join.inputs[0])
    links.new(gin.outputs[0], join.inputs[0])
    links.new(join.outputs[0], gout.inputs[0])


def _noise_displacement(ng, gin, gout):
    amplitude = _value(ng, "Amplitude", 6.0)
    scale = _value(ng, "Noise Scale", 0.05)
    speed = _value(ng, "Speed", 0.5)
    time = ng.nodes.new("GeometryNodeInputSceneTime")
    noise = ng.nodes.new("ShaderNodeTexNoise")
    noise.noise_dimensions = "4D"
    normal = ng.nodes.new("GeometryNodeInputNormal")
    push = ng.nodes.new("ShaderNodeVectorMath")
    push.operation = "SCALE"
    move = ng.nodes.new("GeometryNodeSetPosition")
    links = ng.links
    links.new(_world_position(ng), noise.inputs["Vector"])
    links.new(scale.outputs[0], noise.inputs["Scale"])
    links.new(_math(ng, "MULTIPLY", time.outputs["Seconds"], speed.outputs[0]), noise.inputs["W"])
    centred = _math(ng, "SUBTRACT", noise.outputs[0], 0.5)
    links.new(normal.outputs[0], push.inputs[0])
    links.new(_math(ng, "MULTIPLY", centred, amplitude.outputs[0]), push.inputs["Scale"])
    links.new(gin.outputs[0], move.inputs["Geometry"])
    links.new(push.outputs[0], move.inputs["Offset"])
    links.new(move.outputs[0], gout.inputs[0])


def _height_reveal(ng, gin, gout):
    base = _value(ng, "Lowest Height", -20.0)
    span = _value(ng, "Height Range", 150.0)
    speed = _value(ng, "Speed", 15.0)                     # metres per second
    time = ng.nodes.new("GeometryNodeInputSceneTime")
    split = ng.nodes.new("ShaderNodeSeparateXYZ")
    cut = ng.nodes.new("GeometryNodeDeleteGeometry")
    links = ng.links
    links.new(_world_position(ng), split.inputs[0])
    risen = _math(ng, "MODULO", _math(ng, "MULTIPLY", time.outputs["Seconds"], speed.outputs[0]),
                  span.outputs[0])
    level = _math(ng, "ADD", risen, base.outputs[0])
    links.new(_math(ng, "GREATER_THAN", split.outputs["Z"], level), cut.inputs["Selection"])
    links.new(gin.outputs[0], cut.inputs["Geometry"])
    links.new(cut.outputs[0], gout.inputs[0])


DEMOS = {
    "SUZANNE": ("Suzanne on points", "A monkey head on a share of the vertices, or of the points "
                                     "of a point cloud", _suzanne_on_points),
    "NOISE": ("Noise displacement", "Vertices move along their normal with a noise that drifts "
                                    "over time: press Play", _noise_displacement),
    "REVEAL": ("Height reveal", "The scene builds up from the ground, over and over: press Play",
               _height_reveal),
}


def apply_demo(key: str):
    from .io import ensure_tile_geometry_group
    from .node_layout import arrange
    ng = ensure_tile_geometry_group()
    ng.nodes.clear()
    gin, gout = ng.nodes.new("NodeGroupInput"), ng.nodes.new("NodeGroupOutput")
    DEMOS[key][2](ng, gin, gout)
    arrange(ng)
    return ng


class OGC3D_OT_GeometryDemo(Operator):
    """Replace the shared geometry nodes with a demo graph, on every tile"""
    bl_idname = "ogc3dtiles.geometry_demo"
    bl_label = "Demo Geometry Nodes"
    bl_options = {"REGISTER", "UNDO"}

    demo: bpy.props.EnumProperty(
        name="Demo", items=[(key, label, text) for key, (label, text, _fn) in DEMOS.items()])

    def execute(self, context):
        props = context.scene.ogc3dtiles
        apply_demo(self.demo)
        if not props.tile_geometry:
            props.tile_geometry = True
        self.report({"INFO"}, f"Shared geometry nodes: {DEMOS[self.demo][0]}. "
                              "'Reset to default' in the arrow menu takes it off")
        return {"FINISHED"}


def atmosphere(scene, elevation_deg=35.0, azimuth_deg=140.0) -> None:
    """A sun, a sky that agrees with it, and haze: outdoor light for tiles."""
    sun = bpy.data.objects.get(SUN)
    if sun is None:
        sun = bpy.data.objects.new(SUN, bpy.data.lights.new(SUN, "SUN"))
        scene.collection.objects.link(sun)
    sun.data.energy = 4.0
    sun.data.angle = math.radians(0.6)
    elevation, azimuth = math.radians(elevation_deg), math.radians(azimuth_deg)
    sun.rotation_euler = (math.pi / 2 - elevation, 0.0, math.pi - azimuth)
    sun.location = (0.0, 0.0, 300.0)

    world = scene.world or bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    sky = nt.nodes.new("ShaderNodeTexSky")
    for name, value in (("sun_elevation", elevation), ("sun_rotation", azimuth), ("sun_disc", False)):
        if hasattr(sky, name):                   # the lamp is the sun: no second disc in the sky
            setattr(sky, name, value)
    background = nt.nodes.new("ShaderNodeBackground")
    background.inputs["Strength"].default_value = 0.25
    out = nt.nodes.new("ShaderNodeOutputWorld")
    sky.location, background.location, out.location = (-300, 0), (0, 0), (250, 0)
    nt.links.new(sky.outputs[0], background.inputs["Color"])
    nt.links.new(background.outputs[0], out.inputs["Surface"])
    world["ogc3d_lit"] = True

    props = scene.ogc3dtiles
    if not props.comp_enabled:
        props.comp_enabled = True
    props.comp_haze = 0.5


class OGC3D_OT_Atmosphere(Operator):
    """Outdoor light in one click: a sun lamp, a sky world that agrees with it, and haze
    from the beauty compositor. With Shared shader nodes on, lower Baked Light to let
    the sun shade the tiles"""
    bl_idname = "ogc3dtiles.atmosphere"
    bl_label = "Atmosphere Preset"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        atmosphere(context.scene)
        self.report({"INFO"}, f"'{SUN}' lamp, sky world and haze set: see them in Rendered shading")
        return {"FINISHED"}


_classes = [OGC3D_OT_GeometryDemo, OGC3D_OT_Atmosphere]


def register():
    for c in _classes:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(_classes):
        bpy.utils.unregister_class(c)
