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
if hasattr(P, "render_converge_cli"): P.render_converge_cli = False   # these scripts converge themselves
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
    # every tile the push-in needs loads here, from the widest view at the detail of the closest one; the stream is
    # then paused, so no tile swaps for a finer one while the frames render (the first take popped)
    P.max_screen_space_error = 3 * 0.8; look_at(cam, e0, tgt); converge(400, settle=3.0, min_wait=30)
    for it_ in P.tilesets: it_.enabled = False
    sc.render.film_transparent = False; light_bg((0.97, 0.97, 0.97))
    d = os.path.join(OUT, "anim_" + shot); os.makedirs(d, exist_ok=True)
    W, H = sc.render.resolution_x, sc.render.resolution_y
    yy, xx = np.mgrid[0:H, 0:W]; u = xx / W; v = yy / H                 # v from the bottom (Blender pixel order)
    def px(path):
        im = bpy.data.images.load(path); a = np.empty(W * H * 4, np.float32); im.pixels.foreach_get(a)
        bpy.data.images.remove(im); return a.reshape(H, W, 4)
    # two runs of this shot, PASS=eevee first: a 4 GB card does not hold the Cycles scene and EEVEE's textures at
    # once (EEVEE crashed in GPU_texture_update right after the first Cycles frame)
    N = 168; t0 = time.monotonic(); PASS = os.environ.get("PASS", "")
    for i in range(N):
        t = i / (N - 1)
        fp = os.path.join(d, "f_%04d.png" % i)
        if os.path.exists(fp) and os.path.getsize(fp) > 100000: continue     # resume after a timeout
        look_at(cam, e0.lerp(e1, ease(t)), tgt); bpy.context.view_layer.update()
        b_ = os.path.join(d, "albedo_%04d.png" % i)
        if PASS == "eevee":
            if os.path.exists(b_) and os.path.getsize(b_) > 100000: continue
            eevee(16); relight(Albedo_Strength=1.0, Baked_Light=1.0)
            P.comp_enabled = True; P.comp_edges = "EDL"; P.comp_edl_strength = 10.0; P.comp_ao = 0.0; P.comp_haze = 0.0
            sc.render.filepath = b_; bpy.ops.render.render(write_still=True)
            log("albedo %d/%d, %.0f s so far" % (i + 1, N, time.monotonic() - t0)); continue
        cycles(32); P.comp_enabled = False; relight(Albedo_Strength=0.0, Baked_Light=0.0)
        a_ = os.path.join(d, "clay.png"); sc.render.filepath = a_; bpy.ops.render.render(write_still=True)
        A, B = px(a_), px(b_)
        p = 0.5 + 0.3 * math.sin(2 * math.pi * t)                          # the line sweeps and comes back: loops
        s = (u - 0.25 * v) - (p - 0.125)                                    # a diagonal leaning right
        m = np.clip(s * W / 1.5, -1, 1) * 0.5 + 0.5                         # 1.5 px soft edge, albedo on the right
        out = A * (1 - m[..., None]) + B * m[..., None]
        line = np.abs(s) * W < 1.5; out[line] = (1, 1, 1, 1)
        im = bpy.data.images.new("split", W, H, alpha=True); im.pixels.foreach_set(out.astype(np.float32).ravel())
        im.filepath_raw = os.path.join(d, "f_%04d.png" % i); im.file_format = "PNG"; im.save(); bpy.data.images.remove(im)
        os.remove(b_); log("frame %d/%d, %.0f s so far" % (i + 1, N, time.monotonic() - t0))
    if PASS != "eevee": os.remove(os.path.join(d, "clay.png"))
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
elif shot in ("a_tiles", "a_cameras"):
    # a_tiles: Notre-Dame, Google tiles in EEVEE against every tile in its own colour, split by a moving diagonal,
    #   while the camera pushes in and the tiles refine.
    # a_cameras: one camera, three projections (perspective, orthographic, panoramic), Cycles, with a top view inset
    #   of the tiles it selected and its view volume.
    import numpy as np
    from mathutils import Quaternion
    d = os.path.join(OUT, "anim_" + shot); os.makedirs(d, exist_ok=True)
    W, H = 1280, 720
    def px(path):
        im = bpy.data.images.load(path); w_, h_ = im.size; a = np.empty(w_ * h_ * 4, np.float32); im.pixels.foreach_get(a)
        bpy.data.images.remove(im); return a.reshape(h_, w_, 4)
    def save(out, i):
        im = bpy.data.images.new("comp", W, H, alpha=True); im.pixels.foreach_set(out.astype(np.float32).ravel())
        im.filepath_raw = os.path.join(d, "f_%04d.png" % i); im.file_format = "PNG"; im.save(); bpy.data.images.remove(im)
    def pass_(name, cam_):
        sc.camera = cam_; q = os.path.join(d, name + ".png"); sc.render.filepath = q
        bpy.ops.render.render(write_still=True); return px(q)
    def rot(v, deg):
        a = math.radians(deg); return Vector((v.x * math.cos(a) - v.y * math.sin(a), v.x * math.sin(a) + v.y * math.cos(a), v.z))
    t0 = time.monotonic(); SSE_ = 10 if shot == "a_tiles" else 16      # horizon views: 6 never settles
    if shot == "a_tiles":
        at(48.85296, 2.35010); add(GOOGLE); sky(32, 200, 0.8)
        tgt = Vector((0, 10, 25)); v0 = Vector((-20, -420, 260)) - tgt
        def eye(t): return tgt + rot(v0, -20 + 40 * ease(t)) * (1.15 - 0.4 * ease(t))
        cam = camera("Cam", eye(0), tgt, 32)
        start(cam, SSE_, wait=300, min_wait=30)
        yy, xx = np.mgrid[0:H, 0:W]; u = xx / W; v = yy / H
        N = 168
        for i in range(N):
            t = i / (N - 1)
            if os.path.exists(os.path.join(d, "f_%04d.png" % i)): continue
            look_at(cam, eye(t), tgt); bpy.context.view_layer.update(); converge(40, settle=0.35)
            eevee(32); A = pass_("beauty", cam)
            tile_colours(); workbench("OBJECT"); B = pass_("tiles", cam)
            p = 0.5 + 0.3 * math.sin(2 * math.pi * t)
            s_ = (u - 0.25 * v) - (p - 0.125)
            m = np.clip(s_ * W / 1.5, -1, 1) * 0.5 + 0.5                    # tiles on the right
            out = A * (1 - m[..., None]) + B * m[..., None]; out[np.abs(s_) * W < 1.5] = (1, 1, 1, 1)
            save(out, i); log("frame %d/%d, %.0f s so far" % (i + 1, N, time.monotonic() - t0))
    else:
        at(41.89021, 12.49223); add(GOOGLE); sky(40, 200, 0.8)
        e_p = Vector((-480, -420, 160)); v_p = Vector((0, 0, 25)) - e_p
        cam = camera("Cam", e_p, (0, 0, 25), 28)
        start(cam, SSE_, wait=300, min_wait=30)
        S, M = 400, 18; N = 168; seg = N // 3
        down = Vector((0, 0, -1)).to_track_quat("-Z", "Y")
        for i in range(N):
            k, j = divmod(i, seg); t = j / (seg - 1)
            if os.path.exists(os.path.join(d, "f_%04d.png" % i)): continue
            cd = cam.data
            if k == 0:                       # perspective: the view swings across the Colosseum
                cd.type = "PERSP"; cd.lens = 28; look_at(cam, e_p, e_p + rot(v_p, -16 + 32 * ease(t)))
                mc, ms, ml = Vector((650, 520, 0)), 3600, 1300; rx, ry = W, H
            elif k == 1:                     # orthographic, straight down: zoom in and turn
                cd.type = "ORTHO"; cd.ortho_scale = 760 - 360 * ease(t); cd.clip_end = 5000
                cam.location = (0, 0, 1500); cam.rotation_quaternion = Quaternion((0, 0, 1), math.radians(25 * ease(t))) @ down
                mc, ms, ml = Vector((0, 0, 0)), 1300, 1600; rx, ry = W, H
            else:                            # panoramic: the camera walks up to the arena
                cd.type = "PANO"
                try: cd.panorama_type = "EQUIRECTANGULAR"
                except Exception: cd.cycles.panorama_type = "EQUIRECTANGULAR"
                e = Vector((-60, -330, 35)).lerp(Vector((-60, -150, 35)), ease(t)); look_at(cam, e, e + Vector((0, 1, 0)))
                mc, ms, ml = e.copy(), 2600, 0; rx, ry = W, 640
            res(rx, ry); bpy.context.view_layer.update()
            converge(120 if j == 0 else 40, settle=0.35)
            cycles(24); sc.render.film_transparent = False; A = pass_("view", cam)
            tile_colours()
            if k < 2:
                segs = frustum_segs(cam, ml)
            else:
                c0 = cam.location.copy(); R = 220; st_ = math.pi / 24
                segs = [(c0 + Vector((R * math.cos(a), R * math.sin(a), 0)), c0 + Vector((R * math.cos(a + st_), R * math.sin(a + st_), 0))) for a in [n * st_ for n in range(48)]]
                segs += [(c0 + Vector(a) * 120, c0 + Vector(b) * 120) for a, b in [((-1,-1,0),(1,-1,0)),((1,-1,0),(1,1,0)),((1,1,0),(-1,1,0)),((-1,1,0),(-1,-1,0)),((-1,-1,0),(1,1,0)),((1,-1,0),(-1,1,0))]]
            fr = tube_lines("Frustum", segs, colour=(1, 1, 1), radius=ms / 300)
            tc = top_cam(mc, ms); workbench("OBJECT"); sc.display.shading.show_shadows = False
            res(S, S); B = pass_("top", tc)
            cu, mt = fr.data, fr.data.materials[0]; bpy.data.objects.remove(fr); bpy.data.curves.remove(cu); bpy.data.materials.remove(mt)
            res(W, H)
            out = np.empty((H, W, 4), np.float32); out[:] = (0.08, 0.08, 0.08, 1)
            o_ = (H - A.shape[0]) // 2; out[o_:o_ + A.shape[0]] = A
            y1, x1 = H - M, W - M                                           # top-right corner (rows from the bottom)
            out[y1 - S - 3:y1 + 3, x1 - S - 3:x1 + 3] = (1, 1, 1, 1); out[y1 - S:y1, x1 - S:x1] = B
            save(out, i); log("frame %d/%d, %.0f s so far" % (i + 1, N, time.monotonic() - t0))
    for f_ in os.listdir(d):
        if not f_.startswith("f_"): os.remove(os.path.join(d, f_))
