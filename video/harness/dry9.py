import sys, os, time; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from take import *
L = layout(); U = L['UI']
human.click("left", *ui(150, 624)); time.sleep(0.4); human.key("a", mods=("ctrl",)); human.type_text("Cathedrale Clermont-Ferrand"); human.key("enter"); time.sleep(3.0)
shot(os.path.join(H, "ui_cf4.png"), U)
