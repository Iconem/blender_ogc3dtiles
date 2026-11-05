---
title: "Rendering"
description: "Which camera selects the tiles, animations that wait for their tiles, Cycles, orthographic views"
---

## Which view selects the tiles

**Stream for**, in the LOD / Streaming and Render panels, says which view decides what is loaded and
how fine.

| Stream for | Tiles are selected for |
|---|---|
| **3D viewport** (default) | The view you navigate in. |
| **Scene camera** | The active scene camera, at the render resolution. Scrubbing the timeline re-selects tiles along the camera path. |
| **Chosen camera** | A camera object you pick. |

With *Scene camera* or *Chosen camera* you keep navigating the viewport freely while another camera
does the selecting: step back and see exactly which tiles a shot pulls in, and how detailed they are.
Move or animate that camera and the tiles follow.

To freeze what is loaded while you look around, untick the tileset's checkbox in the list: nothing
more is loaded or unloaded until you tick it again.

## Animations that wait for their tiles

Blender cannot pause inside a render to wait for tiles: streaming stops while a frame renders, so
*Render Animation* renders whatever happens to be loaded. **Render converged animation**, in the
Render panel, does it the other way round: it steps through the frame range from the scene camera,
waits for the tiles of each frame, then renders it.

| Setting | Meaning |
|---|---|
| **Warm-up s** | Minimum wait before the first frame (10 by default): empty scene, cold cache. |
| **Settle s** | A frame renders once the queue is empty and nothing has changed for this long. |
| **Max wait s** | A ceiling per frame, so one slow tile never stalls the render. |

Frames go to the scene's Output path, one file per frame, with the scene's output settings. ESC
cancels. The sidebar shows the frame, the queue length and how long the scene has been quiet.

Tips:

- For *Settle s*, take the time the viewport usually needs to stop changing after you jump the camera,
  plus a margin: one or two seconds on a local cache, more over a slow link.
- Lower *Max SSE* before rendering if you want finer tiles than you navigate with.

## Cycles

- A Cycles viewport restarts its render whenever tiles appear or disappear. That is unavoidable while
  streaming; pause the tileset (its checkbox in the list) for a stable preview.
- If *GPU Compute* is greyed out in the render device selector, no device is ticked under Preferences,
  System, Cycles Render Devices.
- The beauty compositor shows less in a Cycles viewport than in EEVEE: see
  [Nodes: Compositor](/features/nodes-compositor).

## Orthographic views

Orthographic viewports and cameras work: plans and elevations select the tiles that the same frame
would get in perspective.

## Clip range

When a tileset arrives, the add-on sets the clip range of every 3D viewport to fit it: clip end at
6 times the tileset's radius, between 1 km and 200 km. Camera objects get the same clip end when
theirs is smaller, since Blender's 100 m default would render a site as empty.

- For a globe-scale tileset, raise the clip end by hand.
- If you use the clipping region (Alt+B), keep clip start above clip end / 10,000,000: beyond that
  ratio Blender's region stops clipping correctly.

## How it works

- cesium-native only knows perspective cameras. For an orthographic view the add-on hands it a
  1-degree camera pulled back far enough that its frame at the view's pivot matches the orthographic
  one: same screen-space error, same tiles. cesium-native's fog culling is off, as it would cull that
  far-away eye's view. The pure Python backend reads the orthographic projection directly.
- Clip start is raised to clip end / 1,000,000. With a very large range, orthographic depth loses
  precision, and Blender computes the Alt+B planes in single precision.
- The clipping region only affects drawing, not which tiles stream.
