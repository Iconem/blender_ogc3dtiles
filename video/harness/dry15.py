import sys, os, time; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from take import *
L = layout(); U = L['UI']; V = L['WINDOW']
human.glide(*ui(120, 756), 0.4); time.sleep(0.2); human.drag("left", 84, 0, 1.0); time.sleep(0.5)   # albedo back to ~1
hover(U, 0.5, 0.5, 0.3); human.wheel(-12, 0.04); time.sleep(0.8)                                    # scroll the sidebar down
shot(os.path.join(H, "ui_cf13.png"), U); shot(os.path.join(H, "outliner.png"), (1579, 62, 339, 192))
