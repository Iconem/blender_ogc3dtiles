import sys, os, time; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from take import *
L = layout(); V = L['WINDOW']; U = L['UI']
scroll_until("clear_btn", U, step=10); park()
def nav_walk():
    human.click("left", 227, 77); time.sleep(0.7); human.glide(277, 430, 0.5); time.sleep(0.9); human.glide(600, 430, 0.4); time.sleep(0.3); human.glide(617, 948, 0.6); time.sleep(0.3); human.click("left"); time.sleep(0.8)
def run(secs): human._key(human.VK["shift"]); human.hold("w", secs); human._key(human.VK["shift"], True)
take_start("s5_camera_stream", L['client']); time.sleep(1.0)
try:
    hover(V, 0.5, 0.5, 0.5); human.orbit(40, -15, 1.2); time.sleep(0.6)
    mark("camera to view"); human.key("numpad0", mods=("ctrl", "alt")); time.sleep(2.0)
    mark("stream for: scene camera"); park(); sf = locate("stream_for", U); dd = (sf[0] + 130, sf[1]); human.click("left", *dd); time.sleep(1.0)
    click_tpl("it_scene_camera", rect=(U[0] - 250, dd[1] - 140, U[2] + 250, 300)); time.sleep(2.5)
    hover(V, 0.5, 0.5, 0.5); mark("walk navigation"); nav_walk()
    human.move_rel(110, 10, 2.0); time.sleep(0.3); run(4.5); time.sleep(0.3)
    human.move_rel(-220, 50, 2.5); time.sleep(0.3); run(3.0); time.sleep(0.2); human.move_rel(60, -70, 1.8); time.sleep(0.5)
    human.click("left"); time.sleep(1.5); mark("walk done")
    mark("leave camera, top view"); human.key("numpad0"); time.sleep(1.0); human.key("numpad7"); time.sleep(1.2); human.wheel(-7, 0.15); time.sleep(2.5)
    mark("select camera"); human.click("left", 1700, 158); time.sleep(0.6)
    hover(V, 0.5, 0.5, 0.5); mark("grab camera"); human.key("g"); time.sleep(0.3); human.glide(*center(V, 0.72, 0.45), 6.0); time.sleep(0.5); human.click("left"); time.sleep(3.0)
    human.key("g"); time.sleep(0.3); human.glide(*center(V, 0.35, 0.6), 6.0); time.sleep(0.5); human.click("left"); time.sleep(4.0)
finally:
    take_stop("s5_camera_stream")
print(blender("import bpy; p=bpy.context.scene.ogc3dtiles; print(p.view_source, [round(v,1) for v in bpy.context.scene.camera.location])"))
