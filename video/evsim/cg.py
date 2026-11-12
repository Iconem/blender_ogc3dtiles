exec(open(os.path.join(os.environ["TEMP"],"ogc_tests","r9","capx.py")).read())
# n_name.txt: "<phase> <library name part>"; phase 1 loads, phase 2 frames, restarts and records
phase,n=open(os.path.join(R9,"n_name.txt")).read().strip().split(" ",1)
tag=n.split()[0].replace(",","")
ign="IGN LiDAR" in n
w,a,sp,r=v3d(); sp.show_region_ui=True; sp.shading.type="MATERIAL"
def go():
    P.tile_geometry=False; P.meta_color=False; P.view_source="VIEWPORT"; P.comp_enabled=False
    P.read_metadata=ign
    bpy.context.scene.world=None
    sp.region_3d.use_clip_planes=False; sp.region_3d.view_perspective="PERSP"
    sp.shading.type="MATERIAL"
    w2,a2,sp2,r2=v3d()
    with bpy.context.temp_override(window=w,area=a,region=r):
        try: bpy.ops.ogc3dtiles.stop_stream()
        except Exception as e: print("stop",e)
    for o in list(bpy.context.scene.objects): bpy.data.objects.remove(o)
    P.tilesets.clear(); P.origin_mode="AUTO"; P.origin_valid=False
    rows=lib.read_all(extras._library_paths())
    e=next(x for p,x in rows if n in x.get("name",""))
    it=P.tilesets.add(); lib.apply_entry(it,e,add_overlay=lambda i:i.overlays.add()); P.active_tileset=0
    with bpy.context.temp_override(window=w,area=a,region=r):
        if ign:
            extras._overlay_presets[:] = lib.overlay_presets(extras._library_paths())
            names=[p["name"] for p in extras._overlay_presets]; print(names)
            print(bpy.ops.ogc3dtiles.overlay_preset(index=next(i for i,x in enumerate(names) if "IGN" in x)))
            it.use_overlays=True; print("overlays", it.use_overlays, len(it.overlays), [(o.name,o.kind) for o in it.overlays])
        print(bpy.ops.ogc3dtiles.start_stream())
    return it
if phase=="1":
    go()
else:
    k,mn,mx=bbox()
    c=[(mn[i]+mx[i])/2 for i in range(3)]; size=max(mx[i]-mn[i] for i in range(2))
    print("tiles",k,"min",[round(v,1) for v in mn],"max",[round(v,1) for v in mx],[c.name for c in P.meta_columns])
    N=200; HOLD=12
    import statistics
    obs=[o for o in bpy.context.scene.objects if "tile_url" in o]
    cs=[o.matrix_world @ (sum((Vector(q) for q in o.bound_box),Vector())/8) for o in obs]
    if len(cs)>20: c=[statistics.median(p[i] for p in cs) for i in range(3)]
    END={"Hayravank":40.0,"IGN":330.0}.get(tag, size*0.28)
    if ign: c=[-263.0,-229.0,mn[2]+110]
    print("target",[round(v,1) for v in c],"end",END)
    def fn(i,M):
        t=smooth((i-HOLD)/(M-HOLD-10))
        setview(size*1.15*(END/(size*1.15))**t,c,lerp(56,70,t),lerp(30,190,t))
        if ign and i==70:
            col=next((x.name for x in P.meta_columns if "class" in x.name.lower()),None)
            if col: P.meta_column=col; P.meta_color=True
        if ign and i==140: P.meta_color=False
    fn(0,N)
    go()
    capture(tag,N,fn)
