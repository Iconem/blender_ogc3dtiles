import sys, os, time; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from take import *
L = layout(); V = L['WINDOW']; U = L['UI']
b = scroll_until("beauty", U); park(); ed = (b[0] + 75, b[1] + 62); human.click("left", *ed); time.sleep(1.0)
shot(os.path.join(H, "pop_edges.png"), (U[0]-300, ed[1]-200, U[2]+300, 400)); human.key("esc"); time.sleep(0.4)
from PIL import Image, ImageDraw
im=Image.open(os.path.join(H,'pop_edges.png')); d=ImageDraw.Draw(im)
for y in range(0, im.height, 50): d.line((0,y,im.width,y), fill='red'); d.text((2,y), str(y), fill='yellow')
for x in range(0, im.width, 50): d.line((x,0,x,im.height), fill='blue'); d.text((x,2), str(x), fill='cyan')
im.save(os.path.join(H,'pop_edges_grid.png'))
