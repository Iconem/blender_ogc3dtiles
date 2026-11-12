import bpy, mathutils
p = bpy.context.scene.ogc3dtiles
# keep Google (entry 0) streaming, drop Bing, split the view: camera view left, fixed top view right centred on the camera
if p.is_streaming: bpy.ops.ogc3dtiles.stop_stream()
bpy.ops.ogc3dtiles.clear_tiles()
while len(p.tilesets) > 1: p.tilesets.remove(len(p.tilesets) - 1)
for o in list(bpy.data.objects):
    if o.name.startswith("3D Tiles"): bpy.data.objects.remove(o, do_unlink=True)
p.view_source = 'VIEWPORT'
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
sc = bpy.context.scene; cam = sc.camera; cam.location = (260, -330, 160); cam.rotation_euler = (1.15, 0, 0.65); cam.data.display_size = 100.0
sc.render.resolution_x = 1920; sc.render.resolution_y = 1080
rl = left.spaces[0].region_3d; rl.view_perspective = 'CAMERA'
rr = right.spaces[0].region_3d; rr.view_perspective = 'ORTHO'; rr.view_rotation = mathutils.Euler((0.0, 0, 0)).to_quaternion(); rr.view_location = mathutils.Vector((140, -170, 0)); rr.view_distance = 1000
bpy.ops.object.select_all(action='DESELECT')
bpy.ops.ogc3dtiles.start_stream()
print("prep11b areas", [(a.x, a.width) for a in areas], "cam", cam.location[:], [t.name for t in p.tilesets])
