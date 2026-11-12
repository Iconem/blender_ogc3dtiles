import sys, os, time; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from take import *
L = layout(); V = L['WINDOW']; U = L['UI']
scroll_until("clear_btn", U, step=10); park(); wait_visible(60, 40)
take_start("s6b_clermont_suzanne_compositor", L['client']); time.sleep(1.0)
try:
    hover(V, 0.5, 0.5, 0.5); mark("shift+b cathedral"); human.border_zoom(*center(V, 0.40, 0.40), *center(V, 0.60, 0.62), 1.1); time.sleep(4.0)
    mark("demo graphs: suzanne on points"); p = scroll_until("demo_graphs", U); park(); human.click("left", *p); time.sleep(1.2)
    click_tpl("it_suzanne", rect=(U[0] - 300, p[1] - 150, U[2] + 300, 320)); time.sleep(4.0)
    hover(V, 0.5, 0.55, 0.6); human.orbit(140, -30, 2.5); time.sleep(1.0); human.wheel(2); time.sleep(2.0)
    mark("rendered"); human.click("left", *SHADING['rendered']); time.sleep(3.0)
    mark("beauty compositor"); b = scroll_until("beauty", U); park(); human.click("left", b[0] - 90, b[1]); time.sleep(4.0); park()
    b = scroll_until("beauty", U); park(); ed = (b[0] + 75, b[1] + 62)
    mark("edges: normal creases"); human.click("left", *ed); time.sleep(1.2); click_tpl("it_normal_creases", rect=(U[0] - 300, ed[1] - 200, U[2] + 300, 400)); time.sleep(4.0)
    hover(V, 0.5, 0.5, 0.6); human.orbit(-120, 20, 2.5); time.sleep(3.0)
finally:
    take_stop("s6b_clermont_suzanne_compositor")
print(blender("import bpy; p=bpy.context.scene.ogc3dtiles; print(p.tile_geometry, p.comp_enabled, p.comp_edges)"))
