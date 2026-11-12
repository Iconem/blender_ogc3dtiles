exec(open(os.path.join(os.environ["TEMP"],"ogc_tests","r9","capx.py")).read())
import random
random.seed(7)
CUR={"xy":[700.0,560.0],"down":False,"rect":None,"key":""}
def _w(): return v3d()[0]
def _wxy():
    w,a,sp,r=v3d(); return int(a.x+CUR["xy"][0]), int(a.y+a.height-CUR["xy"][1])
def ev(t,v,**k):
    x,y=_wxy(); _w().event_simulate(type=t,value=v,x=x,y=y,**k)
def wait(n):
    for _ in range(n): yield
def mv(to,n=None,arc=None,hold=None):
    x0,y0=CUR["xy"]; dx,dy=to[0]-x0,to[1]-y0; d=math.hypot(dx,dy)
    if n is None: n=max(4,int(4+d/70+random.uniform(-1,2)))
    if arc is None: arc=random.uniform(-0.12,0.12)*d
    nx,ny=(-dy/d,dx/d) if d else (0,0)
    for i in range(1,n+1):
        t=i/n; s=t*t*t*(10-15*t+6*t*t); b=math.sin(math.pi*s)*arc
        j=0 if i==n else random.uniform(-1.5,1.5)
        CUR["xy"]=[x0+dx*s+nx*b+j, y0+dy*s+ny*b+j]
        ev("MOUSEMOVE","NOTHING",**(hold or {})); yield
def pause(a=3,b=8): yield from wait(random.randint(a,b))
def wheel(k,key="wheel"):
    CUR["key"]=key
    for _ in range(abs(k)):
        ev("WHEELUPMOUSE" if k>0 else "WHEELDOWNMOUSE","PRESS"); yield
        yield from wait(random.randint(1,3))
    CUR["key"]=""
def mdrag(dx,dy,n=None):
    ev("MIDDLEMOUSE","PRESS"); CUR["down"]=True; CUR["key"]="middle drag"; yield
    yield from mv((CUR["xy"][0]+dx,CUR["xy"][1]+dy),n)
    yield from wait(random.randint(0,2))
    ev("MIDDLEMOUSE","RELEASE"); CUR["down"]=False; CUR["key"]=""; yield
def ldrag(to,n=None,key="drag",hold=None):
    ev("LEFTMOUSE","PRESS",**(hold or {})); CUR["down"]=True; CUR["key"]=key; yield
    yield from mv(to,n,arc=0,hold=hold)
    yield from wait(2)
    ev("LEFTMOUSE","RELEASE",**(hold or {})); CUR["down"]=False; CUR["key"]=""; yield
def lclick(key="click"):
    ev("LEFTMOUSE","PRESS"); CUR["down"]=True; CUR["key"]=key; yield
    ev("LEFTMOUSE","RELEASE"); CUR["down"]=False; yield
    CUR["key"]=""
def keytap(k,label,**mods):
    CUR["key"]=label; ev(k,"PRESS",**mods); yield
    ev(k,"RELEASE",**mods); yield
def capture3(name, story, interval=0.1):
    bpy.context.preferences.view.smooth_view=200
    bpy.context.scene.render.image_settings.file_format="PNG"; bpy.context.scene.render.image_settings.compression=0
    out=os.path.join(R9,"cap_"+name); os.makedirs(out,exist_ok=True)
    for f in os.listdir(out): os.remove(os.path.join(out,f))
    st={"i":0,"t0":time.time(),"meta":[]}; g=story(); w,a,sp,r=v3d()
    def fin(msg):
        json.dump(st["meta"],open(os.path.join(out,"meta.json"),"w"))
        open(os.path.join(out,"done.txt"),"w").write(msg)
    def tick():
        try:
            with bpy.context.temp_override(window=w,area=a,region=r):
                bpy.ops.screen.screenshot_area(filepath=os.path.join(out,"f_%04d.png"%st["i"]))
            st["meta"].append(dict(xy=list(CUR["xy"]),down=CUR["down"],rect=None,key=CUR["key"]))
            st["i"]+=1
            try: next(g)
            except StopIteration:
                fin("%d frames in %.1f s"%(st["i"],time.time()-st["t0"])); return None
        except Exception:
            fin(traceback.format_exc()); return None
        return interval
    bpy.app.timers.register(tick); print("capturing",name)
