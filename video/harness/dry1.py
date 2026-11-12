import sys, os, time; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from take import *
TS = r"%OGC_SCRATCH%\dl\sacre_coeur\3dtiles\tileset.json"
L = layout(); V = L['WINDOW']
paste_into_field(*W['url'], TS); time.sleep(0.5); human.click("left", *W['add']); time.sleep(0.8)
shot(os.path.join(H, "ui_entry.png"), L['UI'])
