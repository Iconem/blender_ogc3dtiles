import sys, os, time; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from take import *
L = layout(); U = L['UI']; V = L['WINDOW']
hover(V, 0.5, 0.5, 0.3); human.border_zoom(*center(V, 0.40, 0.40), *center(V, 0.60, 0.62), 1.0); time.sleep(6)
human.click("left", *ui(100, 591)); time.sleep(0.6)      # collapse Scene Origin
shot(os.path.join(H, "ui_cf7.png"), U)
