# ───────────────────────────── animations ─────────────────────────────
# One converged render per frame: the camera (or a setting) moves, the tiles of that frame finish loading, the frame
# renders. Frames go to slides_shots/anim_<shot>/f_NNNN.png; enc_anim.sh turns them into docs/video clips.
FPS = 24
def ease(t):
    t = max(0.0, min(1.0, t)); return t * t * (3 - 2 * t)
def look_at(cam, eye, target):
    cam.location = Vector(eye); cam.rotation_quaternion = (Vector(target) - Vector(eye)).to_track_quat("-Z", "Y")
def anim(frames, step, wait=25.0, settle=0.35):
    """step(i, t) sets the frame up (t from 0 to 1); then the tiles converge and the frame renders."""
    d = os.path.join(OUT, "anim_" + shot); os.makedirs(d, exist_ok=True)
    sc.render.fps = FPS; t0 = time.monotonic()
    for i in range(frames):
        p = os.path.join(d, "f_%04d.png" % i)
        step(i, i / max(frames - 1, 1)); bpy.context.view_layer.update()
        converge(wait, settle=settle)
        sc.render.filepath = p; bpy.ops.render.render(write_still=True)
        log("frame %d/%d, %.0f s so far" % (i + 1, frames, time.monotonic() - t0))
    open(os.path.join(d, "done.txt"), "w").write("%d frames" % frames)

reset(); res(1280, 720)
if shot == "a_gizeh":
    # Khafre and Khufu, Workbench with the normal matcap, a slow orbit around the pair
    add("Gizeh /"); P.origin_mode = "AUTO"; P.origin_valid = False; sky(38, 215)
    a1 = Vector((-27.797, 209.119, 109.741)); a2 = Vector((308.567, 564.109, 96.795))
    m = (a1 + a2) / 2; d = a2 - a1; d.z = 0; L = d.length
    side = Vector((d.y, -d.x, 0)).normalized()
    if side.y > 0: side = -side
    tgt = Vector((m.x, m.y, (a1.z - 143.5 + a2.z - 138.5) / 2 + 45))
    base = math.atan2(side.y, side.x)
    def eye(t):
        a = base + math.radians(-35 + 70 * ease(t)); r = 1.75 * L
        return tgt + Vector((r * math.cos(a), r * math.sin(a), 0.62 * r))
    cam = camera("Cam", eye(0), tgt, 35)
    start(cam, 3, wait=240, min_wait=40)
    workbench("SINGLE"); s_ = sc.display.shading; s_.light = "MATCAP"; s_.show_cavity = False; s_.show_shadows = False
    s_.studio_light = "check_normal+y.exr"; sc.render.film_transparent = True
    anim(144, lambda i, t: look_at(cam, eye(t), tgt))
elif shot == "a_ign":
    # IGN LiDAR HD around the Eiffel Tower, LAS classes and eye-dome lighting, a partial orbit
    at(48.85826, 2.29450); P.read_metadata = True; add("IGN LiDAR HD, Eiffel"); sky(30, 230)
    tgt = Vector((0, 0, 70))
    def eye(t):
        a = math.radians(-52 + 80 * ease(t)); r = 560
        return tgt + Vector((r * math.cos(a), r * math.sin(a), 360))
    cam = camera("Cam", eye(0), tgt, 35)
    P.point_radius_mode = "SCREEN"; P.point_px = 7.0
    start(cam, 2, wait=240, min_wait=40)
    P.meta_column = "classification"; P.meta_color = True; settle(40)
    eevee(16); light_bg(); sc.view_settings.view_transform = "Standard"; sc.view_settings.exposure = -1.2
    P.comp_enabled = True; P.comp_edges = "EDL"; P.comp_edl_strength = 14.0; P.comp_ao = 0.0; P.comp_haze = 0.0
    anim(144, lambda i, t: look_at(cam, eye(t), tgt))
elif shot == "a_geghard":
    # Geghard, interior and exterior clouds through 3dtiled: a section plane comes down through the church
    at(40.14056, 44.81778); it = add("Geghard monastery, Armenia"); it2 = add("Geghard monastery interior"); sky(35, 200)
    C = Vector((62, -5, 0)); g, r = 33.0, 54.0                     # ground and roof heights (geghard_cut)
    mid = Vector((C.x, C.y, g + 0.4 * (r - g)))
    eye0 = mid + Vector((30, -46, 52)); tgt = Vector((C.x, C.y, g))
    cam = camera("Cam", eye0, tgt, 35)
    start(cam, 1.5, wait=300, min_wait=60)
    sc.render.film_transparent = False; eevee(16); light_bg(); sc.view_settings.view_transform = "Standard"
    P.comp_enabled = True; P.comp_edges = "EDL"; P.comp_edl_strength = 8.0; P.comp_ao = 0.0; P.comp_haze = 0.0
    boxes = [clip_box(t_, (C.x, C.y, r + 30 - 300), (400, 400, 300)) for t_ in (it, it2)]
    def step(i, t):
        top = (r + 30) + ((g + 0.33 * (r - g)) - (r + 30)) * ease(min(1.0, t / 0.75))
        for b in boxes: b.location.z = top - 300
        a = math.radians(-8 * ease(t)); v = eye0 - tgt
        look_at(cam, tgt + Vector((v.x * math.cos(a) - v.y * math.sin(a), v.x * math.sin(a) + v.y * math.cos(a), v.z)), tgt)
    P.max_screen_space_error = 1.5
    anim(144, step, wait=40)
