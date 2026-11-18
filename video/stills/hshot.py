# hshot.py: headless stills for the slide decks (blender -b --factory-startup? no: user prefs for the add-on)
#   blender -b --python hshot.py -- <shot>
# Writes slides_shots/<shot>_<variant>.png. Streams with ui.stream_tick in a loop, no window.
import os, sys, time, math, importlib, colorsys, zlib
import bpy
from mathutils import Vector
R9 = os.path.join(os.environ["TEMP"], "ogc_tests", "r9")
PK = "bl_ext.user_default.ogc_3dtiles_streaming"
ui = importlib.import_module(PK + ".ui"); lib = importlib.import_module(PK + ".library")
extras = importlib.import_module(PK + ".ui.extras")
gd = importlib.import_module(PK + ".geometry_demos")
origin = importlib.import_module(PK + ".tileset.origin")
geosearch = importlib.import_module(PK + ".geosearch")
io_ = importlib.import_module(PK + ".io")
shot = sys.argv[sys.argv.index("--") + 1]
sc = bpy.context.scene; P = sc.ogc3dtiles
OUT = os.path.join(R9, "slides_shots"); os.makedirs(OUT, exist_ok=True)
GOOGLE = "Google Photorealistic 3D Tiles"

def log(*a):
    print("[hshot]", *a, flush=True)

def reset():
    for o in list(bpy.data.objects): bpy.data.objects.remove(o)
    P.tilesets.clear(); P.comp_enabled = False

def add(entry):
    rows = lib.read_all(extras._library_paths())
    e = next(x for p, x in rows if x.get("name", "").startswith(entry))
    it = P.tilesets.add(); lib.apply_entry(it, e, add_overlay=lambda i: i.overlays.add())
    return it

def at(lat, lon, h=None):
    if h is None:
        h, msl, n, notes = geosearch.ellipsoid_height(lat, lon, io_.default_cache_dir(),
                                                      geosearch.TERRARIUM_URL, geosearch.GEOID_URL)
        log("ground", msl, "geoid", n, "->", h)
    P.origin_mode = "CUSTOM"; origin.set_origin(P, lat, lon, h); P.origin_valid = True

def camera(name, eye, target, lens=35.0, ortho=None, pano=False):
    cam = bpy.data.objects.get(name) or bpy.data.objects.new(name, bpy.data.cameras.new(name))
    if cam.name not in sc.collection.objects: sc.collection.objects.link(cam)
    cam.data.clip_start = 0.5; cam.data.clip_end = 1e6; cam.rotation_mode = "QUATERNION"
    eye, target = Vector(eye), Vector(target)
    cam.location = eye; cam.rotation_quaternion = (target - eye).to_track_quat("-Z", "Y")
    cam.data.lens = lens
    if ortho:
        cam.data.type = "ORTHO"; cam.data.ortho_scale = ortho
    if pano:
        cam.data.type = "PANO"
        try: cam.data.panorama_type = "EQUIRECTANGULAR"
        except Exception: cam.data.cycles.panorama_type = "EQUIRECTANGULAR"
    return cam

def res(x=1920, y=1080):
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = x, y, 100

def cycles(samples=48):
    cp = bpy.context.preferences.addons["cycles"].preferences
    cp.compute_device_type = "OPTIX"; cp.get_devices()
    for d in cp.devices: d.use = d.type != "CPU"
    sc.render.engine = "CYCLES"; sc.cycles.device = "GPU"; sc.cycles.samples = samples
    sc.cycles.use_adaptive_sampling = True; sc.cycles.adaptive_threshold = 0.02; sc.cycles.use_denoising = True
    try: sc.cycles.denoiser = "OPTIX"
    except Exception: pass
    look()

def eevee(samples=64):
    sc.render.engine = "BLENDER_EEVEE" if "BLENDER_EEVEE" in [i.identifier for i in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items] else "BLENDER_EEVEE_NEXT"
    sc.eevee.taa_render_samples = samples
    look()

def workbench(color="SINGLE"):
    sc.render.engine = "BLENDER_WORKBENCH"
    s = sc.display.shading
    s.light = "STUDIO"; s.color_type = color; s.single_color = (0.8, 0.8, 0.8)
    s.show_cavity = True; s.cavity_type = "BOTH"; s.curvature_ridge_factor = 1.0; s.curvature_valley_factor = 1.0
    s.cavity_ridge_factor = 1.0; s.cavity_valley_factor = 1.0
    s.show_shadows = True; s.shadow_intensity = 0.4
    sc.display.shadow_focus = 0.2
    try: sc.display.render_aa = "16"
    except Exception: pass
    sc.view_settings.view_transform = "Standard"

def look():
    sc.render.image_settings.file_format = "PNG"; sc.view_settings.view_transform = "AgX"; sc.view_settings.look = "None"

