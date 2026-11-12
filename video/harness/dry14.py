import sys, os, time; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from take import *
L = layout(); U = L['UI']; V = L['WINDOW']
human.glide(*ui(200, 756), 0.5); time.sleep(0.2); human.drag("left", -84, 0, 1.6); time.sleep(1.2)
shot(os.path.join(H, "ui_cf12.png"), (U[0], U[1]+730, U[2], 170)); shot(os.path.join(H, "cf4.png"), V)
