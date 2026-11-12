import bpy, mathutils
p = bpy.context.scene.ogc3dtiles
if p.is_streaming: bpy.ops.ogc3dtiles.stop_stream()
bpy.ops.ogc3dtiles.clear_tiles()
while p.tilesets: p.tilesets.remove(0)
for o in list(bpy.data.objects):
    if o.name.startswith("3D Tiles") or o.name.split('.')[0] in ("Cube", "Circle"): bpy.data.objects.remove(o, do_unlink=True)
p.origin_mode = 'CUSTOM'; p.origin_lat = 45.77874; p.origin_lon = 3.08583; p.origin_height = 462.0
p.tileset_url = "https://3d.craig.fr/datasets/Clermont/3dtiles/tileset.json"; bpy.ops.ogc3dtiles.tileset_add(); p.tilesets[0].name = "Clermont-Ferrand mesh"; p.tileset_url = ""
w = bpy.context.window_manager.windows[0]; a = next(a for a in w.screen.areas if a.type=='VIEW_3D'); sp=a.spaces[0]; r=sp.region_3d
sp.shading.type='MATERIAL'; r.view_perspective='PERSP'; r.view_location = mathutils.Vector((0,0,20)); r.view_distance = 420; r.view_rotation = mathutils.Euler((1.15, 0, 0.6)).to_quaternion()
bpy.context.scene.cursor.location = (0, 0, 0); bpy.ops.object.select_all(action='DESELECT')
for ar in w.screen.areas:
    if ar.type == 'PROPERTIES': ar.spaces[0].context = 'SCENE'
bpy.ops.ogc3dtiles.start_stream(); print("prep7d clermont")
