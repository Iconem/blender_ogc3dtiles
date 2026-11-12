import bpy, time
p = bpy.context.scene.ogc3dtiles
if p.is_streaming: bpy.ops.ogc3dtiles.stop_stream()
bpy.ops.ogc3dtiles.clear_tiles()
while p.tilesets: p.tilesets.remove(0)
for o in list(bpy.data.objects):
    if o.name.startswith("3D Tiles"): bpy.data.objects.remove(o, do_unlink=True)
p.tileset_url = "%3DTILED%/tiles/tileset.json?url=https://data.geopf.fr/telechargement/download/LiDARHD-NUALID/NUALHD_1-0__LAZ_LAMB93_KE_2025-06-06/LHD_FXX_0648_6863_PTS_LAMB93_IGN69.copc.laz&cache=hierarchy&attributes=intensity,classification"
bpy.ops.ogc3dtiles.tileset_add(); p.tilesets[0].name = "IGN LiDAR HD Eiffel (COPC via 3dtiled)"
w = bpy.context.window_manager.windows[0]; a = next(a for a in w.screen.areas if a.type=='VIEW_3D'); a.spaces[0].shading.type='SOLID'
bpy.ops.ogc3dtiles.start_stream(); print("started")
