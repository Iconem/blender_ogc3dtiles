import sys, os, time; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from take import *
L = layout(); V = L['WINDOW']
def cam(): return blender("import bpy; c=bpy.context.scene.camera; print([round(v,1) for v in c.location])").strip()
def nav(y):
    human.click("left", 227, 77); time.sleep(0.7); human.glide(277, 430, 0.5); time.sleep(0.9); human.glide(600, 430, 0.4); time.sleep(0.3); human.glide(617, y, 0.6); time.sleep(0.3); human.click("left"); time.sleep(0.8)
print("before", cam()); hover(V, 0.5, 0.5, 0.3)
nav(948); human._key(human.VK["shift"]); human.hold("w", 2.0); human._key(human.VK["shift"], True); time.sleep(0.3); human.click("left"); time.sleep(0.8)
print("walk shift+W 2s", cam())
nav(923); time.sleep(0.5); human.hold("w", 3.0); time.sleep(0.3); human.click("left"); time.sleep(0.8)
print("fly W 3s", cam())
