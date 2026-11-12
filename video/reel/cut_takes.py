"""Cut the screencast takes for the reel: keep ranges, drop static frames, speed up cursor-only stretches.

usage: python -I cut_takes.py <plan.json> [name.mp4 ...]

plan.json: { "<name>.mp4": { "src": "<path>", "activity": "<activity.json>", "keep": [[from, to|null], ...] } }
Times are source seconds. For every take it writes
  public/<name>.mp4            1920x1080, 30 fps, the kept frames
  public/timemaps.json[name]   the kept source frame indices, in order (output frame i shows source frame kept[i])
  public/takes.json[name]      the output frame count

A frame is static when fewer than STATIC_PX pixels changed since the previous one (activity.py), and
"quiet" when fewer than QUIET_PX did (a cursor moving, a tile or two trickling in). A static run keeps
its first STATIC_MIN frames plus a sixth of its length, the rest is dropped (nothing moves, so the cut is invisible). A quiet
run longer than QUIET_AFTER seconds plays its remainder QUIET_SPEED times faster.
"""
import ctypes
import json
import os
import subprocess
import sys

import numpy as np

FF = os.path.expanduser("~") + "/AppData/Local/Microsoft/WinGet/Packages/Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe/ffmpeg-9.0.2-full_build/bin/ffmpeg.exe"
FPS = 30
W, H = 1920, 1080
STATIC_PX, STATIC_MIN = 8, 5
QUIET_PX, QUIET_AFTER, QUIET_SPEED = 300, 1.5, 3
BELOW_NORMAL = 0x4000

here = os.path.dirname(os.path.abspath(__file__))
public = os.path.join(here, "public")
plan = json.load(open(sys.argv[1]))
only = sys.argv[2:]
timemaps_path = os.path.join(public, "timemaps.json")
takes_path = os.path.join(public, "takes.json")
timemaps = json.load(open(timemaps_path)) if os.path.exists(timemaps_path) else {}
takes = json.load(open(takes_path)) if os.path.exists(takes_path) else {}

ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), BELOW_NORMAL)


def kept_frames(changed, keep):
    n = len(changed)
    k = np.zeros(n, dtype=bool)
    for a, b in keep:
        k[int(round(a * FPS)) : (n if b is None else min(n, int(round(b * FPS))))] = True
    c = np.array(changed)
    # smooth the activity so a single busy frame does not break a quiet run
    win = 6
    smooth = np.array([c[max(0, i - win) : i + 1].max() for i in range(n)])
    static = c < STATIC_PX          # raw: the driver's glides pause between steps, those pauses go too
    quiet = smooth < QUIET_PX
    out = []
    i = 0
    while i < n:
        if not k[i]:
            i += 1
            continue
        if static[i]:
            j = i
            while j < n and k[j] and static[j]:
                j += 1
            run = j - i                   # a 6-frame pause stays, 3 s becomes 0.7 s, 10 s becomes 1.9 s
            out.extend(range(i, i + min(run, STATIC_MIN + run // 6)))
            i = j
        elif quiet[i]:
            j = i
            while j < n and k[j] and quiet[j] and not static[j]:
                j += 1
            head = min(j, i + int(QUIET_AFTER * FPS))
            out.extend(range(i, head))
            out.extend(range(head, j, QUIET_SPEED))
            i = j
        else:
            out.append(i)
            i += 1
    return out


for name, spec in plan.items():
    if only and name not in only:
        continue
    act = json.load(open(spec["activity"]))["changed"]
    kept = kept_frames(act, spec.get("keep", [[0, None]]))
    src = spec["src"]
    dec = subprocess.Popen(
        [FF, "-hide_banner", "-loglevel", "error", "-threads", "2", "-i", src, "-vf", f"fps={FPS},scale={W}:{H}:flags=lanczos",
         "-f", "rawvideo", "-pix_fmt", "yuv420p", "-"],
        stdout=subprocess.PIPE, creationflags=BELOW_NORMAL,
    )
    out = os.path.join(public, name)
    enc = subprocess.Popen(
        [FF, "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "yuv420p", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
         "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p", "-an", out],
        stdin=subprocess.PIPE, creationflags=BELOW_NORMAL,
    )
    fsize = W * H * 3 // 2
    want = iter(kept)
    nxt = next(want, None)
    i = written = 0
    while nxt is not None:
        buf = dec.stdout.read(fsize)
        if len(buf) < fsize:
            break
        if i == nxt:
            enc.stdin.write(buf)
            written += 1
            nxt = next(want, None)
        i += 1
    dec.stdout.close()
    dec.wait()
    enc.stdin.close()
    enc.wait()
    timemaps[name] = kept[:written]
    takes[name] = written
    print(f"{name}: {len(act)} source frames -> {written} ({written / FPS:.1f} s)")
    json.dump(timemaps, open(timemaps_path, "w"))
    json.dump(takes, open(takes_path, "w"), indent=2)
