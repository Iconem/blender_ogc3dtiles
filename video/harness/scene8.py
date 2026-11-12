import sys, os, time; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from take import *
L = layout(); V = L['WINDOW']; U = L['UI']
scroll_until("clear_btn", U, step=10); park(); n = wait_visible(200, 40); print("visible", n)
take_start("s8_splat_eevee_cycles", L['client']); time.sleep(1.0)
try:
    hover(V, 0.52, 0.6, 0.6); mark("shift+b facade"); human.border_zoom(*center(V, 0.41, 0.55), *center(V, 0.57, 0.78), 1.1); time.sleep(1.5)
    human.orbit(110, -70, 1.8); time.sleep(1.0)
    mark("ctrl+space maximise"); human.key("space", mods=("ctrl",)); time.sleep(1.5)
    L2 = layout(); V2 = L2['WINDOW']; hover(V2, 0.5, 0.5, 0.5); human.orbit(-180, -20, 3.0); time.sleep(0.5); human.wheel(2); time.sleep(1.5); human.orbit(120, 30, 2.5); time.sleep(1.0)
    mark("ctrl+space back"); human.key("space", mods=("ctrl",)); time.sleep(1.5)
    mark("cycles"); human.click("left", 1826, 356); time.sleep(0.9); human.click("left", 1779, 439); time.sleep(10.0)
    hover(V, 0.5, 0.5, 0.5); human.orbit(90, -20, 2.5); time.sleep(8.0)
    mark("back to eevee"); human.click("left", 1826, 356); time.sleep(0.9); human.click("left", 1779, 385); time.sleep(3.0)
finally:
    take_stop("s8_splat_eevee_cycles")
print(blender("import bpy; print(bpy.context.scene.render.engine)"))