def grey_world(strength=1.0, c=(0.8, 0.82, 0.85)):
    w = sc.world or bpy.data.worlds.new("World"); sc.world = w; w.use_nodes = True
    bg = w.node_tree.nodes.get("Background")
    if bg is None:
        w.node_tree.nodes.clear()
        bg = w.node_tree.nodes.new("ShaderNodeBackground"); out = w.node_tree.nodes.new("ShaderNodeOutputWorld")
        w.node_tree.links.new(bg.outputs[0], out.inputs[0])
    bg.inputs[0].default_value = (*c, 1); bg.inputs[1].default_value = strength

def sky(elev=35.0, az=140.0, baked=None):
    gd.atmosphere(sc, elev, az); P.comp_enabled = False
    if baked is not None:
        relight(Baked_Light=baked)

def converge(max_wait=90.0, settle=1.5, min_wait=0.0):
    t0 = time.monotonic()
    while True:
        ui.stream_tick(bpy.context)
        now = time.monotonic()
        quiet = now - ui._state.get("last_change_t", now)
        if (ui._state.get("pending_total", 1) == 0 and quiet >= settle and now - t0 >= min_wait) or now - t0 > max_wait:
            log("converged in %.1f s, pending %s" % (now - t0, ui._state.get("pending_total")))
            return
        time.sleep(0.03)

def start(view_cam, sse=4.0, wait=90.0, min_wait=20.0):
    sc.camera = view_cam
    P.view_source = "OBJECT"; P.view_camera = view_cam; P.max_screen_space_error = float(sse)
    log(bpy.ops.ogc3dtiles.start_stream())
    converge(wait, min_wait=min_wait)

def render(name, cam=None):
    if cam is not None: sc.camera = cam
    p = os.path.join(OUT, f"{shot}_{name}.png"); sc.render.filepath = p
    t = time.monotonic(); bpy.ops.render.render(write_still=True); log("wrote", p, "%.1f s" % (time.monotonic() - t))

def tiles():
    return [o for o in sc.objects if "tile_url" in o and o.type in ("MESH", "POINTCLOUD")]

def tile_colours():
    for o in tiles():
        h = (zlib.crc32(o.name.encode()) % 1000) / 1000.0
        o.color = (*colorsys.hsv_to_rgb(h, 0.55, 0.95), 1.0)

def relight(**vals):
    P.auto_relight = True
    ng = bpy.data.node_groups.get("OGC3D Relight")
    for k, v in vals.items():
        k = k.replace("_", " ").replace("X ray", "X-ray")
        for n in ng.nodes:
            if (n.label == k or n.name == k) and n.outputs: n.outputs[0].default_value = v

def tube_lines(name, segs, colour=(0.76, 0.34, 0.04), radius=6.0):
    """Polyline segments as a thick curve, an emissive object visible in every engine."""
    cu = bpy.data.curves.new(name, "CURVE"); cu.dimensions = "3D"; cu.bevel_depth = radius; cu.bevel_resolution = 2
    for a, b in segs:
        sp = cu.splines.new("POLY"); sp.points.add(1)
        sp.points[0].co = (*a, 1); sp.points[1].co = (*b, 1)
    ob = bpy.data.objects.new(name, cu); sc.collection.objects.link(ob)
    m = bpy.data.materials.new(name); m.use_nodes = True
    bs = m.node_tree.nodes.get("Principled BSDF")
    bs.inputs["Base Color"].default_value = (*colour, 1); bs.inputs["Emission Color"].default_value = (*colour, 1)
    bs.inputs["Emission Strength"].default_value = 2.0
    m.diffuse_color = (*colour, 1); cu.materials.append(m); ob.color = (*colour, 1)
    return ob

