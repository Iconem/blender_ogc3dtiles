"""Host-side take driver: talk to the GUI Blender (cmd.py/out.txt), record with ffmpeg, drive real input."""
import os, sys, time, subprocess, json
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H)
import human
FF = r"C:\Users\cnj\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.2-full_build\bin\ffmpeg.exe"
_rec = None

def blender(code, timeout=120):
    """Run python inside the GUI Blender, return its stdout."""
    out = os.path.join(H, "out.txt"); cmd = os.path.join(H, "cmd.py")
    if os.path.exists(out): os.remove(out)
    open(cmd, "w", encoding="utf-8").write(code)
    t0 = time.time()
    while not os.path.exists(out):
        time.sleep(0.2)
        if time.time() - t0 > timeout: raise TimeoutError("blender did not answer")
    return open(out, encoding="utf-8").read()

def layout(area_index=0):
    """Screen rects of the 3D viewport window region and the sidebar (UI) region."""
    h, (cx, cy, cw, ch) = human.focus()
    txt = blender("""
import bpy, json
win = bpy.context.window_manager.windows[0]
a = next(a for a in win.screen.areas if a.type=='VIEW_3D')
d = {'win': [win.width, win.height]}
for r in a.regions:
    if r.type in ('WINDOW','UI','HEADER','TOOLS'): d[r.type] = [r.x, r.y, r.width, r.height]
print(json.dumps(d))""")
    d = json.loads(txt.strip().splitlines()[-1]); ww, wh = d['win']
    # Blender y is bottom-up inside the client area; client height == wh
    def rect(k):
        x, y, w, hh = d[k]; return (cx + x, cy + (wh - y - hh), w, hh)
    out = {k: rect(k) for k in d if k != 'win'} | {'client': (cx, cy, cw, ch)}
    if 'UI' in out: UI0[0], UI0[1] = out['UI'][0], out['UI'][1]
    return out

def rec_start(path, rect, fps=30):
    global _rec
    x, y, w, h = rect; w -= w % 2; h -= h % 2
    cmd = [FF, "-y", "-hide_banner", "-loglevel", "error", "-f", "gdigrab", "-framerate", str(fps), "-draw_mouse", "1",
           "-offset_x", str(x), "-offset_y", str(y), "-video_size", f"{w}x{h}", "-i", "desktop",
           "-c:v", "h264_qsv", "-preset", "veryslow", "-global_quality", "20", "-pix_fmt", "nv12", path]
    _rec = subprocess.Popen(cmd, stdin=subprocess.PIPE); time.sleep(0.8)

def rec_stop():
    global _rec
    if _rec: _rec.stdin.write(b"q"); _rec.stdin.flush(); _rec.wait(); _rec = None

def center(rect, fx=0.5, fy=0.5):
    x, y, w, h = rect; return round(x + w * fx), round(y + h * fy)

def hover(rect, fx, fy, dur=0.5):
    human.glide(*center(rect, fx, fy), dur); time.sleep(0.35)   # let Blender register the region change

def clip(text):
    """Put text on the Windows clipboard (so a take can Ctrl+V it like a person would)."""
    subprocess.run(["powershell", "-NoProfile", "-Command", "Set-Clipboard -Value ([Console]::In.ReadToEnd().TrimEnd())"],
                   input=text.encode("utf-8"), check=True)

def shot(path, rect=None):
    from PIL import ImageGrab
    im = ImageGrab.grab()
    if rect: x, y, w, h = rect; im = im.crop((x, y, x + w, y + h))
    im.save(path); return path

def paste_into_field(x, y, text):
    """Click a text field, select all, paste, Enter."""
    clip(text); human.click("left", x, y); time.sleep(0.25)
    human.key("a", mods=("ctrl",)); time.sleep(0.1); human.key("v", mods=("ctrl",)); time.sleep(0.2); human.key("enter")

# --- sidebar widget positions (maximized 1920x1200 window, UI region at (1226,126), default panel state) ---
UI0 = [1226, 126]
def ui(dx, dy): return UI0[0] + dx, UI0[1] + dy
W = dict(start=ui(95, 98), clear=ui(240, 98), add=ui(292, 130), url=ui(198, 234), ion=ui(198, 265),
         origin_hdr=ui(100, 384), lod_hdr=ui(110, 417), max_sse=ui(160, 485),
         mat_hdr=ui(110, 628), shared_shader=ui(30, 665), open_mat=ui(160, 727),
         geo_hdr=ui(115, 768), shared_geo=ui(30, 805), demo_graphs=ui(160, 836), points=ui(170, 867), radius=ui(170, 898))
SHADING = dict(wire=(1457, 77), solid=(1481, 77), material=(1505, 77), rendered=(1529, 77))
_marks = []; _t0 = 0
def mark(label):
    _marks.append((round(time.time() - _t0, 2), label)); print(f"[{_marks[-1][0]:6.2f}] {label}")
def take_start(name, rect):
    global _t0, _marks
    _marks = []; path = os.path.join(H, "takes", name + ".mp4"); rec_start(path, rect); _t0 = time.time(); return path
def take_stop(name):
    rec_stop(); json.dump(_marks, open(os.path.join(H, "takes", name + ".json"), "w"), indent=1)
def wait_tiles(n, timeout=60):
    t0 = time.time()
    while time.time() - t0 < timeout:
        k = int(blender("import bpy; print(bpy.context.scene.ogc3dtiles.tiles_loaded)").strip() or 0)
        if k >= n: return k
        time.sleep(0.5)
    return k

# sidebar with one tileset entry selected (default panel state)
W1 = dict(entry=ui(150, 136), save_lib=ui(90, 310), overlays=ui(36, 388), clipping=ui(36, 431),
          origin_hdr=ui(100, 556), lod_hdr=ui(110, 589), max_sse=ui(160, 657))
