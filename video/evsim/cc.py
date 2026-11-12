exec(open(os.path.join(os.environ["TEMP"],"ogc_tests","r9","capx.py")).read())
w,a,sp,r=v3d(); sp.show_region_ui=True; sp.shading.type="MATERIAL"; sp.region_3d.use_clip_planes=False
sc=bpy.context.scene; cam=sc.camera; cam.data.display_size=80; cam.data.show_passepartout=False
for o in sc.objects: o.select_set(o is cam)
P.view_source="CAMERA"; P.tile_geometry=False; P.meta_color=False
N=230; A=95
def fn(i,n):
    if i<A:
        sp.region_3d.view_perspective="CAMERA"
        sc.frame_set(int(round(lerp(1,120,i/(A-1)))))
    else:
        t=(i-A)/(n-A-1)
        setview(lerp(1700,1100,smooth(t)),(0,0,0),lerp(50,62,t),lerp(-20,70,t))
        sc.frame_set(int(round(lerp(120,1,smooth(min(1,t*1.15))))))
sc.frame_set(1)
capture("camera",N,fn,animate=False)
