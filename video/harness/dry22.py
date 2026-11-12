import sys, os, time; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from take import *
L = layout(); U = L['UI']; V = L['WINDOW']
hover(U, 0.5, 0.5, 0.3); human.wheel(-40, 0.03); time.sleep(0.6); shot(os.path.join(H, "ui_ei6.png"), U)
human.wheel(40, 0.03); time.sleep(0.5)
human.click("left", *ui(36, 423)); time.sleep(0.8); human.click("left", *ui(286, 508)); time.sleep(0.9)
shot(os.path.join(H, "ui_ei7.png"), (U[0]-400, U[1]+380, U[2]+400, 400)); human.key("esc"); time.sleep(0.3)
from PIL import Image
a=Image.open(os.path.join(H,"ui_ei6.png")); b=Image.open(os.path.join(H,"ui_ei7.png")); c=Image.new('RGB',(a.width+b.width,max(a.height,b.height)),'black'); c.paste(a,(0,0)); c.paste(b,(a.width,0)); c.save(os.path.join(H,"ui_ei67.jpg"),quality=80)
