import bpy, mathutils
p = bpy.context.scene.ogc3dtiles; t = p.tilesets[0]
t.use_clipping = False
while t.clip_polygons: t.clip_polygons.remove(0)
for o in list(bpy.data.objects):
    if o.name.split('.')[0] in ("Cube", "Circle"): bpy.data.objects.remove(o, do_unlink=True)
w = bpy.context.window_manager.windows[0]; a = next(a for a in w.screen.areas if a.type=='VIEW_3D'); r = a.spaces[0].region_3d
r.view_location = mathutils.Vector((0, 0, 30)); r.view_distance = 450; r.view_rotation = mathutils.Euler((1.05, 0, 0.5)).to_quaternion()
bpy.context.scene.cursor.location = (0, 0, 0); bpy.ops.object.select_all(action='DESELECT'); print("prep7f clean", t.use_clipping, len(t.clip_polygons))
