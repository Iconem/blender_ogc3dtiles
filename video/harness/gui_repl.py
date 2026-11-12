import bpy, os, io, traceback, contextlib, time
H = os.path.dirname(os.path.abspath(__file__))
CMD = os.path.join(H, "cmd.py"); OUT = os.path.join(H, "out.txt")

def view3d_override():
    win = bpy.context.window_manager.windows[0]
    for area in win.screen.areas:
        if area.type == 'VIEW_3D':
            region = next(r for r in area.regions if r.type == 'WINDOW')
            return dict(window=win, screen=win.screen, area=area, region=region, scene=bpy.context.scene)
    return None

def shot(path):
    ov = view3d_override()
    with bpy.context.temp_override(**ov):
        bpy.ops.screen.screenshot_area(filepath=path)
    return path

def poll():
    if os.path.exists(CMD):
        src = open(CMD, encoding="utf-8").read(); os.remove(CMD)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            try:
                exec(compile(src, "cmd.py", "exec"), {"bpy": bpy, "shot": shot, "view3d_override": view3d_override, "H": H})
            except Exception:
                traceback.print_exc(file=buf)
        open(OUT + ".tmp", "w", encoding="utf-8").write(buf.getvalue()); os.replace(OUT + ".tmp", OUT)
    return 0.5

bpy.app.timers.register(poll, persistent=True)
print("[gui_repl] ready", H)
