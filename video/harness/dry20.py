import sys, os, time; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from take import *
L = layout(); U = L['UI']; V = L['WINDOW']
human.click("left", *ui(170, 581)); time.sleep(0.8); shot(os.path.join(H, "ui_ei3.png"), (U[0]-200, U[1]+450, U[2]+200, 300)); human.key("esc"); time.sleep(0.3)
human.click("left", *ui(100, 824)); time.sleep(0.8); hover(U, 0.5, 0.5, 0.3); human.wheel(-20, 0.03); time.sleep(0.6); shot(os.path.join(H, "ui_ei4.png"), U)
from PIL import Image
a=Image.open(os.path.join(H,"ui_ei3.png")); b=Image.open(os.path.join(H,"ui_ei4.png")); c=Image.new('RGB',(a.width+b.width,max(a.height,b.height)),'black'); c.paste(a,(0,0)); c.paste(b,(a.width,0)); c.save(os.path.join(H,"ui_ei34.jpg"),quality=80)
