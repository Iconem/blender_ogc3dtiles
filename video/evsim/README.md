# Screencasts, second workflow: frame-stepped capture inside Blender

These scripts made the `evsim_*`, `drawnptr_*` and `scripted_*` videos on the
`videos-2026-11` release (2026-11-06, Blender 5.3, laptop). The docs page
*Development > Screencasts* (`site/content/docs/dev/screencasts.md`) is the
summary of both workflows. They are the
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

All three capture functions take `animate=True, fps=12`: the scene frame is
stepped once per tick with the scene fps set to the clip fps for the take, so
*Scene Time* nodes (the noise and reveal geometry demos) move one clip frame per
tick instead of standing still. Camera takes that set the frame themselves
(`camtake.py`, `cc.py`) pass `animate=False`. They also set *Undo Steps* to 0 for
the take (see below) and restore undo steps, fps and frame when the take ends
or fails.

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
search box instead of the sidebar, and it only reaches operators, not properties.
For properties the region rectangles are the useful part of the API: the sidebar
region gives the x range and the top, and the add-on's panels lay rows out from
the top at a known row height, so a row's y can be computed from the panel order
and the collapse state instead of read off a screenshot.

## Whole window, not only the 3D view

`bpy.ops.screen.screenshot(filepath=...)` saves the full Blender window (every
editor, header and sidebar); `screenshot_area` saves one area. Both work from a
timer; checked on 5.3, the window shot is 1920 x 1137 for the test window. Use
the window shot when the take shows the node editor or the preferences.

## Why Blender crawled after three or four takes (the other workflow)

Memfile undo. Every click on a property pushes an undo step, and each step keeps
a copy of every tile mesh created since the previous step, for 32 steps by
default. Tiles keep streaming between clicks, so the steps fill with meshes.
Measured here on the Clermont mesh at 2 px SSE with one undo-pushing operator per
second for 90 s:

| Undo steps | Tiles | Working set |
|---|---|---|
| 32 | 310 | 6.2 GB |
| 0 | 345 | 3.4 GB |

Stop and Clear free the meshes themselves (0 orphan meshes after a purge), so it
is not a leak in the add-on. The capture functions here set Undo Steps to 0 for
the take and put the preference back afterwards (`_take_begin` / `_take_end` in
`capx.py`). For a chain of real-time takes, set Preferences > System > Undo
Steps to 0 before the chain (`bpy.context.preferences.edit.undo_steps = 0`) and
restore it, or restart Blender between chains. View changes made through
`region_3d` push no undo step; `event_simulate` clicks push the same steps a
user's clicks do.

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
