import bpy, mathutils
p = bpy.context.scene.ogc3dtiles
if p.is_streaming: bpy.ops.ogc3dtiles.stop_stream()
bpy.ops.ogc3dtiles.clear_tiles()
while len(p.tilesets) > 1: p.tilesets.remove(len(p.tilesets) - 1)
t = p.tilesets[0]; t.enabled = True; t.name = "Clermont-Ferrand mesh"
while t.clip_polygons: t.clip_polygons.remove(0)
t.use_clipping = False
for o in list(bpy.data.objects):
    if o.name.split('.')[0] in ("Cube", "Circle") or o.name.startswith("3D Tiles"): bpy.data.objects.remove(o, do_unlink=True)
p.active_tileset = 0; p.origin_mode = 'CUSTOM'; p.origin_lat = 45.77874; p.origin_lon = 3.08583; p.origin_height = 462.0; p.place_query = ""
w = bpy.context.window_manager.windows[0]; a = next(a for a in w.screen.areas if a.type=='VIEW_3D'); sp=a.spaces[0]; r=sp.region_3d
sp.shading.type='MATERIAL'; r.view_perspective='PERSP'; r.view_location = mathutils.Vector((0,0,20)); r.view_distance = 420; r.view_rotation = mathutils.Euler((1.15, 0, 0.6)).to_quaternion()
bpy.ops.ogc3dtiles.start_stream(); print("prep9", [(x.name, x.enabled) for x in p.tilesets])
