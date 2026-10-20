"""
compositor.py — screen-space "beauty" pass for streamed tiles, built from
render passes in the compositor (no AI): edge darkening (eye-dome lighting
from depth, and/or Sobel creases from normals), ambient occlusion, mist haze,
a colour grade and a soft glare.

``build_beauty_tree(scene, edges)`` creates the node group and enables it;
the sidebar operator also switches every 3D viewport's compositor to
"Always" so Rendered shading shows it live.  ``scripts/compositor_demo.py``
reuses this module for headless renders.
"""
from __future__ import annotations

import bpy
from bpy.types import Operator

TREE_NAME = "OGC3D Beauty"


def _passes(scene):
    vl = bpy.context.view_layer if bpy.context.view_layer else scene.view_layers[0]
    vl.use_pass_normal = True
    vl.use_pass_z = True
    vl.use_pass_mist = True
    vl.use_pass_diffuse_color = True
    vl.use_pass_ambient_occlusion = True
    if hasattr(scene.eevee, "use_gtao"):
        scene.eevee.use_gtao = True
    if scene.world is not None:
        # mist range from the extent of the visible tiles (haze that only
        # starts to bite in the far third of the scene)
        size = _tiles_extent(scene)
        ms = scene.world.mist_settings
        if size > 0:
            ms.start, ms.depth = size * 0.3, size * 1.5
        elif ms.depth <= 25.0:
            ms.start, ms.depth = 50.0, 600.0


def _tiles_extent(scene) -> float:
    from mathutils import Vector
    coll = bpy.data.collections.get("3D Tiles")
    if coll is None:
        return 0.0
    lo = Vector((1e30, 1e30, 1e30))
    hi = -lo
    n = 0
    for o in coll.all_objects:
        if o.type != "MESH" or o.hide_viewport:
            continue
        for c in o.bound_box:
            p = o.matrix_world @ Vector(c)
            lo = Vector((min(lo.x, p.x), min(lo.y, p.y), min(lo.z, p.z)))
            hi = Vector((max(hi.x, p.x), max(hi.y, p.y), max(hi.z, p.z)))
        n += 1
    return (hi - lo).length if n else 0.0


