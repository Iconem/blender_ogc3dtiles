import bpy, mathutils
p = bpy.context.scene.ogc3dtiles
if p.is_streaming: bpy.ops.ogc3dtiles.stop_stream()
bpy.ops.ogc3dtiles.clear_tiles()
while p.tilesets: p.tilesets.remove(0)
for o in list(bpy.data.objects):
    if o.name.startswith("3D Tiles"): bpy.data.objects.remove(o, do_unlink=True)
p.origin_mode = 'CUSTOM'; p.origin_lat = 41.8902; p.origin_lon = 12.4922; p.origin_height = 70
p.tileset_url = "%3DTILED%/bing/tileset.json"
bpy.ops.ogc3dtiles.tileset_add(); p.tilesets[0].name = "Bing Maps 3D (via 3dtiled)"
w = bpy.context.window_manager.windows[0]; a = next(a for a in w.screen.areas if a.type=='VIEW_3D'); sp=a.spaces[0]; r=sp.region_3d
sp.shading.type='MATERIAL'; r.view_location = mathutils.Vector((0,0,0)); r.view_distance = 900; r.view_rotation = mathutils.Euler((1.0, 0, 0.6)).to_quaternion()
bpy.ops.ogc3dtiles.start_stream(); print("started bing")
