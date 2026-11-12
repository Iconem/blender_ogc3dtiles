import sys, os, time; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from take import *
L = layout(); V = L['WINDOW']
hover(V, 0.5, 0.5, 0.3); human.orbit(110, -70, 1.6); time.sleep(1.2)
shot(os.path.join(H, "v2.png"), V)
from PIL import Image; Image.open(os.path.join(H,"v2.png")).convert('RGB').resize((1180,728)).save(os.path.join(H,"v2.jpg"),quality=80)
