"""Exec ogc_tests/cmd.py when it appears, write stdout/err to cmd.out."""
import contextlib, io, os, traceback
import bpy
D = os.path.join(os.environ.get("TEMP", "/tmp"), "ogc_tests", "r9")
CMD, OUT = os.path.join(D, "cmd.py"), os.path.join(D, "cmd.out")
G = {"bpy": bpy}

def _poll():
    if os.path.exists(CMD):
        src = open(CMD, encoding="utf-8").read()
        os.remove(CMD)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            try:
                exec(compile(src, "cmd", "exec"), G)
            except Exception:
                traceback.print_exc(file=buf)
        open(OUT + ".tmp", "w", encoding="utf-8").write(buf.getvalue())
        os.replace(OUT + ".tmp", OUT)
    return 0.3

bpy.app.timers.register(_poll, first_interval=1.0, persistent=True)
