import sys, os, time; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from take import *
TS = r"%OGC_SCRATCH%\dl\sacre_coeur\3dtiles\tileset.json"
L = layout(); V = L['WINDOW']; U = L['UI']
scroll_until("clear_btn", U, step=10); park()
take_start("s1c_sacre_coeur_full", L['client']); time.sleep(1.0)
try:
    mark("paste tileset path"); human.glide(*W['url'], 0.8); time.sleep(0.3); paste_into_field(*W['url'], TS); time.sleep(0.7)
    mark("add"); human.click("left", *W['add']); time.sleep(0.9)
    mark("rename"); human.dbl_click(*W1['entry']); time.sleep(0.4); human.key("a", mods=("ctrl",)); human.type_text("Sacre-Coeur splat"); human.key("enter"); time.sleep(0.6)
    mark("scene origin: auto"); human.click("left", *W1['origin_hdr']); time.sleep(1.2)
    mark("start"); human.click("left", *W['start']); time.sleep(0.4)
    hover(V, 0.5, 0.55, 0.9); n = wait_visible(40, 30); mark(f"{n} tiles"); time.sleep(1.0)
    human.key("home"); time.sleep(1.5); mark("home")
    mark("rendered"); human.click("left", *SHADING['rendered']); time.sleep(2.5)
    hover(V, 0.5, 0.5, 0.5); mark("orbit to the north side"); human.orbit(-420, 20, 3.0); time.sleep(1.0)
    blender("import bpy, mathutils\nw=bpy.context.window_manager.windows[0]\na=next(a for a in w.screen.areas if a.type=='VIEW_3D')\nr=a.spaces[0].region_3d\nprint(round(r.view_distance), [round(v) for v in r.view_location], [round(v,2) for v in r.view_rotation.to_euler()])")
    mark("shift+b facade"); human.border_zoom(*center(V, 0.41, 0.50), *center(V, 0.57, 0.75), 1.1); time.sleep(1.6)
    mark("orbit"); human.orbit(110, -70, 1.8); time.sleep(1.2)
    mark("shift+b horses"); human.border_zoom(*center(V, 0.33, 0.56), *center(V, 0.60, 0.76), 1.1); time.sleep(1.8)
    mark("orbit around"); human.orbit(-200, -25, 3.2); time.sleep(0.8); human.wheel(2); time.sleep(1.0); human.orbit(150, 15, 2.6); time.sleep(1.5)
finally:
    take_stop("s1c_sacre_coeur_full")
