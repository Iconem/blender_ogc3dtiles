import sys, os, time; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from take import *
L = layout(); V = L['WINDOW']; U = L['UI']
scroll_until("clear_btn", U, step=10); park(); c = locate("clipping_off", U); human.click("left", c[0] - 30, c[1]); time.sleep(1.0); park()
shot(os.path.join(H, "ui_clip.png"), U)
from PIL import Image, ImageDraw
im=Image.open(os.path.join(H,'ui_clip.png')); d=ImageDraw.Draw(im)
for y in range(0, im.height, 50): d.line((0,y,im.width,y), fill='red'); d.text((2,y), str(y), fill='yellow')
im.save(os.path.join(H,'ui_clip_grid.png'))
