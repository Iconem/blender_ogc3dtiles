import sys, os, time; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from take import *
TS = r"%OGC_SCRATCH%\dl\sacre_coeur\3dtiles\tileset.json"
L = layout(); V = L['WINDOW']; U = L['UI']
scroll_until("clear_btn", U, step=10); park()
blender(f"import bpy; p=bpy.context.scene.ogc3dtiles; p.tileset_url=r'{TS}'; bpy.ops.ogc3dtiles.tileset_add(); p.tilesets[0].name='Sacre-Coeur splat'; p.tileset_url=''; print('ok')")
time.sleep(0.8); human.click("left", *W1['origin_hdr']); time.sleep(1.2); park(); shot("sc_ui1.png", U)
blender("import bpy; bpy.ops.ogc3dtiles.start_stream(); print('started')")
hover(V, 0.5, 0.5, 0.5); wait_visible(40, 40); time.sleep(2)
blender("""import bpy, json, mathutils
v=json.load(open(r'%s'))
w=bpy.context.window_manager.windows[0]; a=next(a for a in w.screen.areas if a.type=='VIEW_3D'); r=a.spaces[0].region_3d
r.view_location=mathutils.Vector(v['loc']); r.view_rotation=mathutils.Quaternion(v['rot']); r.view_distance=v['dist']; r.view_perspective='PERSP'
a.spaces[0].shading.type='RENDERED'; print('view set')""" % os.path.join(H, "view_fronton.json"))
time.sleep(4); shot("sc_vp1.png", V); print(V, U)
