import sys, os, time; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from take import *
# Shramko 103 M-splat Lublin scan as 3D Tiles (merged tiles from 3dtiled): Start with Auto origin, Home,
# wait for the coarse levels, Shift+B twice into the old town, orbit while the fine tiles refine.
# Prep: prep_lublin.py (tileset added, not started, Rendered shading).
L = layout(); V = L['WINDOW']; U = L['UI']
scroll_until("clear_btn", U, step=10); park(); hover(V, 0.5, 0.5, 0.4); time.sleep(0.4)
take_start("s15_shramko_lublin", L['client']); time.sleep(0.8)
try:
    mark("start"); human.click("left", *W['start']); time.sleep(0.5)
    hover(V, 0.5, 0.55, 0.8); n = wait_visible(25, 60); mark(f"{n} coarse tiles"); time.sleep(1.5)
    mark("home"); human.key("home"); time.sleep(3.0)
    mark("orbit"); human.orbit(70, -15, 2.0); time.sleep(3.0)
    mark("shift+b"); human.border_zoom(*center(V, 0.36, 0.36), *center(V, 0.62, 0.64), 1.1); time.sleep(6.0)
    human.orbit(-60, 10, 2.0); time.sleep(5.0)
    mark("shift+b tighter"); human.border_zoom(*center(V, 0.38, 0.40), *center(V, 0.60, 0.62), 1.1); time.sleep(8.0)
    human.orbit(90, -20, 3.0); time.sleep(6.0); human.wheel(2, 0.2); time.sleep(6.0)
finally:
    take_stop("s15_shramko_lublin")
print(blender("import bpy; p=bpy.context.scene.ogc3dtiles; print(sum(1 for o in bpy.data.objects if o.name.startswith('t_') and not o.hide_viewport), getattr(p,'status_text',''))"))
