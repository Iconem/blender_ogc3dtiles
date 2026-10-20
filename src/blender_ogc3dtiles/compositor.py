"""
compositor.py — screen-space "beauty" pass for streamed tiles, built from
render passes in the compositor (no AI): edge darkening (eye-dome lighting
from depth and/or Sobel creases from normals), ambient occlusion, mist haze,
a colour grade and a soft glare.

``build_beauty_tree(scene)`` creates the node group once with BOTH edge
branches; every tunable (edge mode, EDL strength, crease strength, AO, haze)
is a Value node that ``apply_settings`` sets from the sidebar sliders, so
edits show up live in the viewport (Rendered shading, compositor "Always")
without a rebuild.  ``scripts/compositor_demo.py`` reuses this module for
headless renders.
"""
from __future__ import annotations

import bpy
from bpy.types import Operator

TREE_NAME = "OGC3D Beauty"
EDL_ENABLE = "EDL Enable"
CREASE_ENABLE = "Crease Enable"
EDL_STRENGTH = "EDL Strength"
CREASE_STRENGTH = "Crease Strength"
AO_STRENGTH = "AO Strength"
HAZE = "Haze"
HAZE_START = "Haze Start"          # metres: haze begins
HAZE_END = "Haze End"              # metres: full haze
VERSION_NODE = HAZE_START          # trees without it were built by an older version


def _passes(scene):
    vl = bpy.context.view_layer if bpy.context.view_layer else scene.view_layers[0]
    vl.use_pass_normal = True
    vl.use_pass_z = True
    vl.use_pass_diffuse_color = True
    vl.use_pass_ambient_occlusion = True
    if hasattr(scene.eevee, "use_gtao"):
        scene.eevee.use_gtao = True


def _haze_range(scene):
    """Haze from the Depth pass (the viewport's Mist pass is not normalised,
    it washed the whole view out): starts at the tiles' extent, full at 4 x
    (a viewer framing the whole site sits about one extent away); a
    300..3000 m default before anything is loaded."""
    size = _tiles_extent(scene)
    return (size, size * 4.0) if size > 0 else (300.0, 3000.0)


def ensure_world_light(scene) -> bool:
    """Rendered shading lights the scene with its world + lights only.  A
    fresh .blend has Blender's default dark-grey world and a 1 kW point light
    (useless at site scale), so streamed tiles look nearly black next to
    Material Preview's studio HDRI.  Brighten such an unlit world once
    (uniform light grey); returns True when it changed something."""
    if any(o.type == "LIGHT" and o.data.type == "SUN" for o in scene.objects):
        return False
    world = scene.world
    if world is None:
        world = scene.world = bpy.data.worlds.new("World")
    if world.get("ogc3d_lit"):
        return False
    world.use_nodes = True
    bg = next((n for n in world.node_tree.nodes if n.type == "BACKGROUND"), None)
    if bg is None:
        return False
    col = bg.inputs["Color"].default_value
    if max(col[:3]) * bg.inputs["Strength"].default_value > 0.3 or bg.inputs["Color"].is_linked:
        return False                      # the user already lit it
    bg.inputs["Color"].default_value = (0.85, 0.87, 0.9, 1.0)
    bg.inputs["Strength"].default_value = 1.0
    world["ogc3d_lit"] = True
    return True


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


def _settings(scene, edges=None, edl_strength=None, crease_strength=None, ao=None, haze=None):
    """Slider values: explicit arguments win, then the scene properties, then defaults."""
    p = getattr(scene, "ogc3dtiles", None)
    g = (lambda name, d: float(getattr(p, name, d)) if p is not None else d)
    edges = (edges or (getattr(p, "comp_edges", "EDL") if p is not None else "EDL")).upper()
    return {
        EDL_ENABLE: 1.0 if edges in ("EDL", "BOTH") else 0.0,
        CREASE_ENABLE: 1.0 if edges in ("NORMAL", "BOTH") else 0.0,
        EDL_STRENGTH: g("comp_edl_strength", 4.0) if edl_strength is None else float(edl_strength),
        CREASE_STRENGTH: g("comp_crease_strength", 1.0) if crease_strength is None else float(crease_strength),
        AO_STRENGTH: g("comp_ao", 0.5) if ao is None else float(ao),
        HAZE: g("comp_haze", 0.35) if haze is None else float(haze),
    }


def apply_settings(scene, **kw) -> bool:
    """Push the sidebar sliders into the existing tree's Value nodes."""
    nt = bpy.data.node_groups.get(TREE_NAME) if hasattr(scene, "compositing_node_group") else getattr(scene, "node_tree", None)
    if nt is None or nt.nodes.get(VERSION_NODE) is None:
        return False
    for name, val in _settings(scene, **kw).items():
        node = nt.nodes.get(name)
        if node is not None:
            node.outputs[0].default_value = val
    return True