elif shot == "a_colosseum_clip":
    # the Colosseum, Google tiles in EEVEE: a clip box closes in from the city to the amphitheatre
    at(41.89021, 12.49223); it = add(GOOGLE); sky(40, 200, 0.8)
    me = bpy.data.meshes.new("Clip box")
    me.from_pydata([(x, y, z) for x in (-1, 1) for y in (-1, 1) for z in (0, 1)], [],
                   [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)])
    box = bpy.data.objects.new("Clip box", me); sc.collection.objects.link(box)
    box.scale = (900, 800, 120); box.location = (0, 0, -30); box.hide_render = True
    c = it.clip_polygons.add(); c.obj = box; c.shape = "BOX"
    it.clip_mode = "KEEP_ANY"; it.use_clipping = True
    tgt = Vector((0, 0, -10)); v0 = Vector((520, -560, 380)) - tgt
    def eye(t):
        a = math.radians(-14 + 28 * ease(t))
        return tgt + Vector((v0.x * math.cos(a) - v0.y * math.sin(a), v0.x * math.sin(a) + v0.y * math.cos(a), v0.z))
    cam = camera("Cam", eye(0), tgt, 42)
    start(cam, 6, wait=300, min_wait=30)
    eevee(32); sc.render.film_transparent = True
    def step(i, t):
        k = ease((t - 0.1) / 0.6)
        box.scale = (900 + (190 - 900) * k, 800 + (160 - 800) * k, 120)
        look_at(cam, eye(t), tgt)
    anim(144, step, wait=40)
