import sys, os, time; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from take import *
L = layout(); V = L['WINDOW']; U = L['UI']
scroll_until("clear_btn", U, step=10); park(); print("visible", wait_visible(60, 60))
park(); shot("cf3_ui0.png", U)
hover(U, 0.5, 0.5, 0.4); human.wheel(-12, 0.05); time.sleep(0.9); park(); shot("cf3_ui1.png", U)
