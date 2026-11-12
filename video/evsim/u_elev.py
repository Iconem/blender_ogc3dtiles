exec(open(os.path.join(os.environ["TEMP"],"ogc_tests","r9","capx2.py")).read())
w,a,sp,r=v3d(); sp.show_region_ui=True; sp.shading.type="MATERIAL"; sc=bpy.context.scene
P.tile_geometry=False; P.meta_color=False; P.read_metadata=False; P.view_source="VIEWPORT"; P.comp_enabled=False
sc.world=None; P.max_screen_space_error=8.0; sc.render.engine="BLENDER_EEVEE"
setview(95,(0,0,0),58,20)
it=start("Elevator"); P.active_tileset=0
L={}
def light(i):
    o=L["o"]; t=i*0.16; o.location=(7*math.cos(t),7*math.sin(t),5)
def story():
    yield from wait(12)
    N=70
    for i in range(N):
        t=smooth(i/(N-1)); setview(95*(24/95)**t,(0,0,2*t),lerp(58,72,t),lerp(20,150,t)); yield
    yield from wait(8)
    ld=bpy.data.lights.new("MovingLight","POINT"); ld.energy=20000; ld.color=(1,0.75,0.4); ld.shadow_soft_size=0.3
    o=bpy.data.objects.new("MovingLight",ld); sc.collection.objects.link(o); L["o"]=o
    sp.shading.type="RENDERED"; CUR["key"]="EEVEE, Rendered, moving point light"
    for i in range(45): light(i); yield
    sc.render.engine="CYCLES"; sc.cycles.preview_samples=64
    CUR["key"]="Cycles, Rendered, same light"
    yield from wait(40)
    CUR["key"]="Cycles, Rendered: orbiting restarts the render"
    for i in range(14):
        setview(24,(0,0,2),72,150+i*1.5); yield
    CUR["key"]="Cycles, Rendered, same light"
    yield from wait(40)
    CUR["key"]=""
    sc.render.engine="BLENDER_EEVEE"; sp.shading.type="MATERIAL"
    yield from wait(4)
capture2("Elevator",story,interval=0.3)
