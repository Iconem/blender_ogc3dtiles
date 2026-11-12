import sys, os, time; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from take import *
# Raster overlay on the Clermont photomesh: IGN orthophotos draped live over the tiles, opacity moved.
# (On the IGN COPC point tiles cesium-native upsamples thousands of tiles and hands back 2x2 px rasters,
# so the overlay is shown on a mesh.) Prep: prep_nodes.py, Material Preview, tiles loaded.
L = layout(); V = L['WINDOW']; U = L['UI']
scroll_until("clear_btn", U, step=10); park(); wait_visible(40, 60); hover(V, 0.5, 0.5, 0.4); time.sleep(0.4)
take_start("s4f_clermont_overlay", L['client']); time.sleep(0.8)
try:
    mark("shift+b"); human.border_zoom(*center(V, 0.30, 0.30), *center(V, 0.70, 0.72), 1.1); time.sleep(2.5)
    mark("raster overlays"); p = locate("overlays_off", U); human.click("left", p[0] - 55, p[1]); time.sleep(1.0); park()
    mark("overlay from presets"); bm = locate("bookmark", (U[0], p[1] + 20, U[2], 120)); human.click("left", *bm); time.sleep(1.0)
    human.key("i"); time.sleep(0.8); mark("IGN orthophotos WMTS")
    hover(V, 0.5, 0.5, 0.6); time.sleep(6.0); human.orbit(80, -15, 2.4); time.sleep(3.0)
    mark("opacity"); park()
    op = blender("import bpy; p=bpy.context.scene.ogc3dtiles; t=p.tilesets[0]; print(t.overlays[0].alpha)").strip()
    try:
        sl = locate("overlay_opacity", U); human.glide(*sl, 0.6); time.sleep(0.3); human.drag("left", -120, 0, 2.0); time.sleep(2.0); human.drag("left", 120, 0, 1.5); time.sleep(1.5)
    except Exception as e:
        print("opacity slider skipped:", e)
    hover(V, 0.5, 0.5, 0.5); human.orbit(-70, 12, 2.2); time.sleep(2.0); human.wheel(2, 0.2); time.sleep(3.0)
finally:
    take_stop("s4f_clermont_overlay")
print(blender("import bpy; p=bpy.context.scene.ogc3dtiles; t=p.tilesets[0]; print(t.use_overlays, [(o.name,o.enabled,o.alpha) for o in t.overlays])"))
