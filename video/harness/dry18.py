import sys, os, time; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from take import *
L = layout(); U = L['UI']; V = L['WINDOW']
hover(V, 0.5, 0.5, 0.4); time.sleep(0.3); human.key("r"); time.sleep(0.2); human.key("x"); time.sleep(0.2)
human.glide(*center(V, 0.75, 0.5), 2.0); time.sleep(0.3); human.click("left"); time.sleep(1.5)
print(blender("import bpy; s=bpy.data.objects['OGC3D Sun']; print([round(v,2) for v in s.rotation_euler])"))
shot(os.path.join(H, "cf7.png"), V)
human.click("left", 1826, 356); time.sleep(0.8); shot(os.path.join(H, "props2.png"), (1579, 254, 339, 300)); human.key("esc")