elif shot == "a_xray":
    # the San Pietro interior mesh from outside: X-ray fades in and the nave appears through the walls
    at(41.90219, 12.45334); add("Interior 473M, quantized JPEG"); grey_world(1.0, (1, 1, 1))
    cam = camera("Cam", (0, -600, 400), (0, 0, 0), 32)
    start(cam, 6, wait=60, min_wait=25)
    lo, hi = bounds(); c = (lo + hi) / 2; sz = (hi - lo).length
    def eye(t):
        a = math.radians(-80 + 50 * ease(t)); return c + Vector((0.75 * sz * math.cos(a), 0.75 * sz * math.sin(a), 0.55 * sz))
    cam = camera("Cam", eye(0), c, 32); P.view_camera = cam; sc.camera = cam; P.max_screen_space_error = 4.0
    converge(150, min_wait=20)
    eevee(32); sc.render.film_transparent = True
    def step(i, t):
        relight(Albedo_Strength=1.0, Baked_Light=1.0, X_ray=ease((t - 0.15) / 0.35), X_ray_Falloff=2.0)
        look_at(cam, eye(t), c)
    anim(144, step)
elif shot == "a_splat_xray":
    # Kirants monastery, Gaussian splats in a forest: the splats, then the add-on's X-ray on a dark background, the
    # points in their own colours and then in one tint, joined by diagonal wipes
    import numpy as np
    add("Kirants"); P.origin_mode = "AUTO"; P.origin_valid = False; sky(35, 200)
    cam = camera("Cam", (0, -600, 400), (0, 0, 0), 32); start(cam, 8, wait=90, min_wait=25)
    lo, hi = bounds(); c = (lo + hi) / 2; sz = (hi - lo).length
    f = 0.22; a0 = math.radians(-60); e0 = c + Vector((f * sz * math.cos(a0), f * sz * math.sin(a0), 0.6 * f * sz))
    look_at(cam, e0, c); bpy.context.view_layer.update()
    # the church: first the ray through where it shows in this framing, then the nearest dense splats along the
    # ray through the middle of a closer frame
    u, v = 0.585, 0.36; sw = cam.data.sensor_width
    d = cam.matrix_world.to_3x3() @ Vector(((u - 0.5) * sw / cam.data.lens, (0.5 - v) * sw / cam.data.lens * 720 / 1280, -1.0))
    T = e0 + d * ((c.z - e0.z) / d.z); A = T + Vector((0, 0, 10)); look_at(cam, A + (e0 - T) * 0.55, A)
    P.max_screen_space_error = 3.0; converge(240, min_wait=25); bpy.context.view_layer.update()
    E = np.array(cam.matrix_world.translation); Dv = np.array(cam.matrix_world.to_3x3() @ Vector((0, 0, -1))); deps = []
    for o in tiles():
        co = np.empty(len(o.data.vertices) * 3, np.float32); o.data.vertices.foreach_get("co", co); M = np.array(o.matrix_world)
        w = co.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3] - E; dz = w @ Dv
        deps.append(dz[(np.linalg.norm(w - np.outer(dz, Dv), axis=1) < 2.5) & (dz > 1)])
    dep = float(np.percentile(np.concatenate(deps), 25)); C = Vector((E + Dv * dep).tolist()) - Vector((0, 0, 7))
    back = Vector((-Dv).tolist()); R = 1.6 * dep; h = back.z * R; rad = math.hypot(back.x, back.y) * R; az0 = math.atan2(back.y, back.x)
    def eye(t):
        az = az0 + math.radians(-35 + 70 * ease(t)); return C + Vector((rad * math.cos(az), rad * math.sin(az), h))
    look_at(cam, eye(0), C); converge(240, min_wait=20)
    eevee(32); sc.render.film_transparent = False; light_bg((0.006, 0.008, 0.014))
    P.xray_radius = 0.05
    # three looks joined by two diagonal wipes: the splats, X-ray in their own colours, X-ray in one tint. Each frame
    # renders the one or two looks on screen, the wipe joins them (as in a_bayon_split)
    d = os.path.join(OUT, "anim_" + shot); os.makedirs(d, exist_ok=True)
    W, H = sc.render.resolution_x, sc.render.resolution_y
    yy, xx = np.mgrid[0:H, 0:W]; u = xx / W; v = yy / H                 # v from the bottom (Blender pixel order)
    def px(path):
        im = bpy.data.images.load(path); a = np.empty(W * H * 4, np.float32); im.pixels.foreach_get(a)
        bpy.data.images.remove(im); return a.reshape(H, W, 4)
    LOOKS = {"splats": (False, 0.0, 0.3), "xray": (True, 0.0, 0.3), "tint": (True, 1.0, 0.12)}
    WIPES = (("splats", "xray", 0.18, 0.40), ("xray", "tint", 0.58, 0.80))
    def looks(t):
        for a_, b_, t0_, t1_ in WIPES:
            if t < t0_: return [(a_, 0.0)]
            if t < t1_: return [(a_, 0.0), (b_, ease((t - t0_) / (t1_ - t0_)))]
        return [(WIPES[-1][1], 0.0)]
    N = int(os.environ.get("FRAMES", 192)); t0 = time.monotonic()
    for i in range(N):
        t = i / (N - 1); look_at(cam, eye(t), C); bpy.context.view_layer.update(); converge(25, settle=0.35)
        imgs = []
        for name, k in looks(t):
            on, tint, strength = LOOKS[name]
            if P.xray != on: P.xray = on
            P.xray_tint_amount = tint; P.xray_strength = strength
            f = os.path.join(d, "look_%d.png" % len(imgs)); sc.render.filepath = f
            bpy.ops.render.render(write_still=True); imgs.append((f, k))
        out = px(imgs[0][0])
        if len(imgs) == 2:
            B, k = px(imgs[1][0]), imgs[1][1]
            q = -0.15 + 1.4 * k                                         # the line crosses the whole frame
            s_ = (u + 0.35 * (1 - v)) / 1.35 - q                        # a diagonal from the top left corner
            m = np.clip(-s_ * W / 2.0, -1, 1) * 0.5 + 0.5                # 2 px soft edge, the new look behind the line
            out = out * (1 - m[..., None]) + B * m[..., None]
            glow = np.exp(-(s_ * W / 2.5) ** 2)[..., None] * 0.8        # a thin light line
            out[..., :3] = out[..., :3] + glow * (1 - out[..., :3])
        im = bpy.data.images.new("wipe", W, H, alpha=True); im.pixels.foreach_set(out.astype(np.float32).ravel())
        im.filepath_raw = os.path.join(d, "f_%04d.png" % i); im.file_format = "PNG"; im.save(); bpy.data.images.remove(im)
        log("frame %d/%d %s, %.0f s so far" % (i + 1, N, [n for n, _ in looks(t)], time.monotonic() - t0))
    for f in ("look_0.png", "look_1.png"):
        if os.path.exists(os.path.join(d, f)): os.remove(os.path.join(d, f))
    open(os.path.join(d, "done.txt"), "w").write("%d frames" % N)
    if os.environ.get("TESTOFF"):
        P.xray = False; look_at(cam, eye(0), C); bpy.context.view_layer.update(); render("off_again")
