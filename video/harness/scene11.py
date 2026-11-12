import sys, os, time; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from take import *
L = layout(); U = L['UI']; C = L['client']
LV = (2, 62, 786, 971); RV = (791, 62, 785, 971)    # left and right 3D views (screen px)
scroll_until("clear_btn", U, step=10); park()
def nav_walk():
    hover(LV, 0.5, 0.5, 0.4); human.key("f3"); time.sleep(0.8); human.type_text("walk navigation"); time.sleep(1.2); human.key("enter"); time.sleep(0.8)
def run(secs): human._key(human.VK["shift"]); human.hold("w", secs); human._key(human.VK["shift"], True)
take_start("s11_google_split_camera", C); time.sleep(1.5)
try:
    mark("LOD panel"); park()
    try: sf = locate("stream_for", U)
    except LookupError:
        lh = scroll_until("lod_header", U); human.click("left", *lh); time.sleep(0.9); park(); sf = locate("stream_for", U)
    mark("stream for: scene camera")
    dd = (sf[0] + 130, sf[1]); human.click("left", *dd); time.sleep(1.0); click_tpl("it_scene_camera", rect=(U[0] - 250, dd[1] - 140, U[2] + 250, 300)); time.sleep(3.0)
    mark("walk navigation in the camera"); nav_walk()
    human.move_rel(90, 0, 2.0); time.sleep(0.3); run(5.0); time.sleep(0.3); human.move_rel(-200, 40, 3.0); time.sleep(0.3); run(4.0); time.sleep(0.3); human.move_rel(80, -60, 2.0); time.sleep(0.5)
    human.click("left"); time.sleep(2.0); mark("walk done")
    mark("select the camera, grab it in the top view"); blender(open(os.path.join(H, "selcam.py")).read()); time.sleep(0.6)
    hover(RV, 0.5, 0.5, 0.6); human.key("g"); time.sleep(0.3); human.glide(*center(RV, 0.75, 0.35), 7.0); time.sleep(0.4); human.click("left"); time.sleep(4.0)
    human.key("g"); time.sleep(0.3); human.glide(*center(RV, 0.35, 0.65), 7.0); time.sleep(0.4); human.click("left"); time.sleep(5.0)
finally:
    take_stop("s11_google_split_camera")
print(blender("import bpy; p=bpy.context.scene.ogc3dtiles; print(p.view_source, [round(v) for v in bpy.context.scene.camera.location], p.status_text)"))
