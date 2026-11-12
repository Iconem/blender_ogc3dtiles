import sys, os, time; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from take import *
L = layout(); U = L['UI']; V = L['WINDOW']
human.click("left", *ui(36, 423)); time.sleep(1.0); shot(os.path.join(H, "ui_ei1.png"), U)
human.click("left", *ui(36, 423)); time.sleep(0.5)
hover(U, 0.5, 0.5, 0.3); human.wheel(-40, 0.03); time.sleep(0.8); shot(os.path.join(H, "ui_ei2.png"), U)
from PIL import Image
a=Image.open(os.path.join(H,"ui_ei1.png")); b=Image.open(os.path.join(H,"ui_ei2.png")); c=Image.new('RGB',(a.width+b.width,a.height),'black'); c.paste(a,(0,0)); c.paste(b,(a.width,0)); c.save(os.path.join(H,"ui_ei12.jpg"),quality=80)
