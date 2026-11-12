import sys, os, time; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from take import *
L = layout(); U = L['UI']; V = L['WINDOW']
human.click("left", *ui(160, 792)); time.sleep(1.0)                      # Atmosphere preset (sidebar scrolled by 12 clicks)
human.click("left", *SHADING['rendered']); time.sleep(3.0)
human.click("left", 1770, 77); time.sleep(0.3); human.type_text("Sun"); human.key("enter"); time.sleep(0.8)
shot(os.path.join(H, "outliner2.png"), (1579, 62, 339, 192)); shot(os.path.join(H, "cf5.png"), V)
print(blender("import bpy; print([o.name for o in bpy.data.objects if o.type=='LIGHT'], bpy.context.scene.render.engine)"))
