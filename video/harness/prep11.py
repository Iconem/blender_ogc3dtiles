import bpy, mathutils
p = bpy.context.scene.ogc3dtiles
p.tilesets[0].name = "Google Photorealistic 3D Tiles"; p.view_source = 'VIEWPORT'
w = bpy.context.window_manager.windows[0]
areas = [a for a in w.screen.areas if a.type == 'VIEW_3D']
if len(areas) == 1:
    a = areas[0]
    with bpy.context.temp_override(window=w, screen=w.screen, area=a, region=next(r for r in a.regions if r.type=='WINDOW')):
        bpy.ops.screen.area_split(direction='VERTICAL', factor=0.5)
areas = sorted([a for a in w.screen.areas if a.type == 'VIEW_3D'], key=lambda a: a.x)
left, right = areas[0], areas[1]
left.spaces[0].shading.type = 'MATERIAL'; right.spaces[0].shading.type = 'MATERIAL'
left.spaces[0].show_region_ui = False; right.spaces[0].show_region_ui = True
cam = bpy.context.scene.camera; cam.location = (260, -330, 160); cam.rotation_euler = (1.15, 0, 0.65)
bpy.context.scene.render.resolution_x = 1920; bpy.context.scene.render.resolution_y = 1080
rl = left.spaces[0].region_3d; rl.view_perspective = 'CAMERA'
rr = right.spaces[0].region_3d; rr.view_perspective = 'ORTHO'; rr.view_rotation = mathutils.Euler((0.35, 0, 0)).to_quaternion(); rr.view_location = mathutils.Vector((0, -120, 0)); rr.view_distance = 1400
left.spaces[0].overlay.show_overlays = True
print("areas", [(a.x, a.width) for a in areas], "cam", cam.location[:])
