import sys, os, time; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from take import *
L = layout(); C = L['client']
A = layout_areas(); LV = A[0]['WINDOW']; RV = A[1]['WINDOW']; U = A[1]['UI']; print("left", LV, "right", RV, "ui", U)
UI0[0], UI0[1] = U[0], U[1]
hover(LV, 0.5, 0.5, 0.3); print("settled", wait_settled(120, 10))
def nav_walk():
    hover(LV, 0.5, 0.5, 0.4); human.key("f3"); time.sleep(0.8); human.type_text("walk navigation"); time.sleep(1.2); human.key("enter"); time.sleep(0.8)
def run(secs): human._key(human.VK["shift"]); human.hold("w", secs); human._key(human.VK["shift"], True)
take_start("s11b_google_split_camera", C); time.sleep(1.5)
try:
    mark("stream for: scene camera"); hover(RV, 0.5, 0.8, 0.3)
    try: sf = locate("stream_for", U)
    except LookupError:
        lh = scroll_until("lod_header", U); human.click("left", *lh); time.sleep(0.9); hover(RV, 0.5, 0.8, 0.3); sf = locate("stream_for", U)
    dd = (sf[0] + 130, sf[1]); human.click("left", *dd); time.sleep(1.0); click_tpl("it_scene_camera", rect=(U[0] - 250, dd[1] - 140, U[2] + 250, 300)); time.sleep(3.0)
    mark("walk navigation in the camera (left); right view stays put"); nav_walk()
    human.move_rel(90, 0, 2.0); time.sleep(0.3); run(5.0); time.sleep(0.3); human.move_rel(-200, 40, 3.0); time.sleep(0.3); run(4.0); time.sleep(0.3); human.move_rel(80, -60, 2.0); time.sleep(0.5)
    human.click("left"); time.sleep(2.0); mark("walk done")
    mark("grab the camera in the top view"); blender(open(os.path.join(H, "selcam.py")).read()); time.sleep(0.6)
    hover(RV, 0.5, 0.5, 0.6); human.key("g"); time.sleep(0.3); human.glide(*center(RV, 0.70, 0.35), 7.0); time.sleep(0.4); human.click("left"); time.sleep(4.0)
    human.key("g"); time.sleep(0.3); human.glide(*center(RV, 0.30, 0.65), 7.0); time.sleep(0.4); human.click("left"); time.sleep(5.0)
finally:
    take_stop("s11b_google_split_camera")
print(blender("import bpy; p=bpy.context.scene.ogc3dtiles; print(p.view_source, [round(v) for v in bpy.context.scene.camera.location], p.status_text)"))
