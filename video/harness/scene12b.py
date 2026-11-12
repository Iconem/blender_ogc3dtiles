import sys, os, time, json; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from take import *
L = layout(); V = L['WINDOW']; U = L['UI']
scroll_until("clear_btn", U, step=10); park(); hover(V, 0.5, 0.5, 0.3); print("settled", wait_settled(120, 10))
EYE1, EYE2 = ui(246, 135), ui(246, 160)
HID = open(os.path.join(H, "hid.py"), encoding="utf-8").read()
def hidden():
    return json.loads(blender(HID).strip().splitlines()[-1].replace("True", "true").replace("False", "false"))
def eye(pt, i):
    """Click the eye of row i and make sure it toggled (a click on a non-hovered row is sometimes swallowed)."""
    before = hidden()[i]
    for _ in range(3):
        human.glide(*pt, 0.8); time.sleep(0.4); human.click("left"); time.sleep(0.9)
        if hidden()[i] != before: return
        print("eye click did not toggle, again")
take_start("s12b_google_bing_eyes", L['client']); time.sleep(1.0)
try:
    hover(V, 0.5, 0.5, 0.5); mark("google + bing, both on the colosseum"); human.orbit(160, -25, 3.0); time.sleep(1.0)
    f = proj([[0, 0, 20]])[0]; mark("shift+b on the colosseum"); human.border_zoom(*center(V, cl(f[0] - 0.09), cl(f[1] - 0.11)), *center(V, cl(f[0] + 0.09), cl(f[1] + 0.11)), 1.1)
    hover(V, 0.5, 0.5, 0.5); human.orbit(30, -5, 2.0); time.sleep(1.0); print("refined", wait_settled(60, 6)); time.sleep(1.0)
    mark("hide google: bing only"); eye(EYE1, 0); hover(V, 0.5, 0.5, 0.5); human.orbit(90, 10, 2.5); time.sleep(1.5); print("refined", wait_settled(40, 5)); time.sleep(1.0)
    mark("show google, hide bing: google only"); eye(EYE1, 0); eye(EYE2, 1); hover(V, 0.5, 0.5, 0.5); human.orbit(-120, -15, 3.0); time.sleep(1.5); print("refined", wait_settled(40, 5)); time.sleep(1.0)
    mark("solid shading: the tiled mesh itself"); human.click("left", *SHADING['solid']); time.sleep(1.5); hover(V, 0.5, 0.5, 0.5); human.orbit(70, 10, 2.5); time.sleep(1.5)
    mark("bing back on, solid"); eye(EYE2, 1); hover(V, 0.5, 0.5, 0.5); human.orbit(40, 0, 1.5); time.sleep(1.0); print("refined", wait_settled(40, 5)); time.sleep(1.0)
    mark("google off: bing alone, solid"); eye(EYE1, 0); hover(V, 0.5, 0.5, 0.5); human.orbit(50, -10, 2.0); time.sleep(2.0)
    mark("material preview again"); human.click("left", *SHADING['material']); time.sleep(1.5); hover(V, 0.5, 0.5, 0.5); human.orbit(-60, 5, 2.5); time.sleep(2.0)
finally:
    take_stop("s12b_google_bing_eyes")
print("hidden flags (google, bing):", hidden())
