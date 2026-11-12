import bpy, mathutils
p = bpy.context.scene.ogc3dtiles
if p.is_streaming: bpy.ops.ogc3dtiles.stop_stream()
bpy.ops.ogc3dtiles.clear_tiles()
while len(p.tilesets) > 1: p.tilesets.remove(len(p.tilesets) - 1)
p.tilesets[0].enabled = True; p.active_tileset = 0; p.tileset_url = ""
w = bpy.context.window_manager.windows[0]; a = next(a for a in w.screen.areas if a.type=='VIEW_3D'); sp=a.spaces[0]; r=sp.region_3d
r.view_location = mathutils.Vector((0,0,0)); r.view_distance = 500; r.view_rotation = mathutils.Euler((1.05, 0, 0.6)).to_quaternion()
bpy.ops.ogc3dtiles.start_stream(); print("prep12b", [(t.name, t.enabled) for t in p.tilesets])