def tiles_visible():
    return int(blender("import bpy; print(sum(1 for o in bpy.data.objects if o.name.startswith('t_') and not o.hide_viewport))").strip() or 0)
def wait_visible(n, timeout=60):
    t0 = time.time(); k = 0
    while time.time() - t0 < timeout:
        k = tiles_visible()
        if k >= n: break
        time.sleep(0.5)
    return k

# --- template matching for sidebar widgets (positions move with scrolling and panel state) ---
import numpy as _np
TPL = os.path.join(H, "tpl")
def make_tpl(name, src_png, x, y, w, h):
    from PIL import Image
    Image.open(src_png).crop((x, y, x + w, y + h)).save(os.path.join(TPL, name + ".png"))
def _locate_once(name, rect, thresh):
    import cv2
    from PIL import ImageGrab
    rect = rect or layout()['UI']
    x, y, w, h = rect
    img = _np.array(ImageGrab.grab((x, y, x + w, y + h)).convert('L'))
    t = cv2.imread(os.path.join(TPL, name + ".png"), cv2.IMREAD_GRAYSCALE)
    r = cv2.matchTemplate(img, t, cv2.TM_CCOEFF_NORMED); _, mv, _, ml = cv2.minMaxLoc(r)
    if mv < thresh: raise LookupError(f"{name}: best match {mv:.2f}")
    return x + ml[0] + t.shape[1] // 2, y + ml[1] + t.shape[0] // 2
def locate(name, rect=None, thresh=0.88):
    """Screen centre of tpl/<name>.png inside rect (default: the sidebar); waits until the
    position is stable (Blender animates region scrolling)."""
    rect = rect or layout()['UI']
    a = _locate_once(name, rect, thresh)
    for _ in range(6):
        time.sleep(0.25); b = _locate_once(name, rect, thresh)
        if b == a: return b
        a = b
    return a
def click_tpl(name, dx=0, dy=0, rect=None, pause=0.3, tries=4):
    for i in range(tries):
        try: px, py = locate(name, rect); break
        except LookupError:
            if i == tries - 1: raise
            time.sleep(0.6)
    human.click("left", px + dx, py + dy); time.sleep(pause); return px + dx, py + dy
def park():
    """Move the mouse to a quiet spot of the 3D viewport so no tooltip covers the sidebar."""
    x, y, w, h = layout()['WINDOW']; human.glide(x + int(w * 0.5), y + int(h * 0.85), 0.3); time.sleep(0.6)
def scroll_until(name, rect=None, step=-10, tries=8):
    """Wheel over the sidebar until the template is visible; returns its centre."""
    rect = rect or layout()['UI']
    for i in range(tries):
        park()
        try: return locate(name, rect)
        except LookupError: hover(rect, 0.5, 0.5, 0.25); human.wheel(step, 0.04); time.sleep(0.9)
    park(); return locate(name, rect)

def url_field():
    """Screen point inside the URL text field of the selected tileset entry (the list height varies)."""
    park(); lab = locate("url_label", layout()['UI']); return lab[0] + 170, lab[1]

def wait_settled(timeout=240, quiet=12):
    """Wait until the number of visible tiles stops changing for `quiet` seconds (streaming settled for this view)."""
    t0 = time.time(); last = -1; since = time.time()
    while time.time() - t0 < timeout:
        k = tiles_visible()
        if k != last: last = k; since = time.time()
        elif time.time() - since >= quiet: return k
        time.sleep(1.0)
    return last

def status_counts():
    import re
    s = blender("import bpy; print(bpy.context.scene.ogc3dtiles.status_text)").strip()
    m = re.search(r"(\d+)/(\d+)", s); return (int(m.group(1)), int(m.group(2)), s) if m else (0, 0, s)

def wait_loaded(timeout=360, quiet=8, min_time=60):
    """Wait until every tile the tileset wants is loaded (a/b in the status text with a == b), stable for `quiet` s."""
    t0 = time.time(); since = None
    while time.time() - t0 < timeout:
        a, b, s = status_counts()
        if a == b and b > 0 and time.time() - t0 >= min_time:
            since = since or time.time()
            if time.time() - since >= quiet: return s
        else: since = None
        time.sleep(1.0)
    return s

_PROJ = open(os.path.join(H, "proj.py"), encoding="utf-8").read()
def proj(pts):
    """Project 3D scene points to fractions (fx, fy) of the active 3D viewport WINDOW region (y down)."""
    return json.loads(blender("PTS=" + json.dumps(pts) + "\n" + _PROJ).strip().splitlines()[-1])
def cl(v, lo=0.03, hi=0.97): return min(hi, max(lo, v))

def layout_areas():
    """Screen rects of every 3D viewport area (left to right): [{'WINDOW': rect, 'UI': rect, 'HEADER': rect}, ...]."""
    h, (cx, cy, cw, ch) = human.focus()
    txt = blender("import bpy, json\nwin = bpy.context.window_manager.windows[0]; out = []\nfor a in sorted([a for a in win.screen.areas if a.type=='VIEW_3D'], key=lambda a: a.x):\n    out.append({r.type: [r.x, r.y, r.width, r.height] for r in a.regions if r.type in ('WINDOW','UI','HEADER')})\nprint(json.dumps({'win': [win.width, win.height], 'areas': out}))")
    d = json.loads(txt.strip().splitlines()[-1]); ww, wh = d['win']
    def rect(v): x, y, w, hh = v; return (cx + x, cy + (wh - y - hh), w, hh)
    return [{k: rect(v) for k, v in a.items()} for a in d['areas']]
