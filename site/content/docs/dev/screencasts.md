---
title: "Screencasts"
description: "The two ways the demo videos are recorded: real input captured in real time, or frame-stepped captures from inside Blender"
---

The demo clips on the Releases page come from the scripts under `video/` in the repository. Two
workflows exist; the prefix of a clip's file name says which one made it.

| Prefix | Folder | Input | Timing | Pointer |
|---|---|---|---|---|
| `s*_` (s01_ to s13_) | `video/harness/` | real mouse and keyboard through `SendInput` | real time, ffmpeg screen capture at 30 fps | the real cursor |
| `evsim_` | `video/evsim/` | Blender events through `window.event_simulate` | one screenshot per step, 12 fps clip | drawn in post |
| `drawnptr_` | `video/evsim/` | operators and property setters from a script | one screenshot per step | drawn in post |
| `scripted_` | `video/evsim/` | the view or the camera set per frame | one screenshot per step | none |

`video/PROCESS.md` is the full write-up of the first workflow and the reel; `video/evsim/README.md`
documents the second. This page is the summary and the lessons that apply to both.

## Real time: `video/harness/`

Blender runs with `gui_repl.py`, which polls a command file so a shell script can run Python inside
the GUI session. `human.py` sends mouse and keyboard input with scan codes, so Blender sees a person.
`take.py` records the Blender client area with ffmpeg and writes a mark file (time, label) that the
cutting scripts in `video/reel/` turn into the reel.

What it shows is faithful: tiles stream at the real pace, the real cursor moves, menus open as they
would for a user. The cost is retakes. The window must have the focus, a dropdown that misses by a
few pixels needs a new take, the machine must be idle, and every button has to be found on screen.

## Frame-stepped: `video/evsim/`

Everything runs inside Blender from a `bpy.app.timers` tick. Each tick advances the story by one
step, redraws, and saves the 3D view with `bpy.ops.screen.screenshot_area` (or the whole window with
`bpy.ops.screen.screenshot`). `post.py` draws the pointer, a ring while a button is down, the key
label, a caption and a blur box, then encodes the clip at 12 fps.

A tick only runs when Blender is idle, so the time spent loading tiles between two steps is not in
the clip: a two minute session becomes a 20 s clip, nothing needs the focus, nothing on the machine
disturbs it, and there are no misclicks because the coordinates go straight into the event. The cost
is that tiles appear faster than they stream. Use it for feature clips; use the real time workflow
when the point of the clip is the streaming pace.

Three levels of faithfulness, from the least to the most:

- `scripted_`: a function sets the view (or the scene frame for camera takes) at each step.
- `drawnptr_`: a generator calls `bpy.ops.view3d.*` and property setters, and moves a pointer state
  that is drawn in post.
- `evsim_`: real Blender events (`MOUSEMOVE`, wheel, middle drag, Shift+B drag, clicks and slider
  drags on the sidebar) through `window.event_simulate`; Blender's own handlers do the work. Blender
  must be started with `--enable-event-simulate`.

## Finding a button on the screen

Blender has no public API for the rectangle of a button. `area.regions[].x, y, width, height` give
the regions and nothing finer. Three workarounds:

- **Template matching** (`harness/take.py` `locate(name)`): OpenCV against a cut-out of a
  screenshot, threshold 0.88. Robust to scrolling, needs a new template when the sidebar width, the
  UI scale or the theme changes.
- **Pixel constants** in the area's coordinates, read off one screenshot. Valid for one window size,
  one sidebar width, UI scale 1.0 and the panel collapse state the preparation script sets.
- **Region rectangles plus row order**: the sidebar region gives the x range and the top, the add-on's
  panels lay rows out from the top at a known row height, so a row's y follows from the panel order
  and the collapse state without a screenshot. This is the layout-independent way for properties.

The F3 operator search (`F3`, type the name, Enter) needs no coordinates at all, but it reaches
operators only, not properties, and the clip then shows the search box instead of the sidebar.

## Animated demos

The geometry demos (noise displacement, height reveal) read the *Scene Time* node, so they only move
when the scene frame changes. A frame-stepped take therefore has to step the scene frame itself:
`capture()`, `capture2()` and `capture3()` do it by default (`animate=True`), setting the scene fps
to the clip fps for the take so one tick is one clip frame of scene time, and restoring the fps and
the frame afterwards. Camera takes that drive the frame themselves pass `animate=False`. The
*Render converged* operator steps the frame range on its own, so rendered clips animate anyway.

## Blender slowing down after a few takes

Memfile undo. Every click on a property pushes an undo step, and each step keeps a copy of every
tile mesh created since the previous step, for 32 steps by default. Tiles keep streaming between
clicks, so the steps fill with meshes. Measured on a 2 px SSE mesh with one undo-pushing operator per
second for 90 s:

| Undo steps | Tiles | Working set |
|---|---|---|
| 32 | 310 | 6.2 GB |
| 0 | 345 | 3.4 GB |

Stop and Clear free the meshes themselves (no orphan mesh left after a purge), so it is not a leak.
The `evsim/` capture functions set *Undo Steps* to 0 for the take and restore the preference after
it. For the real time workflow, set Preferences > System > Undo Steps to 0 before a chain of takes,
or restart Blender between chains.

## Rules for the clips

- The Google Map Tiles key and the Iconem share links are credentials: blur the URL field whenever
  it is on screen (`post.py` takes a blur box), and never scroll the sidebar in a take that shows it.
- Data by Andrii Shramko (Lublin) is shown with the licence line from the release notes.
- Clips go to the `videos-2026-11` release as assets with the workflow prefix, not into git.
- A minimised Blender window gives stale or 1x1 screenshots; restore it first and capture from a
  timer, not inside the operator that changed the view.
- A Cycles viewport never converges while the view or a light moves: hold still before switching.
