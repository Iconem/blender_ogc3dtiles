import sys, os, time; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from take import *
L = layout(); U = L['UI']; V = L['WINDOW']
human.click("left", 1699, 133); time.sleep(0.5)
hover(V, 0.5, 0.5, 0.5); time.sleep(0.3); human.key("r"); time.sleep(0.2); human.key("x"); time.sleep(0.2)
human.glide(*center(V, 0.5, 0.75), 2.0); time.sleep(0.3); human.click("left"); time.sleep(2.0)
shot(os.path.join(H, "cf6.png"), V)
human.click("left", 1598, 360); time.sleep(0.8)
shot(os.path.join(H, "props.png"), (1579, 254, 339, 500))
print(blender("import bpy; s=bpy.data.objects['OGC3D Sun']; print([round(v,2) for v in s.rotation_euler], bpy.context.view_layer.objects.active.name)"))
