import sys, os, time; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from take import *
L = layout(); V = L['WINDOW']; U = L['UI']
hover(U, 0.5, 0.5, 0.4); human.wheel(-10, 0.05); time.sleep(0.9); park(); shot("cf5_ui.png", U)
