import bpy, mathutils
p = bpy.context.scene.ogc3dtiles
if p.is_streaming: bpy.ops.ogc3dtiles.stop_stream()
bpy.ops.ogc3dtiles.clear_tiles()
while p.tilesets: p.tilesets.remove(0)
p.auto_relight = False; p.comp_enabled = False
for o in list(bpy.data.objects):
    if o.name.startswith("3D Tiles") or o.name == "OGC3D Sun": bpy.data.objects.remove(o, do_unlink=True)
w_ = bpy.data.worlds.get("World")
if w_: w_.use_nodes = False
sc = bpy.context.scene; sc.render.engine = 'BLENDER_EEVEE'
p.origin_mode = 'AUTO'; bpy.ops.ogc3dtiles.origin_reset(); p.tileset_url = ""; p.place_query = ""
w = bpy.context.window_manager.windows[0]; a = next(a for a in w.screen.areas if a.type=='VIEW_3D'); sp=a.spaces[0]; r=sp.region_3d
sp.shading.type='SOLID'; r.view_location = mathutils.Vector((0,0,0)); r.view_distance = 900; r.view_rotation = mathutils.Euler((0.95, 0, 0.5)).to_quaternion()
for ar in w.screen.areas:
    if ar.type == 'PROPERTIES': ar.spaces[0].context = 'SCENE'
print("reset")
