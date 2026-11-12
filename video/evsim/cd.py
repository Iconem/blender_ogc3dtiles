exec(open(os.path.join(os.environ["TEMP"],"ogc_tests","r9","capx.py")).read())
w,a,sp,r=v3d()
with bpy.context.temp_override(window=w,area=a,region=r):
    try: bpy.ops.ogc3dtiles.stop_stream()
    except Exception as e: print("stop",e)
for o in list(bpy.context.scene.objects): bpy.data.objects.remove(o)
P.tilesets.clear(); P.auto_relight=False; P.comp_enabled=False; P.tile_geometry=False
P.read_metadata=False; P.meta_color=False; P.view_source="VIEWPORT"
sc=bpy.context.scene; sc.world=None
rows=lib.read_all(extras._library_paths())
e=next(x for p,x in rows if x.get("name","").startswith("Strasbourg"))
it=P.tilesets.add(); lib.apply_entry(it,e,add_overlay=lambda i:i.overlays.add()); P.active_tileset=0
P.origin_mode="CUSTOM"; P.origin_lat=48.5818; P.origin_lon=7.7509; P.origin_height=190; P.origin_valid=True
sp.show_region_ui=True; sp.shading.type="SOLID"; sp.shading.color_type="TEXTURE"; sp.shading.light="FLAT"
if sp.region_3d.use_clip_planes:
    with bpy.context.temp_override(window=w,area=a,region=r): bpy.ops.view3d.clip_border()
S=150.0
vs=[(x*S,y*S,z*S) for x in (-1,1) for y in (-1,1) for z in (-1,1)]
fs=[(0,1,3,2),(4,6,7,5),(0,4,5,1),(2,3,7,6),(0,2,6,4),(1,5,7,3)]
me=bpy.data.meshes.new("Clip box"); me.from_pydata(vs,[],fs); me.update()
box=bpy.data.objects.new("Clip box",me); sc.collection.objects.link(box); box.display_type="WIRE"; box.location=(-400,0,0)
box.hide_viewport=True
N=215
def view_at(i):
    t=i/N
    setview(lerp(900,700,smooth(t)),(0,0,0),lerp(58,62,t),20+t*150)
def fn(i,n):
    view_at(i)
    if i==45:
        box.hide_viewport=False
        with bpy.context.temp_override(window=w,area=a,region=r,selected_objects=[box]):
            bpy.ops.ogc3dtiles.clip_add()
        it.clip_geometry=True
    if 45<=i<90:
        box.location=(lerp(-400,150,smooth((i-45)/40)),0,0)
    if i==90: it.clip_mode="KEEP_ANY"
    if 90<=i<125:
        k=lerp(1.0,2.2,smooth((i-95)/25)); box.scale=(k,k,1)
    if i==125:
        it.use_clipping=False; box.hide_viewport=True
    if i==135:
        with bpy.context.temp_override(window=w,area=a,region=r):
            bpy.ops.view3d.clip_border(xmin=int(r.width*0.25),xmax=int(r.width*0.62),ymin=int(r.height*0.22),ymax=int(r.height*0.75))
    if i==190 and sp.region_3d.use_clip_planes:
        with bpy.context.temp_override(window=w,area=a,region=r):
            bpy.ops.view3d.clip_border()
view_at(0)
with bpy.context.temp_override(window=w,area=a,region=r):
    print(bpy.ops.ogc3dtiles.start_stream())
capture("clip",N,fn)
