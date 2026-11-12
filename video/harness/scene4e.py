import sys, os, time; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from take import *
# Eiffel classes, redo: feature metadata, reload, colour by classification, then Material Preview (Solid until then: these points have no RGB, Material Preview shows a white sheet).
# (The IGN WMTS overlay on these point tiles comes back as 2x2 px rasters: shown on the Clermont mesh in s4f instead.)
L = layout(); V = L['WINDOW']; U = L['UI']
def top(): scroll_until("clear_btn", U, step=10); park()
top()
take_start("s4e_eiffel_classes", L['client']); time.sleep(0.8)
try:
    hover(V, 0.5, 0.5, 0.4); human.orbit(-40, 8, 1.4); time.sleep(0.6)
    mark("metadata panel")
    for _ in range(3):   # the panel's open state persists between takes: click the header until the checkbox shows
        p = scroll_until("meta_header", U); human.glide(*p, 0.5); time.sleep(0.3); human.click("left"); time.sleep(1.0); park()
        try: locate("read_meta", U); break
        except LookupError: print("metadata header click did not expand, retry")
    mark("read feature metadata"); p = scroll_until("read_meta", U); human.click("left", p[0] - 85, p[1]); time.sleep(0.8)
    mark("stop, clear, start"); top(); human.click("left", *W['start']); time.sleep(0.8); human.click("left", *W['clear']); time.sleep(0.8); human.click("left", *W['start']); time.sleep(0.5)
    hover(V, 0.5, 0.6, 0.8); n = wait_visible(120, 40); mark(f"{n} tiles reloaded"); time.sleep(0.8)
    mark("color tiles by classification"); p = scroll_until("color_by", U); human.click("left", p[0] - 60, p[1]); time.sleep(2.0)
    mark("material preview"); human.click("left", *SHADING['material']); time.sleep(2.5)
    hover(V, 0.5, 0.5, 0.6); human.orbit(120, -25, 2.4); time.sleep(1.5); human.orbit(-60, 10, 1.6); time.sleep(2.0)
finally:
    take_stop("s4e_eiffel_classes")
print(blender("import bpy; p=bpy.context.scene.ogc3dtiles; t=p.tilesets[0]; print(p.read_metadata, p.meta_color, p.meta_column, t.use_overlays, [(o.name,o.kind,o.enabled) for o in t.overlays])"))
