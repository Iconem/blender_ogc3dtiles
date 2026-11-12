import bpy, mathutils
p = bpy.context.scene.ogc3dtiles; p.view_source = 'VIEWPORT'
w = bpy.context.window_manager.windows[0]; a = next(a for a in w.screen.areas if a.type=='VIEW_3D'); sp=a.spaces[0]; r=sp.region_3d
r.view_perspective = 'PERSP'; r.view_location = mathutils.Vector((0,0,20)); r.view_distance = 420; r.view_rotation = mathutils.Euler((1.15, 0, 0.6)).to_quaternion()
c = bpy.context.scene.camera; c.location = (216.5, -316.4, 191.6); c.rotation_euler = (1.15, 0, 0.6)
bpy.context.scene.render.resolution_x = 1920; bpy.context.scene.render.resolution_y = 1080
print("prep5b ok", p.view_source)
