import bpy, mathutils, json
P = json.load(open(r"%OGC_SCRATCH%\private_sanpietro.json"))
p = bpy.context.scene.ogc3dtiles
if p.is_streaming: bpy.ops.ogc3dtiles.stop_stream()
bpy.ops.ogc3dtiles.clear_tiles()
while p.tilesets: p.tilesets.remove(0)
for o in list(bpy.data.objects):
    if o.name.startswith("3D Tiles"): bpy.data.objects.remove(o, do_unlink=True)
p.read_metadata = False; p.meta_color = False; p.tile_geometry = False; p.comp_enabled = False; p.auto_relight = False
for ng in list(bpy.data.node_groups):
    if ng.name.startswith('OGC3D Tile Geometry'): bpy.data.node_groups.remove(ng)
p.origin_mode = 'AUTO'; bpy.ops.ogc3dtiles.origin_reset()
p.tileset_url = P["sp_ext"]["url"]; bpy.ops.ogc3dtiles.tileset_add(); p.tilesets[0].name = "San Pietro - exterior (Iconem)"
p.tileset_url = P["sp_int"]["url"]; bpy.ops.ogc3dtiles.tileset_add(); p.tilesets[1].name = "San Pietro - interior (Iconem)"; p.tilesets[1].enabled = False
p.tileset_url = ""; p.active_tileset = 0
w = bpy.context.window_manager.windows[0]; a = next(a for a in w.screen.areas if a.type=='VIEW_3D'); sp=a.spaces[0]; r=sp.region_3d
sp.shading.type='MATERIAL'; r.view_location = mathutils.Vector((0,0,40)); r.view_distance = 600; r.view_rotation = mathutils.Euler((1.1, 0, 0.5)).to_quaternion()
bpy.ops.ogc3dtiles.start_stream(); print("started san pietro ext")
