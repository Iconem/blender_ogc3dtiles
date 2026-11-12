import bpy, mathutils
p = bpy.context.scene.ogc3dtiles
if p.is_streaming: bpy.ops.ogc3dtiles.stop_stream()
bpy.ops.ogc3dtiles.clear_tiles()
while p.tilesets: p.tilesets.remove(0)
for o in list(bpy.data.objects):
    if o.name.startswith("3D Tiles"): bpy.data.objects.remove(o, do_unlink=True)
p.origin_mode = 'AUTO'; bpy.ops.ogc3dtiles.origin_reset()
p.tileset_url = r"%OGC_SCRATCH%\dl\lublin\3dtiles\tileset.json"
bpy.ops.ogc3dtiles.tileset_add(); p.tilesets[0].name = "Shramko 103M splats (Poland)"; p.tileset_url = ""
w = bpy.context.window_manager.windows[0]; a = next(a for a in w.screen.areas if a.type=='VIEW_3D'); sp=a.spaces[0]; r=sp.region_3d
sp.shading.type='RENDERED'; r.view_perspective='PERSP'; r.view_location = mathutils.Vector((0,0,0)); r.view_distance = 2500; r.view_rotation = mathutils.Euler((1.0, 0, 0.6)).to_quaternion(); sp.clip_end = 100000
bpy.context.scene.render.engine = 'BLENDER_EEVEE'
bpy.ops.ogc3dtiles.start_stream(); print("started lublin")
