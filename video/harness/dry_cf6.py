import sys, os, time; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from take import *
print(blender("""import bpy
ok=[]
for k,a in bpy.context.preferences.addons.items():
    pr=a.preferences
    if pr is not None and hasattr(pr,'beta_material_controls'): pr.beta_material_controls=True; ok.append(k)
print('set on', ok)"""))
L = layout(); V = L['WINDOW']; U = L['UI']
park(); time.sleep(1.0); shot("cf6_ui.png", U)
