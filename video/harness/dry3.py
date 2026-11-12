import sys, os, time; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from take import *
L = layout(); V = L['WINDOW']
hover(V, 0.5, 0.5, 0.3)
human.border_zoom(*center(V, 0.42, 0.50), *center(V, 0.60, 0.80), 1.0); time.sleep(1.5)
shot(os.path.join(H, "v1.png"), V)
hover(V, 0.5, 0.5, 0.3); human.orbit(0, 140, 1.5); time.sleep(1.2)
shot(os.path.join(H, "v2.png"), V)
from PIL import Image
ims=[Image.open(os.path.join(H, f)).convert('RGB') for f in ("v1.png","v2.png")]; w,h=ims[0].size; c=Image.new('RGB',(w,h*2)); c.paste(ims[0],(0,0)); c.paste(ims[1],(0,h)); c.resize((900,int(900*2*h/w))).save(os.path.join(H,"v12.jpg"),quality=78)
