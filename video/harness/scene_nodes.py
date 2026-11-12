import sys, os, time, math; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from take import *
# Shared nodes, one take: shader (atmosphere, clay slider), geometry (Suzanne on points), compositor
# (beauty, normal creases), then EEVEE vs Cycles on the same view.
L = layout(); V = L['WINDOW']; U = L['UI']; PR = (1579, 254, 339, 500)
scroll_until("clear_btn", U, step=10); park(); wait_visible(40, 60)
try:
    locate("shared_shader", U); m = locate("mat_header", U); human.click("left", *m); time.sleep(1.0); park()
except LookupError: pass
hover(V, 0.5, 0.5, 0.4); time.sleep(0.4)
take_start("s13_shared_nodes_eevee_cycles", L['client']); time.sleep(0.8)
try:
    mark("shift+b cathedral"); human.border_zoom(*center(V, 0.40, 0.40), *center(V, 0.60, 0.62), 1.1); time.sleep(2.5)
    mark("material panel")
    for _ in range(3):
        m = scroll_until("mat_header", U); human.glide(*m, 0.5); time.sleep(0.3); human.click("left"); time.sleep(1.0); park()
        try: locate("shared_shader", U); break
        except LookupError: print("header click did not expand, retry")
    mark("shared shader nodes"); click_tpl("shared_shader", rect=U); time.sleep(2.0)
    mark("atmosphere preset"); at = scroll_until("atmo", U, step=-5); human.glide(*at, 0.5); time.sleep(0.3); human.click("left"); time.sleep(1.0)
    mark("rendered"); human.click("left", *SHADING['rendered']); time.sleep(3.0)
    park(); al = locate("albedo", U); sx, sy = al[0] + 100, al[1]
    mark("albedo to clay"); human.glide(sx, sy, 0.7); time.sleep(0.3); human.drag("left", -100, 0, 2.0); time.sleep(2.0)
    mark("albedo back"); human.drag("left", 100, 0, 1.5); time.sleep(1.5)
    mark("demo graphs: suzanne on points"); p = scroll_until("demo_graphs", U); park(); human.glide(*p, 0.5); time.sleep(0.3); human.click("left"); time.sleep(1.0)
    click_tpl("it_suzanne", rect=(U[0] - 300, p[1] - 150, U[2] + 300, 320)); time.sleep(3.0)
    hover(V, 0.5, 0.55, 0.6); human.orbit(100, -25, 2.2); time.sleep(1.5)
    mark("beauty compositor"); b = scroll_until("beauty", U); park(); human.click("left", b[0] - 90, b[1]); time.sleep(3.0); park()
    b = scroll_until("beauty", U); park(); ed = (b[0] + 75, b[1] + 62)
    mark("edges: normal creases"); human.click("left", *ed); time.sleep(1.0)
    try: click_tpl("it_normal_creases", rect=(U[0] - 300, ed[1] - 260, U[2] + 300, 520), tries=2)
    except LookupError:
        human.key("esc"); time.sleep(0.4); blender("import bpy; bpy.context.scene.ogc3dtiles.comp_edges='NORMAL'; print('creases via bpy')")
    time.sleep(3.0)
    hover(V, 0.5, 0.5, 0.6); human.orbit(-80, 15, 2.0); time.sleep(1.5)
    mark("cycles"); human.click("left", 1826, 356); time.sleep(1.0)
    try: click_tpl("it_cycles", rect=PR, tries=2)
    except LookupError:
        human.key("esc"); time.sleep(0.4); blender("import bpy; bpy.context.scene.render.engine='CYCLES'; print('cycles via bpy')")
    time.sleep(10.0)
    hover(V, 0.5, 0.5, 0.5); human.orbit(60, -12, 2.5); time.sleep(8.0)
    mark("back to eevee"); human.click("left", 1826, 356); time.sleep(1.0)
    try: click_tpl("it_eevee", rect=PR, tries=2)
    except LookupError:
        human.key("esc"); time.sleep(0.4); blender("import bpy; bpy.context.scene.render.engine='BLENDER_EEVEE'; print('eevee via bpy')")
    time.sleep(3.0)
finally:
    take_stop("s13_shared_nodes_eevee_cycles")
print(blender("import bpy; p=bpy.context.scene.ogc3dtiles; print(bpy.context.scene.render.engine, p.tile_geometry, p.comp_enabled, p.comp_edges)"))
