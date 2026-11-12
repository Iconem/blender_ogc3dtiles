import bpy, mathutils
p = bpy.context.scene.ogc3dtiles
if p.is_streaming: bpy.ops.ogc3dtiles.stop_stream()
bpy.ops.ogc3dtiles.clear_tiles()
for o in list(bpy.data.objects):
    if o.name.split('.')[0] in ("Cube", "Circle"): bpy.data.objects.remove(o, do_unlink=True)
for t in p.tilesets:
    while t.clip_polygons: t.clip_polygons.remove(0)
    t.use_clipping = False; t.enabled = False
p.origin_mode = 'AUTO'; bpy.ops.ogc3dtiles.origin_reset()
p.tileset_url = "https://s3.eu-west-2.wasabisys.com/ems-sgct-photomaillage/ODACIT/EMS_PM2022/tileset.json"
bpy.ops.ogc3dtiles.tileset_add(); t = p.tilesets[-1]; t.name = "Strasbourg photomesh 2022"
w = bpy.context.window_manager.windows[0]; a = next(a for a in w.screen.areas if a.type=='VIEW_3D'); sp=a.spaces[0]; r=sp.region_3d
sp.shading.type='MATERIAL'; r.view_location = mathutils.Vector((0,0,0)); r.view_distance = 3000; r.view_rotation = mathutils.Euler((1.0, 0, 0.6)).to_quaternion()
bpy.ops.ogc3dtiles.start_stream(); print("started strasbourg", [(x.name, x.enabled) for x in p.tilesets])
