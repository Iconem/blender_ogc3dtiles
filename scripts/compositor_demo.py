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
# usage A: out_plain.png out_comp.png [elev_deg]
# usage B: --views <prefix> name:az:elev:dist[:ox:oy:oz] ...   (offsets = bbox fractions)
multi = bool(argv) and argv[0] == "--views"
out_plain = argv[0] if argv and not multi else ""
out_comp = argv[1] if len(argv) > 1 and not multi else ""
elev = math.radians(float(argv[2])) if len(argv) > 2 and not multi else math.radians(35)
views = []
if multi:
    prefix = argv[1]
    for spec in argv[2:]:
        parts = spec.split(":")
        name, az, el, dist = parts[0], float(parts[1]), float(parts[2]), float(parts[3])
        off = tuple(float(v) for v in parts[4:7]) if len(parts) >= 7 else (0.0, 0.0, 0.0)
        views.append((name, az, el, dist, off))

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
    ext = hi - lo

    def place(az_deg, el_deg, dist_f, off=(0.0, 0.0, 0.0)):
        tgt = ctr + Vector((ext.x * off[0], ext.y * off[1], ext.z * off[2]))
        a, e = math.radians(az_deg), math.radians(el_deg)
        cam.location = tgt + Vector((math.cos(a) * math.cos(e), math.sin(a) * math.cos(e),
                                     math.sin(e))) * size * dist_f
        cam.rotation_euler = (tgt - cam.location).to_track_quat("-Z", "Y").to_euler()

    place(-35, math.degrees(elev), 0.9)
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


# 1. normal-based edges (Sobel on the normal pass) → darken creases
edge = N("CompositorNodeFilter", -600, -300)
set_in(edge, "Type", "Sobel")
nt.links.new(rl.outputs["Normal" if "Normal" in rl.outputs else "Image"], edge.inputs["Image"])
edge_bw = N("CompositorNodeRGBToBW", -400, -300)
nt.links.new(edge.outputs["Image"], edge_bw.inputs["Image"])
edge_inv = mathn(-200, -300, "SUBTRACT")
edge_inv.inputs[0].default_value = 1.0
nt.links.new(edge_bw.outputs["Val"], edge_inv.inputs[1])
edge_gain = mathn(0, -300, "POWER")
edge_gain.inputs[1].default_value = 0.6
nt.links.new(edge_inv.outputs[0], edge_gain.inputs[0])

# 2. ambient occlusion pass multiplied in (when the engine provides it)
print("COMP passes:", [o.name for o in rl.outputs if o.enabled])
ao_mix = mix_rgb(0, 150, "MULTIPLY", 0.7)
nt.links.new(rl.outputs["Image"], ao_mix.inputs[6])
ao_name = next((n for n in ("Ambient Occlusion", "AO") if n in rl.outputs and rl.outputs[n].enabled), None)
if ao_name:
    nt.links.new(rl.outputs[ao_name], ao_mix.inputs[7])
else:
    ao_mix.inputs["Factor"].default_value = 0.0   # pass-through

# 3. creases darkening
crease = mix_rgb(200, 100, "MULTIPLY", 0.5)
nt.links.new(ao_mix.outputs[2], crease.inputs[6])
nt.links.new(edge_gain.outputs[0], crease.inputs[7])

# 4. colour grade (contrast + warmth) and mist haze
cb = N("CompositorNodeColorBalance", 400, 100)
set_in(cb, "Type", "Offset/Power/Slope (ASC-CDL)")
for sock in cb.inputs:
    if sock.name == "Slope" and sock.bl_idname == "NodeSocketColor":
        sock.default_value = (1.08, 1.03, 0.95, 1.0)
    if sock.name == "Power" and sock.bl_idname == "NodeSocketColor":
        sock.default_value = (1.1, 1.1, 1.1, 1.0)
nt.links.new(crease.outputs[2], cb.inputs["Image"])
haze = mix_rgb(600, 100, "MIX", 0.0)
if "Mist" in rl.outputs and rl.outputs["Mist"].enabled:
    mist_gain = mathn(450, -150, "MULTIPLY")
    mist_gain.inputs[1].default_value = 0.35      # keep the haze subtle
    nt.links.new(rl.outputs["Mist"], mist_gain.inputs[0])
    nt.links.new(mist_gain.outputs[0], haze.inputs["Factor"])
nt.links.new(cb.outputs["Image"], haze.inputs[6])
haze.inputs[7].default_value = (0.75, 0.8, 0.9, 1.0)

# 5. soft glare on highlights
glare = N("CompositorNodeGlare", 750, 100)
set_in(glare, "Type", "Fog Glow")
set_in(glare, "Threshold", 1.0)
set_in(glare, "Strength", 0.3)
nt.links.new(haze.outputs[2], glare.inputs["Image"])
nt.links.new(glare.outputs["Image"], out.inputs[0])

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

if multi and objs:
    for name, az_deg, el_deg, dist_f, off in views:
        place(az_deg, el_deg, dist_f, off)
        for tag, comp in (("plain", False), ("beauty", True)):
            sc.render.use_compositing = comp
            if not hasattr(sc, "compositing_node_group"):
                sc.use_nodes = comp
            sc.render.filepath = f"{prefix}_{name}_{tag}.png"
            bpy.ops.render.render(write_still=True)
            print("COMP_VIEW", sc.render.filepath)
