import sys, os, time; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from take import *
L = layout(); V = L['WINDOW']; U = L['UI']
b = scroll_until("beauty", U); park(); human.click("left", b[0] - 90, b[1]); time.sleep(1.5); park()
b = scroll_until("beauty", U); park(); shot(os.path.join(H, "ui_comp2.png"), U)
ed = (b[0] + 110, b[1] + 47); human.click("left", *ed); time.sleep(1.0); shot(os.path.join(H, "pop_edges.png"), (U[0]-300, ed[1]-200, U[2]+300, 400)); human.key("esc"); time.sleep(0.5)
park(); b = scroll_until("beauty", U); human.click("left", b[0] - 90, b[1]); time.sleep(1.0)   # untick
from PIL import Image
ims=[Image.open(os.path.join(H,f)).convert('RGB') for f in ("ui_comp2.png","pop_edges.png")]
W_=sum(i.width for i in ims); cc=Image.new('RGB',(W_, max(i.height for i in ims)),'black'); x=0
for im in ims: cc.paste(im,(x,0)); x+=im.width
cc.save(os.path.join(H,"dry31.jpg"), quality=78)