def build_beauty_tree(scene, edges: str = "EDL", edl_radius_px: int = 3,
                      edl_strength: float = 6.0, haze: float = 0.35):
    """Create (or replace) the 'OGC3D Beauty' compositor tree on ``scene``.
    Blender 5.x: node group on scene.compositing_node_group with a Group
    Output; 4.x: scene.node_tree with a Composite node."""
    _passes(scene)
    if hasattr(scene, "compositing_node_group"):
        old = bpy.data.node_groups.get(TREE_NAME)
        if old is not None:
            bpy.data.node_groups.remove(old)
        nt = bpy.data.node_groups.new(TREE_NAME, "CompositorNodeTree")
        scene.compositing_node_group = nt
        out = nt.nodes.new("NodeGroupOutput")
        out.is_active_output = True
        nt.interface.new_socket(name="Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    else:
        scene.use_nodes = True
        nt = scene.node_tree
        for n in list(nt.nodes):
            nt.nodes.remove(n)
        out = nt.nodes.new("CompositorNodeComposite")
    out.location = (1100, 0)
    rl = nt.nodes.new("CompositorNodeRLayers")
    rl.location = (-900, 0)
    rl.scene = scene

    def N(t, x, y, **kw):
        n = nt.nodes.new(t)
        n.location = (x, y)
        for k, v in kw.items():
            setattr(n, k, v)
        return n

    def set_in(n, name, value):
        """Blender 5.x moved most node options into (menu) input sockets."""
        if name in n.inputs:
            n.inputs[name].default_value = value
        elif hasattr(n, name.lower().replace(" ", "_")):
            setattr(n, name.lower().replace(" ", "_"), value)

    def mix_rgb(x, y, blend, fac):
        m = N("ShaderNodeMix", x, y, data_type="RGBA", blend_type=blend)
        m.inputs["Factor"].default_value = fac
        return m

    def mathn(x, y, op):
        return N("ShaderNodeMath", x, y, operation=op)

    link = nt.links.new

    def normal_edges():
        edge = N("CompositorNodeFilter", -600, -300)
        set_in(edge, "Type", "Sobel")
        link(rl.outputs["Normal" if "Normal" in rl.outputs else "Image"], edge.inputs["Image"])
        bw = N("CompositorNodeRGBToBW", -400, -300)
        link(edge.outputs["Image"], bw.inputs["Image"])
        inv = mathn(-200, -300, "SUBTRACT")
        inv.inputs[0].default_value = 1.0
        link(bw.outputs["Val"], inv.inputs[1])
        gain = mathn(0, -300, "POWER")
        gain.inputs[1].default_value = 0.6
        link(inv.outputs[0], gain.inputs[0])
        return gain.outputs[0]

    def edl_edges():
        """Eye-dome lighting: a pixel further away than its neighbourhood
        (log depth − blurred log depth) gets darkened; silhouettes and
        concavities darken, flat tile borders do not."""
        zname = "Depth" if "Depth" in rl.outputs else "Z"
        logz = mathn(-700, -600, "LOGARITHM")
        logz.inputs[1].default_value = 2.718281828
        link(rl.outputs[zname], logz.inputs[0])
        blur = N("CompositorNodeBlur", -500, -600)
        set_in(blur, "Type", "Gaussian")
        if "Size" in blur.inputs:                       # 5.x: one 2D vector socket
            try:
                blur.inputs["Size"].default_value = (edl_radius_px, edl_radius_px)
            except TypeError:
                blur.inputs["Size"].default_value = float(edl_radius_px)
        if hasattr(blur, "size_x"):                     # 4.x
            blur.size_x = blur.size_y = edl_radius_px
        link(logz.outputs[0], blur.inputs["Image"])
        diff = mathn(-300, -600, "SUBTRACT")
        link(logz.outputs[0], diff.inputs[0])
        link(blur.outputs["Image"], diff.inputs[1])
        pos = mathn(-100, -600, "MAXIMUM")
        pos.inputs[1].default_value = 0.0
        link(diff.outputs[0], pos.inputs[0])
        gain = mathn(100, -600, "MULTIPLY")
        gain.inputs[1].default_value = -edl_strength
        link(pos.outputs[0], gain.inputs[0])
        shade = mathn(300, -600, "EXPONENT")
        link(gain.outputs[0], shade.inputs[0])
        return shade.outputs[0]

    edges = (edges or "EDL").upper()
    if edges == "NORMAL":
        edge_out = normal_edges()
    elif edges == "BOTH":
        a, b = normal_edges(), edl_edges()
        both = mathn(450, -450, "MULTIPLY")
        link(a, both.inputs[0])
        link(b, both.inputs[1])
        edge_out = both.outputs[0]
    else:
        edge_out = edl_edges()

    # ambient occlusion
    ao_mix = mix_rgb(0, 150, "MULTIPLY", 0.7)
    link(rl.outputs["Image"], ao_mix.inputs[6])
    ao_name = next((n for n in ("Ambient Occlusion", "AO")
                    if n in rl.outputs and rl.outputs[n].enabled), None)
    if ao_name:
        link(rl.outputs[ao_name], ao_mix.inputs[7])
    else:
        ao_mix.inputs["Factor"].default_value = 0.0

    # edges
    crease = mix_rgb(200, 100, "MULTIPLY", 0.5)
    link(ao_mix.outputs[2], crease.inputs[6])
    link(edge_out, crease.inputs[7])

    # grade + haze
    cb = N("CompositorNodeColorBalance", 400, 100)
    set_in(cb, "Type", "Offset/Power/Slope (ASC-CDL)")
    for sock in cb.inputs:
        if sock.name == "Slope" and sock.bl_idname == "NodeSocketColor":
            sock.default_value = (1.08, 1.03, 0.95, 1.0)
        if sock.name == "Power" and sock.bl_idname == "NodeSocketColor":
            sock.default_value = (1.1, 1.1, 1.1, 1.0)
    link(crease.outputs[2], cb.inputs["Image"])
    hz = mix_rgb(600, 100, "MIX", 0.0)
    if "Mist" in rl.outputs and rl.outputs["Mist"].enabled:
        mist_gain = mathn(450, -150, "MULTIPLY")
        mist_gain.inputs[1].default_value = haze
        link(rl.outputs["Mist"], mist_gain.inputs[0])
        link(mist_gain.outputs[0], hz.inputs["Factor"])
    link(cb.outputs["Image"], hz.inputs[6])
    hz.inputs[7].default_value = (0.75, 0.8, 0.9, 1.0)

    # glare
    glare = N("CompositorNodeGlare", 800, 100)
    set_in(glare, "Type", "Fog Glow")
    set_in(glare, "Threshold", 1.0)
    set_in(glare, "Strength", 0.3)
    link(hz.outputs[2], glare.inputs["Image"])
    link(glare.outputs["Image"], out.inputs[0])

    scene.render.use_compositing = True
    if not hasattr(scene, "compositing_node_group"):
        scene.use_nodes = True
    return nt


def set_viewport_compositor(context, mode: str = "ALWAYS"):
    """Rendered viewport shading shows the compositor when its 'Compositor'
    option is Always (per 3D viewport)."""
    for window in context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == "VIEW_3D":
                for space in area.spaces:
                    if space.type == "VIEW_3D" and hasattr(space.shading, "use_compositor"):
                        space.shading.use_compositor = mode


class OGC3D_OT_CompositorBuild(Operator):
    """Build the 'OGC3D Beauty' compositor tree (edges, AO, grade, haze, glare)
    for this scene and show it in Rendered viewport shading"""
    bl_idname = "ogc3dtiles.compositor_build"
    bl_label = "Build Beauty Compositor"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = context.scene.ogc3dtiles
        build_beauty_tree(context.scene, props.comp_edges)
        set_viewport_compositor(context, "ALWAYS")
        self.report({"INFO"}, "Compositor tree built: see the Compositing workspace, "
                              "or Rendered shading in the viewport")
        return {"FINISHED"}


class OGC3D_OT_CompositorRemove(Operator):
    """Disable the beauty compositor"""
    bl_idname = "ogc3dtiles.compositor_remove"
    bl_label = "Remove Beauty Compositor"

    def execute(self, context):
        sc = context.scene
        sc.render.use_compositing = False
        if hasattr(sc, "compositing_node_group"):
            sc.compositing_node_group = None
        set_viewport_compositor(context, "DISABLED")
        return {"FINISHED"}


def draw_panel(layout, props):
    layout.prop(props, "comp_edges", text="Edges")
    row = layout.row(align=True)
    row.operator("ogc3dtiles.compositor_build", icon="NODE_COMPOSITING", text="Build")
    row.operator("ogc3dtiles.compositor_remove", icon="X", text="")
    layout.label(text="View: Rendered shading, or the Compositing workspace", icon="INFO")


_classes = [OGC3D_OT_CompositorBuild, OGC3D_OT_CompositorRemove]


def register():
    for c in _classes:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(_classes):
        bpy.utils.unregister_class(c)