def build_beauty_tree(scene, edges: str = None, edl_radius_px: int = 3,
                      edl_strength: float = None, crease_strength: float = None,
                      ao: float = None, haze: float = None):
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

    def value(name, x, y, default=0.0):
        n = N("ShaderNodeValue", x, y)
        n.name = n.label = name
        n.outputs[0].default_value = default
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

    def enable(shade_socket, enable_node, x, y):
        """1 + enable × (shade − 1): the branch is a no-op when disabled."""
        sub = mathn(x, y, "SUBTRACT")
        link(shade_socket, sub.inputs[0])
        sub.inputs[1].default_value = 1.0
        mad = mathn(x + 150, y, "MULTIPLY_ADD")
        link(sub.outputs[0], mad.inputs[0])
        link(enable_node.outputs[0], mad.inputs[1])
        mad.inputs[2].default_value = 1.0
        return mad.outputs[0]

    depth_cache = {}

    def clean_depth():
        """Depth pass usable in both the viewport and final renders: the
        viewport compositor gives 0 (or NaN) where nothing is drawn, renders
        give 1e10.  max() drops NaN, then empty pixels become 'far' (1e5 m)."""
        if "socket" in depth_cache:
            return depth_cache["socket"]
        zname = "Depth" if "Depth" in rl.outputs else "Z"
        nz = mathn(-800, -500, "MAXIMUM")
        link(rl.outputs[zname], nz.inputs[0])
        nz.inputs[1].default_value = 0.0
        is_bg = mathn(-800, -650, "LESS_THAN")
        link(nz.outputs[0], is_bg.inputs[0])
        is_bg.inputs[1].default_value = 1e-6
        far = mathn(-650, -650, "MULTIPLY_ADD")        # d + is_bg × 1e5
        link(is_bg.outputs[0], far.inputs[0])
        far.inputs[1].default_value = 1e5
        link(nz.outputs[0], far.inputs[2])
        depth_cache["socket"] = far.outputs[0]
        return far.outputs[0]

    def normal_edges():
        """Sobel on the normal pass: (1 − strength × |edge|)^0.6, clamped."""
        edge = N("CompositorNodeFilter", -600, -300)
        set_in(edge, "Type", "Sobel")
        link(rl.outputs["Normal" if "Normal" in rl.outputs else "Image"], edge.inputs["Image"])
        bw = N("CompositorNodeRGBToBW", -400, -300)
        link(edge.outputs["Image"], bw.inputs["Image"])
        strength = value(CREASE_STRENGTH, -400, -450, 1.0)
        scaled = mathn(-250, -300, "MULTIPLY")
        link(bw.outputs["Val"], scaled.inputs[0])
        link(strength.outputs[0], scaled.inputs[1])
        inv = mathn(-100, -300, "SUBTRACT")
        inv.inputs[0].default_value = 1.0
        link(scaled.outputs[0], inv.inputs[1])
        inv.use_clamp = True
        gain = mathn(50, -300, "POWER")
        gain.inputs[1].default_value = 0.6
        link(inv.outputs[0], gain.inputs[0])
        return enable(gain.outputs[0], value(CREASE_ENABLE, 50, -450, 0.0), 200, -300)

    def edl_edges():
        """Eye-dome lighting: a pixel further away than its neighbourhood
        (log depth − blurred log depth) gets darkened; silhouettes and
        concavities darken, flat tile borders do not."""
        logz = mathn(-500, -750, "LOGARITHM")
        logz.inputs[1].default_value = 2.718281828
        link(clean_depth(), logz.inputs[0])
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
        strength = value(EDL_STRENGTH, -100, -750, 4.0)
        gain = mathn(100, -600, "MULTIPLY")
        link(pos.outputs[0], gain.inputs[0])
        link(strength.outputs[0], gain.inputs[1])
        neg = mathn(250, -600, "MULTIPLY")
        link(gain.outputs[0], neg.inputs[0])
        neg.inputs[1].default_value = -1.0
        shade = mathn(400, -600, "EXPONENT")
        link(neg.outputs[0], shade.inputs[0])
        return enable(shade.outputs[0], value(EDL_ENABLE, 400, -750, 1.0), 550, -600)

    both = mathn(800, -450, "MULTIPLY")
    link(normal_edges(), both.inputs[0])
    link(edl_edges(), both.inputs[1])
    edge_out = both.outputs[0]

    # ambient occlusion
    ao_mix = mix_rgb(0, 150, "MULTIPLY", 0.5)
    link(rl.outputs["Image"], ao_mix.inputs[6])
    ao_name = next((n for n in ("Ambient Occlusion", "AO")
                    if n in rl.outputs and rl.outputs[n].enabled), None)
    ao_val = value(AO_STRENGTH, -200, 300, 0.5)
    if ao_name:
        link(rl.outputs[ao_name], ao_mix.inputs[7])
        link(ao_val.outputs[0], ao_mix.inputs["Factor"])
    else:
        ao_mix.inputs["Factor"].default_value = 0.0

    # edges
    crease = mix_rgb(200, 100, "MULTIPLY", 1.0)
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
    # haze factor = Haze × ramp(depth: start → end) × alpha
    start_m, end_m = _haze_range(scene)
    ramp = N("ShaderNodeMapRange", 300, -150, data_type="FLOAT", clamp=True)
    link(clean_depth(), ramp.inputs["Value"])
    link(value(HAZE_START, 100, -200, start_m).outputs[0], ramp.inputs["From Min"])
    link(value(HAZE_END, 100, -300, end_m).outputs[0], ramp.inputs["From Max"])
    haze_gain = mathn(450, -150, "MULTIPLY")
    link(ramp.outputs["Result"], haze_gain.inputs[0])
    link(value(HAZE, 300, -300, 0.35).outputs[0], haze_gain.inputs[1])
    haze_fac = haze_gain.outputs[0]
    if "Alpha" in rl.outputs:
        masked = mathn(450, -250, "MULTIPLY")
        link(haze_fac, masked.inputs[0])
        link(rl.outputs["Alpha"], masked.inputs[1])
        haze_fac = masked.outputs[0]
    link(haze_fac, hz.inputs["Factor"])
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
    apply_settings(scene, edges=edges, edl_strength=edl_strength,
                   crease_strength=crease_strength, ao=ao, haze=haze)
    return nt


