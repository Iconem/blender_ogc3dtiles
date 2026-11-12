import bpy, mathutils
p = bpy.context.scene.ogc3dtiles
if p.is_streaming: bpy.ops.ogc3dtiles.stop_stream()
bpy.ops.ogc3dtiles.clear_tiles()
while p.tilesets: p.tilesets.remove(0)
p.tile_geometry = False; p.comp_enabled = False; p.auto_relight = False; p.read_metadata = False; p.meta_color = False
for o in list(bpy.data.objects):
    if o.name.startswith("3D Tiles") or o.name.startswith("OGC3D") or o.name.split('.')[0] in ("Cube", "Circle"): bpy.data.objects.remove(o, do_unlink=True)
w_ = bpy.data.worlds.get("World")
if w_: w_.use_nodes = False
bpy.context.scene.render.engine = 'BLENDER_EEVEE'
p.origin_mode = 'AUTO'; bpy.ops.ogc3dtiles.origin_reset(); p.place_query = ""
p.tileset_url = r"%OGC_SCRATCH%\dl\lublin\3dtiles_merged\tileset.json"
bpy.ops.ogc3dtiles.tileset_add(); p.tilesets[0].name = "Shramko 103M splats (Lublin)"; p.tileset_url = ""
w = bpy.context.window_manager.windows[0]; a = next(a for a in w.screen.areas if a.type=='VIEW_3D'); sp=a.spaces[0]; r=sp.region_3d
sp.shading.type='RENDERED'; r.view_perspective='PERSP'; r.view_location = mathutils.Vector((-500,-500,-190)); r.view_distance = 1800; r.view_rotation = mathutils.Euler((1.0, 0, 0.5)).to_quaternion(); sp.clip_end = 100000
for ar in w.screen.areas:
    if ar.type == 'PROPERTIES': ar.spaces[0].context = 'SCENE'
bpy.ops.object.select_all(action='DESELECT')
print("prep_lublin ready")
