import sys, os, time; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from take import *
L = layout(); V = L['WINDOW']
hover(V, 0.5, 0.5, 0.3); time.sleep(0.5)
take_start("s1b_fronton", L['client']); time.sleep(1.2)
hover(V, 0.52, 0.6, 0.8); time.sleep(0.4)
mark("shift+b facade"); human.border_zoom(*center(V, 0.41, 0.55), *center(V, 0.57, 0.78), 1.1); time.sleep(1.6)
mark("orbit"); human.orbit(110, -70, 1.8); time.sleep(1.2)
mark("shift+b horses"); human.border_zoom(*center(V, 0.33, 0.56), *center(V, 0.60, 0.76), 1.1); time.sleep(1.8)
mark("orbit around"); human.orbit(-200, -25, 3.2); time.sleep(0.8)
mark("wheel in"); human.wheel(2); time.sleep(1.0)
human.orbit(150, 15, 2.6); time.sleep(0.8)
human.orbit(-60, 40, 1.6); time.sleep(1.5)
take_stop("s1b_fronton")
