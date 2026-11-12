import sys, os, time; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from take import *
L = layout(); V = L['WINDOW']
human.click("left", 227, 77); time.sleep(0.8); human.glide(277, 430, 0.5); time.sleep(1.0); human.glide(600, 430, 0.4); time.sleep(0.5)
shot(os.path.join(H, "menu_nav.png"), (150, 300, 900, 800)); human.key("esc"); time.sleep(0.2); human.key("esc")