elif shot == "a_reveal":
    # the height reveal demo graph on Geghard: the monastery builds up from the ground
    at(40.14056, 44.81778); add("Geghard monastery, Armenia"); add("Geghard monastery interior"); sky(35, 200)
    C = Vector((62, -5, 0)); g, r = 33.0, 54.0
    mid = Vector((C.x, C.y, g + 0.4 * (r - g)))
    cam = camera("Cam", mid + Vector((75, -110, 85)), mid, 35)
    start(cam, 2, wait=300, min_wait=60)
    sc.render.film_transparent = False; eevee(16); light_bg(); sc.view_settings.view_transform = "Standard"
    P.comp_enabled = True; P.comp_edges = "EDL"; P.comp_edl_strength = 8.0; P.comp_ao = 0.0; P.comp_haze = 0.0
    gd.apply_demo("REVEAL"); P.tile_geometry = True
    ng = io_.ensure_tile_geometry_group()
    H = (r - g) + 40
    for n in ng.nodes:
        if n.label == "Lowest Height": n.outputs[0].default_value = g - 15
        if n.label == "Height Range": n.outputs[0].default_value = H
        if n.label == "Speed": n.outputs[0].default_value = H * FPS / 110.0   # the whole height in ~110 frames
    sc.frame_start = 1
    anim(132, lambda i, t: sc.frame_set(1 + i), settle=0.2)
elif shot == "a_bayon":
    # the Bayon: clay, then the photogrammetry albedo, then relit by the sun, on a slow push-in
    add("Angkor / tileset_Bayon"); P.origin_mode = "AUTO"; P.origin_valid = False; sky(38, 215)
    cam = camera("Cam", (0, -600, 400), (0, 0, 0), 35)
    start(cam, 4, wait=90, min_wait=30)
    lo, hi = bounds(); c = (lo + hi) / 2; sz = min((hi - lo).length, 1500.0); ang = math.radians(-60)
    e0 = c + Vector((0.5 * sz * math.cos(ang), 0.5 * sz * math.sin(ang), 0.33 * sz)); tgt = c + Vector((0, 0, -0.08 * sz))
    e1 = tgt + (e0 - tgt) * 0.8
    P.max_screen_space_error = 3; look_at(cam, e0, tgt); converge(200, min_wait=20)
    sc.render.film_transparent = False; eevee(16); light_bg((0.97, 0.97, 0.97))      # AgX, as the clay still
    def step(i, t):
        look_at(cam, e0.lerp(e1, ease(t)), tgt)
        k = ease((t - 0.25) / 0.2); s = ease((t - 0.62) / 0.2)       # clay -> albedo -> relit
        relight(Albedo_Strength=k, Baked_Light=k * (1.0 - 0.7 * s))
        P.comp_enabled = True; P.comp_edges = "EDL"; P.comp_edl_strength = 10.0 * k; P.comp_ao = 0.0; P.comp_haze = 0.0
    anim(168, step)
