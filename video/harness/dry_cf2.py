import bpy, mathutils
p = bpy.context.scene.ogc3dtiles
if p.is_streaming: bpy.ops.ogc3dtiles.stop_stream()
bpy.ops.ogc3dtiles.clear_tiles()
p.origin_mode = 'CUSTOM'; p.origin_lat = 45.77865; p.origin_lon = 3.08625; p.origin_height = 400
w = bpy.context.window_manager.windows[0]; a = next(a for a in w.screen.areas if a.type=='VIEW_3D'); sp=a.spaces[0]; r=sp.region_3d
sp.shading.type='MATERIAL'; r.view_location = mathutils.Vector((0,0,20)); r.view_distance = 500; r.view_rotation = mathutils.Euler((0.9, 0, 0.5)).to_quaternion()
bpy.ops.ogc3dtiles.start_stream(); print("started", p.origin_lat, p.origin_lon)
