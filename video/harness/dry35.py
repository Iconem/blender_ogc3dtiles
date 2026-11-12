import sys, os, time; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from take import *
L = layout(); V = L['WINDOW']; U = L['UI']
hover(V, 0.45, 0.5, 0.4); human.key("a", mods=("shift",)); time.sleep(1.0)
x, y = human.pos(); human.glide(x + 20, y + 35, 0.5); time.sleep(1.0)     # "Mesh" row (33 px under the cursor row)
shot(os.path.join(H, "menu_mesh.png"), (x - 250, y - 300, 900, 650))
human.key("esc"); time.sleep(0.2); human.key("esc"); print("pos", x, y)
