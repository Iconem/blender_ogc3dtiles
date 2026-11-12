import sys, os, time, math, json; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from take import *
L = layout(); V = L['WINDOW']; U = L['UI']
# reset state left by dry runs: shader off, material panel collapsed, sidebar at top, sun pref on
blender("import bpy\np=bpy.context.scene.ogc3dtiles; p.auto_relight=False\nfor k,a in bpy.context.preferences.addons.items():\n    pr=a.preferences\n    if pr is not None and hasattr(pr,'beta_material_controls'): pr.beta_material_controls=True\nbpy.ops.object.select_all(action='DESELECT'); print('reset')")
time.sleep(0.8); scroll_until("clear_btn", U, step=10); park()
try:
    locate("shared_shader", U); m = locate("mat_header", U); human.click("left", *m); time.sleep(1.0); park(); print("collapsed material panel")
except LookupError: pass
hover(V, 0.5, 0.5, 0.4); time.sleep(0.5)
def arc(deg, dur, radius=260):
    cx, cy = center(V, 0.5, 0.5); x, y = human.pos(); a0 = math.atan2(y - cy, x - cx)
    n = max(8, int(abs(deg) / 6))
    for i in range(1, n + 1):
        a = a0 + math.radians(deg) * i / n; human.glide(round(cx + radius * math.cos(a)), round(cy + radius * math.sin(a)), dur / n, steps=4)
take_start("s3c_clermont_shader_sun_cycles", L['client']); time.sleep(1.0)
try:
    mark("material panel")
    for _ in range(3):
        m = scroll_until("mat_header", U); human.glide(*m, 0.5); time.sleep(0.3); human.click("left"); time.sleep(1.2); park()
        try: locate("shared_shader", U); break
        except LookupError: print("header click did not expand, retry")
    mark("shared shader nodes"); click_tpl("shared_shader", rect=U); time.sleep(2.5)
    mark("scroll sidebar"); hover(U, 0.5, 0.5, 0.4); human.wheel(-9, 0.05); time.sleep(0.9); park()
    mark("atmosphere preset"); at = scroll_until("atmo", U, step=-5); human.glide(*at, 0.5); time.sleep(0.3); human.click("left"); time.sleep(1.2)
    mark("rendered"); human.click("left", *SHADING['rendered']); time.sleep(4.0)
    park(); al = locate("albedo", U); sx, sy = al[0] + 100, al[1]
    mark("albedo to clay"); human.glide(sx, sy, 0.8); time.sleep(0.4); human.drag("left", -100, 0, 2.4); time.sleep(3.0)
    mark("albedo back"); human.drag("left", 100, 0, 1.8); time.sleep(2.0)
    mark("select sun"); blender("import bpy\ns=bpy.data.objects['OGC3D Sun']; bpy.ops.object.select_all(action='DESELECT'); s.select_set(True); bpy.context.view_layer.objects.active=s\nw=bpy.context.window_manager.windows[0]; a=next(a for a in w.screen.areas if a.type=='VIEW_3D'); s.location=a.spaces[0].region_3d.view_location; print('sun')")
    hover(V, 0.5, 0.5, 0.6); human.glide(*center(V, 0.5, 0.5), 0.3); human.move_rel(260, 0, 0.5); time.sleep(0.4)
    mark("rotate sun about Z"); human.key("r"); time.sleep(0.25); human.key("z"); time.sleep(0.3); arc(130, 4.0); time.sleep(0.4); human.click("left"); time.sleep(2.0)
    human.key("r"); time.sleep(0.25); human.key("z"); time.sleep(0.3); arc(-80, 3.0); time.sleep(0.4); human.click("left"); time.sleep(2.0)
    mark("cycles"); human.click("left", 1598, 360); time.sleep(0.8); human.click("left", 1826, 356); time.sleep(0.8); human.click("left", 1779, 439); time.sleep(12.0)
    hover(V, 0.5, 0.5, 0.5); human.orbit(80, -20, 2.0); time.sleep(6.0)
finally:
    take_stop("s3c_clermont_shader_sun_cycles")
print(blender("import bpy; print(bpy.context.scene.render.engine, [round(v,2) for v in bpy.data.objects['OGC3D Sun'].rotation_euler], bpy.context.scene.ogc3dtiles.auto_relight)"))
