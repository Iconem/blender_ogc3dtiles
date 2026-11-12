import sys, os, time; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from take import *
from PIL import Image
L = layout(); V = L['WINDOW']; U = L['UI']
p = scroll_until("demo_graphs", U); park(); human.click("left", *p); time.sleep(1.0)
shot(os.path.join(H, "pop_demo.png"), (U[0]-300, p[1]-300, U[2]+300, 600)); human.key("esc"); time.sleep(0.5); park()
c = scroll_until("comp_header", U); park(); human.click("left", *c); time.sleep(0.8); park()
c = scroll_until("comp_header", U); park(); shot(os.path.join(H, "ui_comp.png"), U)
ims=[Image.open(os.path.join(H,f)).convert('RGB') for f in ("pop_demo.png","ui_comp.png")]
W_=sum(i.width for i in ims); cc=Image.new('RGB',(W_, max(i.height for i in ims)),'black'); x=0
for im in ims: cc.paste(im,(x,0)); x+=im.width
cc.save(os.path.join(H,"dry30.jpg"), quality=78); print("comp header at", c)
