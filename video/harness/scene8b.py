import sys, os, time; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from take import *
L = layout(); V = L['WINDOW']; U = L['UI']; PR = (1579, 254, 339, 500)
take_start("s8b_splat_cycles", L['client']); time.sleep(1.0)
try:
    hover(V, 0.5, 0.5, 0.5); human.orbit(-60, 10, 1.5); time.sleep(0.8)
    mark("cycles"); human.click("left", 1826, 356); time.sleep(1.0); click_tpl("it_cycles", rect=PR); time.sleep(12.0)
    hover(V, 0.5, 0.5, 0.5); human.orbit(100, -20, 3.0); time.sleep(9.0)
    mark("back to eevee"); human.click("left", 1826, 356); time.sleep(1.0); click_tpl("it_eevee", rect=PR); time.sleep(3.0)
finally:
    take_stop("s8b_splat_cycles")
print(blender("import bpy; print(bpy.context.scene.render.engine)"))
