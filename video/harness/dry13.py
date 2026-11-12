import sys, os, time; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from take import *
L = layout(); U = L['UI']; V = L['WINDOW']
hover(V, 0.5, 0.5, 0.3); time.sleep(0.8); shot(os.path.join(H, "ui_cf9.png"), U)
human.click("left", *ui(292, 693)); time.sleep(0.8); shot(os.path.join(H, "ui_cf10.png"), (U[0]-350, U[1]+450, U[2]+350, 457))
human.key("esc"); time.sleep(0.3)
from PIL import Image
a=Image.open(os.path.join(H,"ui_cf9.png")); b=Image.open(os.path.join(H,"ui_cf10.png")); c=Image.new('RGB',(a.width+b.width, max(a.height,b.height)),'black'); c.paste(a,(0,0)); c.paste(b,(a.width,0)); c.save(os.path.join(H,"ui_cf910.jpg"),quality=80)
