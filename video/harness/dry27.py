import sys, os, time; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from take import *
L = layout(); V = L['WINDOW']
def cam(): return blender("import bpy; c=bpy.context.scene.camera; print([round(v,1) for v in c.location])").strip()
print("before", cam())
hover(V, 0.5, 0.5, 0.3)
human.click("left", 227, 77); time.sleep(0.7); human.glide(277, 430, 0.5); time.sleep(0.9); human.glide(600, 430, 0.4); time.sleep(0.3); human.glide(617, 948, 0.6); time.sleep(0.3); human.click("left"); time.sleep(0.8)
human.wheel(8, 0.08); time.sleep(0.3); human.hold("w", 2.0); time.sleep(0.3); human.click("left"); time.sleep(0.8)
print("after wheel 8 + W 2s", cam())