def is_built(scene) -> bool:
    return bpy.data.node_groups.get(TREE_NAME) is not None and scene.render.use_compositing


def set_stable_viewport(scene, enabled: bool) -> None:
    """EEVEE accumulates viewport samples with a sub-pixel jitter while the
    Depth / Normal passes come from the current sample only, so EDL and
    Sobel creases shimmer by a pixel until the view converges.  One viewport
    sample removes the shimmer (and the anti-aliasing); the previous count
    is kept on the scene and restored when disabled."""
    props = scene.ogc3dtiles
    ee = scene.eevee
    if enabled:
        if props.comp_prev_taa == 0 and ee.taa_samples != 1:
            props.comp_prev_taa = ee.taa_samples
        ee.taa_samples = 1
    elif props.comp_prev_taa:
        ee.taa_samples = props.comp_prev_taa
        props.comp_prev_taa = 0


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
        build_beauty_tree(context.scene)
        set_viewport_compositor(context, "ALWAYS")
        set_stable_viewport(context.scene, context.scene.ogc3dtiles.comp_stable_viewport)
        lit = ensure_world_light(context.scene)
        self.report({"INFO"}, "Compositor tree built: see the Compositing workspace, "
                              "or Rendered shading in the viewport"
                              + (" (unlit scene: world brightened)" if lit else ""))
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
        set_stable_viewport(sc, False)
        return {"FINISHED"}


def draw_panel(layout, props):
    layout.prop(props, "comp_edges", text="Edges")
    col = layout.column(align=True)
    if props.comp_edges in ("EDL", "BOTH"):
        col.prop(props, "comp_edl_strength", text="EDL strength")
    if props.comp_edges in ("NORMAL", "BOTH"):
        col.prop(props, "comp_crease_strength", text="Crease strength")
    col.prop(props, "comp_ao", text="AO")
    col.prop(props, "comp_haze", text="Haze")
    layout.prop(props, "comp_stable_viewport", text="Stable viewport (1 sample, no shimmer)")
    row = layout.row(align=True)
    built = bpy.data.node_groups.get(TREE_NAME) is not None
    row.operator("ogc3dtiles.compositor_build", icon="NODE_COMPOSITING",
                 text="Rebuild" if built else "Build")
    row.operator("ogc3dtiles.compositor_remove", icon="X", text="")
    row.operator("ogc3dtiles.open_nodes", icon="NODETREE", text="").kind = "COMPOSITOR"
    layout.label(text="Shown in Rendered shading (viewport compositor: Always)", icon="INFO")


_classes = [OGC3D_OT_CompositorBuild, OGC3D_OT_CompositorRemove]


def register():
    for c in _classes:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(_classes):
        bpy.utils.unregister_class(c)
