import bpy, mathutils
p = bpy.context.scene.ogc3dtiles
if p.is_streaming: bpy.ops.ogc3dtiles.stop_stream()
bpy.ops.ogc3dtiles.clear_tiles()
while p.tilesets: p.tilesets.remove(0)
p.tileset_url = ""
for o in list(bpy.data.objects):
    if o.name == "Cube" or o.name.startswith("3D Tiles"): bpy.data.objects.remove(o, do_unlink=True)
w = bpy.context.window_manager.windows[0]; a = next(a for a in w.screen.areas if a.type=='VIEW_3D'); sp=a.spaces[0]; r=sp.region_3d
sp.shading.type='SOLID'; r.view_perspective='PERSP'
r.view_location = mathutils.Vector((0,0,0)); r.view_distance = 17; r.view_rotation = mathutils.Euler((1.1, 0, 0.8)).to_quaternion()
sp.clip_end = 100000
print("prepped")
