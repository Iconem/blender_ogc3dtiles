import bpy
for o in list(bpy.data.objects):
    if o.name == "Cube": bpy.data.objects.remove(o, do_unlink=True)
p = bpy.context.scene.ogc3dtiles
p.origin_mode = 'AUTO'; p.tileset_url = ""
while p.tilesets: p.tilesets.remove(0)
win = bpy.context.window_manager.windows[0]
a = next(a for a in win.screen.areas if a.type=='VIEW_3D'); sp = a.spaces[0]
sp.shading.type = 'SOLID'; sp.region_3d.view_perspective = 'PERSP'
print("prepped", [i for i in dir(p) if 'splat' in i.lower() or 'point_radius' in i or 'shading' in i.lower()][:20])
