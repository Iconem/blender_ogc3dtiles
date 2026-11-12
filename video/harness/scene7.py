import sys, os, time; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from take import *
L = layout(); V = L['WINDOW']; U = L['UI']
scroll_until("clear_btn", U, step=10); park(); wait_visible(60, 40)
def add_mesh(item):
    hover(V, 0.42, 0.5, 0.4); human.key("a", mods=("shift",)); time.sleep(0.9)
    x, y = human.pos(); m = locate("it_mesh", (x - 150, y - 100, 500, 400)); human.glide(*m, 0.5); time.sleep(0.9)
    it = locate(item, (x - 150, y - 150, 700, 500)); human.glide(m[0] + 120, m[1], 0.25); human.glide(*it, 0.4); time.sleep(0.3); human.click("left"); time.sleep(0.8)
take_start("s7_clipping", L['client']); time.sleep(1.0)
try:
    mark("add cube"); add_mesh("it_cube")
    mark("scale cube"); hover(V, 0.6, 0.5, 0.4); human.key("s"); time.sleep(0.3); human.type_text("70"); time.sleep(0.3); human.key("enter"); time.sleep(1.0)
    mark("display as bounds"); blender(open(os.path.join(H, "bounds.py")).read()); time.sleep(1.0)
    mark("clipping on"); park(); c = locate("clipping_off", U); human.click("left", c[0] - 30, c[1]); time.sleep(1.0)
    mark("add cube as clipping box"); human.click("left", ui(286, 0)[0], c[1] + 106); time.sleep(3.0)
    hover(V, 0.6, 0.5, 0.5); human.orbit(90, -30, 2.5); time.sleep(1.5)
    mark("grab cube"); human.key("g"); time.sleep(0.3); human.glide(*center(V, 0.72, 0.42), 3.5); time.sleep(0.3); human.glide(*center(V, 0.5, 0.6), 3.5); time.sleep(0.3); human.click("left"); time.sleep(1.5)
    mark("rotate cube"); human.key("r"); time.sleep(0.2); human.key("z"); time.sleep(0.2); human.glide(*center(V, 0.75, 0.55), 2.5); time.sleep(0.3); human.click("left"); time.sleep(1.0)
    human.orbit(-120, 20, 3.0); time.sleep(2.0)
    mark("add circle polygon"); add_mesh("it_circle")
    blender(open(os.path.join(H, "bounds.py")).read())
    hover(V, 0.6, 0.5, 0.4); human.key("s"); time.sleep(0.3); human.type_text("90"); time.sleep(0.3); human.key("enter"); time.sleep(1.0)
    mark("add circle as clip polygon"); park(); human.click("left", ui(286, 0)[0], c[1] + 106); time.sleep(3.0)
    hover(V, 0.6, 0.5, 0.5); human.key("g"); time.sleep(0.3); human.glide(*center(V, 0.35, 0.4), 4.0); time.sleep(0.3); human.click("left"); time.sleep(2.0)
    human.orbit(90, -25, 2.5); time.sleep(3.0)
finally:
    take_stop("s7_clipping")
print(blender("import bpy; p=bpy.context.scene.ogc3dtiles; t=p.tilesets[0]; print(t.use_clipping, [(cp.obj.name if cp.obj else None, cp.shape) for cp in t.clip_polygons])"))
