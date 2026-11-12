import os, sys, time, json, math, importlib
import bpy
from mathutils import Vector, Euler, Quaternion, Matrix
PK = "bl_ext.user_default.ogc_3dtiles_streaming"
ui = importlib.import_module(PK + ".ui")
cn = importlib.import_module(PK + ".clip_nodes")
clipping = importlib.import_module(PK + ".clipping")
lib = importlib.import_module(PK + ".library")
extras = importlib.import_module(PK + ".ui.extras")
P = bpy.context.scene.ogc3dtiles
def v3d():
    for w in bpy.context.window_manager.windows:
        for a in w.screen.areas:
            if a.type == "VIEW_3D":
                return w, a, a.spaces.active, next(r for r in a.regions if r.type == "WINDOW")
def view(dist=800, loc=(0,0,0), rot=(0,0,0), mode="MATERIAL"):
    w,a,sp,r=v3d(); sp.shading.type=mode; sp.clip_end=1e6; rv=sp.region_3d; rv.view_perspective="PERSP"; rv.view_location=loc; rv.view_distance=dist; rv.view_rotation=Euler(rot).to_quaternion()
def redraw(n=1):
    w,a,sp,r=v3d()
    with bpy.context.temp_override(window=w,area=a,region=r):
        t=time.perf_counter(); bpy.ops.wm.redraw_timer(type="DRAW",iterations=n); return (time.perf_counter()-t)/n
def tiles():
    return {o.name:o.as_pointer() for o in bpy.context.scene.objects if "tile_url" in o}
def add_star(name="PrismA", n=16, r1=40, r2=20, c=(0,0)):
    if name in bpy.data.objects: bpy.data.objects.remove(bpy.data.objects[name])
    vs=[((r1 if i%2==0 else r2)*math.cos(2*math.pi*i/n)+c[0], (r1 if i%2==0 else r2)*math.sin(2*math.pi*i/n)+c[1], 0) for i in range(n)]
    me=bpy.data.meshes.new(name); me.from_pydata(vs,[],[list(range(n))]); me.update()
    o=bpy.data.objects.new(name,me); bpy.context.scene.collection.objects.link(o); return o
def start(name):
    w,a,sp,r=v3d()
    with bpy.context.temp_override(window=w,area=a,region=r):
        try: bpy.ops.ogc3dtiles.stop_stream()
        except Exception as e: print("stop",e)
    for o in list(bpy.context.scene.objects): bpy.data.objects.remove(o)
    P.tilesets.clear(); P.origin_mode="AUTO"; P.origin_valid=False
    rows=lib.read_all(extras._library_paths())
    e=next(x for p,x in rows if name in x.get("name",""))
    it=P.tilesets.add(); lib.apply_entry(it,e,add_overlay=lambda i:i.overlays.add())
    print("entry", it.kind)
    with bpy.context.temp_override(window=w,area=a,region=r):
        print(bpy.ops.ogc3dtiles.start_stream())
    return it
