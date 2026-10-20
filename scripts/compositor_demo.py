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
# optional: --edges edl|normal|both   (default edl: eye-dome lighting from the
# depth pass; "normal" is the Sobel-on-normals crease pass, which also traces
# tile borders where per-tile normals disagree)
edges = "edl"
if "--edges" in argv:
    i = argv.index("--edges")
    edges = argv[i + 1]
    del argv[i:i + 2]
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

# ── compositor tree (shared with the add-on's "Compositor" sub-panel) ──────────
import os as _os
_src = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "src")
if _src not in sys.path:
    sys.path.insert(0, _src)
from blender_ogc3dtiles.compositor import build_beauty_tree  # noqa: E402

if objs:
    sc.world.mist_settings.start = size * 0.3
    sc.world.mist_settings.depth = size * 1.5
build_beauty_tree(sc, edges)

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
