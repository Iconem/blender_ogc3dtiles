import bpy, mathutils
p = bpy.context.scene.ogc3dtiles
if p.is_streaming: bpy.ops.ogc3dtiles.stop_stream()
bpy.ops.ogc3dtiles.clear_tiles()
while p.tilesets: p.tilesets.remove(0)
p.tile_geometry = False; p.comp_enabled = False; p.comp_edges = 'EDL'; p.auto_relight = False; p.read_metadata = False; p.meta_color = False
for o in list(bpy.data.objects):
    if o.name.startswith("3D Tiles") or o.name.startswith("OGC3D"): bpy.data.objects.remove(o, do_unlink=True)
w0 = bpy.context.window_manager.windows[0]; a0 = next(a for a in w0.screen.areas if a.type=="VIEW_3D"); a0.spaces[0].show_region_ui = True
for ng in list(bpy.data.node_groups):
    if ng.name.startswith("OGC3D Tile Geometry"): bpy.data.node_groups.remove(ng)
p.origin_mode = 'CUSTOM'; p.origin_lat = 45.77874; p.origin_lon = 3.08583; p.origin_height = 462.0
p.tileset_url = "https://3d.craig.fr/datasets/Clermont/3dtiles/tileset.json"
bpy.ops.ogc3dtiles.tileset_add(); p.tilesets[0].name = "Clermont-Ferrand mesh"
bpy.context.scene.render.engine = 'BLENDER_EEVEE'
w = bpy.context.window_manager.windows[0]; a = next(a for a in w.screen.areas if a.type=='VIEW_3D'); sp=a.spaces[0]; r=sp.region_3d
sp.shading.type='MATERIAL'; r.view_perspective='PERSP'; r.view_location = mathutils.Vector((0,0,20)); r.view_distance = 420; r.view_rotation = mathutils.Euler((1.15, 0, 0.6)).to_quaternion()
pr = bpy.context.preferences.addons["bl_ext.user_default.ogc_3dtiles_streaming"].preferences
pr.library_files = r"%OGC_SCRATCH%\library\demo_library.json"
bpy.ops.ogc3dtiles.start_stream(); print("started clermont for s6", pr.library_files[-20:])
