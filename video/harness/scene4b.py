import sys, os, time; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from take import *
L = layout(); V = L['WINDOW']; U = L['UI']
def top(): scroll_until("clear_btn", U, step=10); park()
top(); p = locate("meta_header", U) if False else None
take_start("s4b_eiffel_classes_overlay", L['client']); time.sleep(1.0)
try:
    hover(V, 0.5, 0.5, 0.5); human.key("home"); time.sleep(1.5); mark("home")
    human.orbit(120, 30, 1.8); time.sleep(0.5)
    mark("shift+b tower"); human.border_zoom(*center(V, 0.30, 0.38), *center(V, 0.52, 0.68), 1.1); time.sleep(2.5)
    mark("material preview"); human.click("left", *SHADING['material']); time.sleep(1.5)
    mark("metadata panel"); p = scroll_until("meta_header", U); human.click("left", *p); time.sleep(0.8)
    mark("read feature metadata"); p = scroll_until("read_meta", U); human.click("left", p[0] - 85, p[1]); time.sleep(0.8)
    mark("stop, clear, start"); top(); human.click("left", *W['start']); time.sleep(0.8); human.click("left", *W['clear']); time.sleep(0.8); human.click("left", *W['start']); time.sleep(0.5)
    hover(V, 0.5, 0.6, 0.8); n = wait_visible(120, 40); mark(f"{n} tiles reloaded"); time.sleep(1.0)
    mark("color tiles by classification"); p = scroll_until("color_by", U); human.click("left", p[0] - 60, p[1]); time.sleep(5.0)
    hover(V, 0.5, 0.5, 0.6); human.orbit(140, -30, 2.4); time.sleep(1.5)
    mark("raster overlays"); top(); p = locate("overlays_off", U); human.click("left", p[0] - 55, p[1]); time.sleep(1.0); park()
    mark("overlay from presets"); bm = locate("bookmark", (U[0], p[1] + 20, U[2], 120)); human.click("left", *bm); time.sleep(1.0)
    human.key("i"); time.sleep(1.0); mark("IGN orthophotos WMTS")
    hover(V, 0.5, 0.5, 0.6); time.sleep(6.0); human.orbit(-120, 20, 2.5); time.sleep(0.5); human.wheel(2); time.sleep(4.0)
    human.orbit(80, -40, 2.0); time.sleep(3.0)
finally:
    take_stop("s4b_eiffel_classes_overlay")
print(blender("import bpy; p=bpy.context.scene.ogc3dtiles; t=p.tilesets[0]; print(p.read_metadata, p.meta_color, p.meta_column, t.use_overlays, [(o.name,o.kind,o.enabled) for o in t.overlays])"))
