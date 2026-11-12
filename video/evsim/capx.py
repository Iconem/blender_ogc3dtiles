import traceback
R9 = os.path.join(os.environ["TEMP"], "ogc_tests", "r9")
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
def capture(name, steps, fn, interval=0.02):
    bpy.context.scene.render.image_settings.file_format = "PNG"; bpy.context.scene.render.image_settings.compression = 0
    out = os.path.join(R9, "cap_" + name); os.makedirs(out, exist_ok=True)
    for f in os.listdir(out): os.remove(os.path.join(out, f))
    st = {"i": 0, "t0": time.time()}
    w, a, sp, r = v3d()
    def tick():
        i = st["i"]
        try:
            if i >= steps:
                open(os.path.join(out, "done.txt"), "w").write("%d frames in %.1f s" % (steps, time.time() - st["t0"]))
                return None
            fn(i, steps)
            for ar in w.screen.areas: ar.tag_redraw()
            with bpy.context.temp_override(window=w, area=a, region=r):
                bpy.ops.screen.screenshot_area(filepath=os.path.join(out, "f_%04d.png" % i))
        except Exception:
            open(os.path.join(out, "done.txt"), "w").write(traceback.format_exc())
            return None
        st["i"] += 1
        return interval
    bpy.app.timers.register(tick)
    print("capturing", name, steps)
