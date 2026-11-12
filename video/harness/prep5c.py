import bpy, mathutils
p = bpy.context.scene.ogc3dtiles
p.auto_relight = False; p.comp_enabled = False; p.view_source = 'VIEWPORT'
for o in list(bpy.data.objects):
    if o.name == "OGC3D Sun": bpy.data.objects.remove(o, do_unlink=True)
w_ = bpy.data.worlds.get("World")
if w_: w_.use_nodes = False
sc = bpy.context.scene; sc.render.engine = 'BLENDER_EEVEE'
w = bpy.context.window_manager.windows[0]; a = next(a for a in w.screen.areas if a.type=='VIEW_3D'); sp=a.spaces[0]; r=sp.region_3d
sp.shading.type='MATERIAL'; r.view_perspective = 'PERSP'; r.view_location = mathutils.Vector((0,0,20)); r.view_distance = 420; r.view_rotation = mathutils.Euler((1.15, 0, 0.6)).to_quaternion()
c = sc.camera; c.location = (216.5, -316.4, 191.6); c.rotation_euler = (1.15, 0, 0.6); c.data.display_size = 100.0; c.data.show_limits = False
sc.render.resolution_x = 1920; sc.render.resolution_y = 1080
for ar in w.screen.areas:
    if ar.type == 'PROPERTIES': ar.spaces[0].context = 'SCENE'
bpy.ops.object.select_all(action='DESELECT')
if not p.is_streaming: bpy.ops.ogc3dtiles.start_stream()
print("prep5c", p.view_source, c.data.display_size, p.is_streaming)
