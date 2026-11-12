import bpy, mathutils
p = bpy.context.scene.ogc3dtiles
if p.is_streaming: bpy.ops.ogc3dtiles.stop_stream()
bpy.ops.ogc3dtiles.clear_tiles()
while p.tilesets: p.tilesets.remove(0)
for o in list(bpy.data.objects):
    if o.name.startswith("3D Tiles"): bpy.data.objects.remove(o, do_unlink=True)
p.tileset_url = r"%OGC_SCRATCH%\dl\sacre_coeur\3dtiles\tileset.json"
bpy.ops.ogc3dtiles.tileset_add(); p.tilesets[0].name = "Sacre-Coeur splat"
w = bpy.context.window_manager.windows[0]; a = next(a for a in w.screen.areas if a.type=='VIEW_3D'); sp=a.spaces[0]; r=sp.region_3d
sp.shading.type='RENDERED'
r.view_location = mathutils.Vector((0, 44, 35)); r.view_distance = 300; r.view_rotation = mathutils.Euler((1.35, 0, 0.0)).to_quaternion()
bpy.ops.ogc3dtiles.start_stream(); print("started")
