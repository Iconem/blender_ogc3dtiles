import traceback
R9 = os.path.join(os.environ["TEMP"], "ogc_tests", "r9")
def _take_begin(sc, animate, fps):
    # no undo steps while a take runs (each step would keep a copy of every tile mesh
    # streamed since the previous one); the scene plays at the clip's fps so Scene Time
    # nodes (geometry demos) advance one clip frame per tick
    ed = bpy.context.preferences.edit
    saved = (ed.undo_steps, sc.render.fps, sc.render.fps_base, sc.frame_current)
    ed.undo_steps = 0
    if animate: sc.render.fps = fps; sc.render.fps_base = 1.0; sc.frame_set(sc.frame_start)
    return saved
def _take_end(sc, saved):
    ed = bpy.context.preferences.edit
    ed.undo_steps, sc.render.fps, sc.render.fps_base, f = saved
    sc.frame_set(f)
def _take_frame(sc, animate, i):
    if animate: sc.frame_set(sc.frame_start + i)
def smooth(t):
    t = max(0.0, min(1.0, t)); return t * t * (3 - 2 * t)
def lerp(a, b, t): return a + (b - a) * t
def setview(dist, loc, pitch_deg, yaw_deg):
    w, a, sp, r = v3d(); rv = sp.region_3d
    rv.view_perspective = "PERSP"; rv.view_location = loc; rv.view_distance = dist
    rv.view_rotation = Euler((math.radians(pitch_deg), 0, math.radians(yaw_deg))).to_quaternion()
def bbox():
    obs = [o for o in bpy.context.scene.objects if "tile_url" in o]
    pts = [o.matrix_world @ Vector(c) for o in obs[:600] for c in o.bound_box]
    mn = [min(p[i] for p in pts) for i in range(3)]; mx = [max(p[i] for p in pts) for i in range(3)]
    return len(obs), mn, mx
def capture(name, steps, fn, interval=0.02, animate=True, fps=12):
    # animate=False when fn drives the scene frame itself (camera takes)
    sc = bpy.context.scene; sc.render.image_settings.file_format = "PNG"; sc.render.image_settings.compression = 0
    saved = _take_begin(sc, animate, fps)
    out = os.path.join(R9, "cap_" + name); os.makedirs(out, exist_ok=True)
    for f in os.listdir(out): os.remove(os.path.join(out, f))
    st = {"i": 0, "t0": time.time()}
    w, a, sp, r = v3d()
    def tick():
        i = st["i"]
        try:
            if i >= steps:
                open(os.path.join(out, "done.txt"), "w").write("%d frames in %.1f s" % (steps, time.time() - st["t0"]))
                _take_end(sc, saved); return None
            _take_frame(sc, animate, i)
            fn(i, steps)
            for ar in w.screen.areas: ar.tag_redraw()
            with bpy.context.temp_override(window=w, area=a, region=r):
                bpy.ops.screen.screenshot_area(filepath=os.path.join(out, "f_%04d.png" % i))
        except Exception:
            open(os.path.join(out, "done.txt"), "w").write(traceback.format_exc())
            _take_end(sc, saved); return None
        st["i"] += 1
        return interval
    bpy.app.timers.register(tick)
    print("capturing", name, steps)
