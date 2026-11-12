import sys, os, time; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from take import *
L = layout(); V = L['WINDOW']; U = L['UI']
scroll_until("clear_btn", U, step=10); park()
hover(V, 0.45, 0.5, 0.4); human.key("a", mods=("shift",)); time.sleep(1.0)
x, y = human.pos(); shot(os.path.join(H, "menu_add.png"), (x - 250, y - 300, 600, 600))
human.glide(x + 30, y + 10, 0.4); time.sleep(0.9); shot(os.path.join(H, "menu_add2.png"), (x - 250, y - 300, 800, 600))
human.key("esc"); time.sleep(0.2); human.key("esc")
from PIL import Image
a=Image.open(os.path.join(H,'menu_add.png')); b=Image.open(os.path.join(H,'menu_add2.png')); c=Image.new('RGB',(a.width+b.width,a.height)); c.paste(a,(0,0)); c.paste(b,(a.width,0)); c.save(os.path.join(H,'menu_add12.jpg'),quality=78); print("pos", x, y)
