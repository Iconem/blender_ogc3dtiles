import sys, os, time; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from take import *
L = layout(); V = L['WINDOW']; U = L['UI']
print(blender("""import bpy, json
from bpy_extras import view3d_utils
from mathutils import Vector
w=bpy.context.window_manager.windows[0]; a=next(a for a in w.screen.areas if a.type=='VIEW_3D'); reg=next(r for r in a.regions if r.type=='WINDOW'); r3=a.spaces[0].region_3d
piv=r3.view_location.copy()
def at(fx,fy):
    co=Vector((fx*reg.width,(1-fy)*reg.height))
    return list(view3d_utils.region_2d_to_location_3d(reg,r3,co,piv))
print(json.dumps({'fronton':at(0.47,0.45),'horses':at(0.47,0.66),'horseL':at(0.32,0.64),'horseR':at(0.62,0.68),'piv':list(piv)}))"""))
park(); human.click("left", *ui(200, 593)); time.sleep(1.0); shot("sc_ui2.png", (U[0]-150, U[1]+400, 500, 400)); human.key("escape"); time.sleep(0.5)
