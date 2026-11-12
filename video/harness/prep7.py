import bpy, mathutils
p = bpy.context.scene.ogc3dtiles
p.tile_geometry = False; p.comp_enabled = False; p.comp_edges = 'EDL'
for o in list(bpy.data.objects):
    if o.name.startswith("OGC3D Suzanne") or o.name in ("Cube", "Circle", "Plane"): bpy.data.objects.remove(o, do_unlink=True)
for t in p.tilesets:
    while t.clip_polygons: t.clip_polygons.remove(0)
    t.use_clipping = False
w = bpy.context.window_manager.windows[0]; a = next(a for a in w.screen.areas if a.type=='VIEW_3D'); sp=a.spaces[0]; r=sp.region_3d
sp.shading.type='MATERIAL'; r.view_perspective='PERSP'; r.view_location = mathutils.Vector((0,0,20)); r.view_distance = 420; r.view_rotation = mathutils.Euler((1.15, 0, 0.6)).to_quaternion()
bpy.ops.object.select_all(action='DESELECT')
print("prep7", p.is_streaming)
