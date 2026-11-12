import bpy, mathutils
p = bpy.context.scene.ogc3dtiles
if p.is_streaming: bpy.ops.ogc3dtiles.stop_stream()
bpy.ops.ogc3dtiles.clear_tiles()
while p.tilesets: p.tilesets.remove(0)
for o in list(bpy.data.objects):
    if o.name.startswith("3D Tiles"): bpy.data.objects.remove(o, do_unlink=True)
p.origin_mode = 'AUTO'; bpy.ops.ogc3dtiles.origin_reset()
p.read_metadata = True; p.meta_color = False
p.tileset_url = r"%OGC_SCRATCH%\dl\eiffel\3dtiles\tileset.json"
bpy.ops.ogc3dtiles.tileset_add(); t = p.tilesets[0]; t.name = "IGN LiDAR HD - Eiffel (COPC)"; t.use_overlays = False
w = bpy.context.window_manager.windows[0]; a = next(a for a in w.screen.areas if a.type=='VIEW_3D'); sp=a.spaces[0]; r=sp.region_3d
sp.shading.type='MATERIAL'
bpy.ops.ogc3dtiles.start_stream(); print("started eiffel")
