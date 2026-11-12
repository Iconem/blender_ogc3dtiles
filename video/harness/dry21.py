import sys, os, time; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from take import *
L = layout(); U = L['UI']; V = L['WINDOW']
human.click("left", *ui(29, 754)); time.sleep(0.5)
hover(U, 0.5, 0.5, 0.3); human.wheel(40, 0.03); time.sleep(0.5)
human.click("left", *W['start']); time.sleep(0.8); human.click("left", *W['start']); time.sleep(0.5)   # Stop, then Start
hover(V, 0.5, 0.5, 0.5); n = wait_visible(100, 40); print("visible", n); time.sleep(2)
hover(U, 0.5, 0.5, 0.3); human.wheel(-40, 0.03); time.sleep(0.6); shot(os.path.join(H, "ui_ei5.png"), U)
print(blender("import bpy; p=bpy.context.scene.ogc3dtiles; print(p.read_metadata, [c.name for c in p.meta_columns], p.meta_color, repr(p.meta_column))"))
