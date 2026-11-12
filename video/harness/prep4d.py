import bpy, mathutils
# Eiffel redo (2026-11-11): tileset added beforehand (the take starts at Start), larger point defaults,
# EEVEE Rendered for colours (Material Preview showed the points as a white sheet in s4b).
p = bpy.context.scene.ogc3dtiles
if p.is_streaming: bpy.ops.ogc3dtiles.stop_stream()
bpy.ops.ogc3dtiles.clear_tiles()
while p.tilesets: p.tilesets.remove(0)
p.auto_relight = False; p.comp_enabled = False; p.read_metadata = False; p.meta_color = False; p.tile_geometry = False
for o in list(bpy.data.objects):
    if o.name.startswith("3D Tiles") or o.name.startswith("OGC3D") or o.name.split('.')[0] in ("Cube", "Circle"): bpy.data.objects.remove(o, do_unlink=True)
w_ = bpy.data.worlds.get("World")
if w_: w_.use_nodes = False
bpy.context.scene.render.engine = 'BLENDER_EEVEE'
p.origin_mode = 'AUTO'; bpy.ops.ogc3dtiles.origin_reset(); p.tileset_url = ""; p.place_query = ""
p.point_display = 'POINTS'; p.point_radius_mode = 'ADAPTIVE'; p.point_adapt_min_px = 2.0; p.point_adapt_max_px = 8.0
p.point_radius = 0.15; p.point_px = 4.0
p.tileset_url = r"%OGC_SCRATCH%\dl\eiffel\3dtiles\tileset.json"
bpy.ops.ogc3dtiles.tileset_add(); t = p.tilesets[0]; t.name = "IGN LiDAR HD Eiffel (COPC)"; t.use_overlays = False
while t.overlays: t.overlays.remove(0)
p.tileset_url = ""
w = bpy.context.window_manager.windows[0]; a = next(a for a in w.screen.areas if a.type=='VIEW_3D'); sp=a.spaces[0]; r=sp.region_3d
sp.shading.type='SOLID'; r.view_perspective='PERSP'; r.view_location = mathutils.Vector((0,0,100)); r.view_distance = 1200; r.view_rotation = mathutils.Euler((1.0, 0, 0.6)).to_quaternion()
for ar in w.screen.areas:
    if ar.type == 'PROPERTIES': ar.spaces[0].context = 'SCENE'
bpy.ops.object.select_all(action='DESELECT')
print("prep4d", p.point_radius_mode, p.point_adapt_max_px)
