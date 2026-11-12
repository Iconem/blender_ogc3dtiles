import sys, os, time; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from take import *
L = layout(); U = L['UI']; V = L['WINDOW']
human.click("left", *ui(160, 661)); time.sleep(1.0)
shot(os.path.join(H, "ui_cf5.png"), U)
human.click("left", *W['start']); time.sleep(0.5)
human.click("left", *SHADING['material']); time.sleep(0.5)
human.click("left", *W1['origin_hdr']); time.sleep(0.5)   # collapse Scene Origin
n = wait_visible(20, 40); print("visible", n)
human.click("left", *W1['origin_hdr'] )  # placeholder no-op? no: re-expand would shift. skip
time.sleep(0.3); human.click("left", *W1['origin_hdr']); time.sleep(0.6)   # toggle back to collapsed
shot(os.path.join(H, "ui_cf6.png"), U); shot(os.path.join(H, "cf2.png"), V)
print(blender("import bpy; p=bpy.context.scene.ogc3dtiles; print(p.origin_mode, p.origin_place, p.origin_lat, p.origin_lon, p.origin_height)"))
