"""Screen-space "beauty" pass for streamed tiles, built from render passes in
the compositor (no AI):  normal-based edge darkening, depth-based ambient
occlusion, mist haze, colour grade and a soft glare.

Usage (headless, on a .blend saved by the streamer):
  blender -b scene.blend --python scripts/compositor_demo.py -- out_plain.png out_comp.png [elev_deg]
Also usable inside Blender: exec(open(path).read()) builds the tree on the
current scene.
"""
import math
import sys

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
out_plain = argv[0] if argv else ""
out_comp = argv[1] if len(argv) > 1 else ""
elev = math.radians(float(argv[2])) if len(argv) > 2 else math.radians(35)

sc = bpy.context.scene
bpy.context.view_layer.update()

# ── frame the visible tiles ─────────────────────────────────────────────────
coll = bpy.data.collections.get("3D Tiles")
objs = [o for o in (coll.all_objects if coll else bpy.data.objects)
        if o is not None and o.type == "MESH" and not o.hide_viewport]
for o in (coll.all_objects if coll else []):
    if o is not None and o.type == "MESH":
        o.hide_render = o.hide_viewport
if objs:
    pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    ctr = (lo + hi) / 2
    size = (hi - lo).length
    cam_data = bpy.data.cameras.new("CompCam")
    cam_data.lens = 35
    cam_data.clip_end = 1e6
    cam = bpy.data.objects.new("CompCam", cam_data)
    sc.collection.objects.link(cam)
    az = math.radians(-35)
    cam.location = ctr + Vector((math.cos(az) * math.cos(elev), math.sin(az) * math.cos(elev),
                                 math.sin(elev))) * size * 0.9
    cam.rotation_euler = (ctr - cam.location).to_track_quat("-Z", "Y").to_euler()
    sc.camera = cam
    sun = bpy.data.lights.new("Sun", "SUN")
    sun.energy = 3.0
    so = bpy.data.objects.new("Sun", sun)
    sc.collection.objects.link(so)
    so.rotation_euler = (math.radians(50), 0, math.radians(30))
    sc.world = sc.world or bpy.data.worlds.new("World")
    sc.world.use_nodes = True
    bg = sc.world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.6, 0.7, 0.8, 1)
    # mist range from the scene extent
    sc.world.mist_settings.start = size * 0.3
    sc.world.mist_settings.depth = size * 1.5

sc.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in [
    e.identifier for e in sc.render.bl_rna.properties["engine"].enum_items] else "BLENDER_EEVEE"
sc.render.resolution_x, sc.render.resolution_y = 1280, 720

# ── passes ──────────────────────────────────────────────────────────────────
vl = bpy.context.view_layer
vl.use_pass_normal = True
vl.use_pass_z = True
vl.use_pass_mist = True
vl.use_pass_diffuse_color = True
vl.use_pass_ambient_occlusion = True
if hasattr(sc.eevee, "use_gtao"):
    sc.eevee.use_gtao = True

# ── compositor tree ─────────────────────────────────────────────────────────
# Blender 5.x: the compositor is a node group on scene.compositing_node_group
# with a Group Output; 4.x: scene.node_tree with a Composite node.
if hasattr(sc, "compositing_node_group"):
    nt = bpy.data.node_groups.new("OGC3D Beauty", "CompositorNodeTree")
    sc.compositing_node_group = nt
    out = nt.nodes.new("NodeGroupOutput")
    out.is_active_output = True
    nt.interface.new_socket(name="Image", in_out="OUTPUT", socket_type="NodeSocketColor")
else:
    sc.use_nodes = True
    nt = sc.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("CompositorNodeComposite")
out.location = (900, 0)
rl = nt.nodes.new("CompositorNodeRLayers")
rl.location = (-900, 0)


def N(t, x, y, **kw):
    n = nt.nodes.new(t)
    n.location = (x, y)
    for k, v in kw.items():
        setattr(n, k, v)
    return n


# 1. normal-based edges (Sobel on the normal pass) → darken creases
edge = N("CompositorNodeFilter", -600, -300, filter_type="SOBEL")
nt.links.new(rl.outputs["Normal"], edge.inputs["Image"])
edge_bw = N("CompositorNodeRGBToBW", -400, -300)
nt.links.new(edge.outputs["Image"], edge_bw.inputs["Image"])
edge_inv = N("CompositorNodeMath", -200, -300, operation="SUBTRACT")
edge_inv.inputs[0].default_value = 1.0
nt.links.new(edge_bw.outputs["Val"], edge_inv.inputs[1])
edge_gain = N("CompositorNodeMath", 0, -300, operation="POWER")
edge_gain.inputs[1].default_value = 0.6
nt.links.new(edge_inv.outputs[0], edge_gain.inputs[0])

# 2. ambient occlusion pass multiplied in (EEVEE GTAO)
ao_mix = N("CompositorNodeMixRGB", 0, 150, blend_type="MULTIPLY")
ao_mix.inputs["Fac"].default_value = 0.7
nt.links.new(rl.outputs["Image"], ao_mix.inputs[1])
nt.links.new(rl.outputs["AO"], ao_mix.inputs[2])

# 3. creases darkening
crease = N("CompositorNodeMixRGB", 200, 100, blend_type="MULTIPLY")
crease.inputs["Fac"].default_value = 0.5
nt.links.new(ao_mix.outputs["Image"], crease.inputs[1])
nt.links.new(edge_gain.outputs[0], crease.inputs[2])

# 4. colour grade (contrast + warmth) and mist haze
cb = N("CompositorNodeColorBalance", 400, 100)
cb.correction_method = "OFFSET_POWER_SLOPE"
cb.slope = (1.08, 1.03, 0.95)
cb.power = (1.1, 1.1, 1.1)
nt.links.new(crease.outputs["Image"], cb.inputs["Image"])
haze = N("CompositorNodeMixRGB", 600, 100, blend_type="MIX")
nt.links.new(rl.outputs["Mist"], haze.inputs["Fac"])
nt.links.new(cb.outputs["Image"], haze.inputs[1])
haze.inputs[2].default_value = (0.75, 0.8, 0.9, 1.0)

# 5. soft glare on highlights
glare = N("CompositorNodeGlare", 750, 100, glare_type="FOG_GLOW")
glare.threshold = 1.0
glare.mix = -0.6
nt.links.new(haze.outputs["Image"], glare.inputs["Image"])
nt.links.new(glare.outputs["Image"], out.inputs["Image"])

if out_plain:
    sc.render.use_compositing = False
    sc.render.filepath = out_plain
    bpy.ops.render.render(write_still=True)
    print("COMP_PLAIN", out_plain)
if out_comp:
    sc.render.use_compositing = True
    if not hasattr(sc, "compositing_node_group"):
        sc.use_nodes = True
    sc.render.filepath = out_comp
    bpy.ops.render.render(write_still=True)
    print("COMP_DONE", out_comp)
