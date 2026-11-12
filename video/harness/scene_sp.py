import sys, os, time; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from take import *
# San Pietro (Iconem share links): exterior arena mesh streaming, Shift+B, orbit; then the interior
# entry switched on with its eye, exterior off, zoom inside. Prep: dry_sp.py (both entries added, ext started).
L = layout(); V = L['WINDOW']; U = L['UI']
scroll_until("clear_btn", U, step=10); park(); wait_visible(30, 60)
hover(V, 0.5, 0.5, 0.4); time.sleep(0.4)
take_start("s14_san_pietro", L['client']); time.sleep(0.8)
try:
    mark("home"); human.key("home"); time.sleep(2.0)
    mark("orbit"); human.orbit(80, -20, 2.0); time.sleep(2.0)
    mark("shift+b arena"); human.border_zoom(*center(V, 0.35, 0.35), *center(V, 0.65, 0.68), 1.1); time.sleep(4.0)
    human.orbit(-90, 15, 2.4); time.sleep(2.5)
    mark("interior on"); human.click("left", *ui(40, 155)); time.sleep(0.8)
    mark("exterior off"); human.click("left", *ui(40, 136)); time.sleep(0.8)
    hover(V, 0.5, 0.5, 0.5); n = wait_visible(10, 40); mark(f"{n} interior tiles"); time.sleep(1.0)
    mark("home"); human.key("home"); time.sleep(2.0)
    mark("shift+b interior"); human.border_zoom(*center(V, 0.38, 0.38), *center(V, 0.62, 0.65), 1.1); time.sleep(3.0)
    human.orbit(120, -10, 3.0); time.sleep(2.0); human.wheel(2, 0.2); time.sleep(2.0); human.orbit(-60, 20, 2.0); time.sleep(2.0)
finally:
    take_stop("s14_san_pietro")
print(blender("import bpy; p=bpy.context.scene.ogc3dtiles; print([(t.name[:20], t.enabled) for t in p.tilesets], p.status_text if hasattr(p,'status_text') else '')"))