def frustum_segs(cam, length, aspect=16 / 9):
    """Edges of a camera's view volume, out to `length` metres (scaled up for a map view)."""
    M = cam.matrix_world; d = cam.data
    if d.type == "ORTHO":
        hw = d.ortho_scale / 2; hh = hw / aspect
        near = [M @ Vector((x * hw, y * hh, 0)) for x, y in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        far = [M @ Vector((x * hw, y * hh, -length)) for x, y in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    else:
        t = 18.0 / d.lens                       # half width / distance for a 36 mm sensor
        near = [M @ Vector((0, 0, 0))] * 4
        far = [M @ Vector((x * t * length, y * t / aspect * length, -length)) for x, y in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    s = [(near[i], far[i]) for i in range(4)] + [(far[i], far[(i + 1) % 4]) for i in range(4)]
    if d.type == "ORTHO":
        s += [(near[i], near[(i + 1) % 4]) for i in range(4)]
    return s

def top_cam(centre, scale, h=4000.0):
    c = Vector(centre)
    cam = camera("Top", c + Vector((0, 0, h)), c, ortho=scale)
    cam.rotation_quaternion = Vector((0, 0, -1)).to_track_quat("-Z", "Y")
    cam.location = c + Vector((0, 0, h)); cam.data.clip_end = h * 3
    return cam

def map_view(cam, centre, scale, length, name):
    """Top view: every tile in its own colour, the selecting camera's frustum drawn large."""
    tile_colours()
    fr = tube_lines("Frustum", frustum_segs(cam, length), colour=(1, 1, 1), radius=scale / 400)
    tc = top_cam(centre, scale)
    workbench("OBJECT"); sc.display.shading.show_shadows = False
    render(name, tc)
    bpy.data.objects.remove(fr)


def bounds():
    obs = [o for o in tiles() if o.visible_get()]
    pts = [o.matrix_world @ Vector(c) for o in obs for c in o.bound_box]
    lo = Vector([min(q[i] for q in pts) for i in range(3)]); hi = Vector([max(q[i] for q in pts) for i in range(3)])
    log("bounds", lo, hi); return lo, hi

def reframe(eye, target, lens=35.0, sse=None, wait=150, min_wait=20):
    cam = camera("Cam", eye, target, lens); P.view_camera = cam; sc.camera = cam
    if sse: P.max_screen_space_error = float(sse)
    converge(wait, min_wait=min_wait); return cam

def clip_box(it, centre, half):
    me = bpy.data.meshes.new("Clip box")
    me.from_pydata([(x, y, z) for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)], [],
                   [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)])
    box = bpy.data.objects.new("Clip box", me); sc.collection.objects.link(box)
    box.location = centre; box.scale = half; box.hide_render = True
    c = it.clip_polygons.add(); c.obj = box; c.shape = "BOX"
    it.clip_mode = "KEEP_ANY"; it.use_clipping = True
    return box

def light_bg(c=(0.93, 0.93, 0.93)):
    """Camera rays see a light grey; lighting still comes from the sky. Keeps EDL (opaque film) on a light page."""
    nt = sc.world.node_tree; out = next(n for n in nt.nodes if n.type == "OUTPUT_WORLD")
    src = out.inputs[0].links[0].from_socket
    lp = nt.nodes.new("ShaderNodeLightPath"); bg = nt.nodes.new("ShaderNodeBackground"); mx = nt.nodes.new("ShaderNodeMixShader")
    bg.inputs[0].default_value = (*c, 1); bg.inputs[1].default_value = 1.0
    nt.links.new(lp.outputs["Is Camera Ray"], mx.inputs[0]); nt.links.new(src, mx.inputs[1]); nt.links.new(bg.outputs[0], mx.inputs[2])
    nt.links.new(mx.outputs[0], out.inputs[0])

def settle(n=60):
    for _ in range(n): ui.stream_tick(bpy.context); time.sleep(0.05)

# ───────────────────────────── shots ─────────────────────────────
reset(); res()
if shot == "notredame":
    at(48.85296, 2.35010); add(GOOGLE); sky(30, 230, 0.8)
    cam = camera("Cam", (250, -230, 270), (0, 0, 30), 32)
    start(cam, 6, wait=240, min_wait=30); cycles(64); render("cycles")
elif shot == "manhattan":
    at(40.74844, -73.98566); add(GOOGLE); sky(28, 250, 0.8)
    cam = camera("Cam", (-600, -2300, 1100), (200, 300, 60), 38)
    start(cam, 6, wait=300, min_wait=30); cycles(64); render("cycles")
elif shot == "colosseum_clip":
    at(41.89021, 12.49223); it = add(GOOGLE); sky(40, 200, 0.8)
    me = bpy.data.meshes.new("Clip box")
    me.from_pydata([(x, y, z) for x in (-1, 1) for y in (-1, 1) for z in (0, 1)], [],
                   [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)])
    box = bpy.data.objects.new("Clip box", me); sc.collection.objects.link(box)
    box.scale = (190, 160, 120); box.location = (0, 0, -30); box.hide_render = True
    c = it.clip_polygons.add(); c.obj = box; c.shape = "BOX"
    it.clip_mode = "KEEP_ANY"; it.use_clipping = True
    cam = camera("Cam", (520, -560, 380), (0, 0, -10), 42)
    start(cam, 4, wait=240, min_wait=30); cycles(64); sc.render.film_transparent = True; render("cycles")
elif shot in ("cam_persp", "cam_ortho", "cam_pano"):
    at(41.89021, 12.49223); add(GOOGLE); sky(40, 200, 0.8)
    if shot == "cam_persp":
        cam = camera("Cam", (-480, -420, 160), (0, 0, 25), 28)
        start(cam, 6, wait=240, min_wait=30); cycles(48); render("view")
        map_view(cam, (900, 700, 0), 4200, 1300, "top")
    elif shot == "cam_ortho":
        cam = top_cam((0, 0, 0), 420, h=1500); cam.name = "Cam"; cam.data.clip_end = 5000
        start(cam, 4, wait=240, min_wait=30); cycles(48); render("view")
        map_view(cam, (0, 0, 0), 1100, 1600, "top")
    else:
        res(2048, 1024)
        cam = camera("Cam", (-60, -230, 35), (-60, 0, 35), pano=True)
        start(cam, 6, wait=240, min_wait=30); cycles(48); render("view")
        tile_colours()
        c0 = cam.location.copy(); R = 220
        ring = [(c0 + Vector((R * math.cos(a), R * math.sin(a), 0)), c0 + Vector((R * math.cos(a + math.pi / 24), R * math.sin(a + math.pi / 24), 0))) for a in [i * math.pi / 24 for i in range(48)]]
        cube = [(c0 + Vector(a) * 120, c0 + Vector(b) * 120) for a, b in [((-1,-1,0),(1,-1,0)),((1,-1,0),(1,1,0)),((1,1,0),(-1,1,0)),((-1,1,0),(-1,-1,0)),((-1,-1,0),(1,1,0)),((1,-1,0),(-1,1,0))]]
        fr = tube_lines("Frustum", ring + cube, colour=(1, 1, 1), radius=5)
        tc = top_cam(c0, 3200); workbench("OBJECT"); sc.display.shading.show_shadows = False
        render("top", tc)
