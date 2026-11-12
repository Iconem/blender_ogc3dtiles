import sys, os, time, json; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from take import *
# Eiffel points, redo: Start, Home, Shift+B on the tower and STAY on it; radius modes with larger sizes
# (attenuated 2..8 px, uniform 0.15 m, screen 4 px), orbits that keep the tower centred. Solid shading:
# IGN LiDAR HD has no RGB, so Material Preview / Rendered show a white sheet (the s4b 0:50 oddity).
L = layout(); V = L['WINDOW']; U = L['UI']
scroll_until("clear_btn", U, step=10); park(); hover(V, 0.5, 0.5, 0.4); time.sleep(0.5)
def tower_zoom(pad):
    b = json.loads(blender(open(os.path.join(H, "tower_box.py")).read()).strip().splitlines()[-1])
    fx0, fx1 = max(0.02, b["fx0"] - pad), min(0.98, b["fx1"] + pad); fy0, fy1 = max(0.02, b["fy0"] - pad), min(0.98, b["fy1"] + pad)
    human.border_zoom(*center(V, fx0, fy0), *center(V, fx1, fy1), 1.1)
take_start("s4d_eiffel_points", L['client']); time.sleep(0.8)
try:
    mark("start"); human.click("left", *W['start']); time.sleep(0.5)
    hover(V, 0.5, 0.55, 0.8); n = wait_visible(60, 25); mark(f"{n} tiles"); time.sleep(0.8)
    mark("home"); human.key("home"); time.sleep(1.2)
    hover(V, 0.5, 0.5, 0.4); mark("shift+b tower"); tower_zoom(0.06); time.sleep(2.5)
    mark("orbit"); human.orbit(-70, -25, 1.8); time.sleep(1.0)
    mark("shift+b tighter"); tower_zoom(0.02); time.sleep(2.5)
    human.orbit(50, 10, 1.4); time.sleep(1.0)
    mark("scroll the sidebar to the Radius controls"); hover(U, 0.5, 0.5, 0.5); time.sleep(0.4); human.wheel(-7, 0.08); time.sleep(0.8); park()
    mark("radius modes"); rl = locate("radius_label", U); dd = (rl[0] + 120, rl[1])
    pop = (U[0] - 250, dd[1] - 160, U[2] + 250, 360)
    for label in ("it_uniform", "it_screen_pixels", "it_attenuated"):
        mark(label); human.glide(*dd, 0.5); time.sleep(0.3); human.click("left"); time.sleep(1.0); click_tpl(label, rect=pop); time.sleep(1.2)
        hover(V, 0.5, 0.5, 0.5); human.orbit(40, -8, 1.4); time.sleep(1.2)
    hover(V, 0.5, 0.5, 0.5); human.wheel(2, 0.15); time.sleep(1.0); human.orbit(60, 12, 2.0); time.sleep(1.5)
finally:
    take_stop("s4d_eiffel_points")
print(blender("import bpy; p=bpy.context.scene.ogc3dtiles; print(p.point_radius_mode, p.point_adapt_max_px)"))
