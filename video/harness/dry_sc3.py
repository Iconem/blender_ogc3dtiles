import sys, os, time; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from take import *
L = layout(); V = L['WINDOW']; U = L['UI']
park(); human.click("left", *ui(100, 591)); time.sleep(1.2); park(); time.sleep(0.5); shot("sc_ui3a.png", (U[0]-150, U[1]+400, 500, 400))
human.glide(*ui(200, 628), 0.5); time.sleep(0.5); human.click("left"); time.sleep(1.8); shot("sc_ui3.png", (U[0]-150, U[1]+400, 500, 400)); human.key("esc"); time.sleep(0.5)
