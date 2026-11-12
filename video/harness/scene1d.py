import sys, os, time, json; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from take import *
TS = r"%OGC_SCRATCH%\dl\sacre_coeur\3dtiles\tileset.json"
FRONTON = [1.84, 46.30, -7.29]; HORSES = [1.33, 48.70, -13.37]; HL = [8.81, 50.05, -12.79]; HR = [-6.15, 47.35, -13.95]
PROJ = open(os.path.join(H, "proj.py")).read()
def proj(pts): return json.loads(blender("PTS=%s\n" % json.dumps(pts) + PROJ).strip().splitlines()[-1])
def cl(v): return min(0.97, max(0.03, v))
L = layout(); V = L['WINDOW']; U = L['UI']
scroll_until("clear_btn", U, step=10); park()
# make sure the Scene Origin panel starts collapsed (the take expands it)
try:
    locate("origin_mode", U); human.click("left", *W1['origin_hdr']); time.sleep(1.0); park(); print("collapsed origin panel")
except LookupError: pass
take_start("s1d_sacre_coeur_full", L['client']); time.sleep(1.0)
try:
    mark("paste tileset path"); human.glide(*W['url'], 0.8); time.sleep(0.3); paste_into_field(*W['url'], TS); time.sleep(0.7)
    mark("add"); human.click("left", *W['add']); time.sleep(0.9)
    mark("rename"); human.dbl_click(*W1['entry']); time.sleep(0.4); human.key("a", mods=("ctrl",)); human.type_text("Sacre-Coeur splat"); human.key("enter"); time.sleep(0.6)
    mark("scene origin panel"); human.click("left", *W1['origin_hdr']); time.sleep(1.2)
    mark("origin modes"); human.glide(*ui(200, 593), 0.6); time.sleep(0.3); human.click("left"); time.sleep(0.8)
    for dy in (56, 83, 110): human.glide(*ui(150, 593 + dy), 0.45); time.sleep(0.55)
    human.glide(*ui(150, 593 + 29), 0.6); time.sleep(0.5); mark("auto"); human.click("left"); time.sleep(0.9)
    mark("start"); human.click("left", *W['start']); time.sleep(0.4)
    hover(V, 0.5, 0.55, 0.9); n = wait_visible(40, 30); mark(f"{n} tiles"); time.sleep(1.0)
    human.key("home"); time.sleep(1.5); mark("home")
    mark("rendered"); human.click("left", *SHADING['rendered']); time.sleep(2.5)
    hover(V, 0.5, 0.5, 0.5); mark("orbit to the north side"); human.orbit(-420, 20, 3.0); time.sleep(1.0)
    f = proj([FRONTON])[0]; print("fronton at", f)
    mark("shift+b fronton"); human.border_zoom(*center(V, cl(f[0]-0.10), cl(f[1]-0.14)), *center(V, cl(f[0]+0.10), cl(f[1]+0.14)), 1.1); time.sleep(1.8)
    mark("orbit"); human.orbit(60, -30, 1.6); time.sleep(1.2)
    a, b, h = proj([HL, HR, HORSES]); print("horses at", a, b, h)
    x0, x1 = sorted([a[0], b[0]]); y0, y1 = min(a[1], b[1], h[1]), max(a[1], b[1], h[1])
    mark("shift+b horses"); human.border_zoom(*center(V, cl(x0-0.04), cl(y0-0.07)), *center(V, cl(x1+0.04), cl(y1+0.07)), 1.1); time.sleep(1.8)
    mark("orbit around"); human.orbit(-200, -25, 3.2); time.sleep(0.8); human.wheel(2); time.sleep(1.0); human.orbit(150, 15, 2.6); time.sleep(1.5)
finally:
    take_stop("s1d_sacre_coeur_full")
