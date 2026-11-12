exec(open(os.path.join(os.environ["TEMP"],"ogc_tests","r9","capx.py")).read())
mode=open(os.path.join(R9,"n_name.txt")).read().strip()
w,a,sp,r=v3d(); sp.show_region_ui=True; sp.shading.type="MATERIAL"; sp.region_3d.use_clip_planes=False
sc=bpy.context.scene; cam=sc.camera; piv=bpy.data.objects["Pivot"]
cam.hide_viewport=False
for o in (cam,piv): o.animation_data_clear()
piv.rotation_euler=(0,0,0); piv.location=(0,0,0)
T=math.radians(38)
if mode=="orbit":
    cam.rotation_euler=(math.atan2(350,220),0,0)
    for f,z,k in ((1,0.0,1.6),(120,math.radians(45),0.75)):
        piv.rotation_euler=(0,0,z); piv.keyframe_insert("rotation_euler",frame=f)
        cam.location=(0,-350*k,220*k); cam.keyframe_insert("location",frame=f)
else:
    cam.rotation_euler=(T,0,0)
    for f,p in ((1,(-200,-250,300)),(65,(200,-250,300)),(120,(200,20,300))):
        cam.location=p; cam.keyframe_insert("location",frame=f)
for o in ((cam,piv) if mode!="orbit" else ()):
    for fc in (o.animation_data.action.fcurves if o.animation_data and hasattr(o.animation_data.action,"fcurves") else []):
        for k in fc.keyframe_points: k.interpolation="LINEAR"
cam.data.display_size=90; cam.data.show_passepartout=True; cam.data.passepartout_alpha=0.5; cam.data.lens=28
for o in sc.objects: o.select_set(o is cam)
P.view_source="CAMERA"; P.tile_geometry=False; P.meta_color=False; P.max_screen_space_error=8.0
A=110; B=150; N=A+B
def fn(i,n):
    if i<A:
        sp.region_3d.view_perspective="CAMERA"
        sc.frame_set(int(round(lerp(1,120,smooth(i/(A-1))))))
    else:
        if i==A: setview(2300 if mode=="orbit" else 1500,(0,150,0),12,0)
        j=i-A
        sc.frame_set(int(round(lerp(1,120,min(1,max(0,(j-12)/(B-30)))))))
sc.frame_set(1)
capture("cam_"+mode,N,fn,interval=0.25)
