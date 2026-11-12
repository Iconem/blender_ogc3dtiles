import bpy
p = bpy.context.scene.ogc3dtiles; p.read_metadata = False; p.meta_color = False
for t in p.tilesets:
    t.use_overlays = False
    while t.overlays: t.overlays.remove(0)
w = bpy.context.window_manager.windows[0]; a = next(a for a in w.screen.areas if a.type=='VIEW_3D'); sp=a.spaces[0]
sp.shading.type = 'SOLID'
print("prepped 4b")
