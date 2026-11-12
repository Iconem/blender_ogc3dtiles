import sys, os, time; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from take import *
L = layout(); U = L['UI']; V = L['WINDOW']
human.click("left", *ui(30, 693)); time.sleep(2.0)
shot(os.path.join(H, "ui_cf8.png"), U); shot(os.path.join(H, "cf3.png"), V)