elif shot == "a_sacre":
    # Sacre-Coeur, a point cloud with eye-dome lighting, a partial orbit
    add("Sacre-Coeur exterior 406M"); P.origin_mode = "AUTO"; P.origin_valid = False; sky(35, 200)
    cam = camera("Cam", (0, -900, 500), (0, 0, 0), 35)
    start(cam, 3, wait=60, min_wait=40)
    lo, hi = bounds(); c = (lo + hi) / 2; sz = min((hi - lo).length, 1500.0); tgt = c + Vector((0, 0, 0.03 * sz))
    def eye(t):
        a = math.radians(-95 + 70 * ease(t)); return c + Vector((0.68 * sz * math.cos(a), 0.68 * sz * math.sin(a), 0.38 * sz))
    cam = camera("Cam", eye(0), tgt, 32); P.view_camera = cam; sc.camera = cam
    converge(150, min_wait=30)
    sc.render.film_transparent = False; eevee(16); light_bg(); sc.view_settings.view_transform = "Standard"
    P.comp_enabled = True; P.comp_edges = "EDL"; P.comp_edl_strength = 4.0; P.comp_ao = 0.0; P.comp_haze = 0.0
    anim(144, lambda i, t: look_at(cam, eye(t), tgt))
else:
    raise SystemExit("unknown animation " + shot)
open(os.path.join(OUT, shot + ".done"), "w").write("ok")
log("done", shot)
