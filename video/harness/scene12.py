import sys, os, time; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from take import *
L = layout(); V = L['WINDOW']; U = L['UI']
scroll_until("clear_btn", U, step=10); park(); wait_visible(150, 90); time.sleep(75)
take_start("s12_google_bing", L['client']); time.sleep(1.0)
try:
    hover(V, 0.5, 0.5, 0.5); mark("google: orbit the colosseum"); human.orbit(220, -30, 3.5); time.sleep(1.0); human.wheel(2); time.sleep(3.0); human.orbit(-150, 20, 3.0); time.sleep(2.0)
    mark("add bing via 3dtiled"); human.click("left", *W['add']); time.sleep(0.9)
    human.dbl_click(*ui(150, 156)); time.sleep(0.4); human.key("a", mods=("ctrl",)); human.type_text("Bing Maps 3D (3dtiled)"); human.key("enter"); time.sleep(0.6)
    uf = url_field(); human.glide(*uf, 0.6); time.sleep(0.2); paste_into_field(*uf, "%3DTILED%/bing/tileset.json"); time.sleep(0.8)
    mark("untick google, restart"); human.click("left", *ui(40, 136)); time.sleep(0.6); human.click("left", *W['start']); time.sleep(2.0); human.click("left", *W['start']); time.sleep(0.5)
    hover(V, 0.5, 0.55, 0.8); n = wait_visible(40, 60); mark(f"bing: {n} tiles"); time.sleep(12.0)
    human.orbit(180, -25, 3.5); time.sleep(6.0); human.wheel(-2); time.sleep(5.0)
finally:
    take_stop("s12_google_bing")
print(blender("import bpy; p=bpy.context.scene.ogc3dtiles; print([(t.name, t.enabled) for t in p.tilesets], p.status_text)"))
