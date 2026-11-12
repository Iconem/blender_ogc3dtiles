"""Real Windows input (SendInput) aimed at the Blender window: smooth mouse moves,
button drags, wheel, keys. Coordinates are physical screen pixels (DPI aware)."""
import ctypes, ctypes.wintypes as w, time, math, sys
u = ctypes.windll.user32
try: ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception: pass

ULONG_PTR = ctypes.c_size_t
class MI(ctypes.Structure):
    _fields_ = [("dx", w.LONG), ("dy", w.LONG), ("mouseData", w.DWORD), ("dwFlags", w.DWORD), ("time", w.DWORD), ("dwExtraInfo", ULONG_PTR)]
class KI(ctypes.Structure):
    _fields_ = [("wVk", w.WORD), ("wScan", w.WORD), ("dwFlags", w.DWORD), ("time", w.DWORD), ("dwExtraInfo", ULONG_PTR)]
class IU(ctypes.Union):
    _fields_ = [("mi", MI), ("ki", KI)]
class INPUT(ctypes.Structure):
    _fields_ = [("type", w.DWORD), ("u", IU)]

SW, SH = u.GetSystemMetrics(0), u.GetSystemMetrics(1)
MOVE, ABS, LD, LU, RD, RU, MD, MU, WHEEL = 0x1, 0x8000, 0x2, 0x4, 0x8, 0x10, 0x20, 0x40, 0x800
KEYUP = 0x2
VK = dict(shift=0x10, ctrl=0x11, alt=0x12, space=0x20, enter=0x0D, esc=0x1B, tab=0x09, home=0x24, delete=0x2E,
          numpad0=0x60, numpad1=0x61, numpad3=0x63, numpad5=0x65, numpad7=0x67, numpad_period=0x6E,
          f3=0x72, f12=0x7B, up=0x26, down=0x28, left=0x25, right=0x27, backspace=0x08)

def _send(*inputs):
    arr = (INPUT * len(inputs))(*inputs)
    u.SendInput(len(inputs), arr, ctypes.sizeof(INPUT))

def _mouse(flags, x=0, y=0, data=0):
    inp = INPUT(type=0)
    if flags & ABS:
        x = int(x * 65535 / (SW - 1)); y = int(y * 65535 / (SH - 1))
    inp.u.mi = MI(x, y, data, flags, 0, 0)
    _send(inp)

EXTENDED = {0x24, 0x23, 0x21, 0x22, 0x2D, 0x2E, 0x25, 0x26, 0x27, 0x28, 0x5B, 0x5C, 0x6F, 0x90}
def _key(vk, up=False):
    scan = u.MapVirtualKeyW(vk, 0)
    flags = 0x8 | (KEYUP if up else 0) | (0x1 if vk in EXTENDED else 0)   # KEYEVENTF_SCANCODE (+EXTENDEDKEY)
    inp = INPUT(type=1); inp.u.ki = KI(vk, scan, flags, 0, 0); _send(inp)

def pos():
    p = w.POINT(); u.GetCursorPos(ctypes.byref(p)); return p.x, p.y

def move_to(x, y):
    _mouse(MOVE | ABS, x, y)

def glide(x, y, dur=0.6, steps=None):
    """Ease-in-out move from the current position."""
    x0, y0 = pos(); steps = steps or max(8, int(dur * 90))
    for i in range(1, steps + 1):
        t = i / steps; s = 0.5 - 0.5 * math.cos(math.pi * t)
        move_to(round(x0 + (x - x0) * s), round(y0 + (y - y0) * s)); time.sleep(dur / steps)

def click(button="left", x=None, y=None, hold=0.06):
    if x is not None: glide(x, y, 0.35)
    d, up_ = {"left": (LD, LU), "right": (RD, RU), "middle": (MD, MU)}[button]
    _mouse(d); time.sleep(hold); _mouse(up_)

def dbl_click(x=None, y=None):
    click("left", x, y); time.sleep(0.08); click("left")

