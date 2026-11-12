# Screencasts, second workflow: frame-stepped capture inside Blender

These scripts made the `evsim_*`, `drawnptr_*` and `scripted_*` videos on the
`videos-2026-11` release (2026-11-06, Blender 5.3, laptop). They are the
alternative to `video/harness/`, which drives Blender from outside with real
Windows input and records the screen in real time. Read `video/PROCESS.md` for
that one; this file explains the difference and when each one is the right tool.

## How it works

Everything runs inside the GUI Blender, from a shell:

- `gui_repl.py`: start Blender with `blender --python gui_repl.py`. A timer polls
  `%TEMP%\ogc_tests\r9\cmd.py`, `exec`s it and writes `cmd.out`.
- `run.sh file.py [timeout]`: prepends `h.py` (add-on module handles, `v3d()`,
  `start(library name)`) and drops the file as `cmd.py`.
- `relaunch.sh`: rebuilds the zip, reinstalls it, restarts the test window.
  `relaunch2.sh`: restart only, with `--enable-event-simulate`, which the third
  workflow needs.
- A capture is a `bpy.app.timers` tick. Every tick advances the story by one
  step, redraws, and saves the 3D view area with `bpy.ops.screen.screenshot_area`
  as `cap_<name>/f_NNNN.png`, plus one line of pointer state in `meta.json`.
- `post.py name [fps] [blur x,y,w,h] [caption]` draws the pointer (an 11 px
  arrow, supersampled), a ring while a button is down, the key label bottom
  left, a caption, blurs one box (the Google URL field), and encodes
  `ui_<name>.mp4` at 1920 px wide, 12 fps. `enc.sh` is the same without the
  pointer.

Three ways to move the scene, from least to most faithful:

| Prefix on the release | Script | What moves the view | Pointer |
|---|---|---|---|
| `scripted_` | `capx.py` `capture(name, steps, fn)` | `fn(i, n)` sets the view or scene frame each tick (`cg.py` generic orbit, `camtake.py` scene camera takes, `cd.py` clipping, `cc.py` camera, `vn2.py` noise render) | none |
| `drawnptr_` | `capx2.py` `capture2(name, story)` | a generator calls `bpy.ops.view3d.view_orbit`, `zoom`, `zoom_border` and property setters, and moves a fake pointer state that `post.py` draws (`u_lublin.py`, `u_elev.py`) | drawn, not real |
| `evsim_` | `capx3.py` `capture3(name, story)` | real Blender events through `window.event_simulate`: `MOUSEMOVE`, wheel, middle drag, `Shift+B` drag, clicks and slider drags on the sidebar. Blender's own handlers do the work (`u_rome3.py`) | drawn (the simulated events do not move the OS cursor, and `screenshot_area` has no cursor) |

`event_simulate` needs Blender started with `--enable-event-simulate`.

## Why it is fast, and what that costs

A tick only runs when Blender is idle, and the clip is encoded at a fixed
12 fps. Time spent loading tiles between two ticks is not in the video. A session
that took two minutes of wall clock becomes a 20 s clip, nothing waits for the
window to be focused, and nothing else on the machine disturbs the capture. There
are no misclicks because coordinates go straight into the event, and nothing can
drift between one frame and the next.

The cost is that the clips are not real time. Tiles appear faster than they
stream, which flatters the add-on. For a demo that has to show real streaming
pace, use `video/harness/` (real time, real cursor, screen recorded by ffmpeg).
For a quick clip of a feature, or when the machine is shared, use this one.

## Finding sidebar widgets

Blender has no public API for the rectangle of a button. `area.regions[].x, y,
width, height` give the regions, nothing finer. Two workarounds exist in this
repo:

- `video/harness/take.py` `locate(name)`: OpenCV template matching against
  `tpl/<name>.png`, cut from a screenshot. Robust to scrolling, needs a new
  template when the sidebar width, zoom or theme changes.
- Here: pixel constants in the area's coordinates, read off one screenshot
  (`u_rome3.py`: Max SSE slider at (1500, 612), *Stream for* at (1420, 587)).
  Valid for one window size, one sidebar width, UI scale 1.0, and the panel
  collapse state the prep sets. Scrolling the sidebar invalidates them.

A layout-independent way to press buttons is the F3 search (`keytap("F3")`, type
the operator name, Enter): no coordinates at all, but the video then shows the
search box instead of the sidebar.

## Pitfalls

- A minimised Blender window gives stale or 1x1 screenshots. Restore it
  (`ShowWindow(hwnd, 9)`) and capture from a timer, not inside the operator that
  changed the view.
- `region_3d.is_perspective` updates only after a redraw.
- A Cycles viewport never converges while the view or a light moves: hold
  40 ticks still before switching.
- A sidebar scroll moves the Google URL field out of the blur box. Blur the
  field, and do not scroll in a take that shows it.
- Big point clouds (Lublin 178 M) take seconds per screenshot; the clip is then
  sped up much more than the others.

Paths in the scripts point to `%TEMP%\ogc_tests\r9` and to the worktree of the
recording session; change `R9` in `capx.py` and the two paths in `relaunch.sh`
to move them. The library names in `cg.py`, `u_lublin.py` and `u_elev.py` are
entries of the private library on the recording machine, not in git.
