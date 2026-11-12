exec(open(os.path.join(os.environ["TEMP"],"ogc_tests","r9","capx.py")).read())
# story-driven capture: a generator yields once per frame; CUR holds the fake mouse state
CUR={"xy":[900.0,600.0],"down":False,"rect":None,"key":""}
def _ov():
    w,a,sp,r=v3d(); return dict(window=w,area=a,region=r)
def a2r(x,y):
    w,a,sp,r=v3d(); return int(x-(r.x-a.x)), int((a.height-y)-(r.y-a.y))
def wait(n):
    for _ in range(n): yield
def move(to,n=8):
    x0,y0=CUR["xy"]
    for i in range(1,n+1):
        t=smooth(i/n); CUR["xy"]=[lerp(x0,to[0],t),lerp(y0,to[1],t)]; yield
def _snap():
    rv=v3d()[2].region_3d; return rv.view_location.copy(), rv.view_distance, rv.view_rotation.copy()
def _set(s):
    rv=v3d()[2].region_3d; rv.view_location=s[0]; rv.view_distance=s[1]; rv.view_rotation=s[2]
def glide(a,b,n):
    for i in range(1,n+1):
        t=smooth(i/n); _set((a[0].lerp(b[0],t), a[1]*(b[1]/a[1])**t, a[2].slerp(b[2],t))); yield
def wheel(k,each=2,key="wheel"):
    CUR["key"]=key
    for _ in range(abs(k)):
        with bpy.context.temp_override(**_ov()): bpy.ops.view3d.zoom(delta=1 if k>0 else -1)
        for _ in range(each): yield
    CUR["key"]=""
def orbit(yaw_deg,pitch_deg,n,drag=(260,0)):
    CUR["down"]=True; CUR["key"]="middle drag"
    x0,y0=CUR["xy"]
    for i in range(1,n+1):
        with bpy.context.temp_override(**_ov()):
            if yaw_deg: bpy.ops.view3d.view_orbit(angle=math.radians(abs(yaw_deg)/n),type="ORBITLEFT" if yaw_deg>0 else "ORBITRIGHT")
            if pitch_deg: bpy.ops.view3d.view_orbit(angle=math.radians(abs(pitch_deg)/n),type="ORBITUP" if pitch_deg>0 else "ORBITDOWN")
        CUR["xy"]=[x0+drag[0]*i/n,y0+drag[1]*i/n]; yield
    CUR["down"]=False; CUR["key"]=""
def zoomrect(x0,y0,x1,y1,n=10,settle=10):
    yield from move((x0,y0),8)
    CUR["down"]=True; CUR["key"]="Shift B"
    for i in range(1,n+1):
        t=smooth(i/n); CUR["xy"]=[lerp(x0,x1,t),lerp(y0,y1,t)]; CUR["rect"]=[x0,y0]+CUR["xy"]; yield
    CUR["down"]=False; CUR["rect"]=None
    a=_snap(); ax0,ay0=a2r(x0,y1); ax1,ay1=a2r(x1,y0)
    with bpy.context.temp_override(**_ov()): bpy.ops.view3d.zoom_border(xmin=ax0,xmax=ax1,ymin=ay0,ymax=ay1)
    b=_snap(); _set(a)
    yield from glide(a,b,7)
    CUR["key"]=""
    yield from wait(settle)
def click(pos,fn,n=8,after=6,key="click"):
    yield from move(pos,n)
    CUR["down"]=True; CUR["key"]=key; yield
    fn(); yield
    CUR["down"]=False; CUR["key"]=""
    yield from wait(after)
def slide(pos,dx,setter,v0,v1,n=12,after=8):
    yield from move(pos,8)
    CUR["down"]=True; CUR["key"]="drag"
    for i in range(1,n+1):
        t=i/n; CUR["xy"]=[pos[0]+dx*t,pos[1]]; setter(lerp(v0,v1,t)); yield
    CUR["down"]=False; CUR["key"]=""
    yield from wait(after)
def capture2(name, story, interval=0.12, animate=True, fps=12):
    sc=bpy.context.scene; saved=_take_begin(sc, animate, fps)
    bpy.context.preferences.view.smooth_view=0
    bpy.context.scene.render.image_settings.file_format="PNG"; bpy.context.scene.render.image_settings.compression=0
    out=os.path.join(R9,"cap_"+name); os.makedirs(out,exist_ok=True)
    for f in os.listdir(out): os.remove(os.path.join(out,f))
    st={"i":0,"t0":time.time(),"meta":[]}; g=story(); w,a,sp,r=v3d()
    def fin(msg):
        json.dump(st["meta"],open(os.path.join(out,"meta.json"),"w"))
        open(os.path.join(out,"done.txt"),"w").write(msg); _take_end(sc, saved)
    def tick():
        try:
            _take_frame(sc, animate, st["i"])
            try: next(g)
            except StopIteration:
                fin("%d frames in %.1f s"%(st["i"],time.time()-st["t0"])); return None
            for ar in w.screen.areas: ar.tag_redraw()
            with bpy.context.temp_override(window=w,area=a,region=r):
                bpy.ops.screen.screenshot_area(filepath=os.path.join(out,"f_%04d.png"%st["i"]))
            st["meta"].append(dict(xy=list(CUR["xy"]),down=CUR["down"],rect=CUR["rect"],key=CUR["key"]))
        except Exception:
            fin(traceback.format_exc()); return None
        st["i"]+=1; return interval
    bpy.app.timers.register(tick); print("capturing",name)
