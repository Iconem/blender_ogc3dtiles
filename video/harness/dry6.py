import sys, os, time; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from take import *
L = layout(); V = L['WINDOW']
paste_into_field(*W['url'], "https://3d.craig.fr/datasets/Clermont/3dtiles/tileset.json"); time.sleep(0.5); human.click("left", *W['add']); time.sleep(0.8)
human.click("left", *W1['origin_hdr']); time.sleep(1.0)
shot(os.path.join(H, "ui_cf1.png"), L['UI'])