def drag(button, dx, dy, dur=1.2, mods=(), ease=True):
    """Press a button at the current position and move by (dx, dy) over dur seconds."""
    d, up_ = {"left": (LD, LU), "right": (RD, RU), "middle": (MD, MU)}[button]
    for m in mods: _key(VK[m])
    time.sleep(0.03); _mouse(d); time.sleep(0.05)
    x0, y0 = pos(); steps = max(10, int(dur * 90))
    for i in range(1, steps + 1):
        t = i / steps; s = (0.5 - 0.5 * math.cos(math.pi * t)) if ease else t
        move_to(round(x0 + dx * s), round(y0 + dy * s)); time.sleep(dur / steps)
    time.sleep(0.05); _mouse(up_)
    for m in reversed(mods): _key(VK[m], True)

def orbit(dx, dy, dur=1.5): drag("middle", dx, dy, dur)
def pan(dx, dy, dur=1.5): drag("middle", dx, dy, dur, mods=("shift",))
def dolly(dy, dur=1.2): drag("middle", 0, dy, dur, mods=("ctrl",))

def wheel(clicks, pause=0.12):
    for _ in range(abs(clicks)):
        _mouse(WHEEL, data=(120 if clicks > 0 else -120) & 0xFFFFFFFF); time.sleep(pause)

def key(name, mods=(), hold=0.05):
    """name: a VK key name or a single character."""
    for m in mods: _key(VK[m]); time.sleep(0.02)
    vk = VK[name] if name in VK else u.VkKeyScanW(ord(name)) & 0xFF
    _key(vk); time.sleep(hold); _key(vk, True)
    for m in reversed(mods): time.sleep(0.02); _key(m if isinstance(m, int) else VK[m], True)

def type_text(s, cps=14):
    for ch in s:
        if ch.isupper(): key(ch.lower(), mods=("shift",))
        else:
            vk = u.VkKeyScanW(ord(ch)); mods = ("shift",) if (vk >> 8) & 1 else ()
            for m in mods: _key(VK[m])
            _key(vk & 0xFF); time.sleep(0.03); _key(vk & 0xFF, True)
            for m in mods: _key(VK[m], True)
        time.sleep(1.0 / cps)

def border_zoom(x0, y0, x1, y1, dur=1.0):
    """Shift+B then drag a rectangle."""
    key("b", mods=("shift",)); time.sleep(0.3)
    glide(x0, y0, 0.3); drag("left", x1 - x0, y1 - y0, dur)

def blender_hwnd():
    hw = []
    @ctypes.WINFUNCTYPE(ctypes.c_bool, w.HWND, w.LPARAM)
    def cb(h, l):
        n = ctypes.create_unicode_buffer(256); u.GetWindowTextW(h, n, 256)
        if u.IsWindowVisible(h):
            if "Blender 5" in n.value: hw.append(h)
            elif n.value.lower().endswith("blender.exe"): u.ShowWindow(h, 6)   # the console: minimize
        return True
    u.EnumWindows(cb, 0); return hw[0]

def focus(h=None, maximize=False):
    h = h or blender_hwnd()
    if u.IsIconic(h): u.ShowWindow(h, 9)
    if maximize: u.ShowWindow(h, 3)
    for _ in range(3):
        _key(VK["alt"]); _key(VK["alt"], True)      # lets a background process take the foreground
        u.SetForegroundWindow(h); time.sleep(0.4)
        if u.GetForegroundWindow() == h: break
    if u.GetForegroundWindow() != h:
        raise RuntimeError("Blender is not the foreground window; refusing to inject input")
    p = w.POINT(0, 0); u.ClientToScreen(h, ctypes.byref(p)); c = w.RECT(); u.GetClientRect(h, ctypes.byref(c))
    return h, (p.x, p.y, c.right, c.bottom)   # client origin and size, screen pixels

if __name__ == "__main__":
    print(SW, SH, focus(maximize="max" in sys.argv))

def move_rel(dx, dy, dur=1.0, steps=None):
    """Relative mouse motion (for Blender walk / fly navigation, which warps the cursor)."""
    steps = steps or max(10, int(dur * 60)); ax = ay = 0.0
    for i in range(1, steps + 1):
        t = i / steps; s = 0.5 - 0.5 * math.cos(math.pi * t)
        tx, ty = dx * s, dy * s; _mouse(MOVE, int(round(tx - ax)), int(round(ty - ay))); ax, ay = ax + int(round(tx - ax)), ay + int(round(ty - ay))
        time.sleep(dur / steps)

def hold(name, secs):
    vk = VK[name] if name in VK else u.VkKeyScanW(ord(name)) & 0xFF
    _key(vk); time.sleep(secs); _key(vk, True)
