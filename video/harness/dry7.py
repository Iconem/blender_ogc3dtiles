import sys, os, time; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from take import *
L = layout(); U = L['UI']
human.click("left", *ui(200, 593)); time.sleep(0.8)
shot(os.path.join(H, "ui_cf2.png"), (U[0]-300, U[1]+350, U[2]+300, 450))
human.key("esc"); time.sleep(0.3)
