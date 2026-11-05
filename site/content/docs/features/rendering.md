---
title: "Rendering"
description: "Converged animations, Cycles, orthographic views and the clip range"
---

## Animations that wait for their tiles

Blender cannot pause inside a render to wait for tiles: streaming advances
on the UI timer, which stops while a frame renders, so *Render Animation*
renders whatever happens to be loaded.  The **Render** section does it the
other way round:

- **Stream for**: *3D viewport* (interactive, default) or *Scene camera*,
  which selects tiles for the active camera at the render resolution, so
  scrubbing the timeline re-selects tiles along the camera path.
- **Render converged animation** steps through the frame range from the
  scene camera.  The first frame waits at least *Warm-up s* (default 10:
  empty scene, cold cache).  Every frame then waits until the download /
  build queue is empty and nothing has changed for *Settle s* (or until
  *Max wait s* has passed), renders the frame with the scene's output settings to the
  Output path (one file per frame, like Render Animation), then moves on.
  ESC cancels; the sidebar shows the frame, the queue length and how long
  the scene has been quiet.  Streaming starts if it is not running, and the
  stream mode is restored afterwards.

Rule of thumb for *Settle s*: the time the viewport usually takes to stop
changing after you jump the camera, plus a margin; one or two seconds on a
local cache, more over a slow link.  Lower *Max SSE* before rendering if
you want finer tiles than you use interactively.

## Cycles viewport

Cycles restarts its viewport render whenever the scene is tagged for update.
The add-on therefore keeps the per-tick status line out of scene properties
and only redraws the sidebar; tiles appearing or disappearing still restart
it, which is unavoidable.  If "GPU Compute" is greyed out in the render
device selector, no device is ticked under Preferences, System, Cycles
Render Devices (CUDA / OptiX / HIP / oneAPI / Metal).

The beauty compositor shows less in a Cycles viewport than in EEVEE: see
[Nodes: Compositor](/features/nodes-compositor).

## Orthographic views and the clip range

The Python traversal reads the orthographic projection directly (SSE =
`ge · viewport_h / frame_height`, no distance term).  cesium-native only
knows perspective cameras, so for an orthographic viewport the adapter hands
it a 1-degree camera pulled back far enough that its frame at the view pivot
matches the orthographic frame: same screen-space error, same tiles, instead
of the thin cone / inflated SSE an un-adjusted 1-degree camera gives
(`ViewState.native_position`, `ortho_eye_offset`).  cesium-native fog
culling is off (it is height-based and would cull that far eye's view).

When a tileset root arrives the add-on sizes every 3D viewport's clip range
to it: clip end = 6 x the root radius, clamped to 1 km - 200 km, clip start
raised to clip end / 1e6; camera objects get the same clip end when theirs
is smaller (the 100 m default renders a site-scale tileset as empty).  The fixed 1e6 m clip end of earlier versions had
two side effects: Blender's clipping region (Alt+B) computes its planes in
single precision from the near and far corners, and past a far / near ratio
of about 1e7 the planes come out NaN (nothing is clipped, or a flat slab is);
and orthographic depth, which spans the whole clip range linearly, dropped to
centimetre precision.  Raise the clip end by hand for globe-scale tilesets;
keep clip start above clip end / 1e7 if you use Alt+B.  The clipping region
only affects drawing, not which tiles stream, and in Blender 5.1 only Solid
and Wireframe shading honour it: EEVEE (Material Preview, Rendered) ignores
the clipping region on any scene, add-on or not.
