import bpy, mathutils
p = bpy.context.scene.ogc3dtiles
p.tile_geometry = False; p.comp_enabled = False; p.comp_edges = 'EDL'
w = bpy.context.window_manager.windows[0]; a = next(a for a in w.screen.areas if a.type=='VIEW_3D'); sp=a.spaces[0]; r=sp.region_3d
sp.shading.type='SOLID'; r.view_perspective='PERSP'; r.view_location = mathutils.Vector((0,0,0)); r.view_distance = 17; r.view_rotation = mathutils.Euler((1.1, 0, 0.8)).to_quaternion()
print("reset6")
