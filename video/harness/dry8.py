import sys, os, time; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from take import *
L = layout(); U = L['UI']
human.click("left", *ui(200, 593)); time.sleep(0.6); human.click("left", *ui(147, 703)); time.sleep(0.8)
shot(os.path.join(H, "ui_cf3.png"), U)