elif shot == "eiffel":
    at(48.85826, 2.29450); add("IGN LiDAR HD, Eiffel"); grey_world(1.0)
    cam = camera("Cam", (430, -520, 210), (0, 0, 125), 35)
    start(cam, 3, wait=120)
    workbench("SINGLE"); render("solid")
    eevee(64); render("colour")
    P.comp_enabled = True; P.comp_edges = "EDL"; P.comp_edl_strength = 6.0; P.comp_ao = 0.0; P.comp_haze = 0.0
    render("edl"); P.comp_enabled = False
    gd.apply_demo("SUZANNE"); P.tile_geometry = True
    ng = io_.ensure_tile_geometry_group()
    for n in ng.nodes:
        if n.label == "Size" or n.name == "Size": n.outputs[0].default_value = 9.0
    for _ in range(40): ui.stream_tick(bpy.context); time.sleep(0.05)
    render("suzanne")
elif shot in ("sacre", "geghard"):
    add("Sacre-Coeur exterior 406M" if shot == "sacre" else "Geghard monastery"); P.origin_mode = "AUTO"; P.origin_valid = False
    sky(35, 200)
    cam = camera("Cam", (0, -900, 500), (0, 0, 0), 35)
    start(cam, 3, wait=60, min_wait=40)
    sc.render.film_transparent = True
    obs = [o for o in tiles() if o.visible_get()]
    pts = [o.matrix_world @ Vector(c) for o in obs for c in o.bound_box]
    lo = Vector([min(q[i] for q in pts) for i in range(3)]); hi = Vector([max(q[i] for q in pts) for i in range(3)])
    c = (lo + hi) / 2; sz = min((hi - lo).length, 1500.0); log("bounds", lo, hi)
    ang = math.radians(-60)
    cam = camera("Cam", c + Vector((0.5 * sz * math.cos(ang), 0.5 * sz * math.sin(ang), 0.3 * sz)), c + Vector((0, 0, -0.05 * sz)), 35)
    P.view_camera = cam; sc.camera = cam
    converge(150, min_wait=30)
    workbench("SINGLE"); render("solid")
    eevee(64); render("colour")
    P.comp_enabled = True; P.comp_edges = "EDL"; P.comp_edl_strength = 4.0; P.comp_ao = 0.0; P.comp_haze = 0.0
    render("edl"); P.comp_enabled = False
    gd.apply_demo("SUZANNE"); P.tile_geometry = True
    ng = io_.ensure_tile_geometry_group()
    for n in ng.nodes:
        if n.label == "Size" or n.name == "Size": n.outputs[0].default_value = max(sz / 75, 0.5)
        if n.label == "Share Of Points" or n.name == "Share Of Points": n.outputs[0].default_value = 0.00004
    for _ in range(60): ui.stream_tick(bpy.context); time.sleep(0.05)
    render("suzanne")
elif shot == "piazza":
    at(41.90225, 12.45720); add("Exterior piazza 400M, meshopt"); sky(38, 215)
    cam = camera("Cam", (170, -150, 95), (-150, 15, 0), 30)
    start(cam, 3, wait=120)
    sc.render.film_transparent = True
    workbench("SINGLE"); render("solid")
    eevee(64)
    relight(Albedo_Strength=0.0, Baked_Light=0.0); render("clay")
    relight(Albedo_Strength=1.0, Baked_Light=1.0); render("albedo")
    relight(Albedo_Strength=1.0, Baked_Light=0.3); render("relit")
    P.comp_enabled = True; P.comp_edges = "BOTH"; P.comp_edl_strength = 4.0; P.comp_crease_strength = 1.0
    P.comp_ao = 0.5; P.comp_haze = 0.35
    render("beauty")
elif shot == "piazza_suz":
    at(41.90225, 12.45720); add("Exterior piazza 400M, meshopt"); sky(38, 215)
    cam = camera("Cam", (60, -70, 40), (-60, 10, 5), 30)
    start(cam, 3, wait=120)
    sc.render.film_transparent = True; eevee(64); relight(Albedo_Strength=1.0, Baked_Light=0.4)
    gd.apply_demo("SUZANNE"); P.tile_geometry = True
    ng = io_.ensure_tile_geometry_group()
    for n in ng.nodes:
        if n.label == "Size" or n.name == "Size": n.outputs[0].default_value = 2.2
        if n.label == "Share Of Points" or n.name == "Share Of Points": n.outputs[0].default_value = 0.00025
    for _ in range(60): ui.stream_tick(bpy.context); time.sleep(0.05)
    render("suzanne")
