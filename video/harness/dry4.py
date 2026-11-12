import sys, os, time; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from take import *
L = layout(); V = L['WINDOW']
hover(V, 0.5, 0.5, 0.3)
human.border_zoom(*center(V, 0.41, 0.55), *center(V, 0.57, 0.78), 1.0); time.sleep(1.5)
shot(os.path.join(H, "v1.png"), V)
from PIL import Image; Image.open(os.path.join(H,"v1.png")).convert('RGB').resize((1180,728)).save(os.path.join(H,"v1.jpg"),quality=80)
