import bpy, mathutils
key = open(r"%OGC_SCRATCH%\private_google_key.txt").read().strip()
p = bpy.context.scene.ogc3dtiles
if p.is_streaming: bpy.ops.ogc3dtiles.stop_stream()
bpy.ops.ogc3dtiles.clear_tiles()
while p.tilesets: p.tilesets.remove(0)
p.view_source = 'VIEWPORT'; p.auto_relight = False; p.comp_enabled = False
for o in list(bpy.data.objects):
    if o.name.startswith("3D Tiles") or o.name.split('.')[0] in ("Cube", "Circle") or o.name == "OGC3D Sun": bpy.data.objects.remove(o, do_unlink=True)
sc = bpy.context.scene; sc.render.engine = 'BLENDER_EEVEE'; sc.camera.data.display_size = 1.0
p.origin_mode = 'CUSTOM'; p.origin_lat = 51.5007; p.origin_lon = -0.1246; p.origin_height = 50.0
p.tileset_url = f"https://tile.googleapis.com/v1/3dtiles/root.json?key={key}"; bpy.ops.ogc3dtiles.tileset_add(); p.tilesets[0].name = "Google Photorealistic 3D Tiles"; p.tileset_url = ""
w = bpy.context.window_manager.windows[0]; a = next(a for a in w.screen.areas if a.type=='VIEW_3D'); sp=a.spaces[0]; r=sp.region_3d
sp.shading.type='MATERIAL'; r.view_perspective='PERSP'; r.view_location = mathutils.Vector((0,0,20)); r.view_distance = 500; r.view_rotation = mathutils.Euler((1.1, 0, 0.5)).to_quaternion()
sc.cursor.location = (0, 0, 0); bpy.ops.object.select_all(action='DESELECT')
for ar in w.screen.areas:
    if ar.type == 'PROPERTIES': ar.spaces[0].context = 'SCENE'
bpy.ops.ogc3dtiles.start_stream(); print("prep7e google london started")
