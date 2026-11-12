exec(open(os.path.join(os.environ["TEMP"],"ogc_tests","r9","capx2.py")).read())
w,a,sp,r=v3d(); sp.show_region_ui=True; sp.shading.type="MATERIAL"
P.tile_geometry=False; P.meta_color=False; P.read_metadata=False; P.view_source="VIEWPORT"; P.comp_enabled=False
bpy.context.scene.world=None; P.max_screen_space_error=8.0
setview(1500,(120,100,0),52,30)
it=start("Lublin 178M"); P.active_tileset=0
def sse(v): P.max_screen_space_error=v
def story():
    yield from wait(14)
    yield from move((620,520),8)
    yield from wheel(4,3)
    yield from wait(6)
    yield from orbit(50,0,16,drag=(-300,10))
    yield from wait(5)
    yield from zoomrect(420,360,820,620,settle=14)
    yield from orbit(-60,-10,18,drag=(320,-40))
    yield from wait(6)
    yield from wheel(3,3)
    yield from wait(10)
    yield from orbit(45,8,16,drag=(-240,30))
    yield from zoomrect(520,380,800,560,settle=16)
    yield from orbit(-50,0,18,drag=(280,0))
    yield from slide((1470,611),-70,sse,8.0,2.0,12,after=22)
    yield from orbit(40,0,14,drag=(-200,0))
    yield from wheel(-7,2)
    yield from wait(12)
capture2("Lublin",story)
