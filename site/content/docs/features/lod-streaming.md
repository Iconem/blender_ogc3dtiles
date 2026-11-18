---
title: "LOD / Streaming"
description: "How fine the tiles are, how fast they come in, and which camera decides"
---

The **LOD / Streaming** panel decides three things: which view the tiles are selected for, how
detailed they get, and how fast they are brought into Blender.

## Stream for: which camera decides

| Stream for | Tiles are selected for |
|---|---|
| **3D viewport** (default) | The view you navigate in. |
| **Scene camera** | The active scene camera, at the render resolution. |
| **Chosen camera** | A camera object you pick in the field below. |

With a camera selected, the viewport is free: orbit, step back, and look at what that camera pulls
in. Tiles refine inside its view and stay coarse, or are not loaded at all, outside of it. Move the
camera, or scrub the timeline when it is animated, and the tiles follow.

![Looking through the scene camera that selects the tiles, over the Capitoline Hill in Rome](/img/lod_camera_view.jpg)

![The same moment from outside: tiles exist, and are detailed, only where the camera looks](/img/lod_outside_view.jpg)

![The same idea rendered: through the scene camera, then from outside with the camera drawn large, over the tiles it selected](/img/lod_camera_render.jpg)

![From outside: the camera drawn large, over the patch of tiles it selected](/img/lod_outside_render.jpg)

- Looking through the camera (Numpad 0) shows what a render will contain.
- Looking from outside shows how far the selection reaches and where detail stops. It is the way to
  check a shot before a long render, or to understand why a view is heavy.
- To freeze what is loaded while you look around, untick the tileset's checkbox in the list.

## Panoramic cameras

![An equirectangular panorama in Cycles over the Colosseum, and from above with one colour per tile: tiles are selected all around the camera](/img/camera_pano.jpg)

![Top view of the panorama's tiles, one colour each](/img/camera_pano_top.jpg)

A panoramic camera (Cycles: equirectangular, fisheye, central cylindrical, cube map face) works as
*Scene camera* or *Chosen camera*. Tiles are selected all around it, as six 90° views of a cube, and
each view gets the panorama's own resolution: an equirectangular render 4096 × 2048 has 1024 px per
quarter turn, so tiles are as fine as the render needs at the horizon; a square one (1920 × 1920)
is finer vertically and gets 960 px. Fisheye cameras skip the cube faces outside their field of
view: a 180° fisheye uses five. Detail close to the camera comes in refinement steps, the finest
last: on Notre-Dame with Google tiles, two minutes for the full set, the tower tops in the last
step. Wait for the loading count to settle before rendering. EEVEE does not render panoramic cameras; Cycles
does.

## Max SSE: how fine

A tileset is a pyramid: a few coarse tiles at the top, and under each tile finer ones that replace
it. Every tile declares its **geometric error**: how far, in metres, it is from the real shape.

Seen from a distance, that error covers a number of pixels on screen: the **screen-space error**
(SSE). A tile whose error covers more pixels than **Max SSE** is replaced by its finer children; one
under it is fine enough and stays.

| Max SSE | Result |
|---|---|
| 2 to 4 | Very fine. Many more tiles, more memory, slower. |
| **8** (default) | A good balance for meshes. |
| 16 to 32 | Coarse and fast: far views, heavy point clouds, slow connections. |

- The setting is live: change it and tiles are re-selected at once.
- Because it is measured in pixels, a larger window or a higher render resolution loads more.
- What a value looks like depends on the tileset and on the tool that made it, since each tool
  declares its errors its own way. Tick the checkbox next to **Tileset Max SSE** on a tileset entry to
  give it its own value instead of this one.
- To see the levels on screen, colour the tiles by *tile level* or *tile error* in
  [Nodes: Metadata](/features/nodes-metadata).

## Concurrent Requests and Viewport Performance: how fast

- **Concurrent Requests** (20 by default, per tileset): how many tiles are requested at the same time.
  With cesium-native it counts tile loads in flight, download and decoding, and changes live; 20 is
  cesium-native's own default. With the Python backend it is the number of parallel downloads, applied
  at the next Start. Raise it on a fast connection, lower it if a server refuses requests.

*Viewport Performance*, folded under it, sets how much the viewport does at each step of the streaming
loop (an update and a redraw of the view). Renders are not affected: a converged render waits for every
tile whatever these are.

- **Imports / tick** (4 by default): how many downloaded tiles become Blender objects at each step of
  the streaming loop. Building objects happens on Blender's main thread, the one that also draws the
  interface. Higher fills the view faster but makes navigation stutter while tiles pour in; lower
  keeps the interface smooth and fills more slowly.

## Max points / vertices (beta)

A ceiling, in millions, on what is shown across all tilesets. Over it, every tileset is streamed
coarser until the view fits, and the panel shows by how much (*SSE x1.50*). Detail returns when there
is room. 0, the default, means no ceiling. The coarsest tiles of a tileset are always shown, so a
ceiling below their size cannot be met.

## Tile bounds

Draws a wire outline around every visible tile, in the 3D view only: nothing is added to the scene
and nothing shows in renders. Drag *Max SSE* or move the view with it on to watch tiles split into
finer ones and coarser ones come back.

- **Off**, the default.
- **Tile objects**: each tile object's bounding box, that is what the tile actually holds. Works
  for meshes, point clouds and Gaussian splats alike; Blender's own *Bounds* display draws nothing
  for splat objects.
- **3D Tiles volumes**: the bounding volume the tileset declares for each tile: a box, a sphere
  (three circles) or a region (a box curved along the globe, as in quantized-mesh terrain). It can
  be larger than what the tile holds. cesium-native backend only.

The colour swatch sets one colour for every outline; the colour icon gives each tile its own random
colour instead. *Width* is the line width in pixels. The eye icon hides the parts of outlines that
are behind mesh and point tiles; off, every outline is drawn on top. Gaussian splats hide no
outline: they are blended without writing depth.

## Advanced

- **cesium-native cache MB**: memory for tiles that are loaded but no longer shown, so that coming
  back to a view is instant. It is not a ceiling on what is shown: tiles in view are never dropped.
- With the pure Python backend: *Max Tiles*, *Foveation cone*, *Edge SSE relax*, *Detail falloff* and
  *Max distance*.
- Build time while navigating, the disk cache, and statistics per tileset.