elif shot == "a_bayon_split":
    # the Bayon, clay in Cycles against albedo with eye-dome lighting in EEVEE, split by a moving diagonal
    import numpy as np
    add("Angkor / tileset_Bayon"); P.origin_mode = "AUTO"; P.origin_valid = False; sky(38, 215)
    cam = camera("Cam", (0, -600, 400), (0, 0, 0), 35)
    start(cam, 4, wait=90, min_wait=30)
    lo, hi = bounds(); c = (lo + hi) / 2; sz = min((hi - lo).length, 1500.0); ang = math.radians(-60)
    e0 = c + Vector((0.5 * sz * math.cos(ang), 0.5 * sz * math.sin(ang), 0.33 * sz)); tgt = c + Vector((0, 0, -0.08 * sz))
    e1 = tgt + (e0 - tgt) * 0.82
    P.max_screen_space_error = 3; look_at(cam, e0, tgt); converge(200, min_wait=20)
    sc.render.film_transparent = False; light_bg((0.97, 0.97, 0.97))
    d = os.path.join(OUT, "anim_" + shot); os.makedirs(d, exist_ok=True)
    W, H = sc.render.resolution_x, sc.render.resolution_y
    yy, xx = np.mgrid[0:H, 0:W]; u = xx / W; v = yy / H                 # v from the bottom (Blender pixel order)
    def px(path):
        im = bpy.data.images.load(path); a = np.empty(W * H * 4, np.float32); im.pixels.foreach_get(a)
        bpy.data.images.remove(im); return a.reshape(H, W, 4)
    N = 168; t0 = time.monotonic()
    for i in range(N):
        t = i / (N - 1)
        fp = os.path.join(d, "f_%04d.png" % i)
        if os.path.exists(fp) and os.path.getsize(fp) > 100000: continue     # resume after a timeout
        look_at(cam, e0.lerp(e1, ease(t)), tgt); bpy.context.view_layer.update(); converge(25, settle=0.35)
        cycles(32); P.comp_enabled = False; relight(Albedo_Strength=0.0, Baked_Light=0.0)
        a_ = os.path.join(d, "clay.png"); sc.render.filepath = a_; bpy.ops.render.render(write_still=True)
        eevee(16); relight(Albedo_Strength=1.0, Baked_Light=1.0)
        P.comp_enabled = True; P.comp_edges = "EDL"; P.comp_edl_strength = 10.0; P.comp_ao = 0.0; P.comp_haze = 0.0
        b_ = os.path.join(d, "albedo.png"); sc.render.filepath = b_; bpy.ops.render.render(write_still=True)
        A, B = px(a_), px(b_)
        p = 0.5 + 0.3 * math.sin(2 * math.pi * t)                          # the line sweeps and comes back: loops
        s = (u - 0.25 * v) - (p - 0.125)                                    # a diagonal leaning right
        m = np.clip(s * W / 1.5, -1, 1) * 0.5 + 0.5                         # 1.5 px soft edge, albedo on the right
        out = A * (1 - m[..., None]) + B * m[..., None]
        line = np.abs(s) * W < 1.5; out[line] = (1, 1, 1, 1)
        im = bpy.data.images.new("split", W, H, alpha=True); im.pixels.foreach_set(out.astype(np.float32).ravel())
        im.filepath_raw = os.path.join(d, "f_%04d.png" % i); im.file_format = "PNG"; im.save(); bpy.data.images.remove(im)
        log("frame %d/%d, %.0f s so far" % (i + 1, N, time.monotonic() - t0))
    for f_ in ("clay.png", "albedo.png"): os.remove(os.path.join(d, f_))
elif shot == "a_venice":
    # Piazza San Marco in the Solid view, a slow dolly across the square
    at(45.43395, 12.33905); add("Venice flyover"); grey_world(1.0)
    e0 = Vector((-60, -320, 300)); e1 = Vector((120, -260, 260)); t0_ = Vector((-60, 110, 0)); t1_ = Vector((20, 120, 0))
    cam = camera("Cam", e0, t0_, 32)
    start(cam, 3, wait=300, min_wait=40)
    sc.render.film_transparent = True; workbench("SINGLE")
    anim(144, lambda i, t: look_at(cam, e0.lerp(e1, ease(t)), t0_.lerp(t1_, ease(t))))
elif shot == "a_canyon":
    # the Grand Canyon from Yavapai Point, Google tiles in EEVEE, a slow pan along the rim
    at(36.06570, -112.11750); add(GOOGLE); sky(25, 250, 0.8)
    eye = Vector((0, -300, 250))
    def tgt(t):
        a = math.radians(-12 + 24 * ease(t)); return eye + Vector((3500 * math.sin(a), 3800 * math.cos(a), -950))
    cam = camera("Cam", eye, tgt(0), 30)
    start(cam, 8, wait=360, min_wait=40)
    eevee(32)
    anim(144, lambda i, t: look_at(cam, eye, tgt(t)), wait=40)
elif shot == "a_tokyo":
    # Tokyo Tower, Google tiles in EEVEE, a partial orbit
    at(35.65858, 139.74543); add(GOOGLE); sky(30, 230, 0.8)
    tgt = Vector((10, 20, 110))
    def eye(t):
        a = math.radians(-128 + 70 * ease(t)); r = 480
        return tgt + Vector((r * math.cos(a), r * math.sin(a), 330))
    cam = camera("Cam", eye(0), tgt, 30)
    start(cam, 6, wait=360, min_wait=40)
    eevee(32)
    anim(144, lambda i, t: look_at(cam, eye(t), tgt), wait=40)
else:
    raise SystemExit("unknown animation " + shot)
open(os.path.join(OUT, shot + ".done"), "w").write("ok")
log("done", shot)
