"""Per-frame activity of a screencast: how many pixels changed since the previous frame.

usage: python -I activity.py <takes dir> <out dir> <name.mp4> ...
Writes <out dir>/<name>.activity.json: {"fps": 30, "changed": [n0, n1, ...]} where n is the
count of pixels (at 960x540, grey) whose value moved by more than 10 levels. A moving cursor
alone gives roughly 20 to 150; a static frame gives 0; tiles loading give thousands.
"""
import json
import os
import subprocess
import sys

import numpy as np

FF = os.path.expanduser("~") + "/AppData/Local/Microsoft/WinGet/Packages/Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe/ffmpeg-9.0.2-full_build/bin/ffmpeg.exe"
W, H = 960, 540

src_dir, out_dir = sys.argv[1], sys.argv[2]
for name in sys.argv[3:]:
    p = subprocess.Popen(
        [FF, "-hide_banner", "-loglevel", "error", "-threads", "2", "-i", os.path.join(src_dir, name),
         "-vf", f"fps=30,scale={W}:{H}", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
        stdout=subprocess.PIPE,
    )
    prev = None
    changed = []
    n = W * H
    while True:
        buf = p.stdout.read(n)
        if len(buf) < n:
            break
        f = np.frombuffer(buf, dtype=np.uint8).astype(np.int16)
        if prev is not None:
            changed.append(int((np.abs(f - prev) > 10).sum()))
        else:
            changed.append(0)
        prev = f
    p.wait()
    out = os.path.join(out_dir, name.replace(".mp4", ".activity.json"))
    with open(out, "w") as fh:
        json.dump({"fps": 30, "changed": changed}, fh)
    idle = sum(1 for c in changed if c < 8) / 30
    print(f"{name}: {len(changed)} frames, {idle:.1f} s fully static")
