import sys, os, time; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from take import *
L = layout(); V = L['WINDOW']; U = L['UI']
scroll_until("clear_btn", U, step=10); park()
take_start("s4c_eiffel_overlay", L['client']); time.sleep(1.0)
try:
    hover(V, 0.5, 0.5, 0.5); human.key("home"); time.sleep(1.5); mark("home")
    human.orbit(120, 30, 1.8); time.sleep(0.5)
    mark("shift+b tower"); human.border_zoom(*center(V, 0.30, 0.38), *center(V, 0.52, 0.68), 1.1); time.sleep(3.0)
    mark("raster overlays"); park(); p = locate("overlays_off", U); human.click("left", p[0] - 55, p[1]); time.sleep(1.0); park()
    mark("overlay from presets"); bm = locate("bookmark", (U[0], p[1] + 20, U[2], 120)); human.click("left", *bm); time.sleep(1.2)
    human.key("i"); time.sleep(1.0); mark("IGN orthophotos WMTS")
    hover(V, 0.5, 0.6, 0.6); time.sleep(12.0); mark("orbit"); human.orbit(-140, 25, 2.8); time.sleep(1.0)
    human.wheel(2); time.sleep(5.0); human.orbit(90, -35, 2.2); time.sleep(4.0)
finally:
    take_stop("s4c_eiffel_overlay")
print(blender("import bpy; p=bpy.context.scene.ogc3dtiles; t=p.tilesets[0]; print(t.use_overlays, [(o.name,o.kind,o.enabled) for o in t.overlays], p.status_text)"))
