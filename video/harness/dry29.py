import sys, os, time; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from take import *
from PIL import Image
L = layout(); V = L['WINDOW']; U = L['UI']
scroll_until("clear_btn", U, step=10); park()
# 1. Demo graphs dropdown
g = scroll_until("geo_header", U); park()
dg = (g[0] + 60, g[1] + 72)   # "Demo graphs" dropdown is two rows under the header
human.click("left", *dg); time.sleep(0.9); shot(os.path.join(H, "pop_demo.png"), (U[0]-300, dg[1]-250, U[2]+300, 500)); human.key("esc"); time.sleep(0.4)
# 2. Compositing: tick beauty, then Edges dropdown
park(); a = scroll_until("atmo", U); park(); human.click("left", a[0] - 140, a[1] - 30); time.sleep(1.5)   # "Beauty compositor nodes" checkbox row above the atmosphere button
park(); shot(os.path.join(H, "ui_comp.png"), U)
# 3. Clipping checkbox
scroll_until("clear_btn", U, step=10); park(); c = locate("clipping_off", U); human.click("left", c[0] - 30, c[1]); time.sleep(1.0); park(); shot(os.path.join(H, "ui_clip.png"), U)
ims=[Image.open(os.path.join(H,f)).convert('RGB') for f in ("pop_demo.png","ui_comp.png","ui_clip.png")]
W_=sum(i.width for i in ims); c=Image.new('RGB',(W_, max(i.height for i in ims)),'black'); x=0
for im in ims: c.paste(im,(x,0)); x+=im.width
c.save(os.path.join(H,"dry29.jpg"), quality=78)