elif shot == "xray":
    at(41.90219, 12.45334); add("Interior 473M, quantized JPEG"); grey_world(1.0, (1, 1, 1))
    cam = camera("Cam", (0, -600, 400), (0, 0, 0), 32)
    start(cam, 6, wait=60, min_wait=25)
    obs = [o for o in tiles() if o.visible_get()]
    pts = [o.matrix_world @ Vector(c) for o in obs for c in o.bound_box]
    lo = Vector([min(q[i] for q in pts) for i in range(3)]); hi = Vector([max(q[i] for q in pts) for i in range(3)])
    c = (lo + hi) / 2; sz = (hi - lo).length; log("bounds", lo, hi)
    ang = math.radians(-55)
    cam = camera("Cam", c + Vector((0.75 * sz * math.cos(ang), 0.75 * sz * math.sin(ang), 0.55 * sz)), c, 32)
    P.view_camera = cam; sc.camera = cam; P.max_screen_space_error = 4.0
    converge(150, min_wait=20)
    eevee(64)
    relight(Albedo_Strength=1.0, Baked_Light=1.0, X_ray=1.0, X_ray_Falloff=2.0)
    sc.render.film_transparent = True; render("xray")
elif shot == "nd_north":
    at(48.85296, 2.35010); add(GOOGLE); sky(32, 200, 0.8)
    cam = camera("Cam", (-20, -420, 260), (0, 10, 25), 32)
    start(cam, 6, wait=240, min_wait=30); cycles(64); render("cycles")
    tile_colours(); workbench("OBJECT"); render("tiles")
elif shot == "tokyo":
    at(35.65858, 139.74543); add(GOOGLE); sky(30, 230, 0.8)
    cam = camera("Cam", (-300, -380, 430), (10, 20, 110), 30)
    start(cam, 6, wait=300, min_wait=30); cycles(64); render("cycles")
elif shot == "colosseum3d":
    at(41.89021, 12.49223); add(GOOGLE); sky(28, 235, 0.8)
    cam = camera("Cam", (-250, -300, 190), (0, 0, 5), 35)
    start(cam, 5, wait=300, min_wait=30); cycles(64); render("cycles")
elif shot == "canyon":
    at(36.06570, -112.11750); add(GOOGLE); sky(25, 250, 0.8)
    cam = camera("Cam", (0, -300, 250), (300, 3500, -700), 30)
    start(cam, 8, wait=360, min_wait=40); cycles(64); render("cycles")
elif shot == "venice":
    at(45.43395, 12.33905); add("Venice flyover"); grey_world(1.0)
    cam = camera("Cam", (40, -300, 330), (-40, 110, 0), 32)
    start(cam, 3, wait=240, min_wait=30)
    sc.render.film_transparent = True; workbench("SINGLE"); render("solid")
elif shot == "bedrock":
    add("Bedrock Amsterdam voxels"); P.origin_mode = "AUTO"; P.origin_valid = False; sky(35, 200)
    cam = camera("Cam", (0, -3000, 2000), (0, 0, 0), 35)
    start(cam, 4, wait=90, min_wait=30)
    lo, hi = bounds(); c = (lo + hi) / 2; sz = (hi - lo).length
    eye = c + Vector((-0.25 * sz, -0.3 * sz, 0.22 * sz)); cam = reframe(eye, c, 35)
    # aim at the centre of the old frame's top quarter, 4x closer (no lens shift: cesium-native ignores it)
    d = cam.matrix_world.to_3x3() @ Vector((0, 0.75 * 18.0 / 35 * 9 / 16, -1))
    reframe(eye, eye + d * 100, 140, wait=150, min_wait=20)
    sc.render.film_transparent = True; eevee(64); render("eevee")
    workbench("MATERIAL"); render("solid")
