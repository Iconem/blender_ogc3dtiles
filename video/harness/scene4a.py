import sys, os, time; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from take import *
TS = r"%OGC_SCRATCH%\dl\eiffel\3dtiles\tileset.json"
L = layout(); V = L['WINDOW']; U = L['UI']
hover(U, 0.5, 0.5, 0.3); human.wheel(40, 0.03); hover(V, 0.5, 0.5, 0.4); time.sleep(0.5)
take_start("s4a_eiffel_points", L['client']); time.sleep(1.0)
try:
    mark("paste path"); human.glide(*W['url'], 0.8); time.sleep(0.2); paste_into_field(*W['url'], TS); time.sleep(0.6)
    mark("add"); human.click("left", *W['add']); time.sleep(0.8)
    mark("rename"); human.dbl_click(*W1['entry']); time.sleep(0.4); human.key("a", mods=("ctrl",)); human.type_text("IGN LiDAR HD - Eiffel (COPC)"); human.key("enter"); time.sleep(0.6)
    mark("start"); human.click("left", *W['start']); time.sleep(0.5)
    hover(V, 0.5, 0.55, 0.8); n = wait_visible(60, 25); mark(f"{n} tiles"); time.sleep(1.0)
    human.key("home"); time.sleep(1.5); mark("home")
    human.orbit(120, 30, 1.8); time.sleep(0.5); mark("orbit")
    def tower_zoom(pad):
        b = json.loads(blender(open(os.path.join(H, "tower_box.py")).read()).strip().splitlines()[-1])
        fx0, fx1 = max(0.02, b["fx0"] - pad), min(0.98, b["fx1"] + pad); fy0, fy1 = max(0.02, b["fy0"] - pad), min(0.98, b["fy1"] + pad)
        human.border_zoom(*center(V, fx0, fy0), *center(V, fx1, fy1), 1.1)
    mark("shift+b tower"); tower_zoom(0.06); time.sleep(3.0)
    human.orbit(-60, -30, 1.6); time.sleep(1.5)
    mark("shift+b tighter"); tower_zoom(0.02); time.sleep(3.0)
    mark("scroll the sidebar to the Radius controls"); hover(U, 0.5, 0.5, 0.5); human.wheel(-7, 0.08); time.sleep(0.8); park()
    mark("radius modes"); rl = locate("radius_label", U); dd = (rl[0] + 120, rl[1])
    pop = (U[0] - 250, dd[1] - 160, U[2] + 250, 360)
    for label in ("it_attenuated", "it_uniform", "it_screen_pixels"):
        mark(label); human.click("left", *dd); time.sleep(1.0); click_tpl(label, rect=pop); time.sleep(3.0)
    hover(V, 0.5, 0.5, 0.5); human.orbit(100, 20, 2.0); time.sleep(1.5)
finally:
    take_stop("s4a_eiffel_points")
print(blender("import bpy; p=bpy.context.scene.ogc3dtiles; print(p.point_radius_mode)"))
