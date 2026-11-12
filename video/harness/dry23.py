import sys, os, time; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from take import *
TS = r"%OGC_SCRATCH%\dl\eiffel\3dtiles\tileset.json"
L = layout(); U = L['UI']; V = L['WINDOW']
human.click("left", *ui(100, 717)); time.sleep(0.4); hover(U, 0.5, 0.5, 0.3); human.wheel(40, 0.03); time.sleep(0.4)
paste_into_field(*W['url'], TS); time.sleep(0.4); human.click("left", *W['add']); time.sleep(0.6); human.click("left", *W['start']); time.sleep(0.5)
hover(V, 0.5, 0.5, 0.5); n = wait_visible(200, 40); time.sleep(1.5); human.key("home"); time.sleep(1.5)
shot(os.path.join(H, "ei1.png"), V)
from PIL import Image; Image.open(os.path.join(H,"ei1.png")).resize((1180,728)).save(os.path.join(H,"ei1.jpg"),quality=80)
