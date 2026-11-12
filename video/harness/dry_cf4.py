import sys, os, time; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from take import *
L = layout(); V = L['WINDOW']; U = L['UI']
scroll_until("clear_btn", U, step=10); park()
m = scroll_until("mat_header", U); human.click("left", *m); time.sleep(1.0); park(); shot("cf4_ui0.png", U)
s = locate("shared_shader", U); human.click("left", *s); time.sleep(2.0); park(); shot("cf4_ui1.png", U); print("mat", m, "shared", s)