elif shot == "geghard_cut":
    # exterior and interior Potree clouds, both through 3dtiled
    at(40.14056, 44.81778); it = add("Geghard monastery, Armenia"); it2 = add("Geghard monastery interior"); sky(35, 200)
    C = Vector((62, -5, 0))                      # the main church, found on a top view (gtop)
    cam = camera("Cam", C + Vector((80, -120, 130)), C, 35)
    start(cam, 1.5, wait=240, min_wait=60)
    import numpy as np
    zs = []
    for o in tiles():
        if not o.visible_get(): continue
        if o.type == "POINTCLOUD":
            n = len(o.data.points); a = np.empty(n * 3, np.float32); o.data.attributes["position"].data.foreach_get("vector", a)
        else:
            n = len(o.data.vertices); a = np.empty(n * 3, np.float32); o.data.vertices.foreach_get("co", a)
        a = a.reshape(-1, 3); w = np.c_[a, np.ones(len(a))] @ np.array(o.matrix_world).T
        zs.append(w[((w[:, 0] - C.x) ** 2 + (w[:, 1] - C.y) ** 2) < 144.0, 2])
    zs = np.concatenate(zs); log("near points", len(zs))
    g, r = float(np.percentile(zs, 2)), float(np.percentile(zs, 99.7)); log("ground", g, "roof", r)
    mid = Vector((C.x, C.y, g + 0.4 * (r - g)))
    sc.render.film_transparent = False; eevee(64); light_bg(); sc.view_settings.view_transform = "Standard"
    def edl(on):
        P.comp_enabled = on
        if on: P.comp_edges = "EDL"; P.comp_edl_strength = 8.0; P.comp_ao = 0.0; P.comp_haze = 0.0
    reframe(mid + Vector((75, -110, 85)), mid, 35, wait=180, min_wait=30)
    edl(True); render("colour")
    gd.apply_demo("REVEAL"); P.tile_geometry = True
    ng = io_.ensure_tile_geometry_group()
    for n in ng.nodes:
        if n.label == "Lowest Height": n.outputs[0].default_value = g - 15
        if n.label == "Height Range": n.outputs[0].default_value = (r - g) + 40
        if n.label == "Speed": n.outputs[0].default_value = (0.5 * (r - g) + 15) * sc.render.fps / 100.0
    sc.frame_set(100); settle(); render("reveal")
    P.tile_geometry = False; settle(20)
    # section along Z low enough to open the vaults and the rock-cut halls, on both clouds
    cz = g + 0.33 * (r - g)
    for t in (it, it2):
        clip_box(t, (C.x, C.y, cz - 300), (400, 400, 300))
    reframe(mid + Vector((24, -34, 50)), Vector((C.x, C.y, g)), 35, sse=1.0, wait=240, min_wait=30)
    settle(); render("cut")
    edl(False)
elif shot == "ign":
    at(48.85826, 2.29450); P.read_metadata = True; add("IGN LiDAR HD, Eiffel"); sky(30, 230)
    cam = camera("Cam", (300, -380, 430), (0, 0, 70), 35)
    P.point_radius_mode = "SCREEN"; P.point_px = 8.0
    start(cam, 2, wait=180, min_wait=30)
    P.meta_column = "classification"; P.meta_color = True; settle(40)
    for c in P.meta_classes:
        log("CLASS", c.column, c.code, c.name, tuple(round(x, 3) for x in getattr(c, "color", (0, 0, 0))[:3]))
    eevee(64); light_bg(); sc.view_settings.view_transform = "Standard"; sc.view_settings.exposure = -1.2; render("class")
    P.comp_enabled = True; P.comp_edges = "EDL"; P.comp_edl_strength = 14.0; P.comp_ao = 0.0; P.comp_haze = 0.0
    render("edl")
    P.comp_edges = "BOTH"; P.comp_crease_strength = 1.0; P.comp_ao = 0.6; P.comp_haze = 0.3
    render("beauty"); P.comp_enabled = False
