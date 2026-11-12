import bpy, mathutils, json, os
p = bpy.context.scene.ogc3dtiles
if p.is_streaming: bpy.ops.ogc3dtiles.stop_stream()
bpy.ops.ogc3dtiles.clear_tiles()
while p.tilesets: p.tilesets.remove(0)
p.view_source = 'VIEWPORT'; p.read_metadata = False; p.meta_color = False; p.auto_relight = False; p.comp_enabled = False
for o in list(bpy.data.objects):
    if o.name.startswith("3D Tiles") or o.name.startswith("OGC3D Sun"): bpy.data.objects.remove(o, do_unlink=True)
p.origin_mode = 'AUTO'; bpy.ops.ogc3dtiles.origin_reset()
p.tileset_url = r"%OGC_SCRATCH%\dl\sacre_coeur\3dtiles\tileset.json"
bpy.ops.ogc3dtiles.tileset_add(); p.tilesets[0].name = "Sacre-Coeur splat"
sc = bpy.context.scene; sc.render.engine = 'BLENDER_EEVEE'
w = bpy.context.window_manager.windows[0]; a = next(a for a in w.screen.areas if a.type=='VIEW_3D'); sp=a.spaces[0]; r=sp.region_3d
sp.shading.type='RENDERED'; r.view_perspective='PERSP'
r.view_location = mathutils.Vector((0, 40, 25)); r.view_distance = 230; r.view_rotation = mathutils.Euler((1.25, 0, 3.14159)).to_quaternion()
for ar in w.screen.areas:
    if ar.type == 'PROPERTIES': ar.spaces[0].context = 'RENDER'
c = bpy.data.objects.get("Camera"); 
if c: c.location = (0, 300, 120)
bpy.ops.ogc3dtiles.start_stream(); print("started sacre")
