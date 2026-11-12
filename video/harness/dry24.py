import sys, os, time; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from take import *
L = layout(); V = L['WINDOW']; U = L['UI']
hover(V, 0.5, 0.5, 0.4); human.key("numpad0", mods=("ctrl", "alt")); time.sleep(1.5)
shot(os.path.join(H, "cam1.png"), V)
human.click("left", 227, 77); time.sleep(0.8); shot(os.path.join(H, "menu_view.png"), (150, 60, 700, 700)); human.key("esc"); time.sleep(0.3)
print(blender("import bpy\nw=bpy.context.window_manager.windows[0]\na=next(a for a in w.screen.areas if a.type=='VIEW_3D')\nprint(a.spaces[0].region_3d.view_perspective, bpy.context.scene.camera.location[:])"))
