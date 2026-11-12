import bpy, mathutils
p = bpy.context.scene.ogc3dtiles
if p.is_streaming: bpy.ops.ogc3dtiles.stop_stream()
bpy.ops.ogc3dtiles.clear_tiles()
while p.tilesets: p.tilesets.remove(0)
p.tileset_url = ""; p.place_query = ""; p.origin_mode = 'AUTO'; bpy.ops.ogc3dtiles.origin_reset()
for o in list(bpy.data.objects):
    if o.name.startswith("3D Tiles") or o.name.split('.')[0] in ("Cube","Circle"): bpy.data.objects.remove(o, do_unlink=True)
bpy.context.scene.render.engine = 'BLENDER_EEVEE'
w = bpy.context.window_manager.windows[0]; a = next(a for a in w.screen.areas if a.type=='VIEW_3D'); sp=a.spaces[0]; r=sp.region_3d
sp.shading.type='SOLID'; r.view_perspective='PERSP'; r.view_location = mathutils.Vector((0,0,0)); r.view_distance = 17; r.view_rotation = mathutils.Euler((1.1, 0, 0.8)).to_quaternion()
for ar in w.screen.areas:
    if ar.type == 'PROPERTIES': ar.spaces[0].context = 'SCENE'
print("prep1c")
