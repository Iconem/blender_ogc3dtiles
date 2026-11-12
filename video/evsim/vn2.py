mats=importlib.import_module(PK+".materials"); io=importlib.import_module(PK+".io")
n=open(os.path.join(os.environ["TEMP"],"ogc_tests","r9","n_name.txt")).read().strip()
sc=bpy.context.scene
w,a,sp,r=v3d()
out=os.path.join(os.environ["TEMP"],"ogc_tests","r9","vid_"+n)
os.makedirs(out,exist_ok=True)
for f in os.listdir(out): os.remove(os.path.join(out,f))
sc.render.filepath=os.path.join(out,"f_")
if n=="reveal":
    P.meta_color=False
    with bpy.context.temp_override(window=w,area=a,region=r):
        bpy.ops.ogc3dtiles.geometry_demo(demo="REVEAL")
    ng=bpy.data.node_groups["OGC3D Tile Geometry"]
    ng.nodes["Lowest Height"].outputs[0].default_value=-70.0
    ng.nodes["Height Range"].outputs[0].default_value=110.0
    ng.nodes["Speed"].outputs[0].default_value=22.0
elif n=="noise":
    P.meta_color=False
    with bpy.context.temp_override(window=w,area=a,region=r):
        bpy.ops.ogc3dtiles.geometry_demo(demo="NOISE")
    ng=bpy.data.node_groups["OGC3D Tile Geometry"]
    ng.nodes["Amplitude"].outputs[0].default_value=70.0
    ng.nodes["Noise Scale"].outputs[0].default_value=0.006
    ng.nodes["Speed"].outputs[0].default_value=0.8
else:
    P.tile_geometry=False
    P.meta_color=True; P.meta_column="tile (random color)"
    mats.sync_metadata(sc, force=True); io.refresh_feature_attributes(sc)
wd=bpy.data.worlds.get("NeutralW") or bpy.data.worlds.new("NeutralW"); wd.use_nodes=True
bg=wd.node_tree.nodes["Background"]; bg.inputs[0].default_value=(1,1,1,1); bg.inputs[1].default_value=1.0; sc.world=wd
sc.frame_set(1); sp.show_region_ui=False; sp.region_3d.view_perspective="CAMERA"
with bpy.context.temp_override(window=w,area=a,region=r):
    print(bpy.ops.ogc3dtiles.render_converged("INVOKE_DEFAULT"))