elif shot == "lod_out":
    at(41.89467, 12.48302); add(GOOGLE); grey_world(1.0)
    cam = camera("Cam", (0, -420, 400), (0, 40, 20), 35)
    start(cam, 8, wait=240, min_wait=30)
    sc.render.film_transparent = True; workbench("TEXTURE"); s_ = sc.display.shading
    s_.light = "FLAT"; s_.show_cavity = False; s_.show_shadows = False
    render("view", cam)
    # Blender's camera gizmo: apex, frame and the filled "up" triangle, drawn 120 m deep
    D = 300.0; M = cam.matrix_world; t = 18.0 / cam.data.lens
    apex = M @ Vector((0, 0, 0))
    cr = [M @ Vector((x * t * D, y * t * D * 9 / 16, -D)) for x, y in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    top = [M @ Vector((-0.7 * t * D, 1.1 * t * D * 9 / 16, -D)), M @ Vector((0.7 * t * D, 1.1 * t * D * 9 / 16, -D)),
           M @ Vector((0, (1.1 * 9 / 16 + 0.55) * t * D, -D))]
    segs = [(apex, c) for c in cr] + [(cr[i], cr[(i + 1) % 4]) for i in range(4)] + [(top[i], top[(i + 1) % 3]) for i in range(3)]
    fr = tube_lines("Frustum", segs, colour=(1.0, 0.55, 0.05), radius=3.5)
    out = camera("Out", (-760, -1050, 760), (0, -100, 130), 40)
    fr.color = (1.0, 0.55, 0.05, 1)
    render("outside", out)
elif shot in ("bayon_shade", "gizeh_shade"):
    add("Angkor / tileset_Bayon" if shot == "bayon_shade" else "Gizeh /"); P.origin_mode = "AUTO"; P.origin_valid = False; sky(38, 215)
    cam = camera("Cam", (0, -600, 400), (0, 0, 0), 35)
    start(cam, 4, wait=60, min_wait=30)
    lo, hi = bounds(); c = (lo + hi) / 2; sz = min((hi - lo).length, 1500.0)
    ang = math.radians(-60)
    reframe(c + Vector((0.45 * sz * math.cos(ang), 0.45 * sz * math.sin(ang), 0.3 * sz)), c + Vector((0, 0, -0.08 * sz)), 35, sse=3, wait=180, min_wait=30)
    sc.render.film_transparent = True; eevee(64)
    relight(Albedo_Strength=0.0, Baked_Light=0.0); render("clay")
    relight(Albedo_Strength=1.0, Baked_Light=1.0); render("albedo")
    relight(Albedo_Strength=1.0, Baked_Light=0.3); render("relit")
elif shot == "gdbg":
    at(40.14056, 44.81778); it = add("Geghard monastery"); sky(35, 200)
    cam = camera("Cam", (120, -150, 110), (0, 30, 0), 35)
    start(cam, 3, wait=120, min_wait=30)
    def counts(tag):
        dg = bpy.context.evaluated_depsgraph_get(); n = 0; k = 0
        for o in tiles():
            if not o.visible_get(): continue
            e = o.evaluated_get(dg); k += 1
            d = getattr(e.data, "points", None) or getattr(e.data, "vertices", None)
            n += len(d) if d is not None else 0
        log(tag, "tiles", k, "points", n)
    sc.render.film_transparent = True; eevee(32); counts("plain"); render("a")
    gd.apply_demo("REVEAL"); P.tile_geometry = True
    ng = io_.ensure_tile_geometry_group()
    for n in ng.nodes:
        if n.label == "Lowest Height": n.outputs[0].default_value = 1000.0
    sc.frame_set(1); settle(); counts("reveal_high"); render("b")
    for n in ng.nodes:
        if n.label == "Lowest Height": n.outputs[0].default_value = 10.0
        if n.label == "Speed": n.outputs[0].default_value = 0.0
        if n.label == "Height Range": n.outputs[0].default_value = 1000.0
    settle(); counts("reveal_m20"); render("c")
    P.tile_geometry = False; settle(20); counts("off"); render("d")
    clip_box(it, (0, 0, -290), (400, 400, 300)); settle(); counts("clip"); render("e")
elif shot == "gtop":
    at(40.14056, 44.81778); add("Geghard monastery"); sky(35, 200)
    cam = top_cam((0, 50, 0), 300, h=600)
    start(cam, 3, wait=120, min_wait=30)
    sc.render.film_transparent = True; eevee(16); render("top")
elif shot == "gizeh_crease":
    add("Gizeh /"); P.origin_mode = "AUTO"; P.origin_valid = False; sky(38, 215)
    cam = camera("Cam", (0, -600, 400), (0, 0, 0), 35)
    start(cam, 4, wait=60, min_wait=30)
    lo, hi = bounds(); c = (lo + hi) / 2; sz = min((hi - lo).length, 1500.0)
    ang = math.radians(-60)
    reframe(c + Vector((0.45 * sz * math.cos(ang), 0.45 * sz * math.sin(ang), 0.3 * sz)), c + Vector((0, 0, -0.08 * sz)), 35, sse=3, wait=180, min_wait=30)
    sc.render.film_transparent = False; eevee(64)
    relight(Albedo_Strength=1.0, Baked_Light=0.6)
    P.comp_enabled = True; P.comp_edges = "NORMAL"; P.comp_crease_strength = 1.0; P.comp_ao = 0.4; P.comp_haze = 0.2
    render("crease")
    workbench("SINGLE"); P.comp_enabled = False; render("solid")
elif shot in ("gizeh_edl", "bayon_edl"):
    add("Gizeh /" if shot == "gizeh_edl" else "Angkor / tileset_Bayon"); P.origin_mode = "AUTO"; P.origin_valid = False; sky(38, 215)
    cam = camera("Cam", (0, -900, 600), (0, 0, 0), 35)
    start(cam, 4, wait=60, min_wait=30)
    lo, hi = bounds(); c = (lo + hi) / 2; sz = (hi - lo).length
    k = 0.8 if shot == "gizeh_edl" else 0.45; sz = sz if shot == "gizeh_edl" else min(sz, 1500.0)
    ang = math.radians(-60)
    reframe(c + Vector((k * sz * math.cos(ang), k * sz * math.sin(ang), 0.55 * k * sz)), c + Vector((0, 0, -0.08 * sz)), 35, sse=3, wait=200, min_wait=30)
    sc.render.film_transparent = False; eevee(64); light_bg(); sc.view_settings.view_transform = "Standard"
    relight(Albedo_Strength=1.0, Baked_Light=1.0)
    P.comp_enabled = True; P.comp_edges = "EDL"; P.comp_edl_strength = 10.0; P.comp_ao = 0.0; P.comp_haze = 0.0
    render("edl")
elif shot == "giza_google":
    at(29.97606, 31.13083); add(GOOGLE); sky(40, 230, 0.8)
    cam = camera("Cam", (950, -950, 620), (40, 0, 40), 35)
    start(cam, 6, wait=300, min_wait=30)
    sc.render.film_transparent = False; eevee(64); light_bg(); sc.view_settings.view_transform = "Standard"
    P.comp_enabled = True; P.comp_edges = "EDL"; P.comp_edl_strength = 10.0; P.comp_ao = 0.0; P.comp_haze = 0.0
    render("edl")
elif shot == "gizeh_geo":
    add("Gizeh /"); P.origin_mode = "AUTO"; P.origin_valid = False; sky(38, 215)
    cam = camera("Cam", (0, -900, 600), (0, 0, 0), 35)
    start(cam, 4, wait=60, min_wait=30)
    import numpy as np
    pts = []
    for o in tiles():
        if o.type != "MESH" or not o.visible_get(): continue
        n = len(o.data.vertices); a = np.empty(n * 3, np.float32); o.data.vertices.foreach_get("co", a)
        a = a.reshape(-1, 3); pts.append(np.c_[a, np.ones(len(a))] @ np.array(o.matrix_world).T)
    pts = np.concatenate(pts)[:, :3]
    k1 = pts[np.argmax(pts[:, 2])]
    far = pts[np.hypot(pts[:, 0] - k1[0], pts[:, 1] - k1[1]) > 150]
    k2 = far[np.argmax(far[:, 2])]
    log("apexes", k1, k2)
    a1, a2 = Vector(k1), Vector(k2); m = (a1 + a2) / 2; d = (a2 - a1); d.z = 0; L = d.length
    side = Vector((d.y, -d.x, 0)).normalized()           # perpendicular to the pair, on the south side
    if side.y > 0: side = -side
    ground = min(a1.z, a2.z) - 140
    tgt = Vector((m.x, m.y, ground + 40))
    eye = tgt + side * (1.15 * L) + Vector((0, 0, 0.75 * L))
    reframe(eye, tgt, 35, sse=2, wait=240, min_wait=30)
    # solid view variants (Workbench)
    workbench("SINGLE"); s_ = sc.display.shading; s_.single_color = (1, 1, 1); render("solid")
    s_.light = "MATCAP"; s_.show_cavity = False; s_.show_shadows = False
    caps = [l.name for l in bpy.context.preferences.studio_lights if l.type == "MATCAP"]; log("matcaps", caps)
    for want, tag in (("check_normal+y", "matcap_normal"), ("clay_brown", "matcap_clay"), ("clay_muddy", "matcap_muddy")):
        hit = next((c for c in caps if c.startswith(want)), None)
        if hit: s_.studio_light = hit; render(tag)
    # EEVEE, pure white geometry through the beauty compositor
    sc.render.film_transparent = False; eevee(64); light_bg(); sc.view_settings.view_transform = "Standard"
    relight(Albedo_Strength=0.0, Baked_Light=0.0)
    P.comp_enabled = True
    P.comp_edges = "EDL"; P.comp_edl_strength = 10.0; P.comp_ao = 0.0; P.comp_haze = 0.0; render("white_edl")
    P.comp_edges = "NORMAL"; P.comp_crease_strength = 1.0; render("white_crease")
    P.comp_edges = "BOTH"; P.comp_ao = 0.7; render("white_both_ao")
    P.comp_enabled = False; render("white")
elif shot == "gizeh_fit":
    from bpy_extras.object_utils import world_to_camera_view as w2c
    add("Gizeh /"); P.origin_mode = "AUTO"; P.origin_valid = False; sky(38, 215)
    cam = camera("Cam", (0, -900, 600), (0, 0, 0), 35)
    start(cam, 4, wait=60, min_wait=30)
    a1 = Vector((-27.797, 209.119, 109.741)); a2 = Vector((308.567, 564.109, 96.795))   # Khafre, Khufu apexes (gizeh_geo)
    base1, base2 = a1.z - 143.5, a2.z - 138.5                                           # heights of the two pyramids
    pts = [a1, a2]
    for a, b, h in ((a1, base1, 108.0), (a2, base2, 118.0)):                            # half base widths, with margin
        pts += [Vector((a.x + dx * h, a.y + dy * h, b)) for dx in (-1, 1) for dy in (-1, 1)]
    m = (a1 + a2) / 2; d = a2 - a1; d.z = 0; L = d.length
    side = Vector((d.y, -d.x, 0)).normalized()
    if side.y > 0: side = -side
    tgt = Vector((m.x, m.y, (base1 + base2) / 2 + 45))
    for f in [1.0 + 0.05 * i for i in range(60)]:
        cam.location = tgt + side * (f * L) + Vector((0, 0, 0.6 * f * L))
        cam.rotation_quaternion = (tgt - cam.location).to_track_quat("-Z", "Y"); bpy.context.view_layer.update()
        q = [w2c(sc, cam, p) for p in pts]
        if all(0.06 < v.x < 0.94 and 0.08 < v.y < 0.92 and v.z > 0 for v in q): break
    log("fit factor", f)
    reframe(tuple(cam.location), tgt, 35, sse=2, wait=240, min_wait=30)
    workbench("SINGLE"); s_ = sc.display.shading; s_.light = "MATCAP"; s_.show_cavity = False; s_.show_shadows = False
    s_.studio_light = "check_normal+y.exr"; sc.render.film_transparent = True
    render("matcap_normal")
else:
    raise SystemExit("unknown shot " + shot)
open(os.path.join(OUT, shot + ".done"), "w").write("ok")
log("done", shot)
