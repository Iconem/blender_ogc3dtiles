---
title: "Quick start"
description: "Stream a first tileset in five steps"
---

1. Open the sidebar of the 3D viewport (**N**) and pick the **3D Tiles** tab.
2. Press **+** to add a tileset entry and paste a `tileset.json` URL: a Cesium ion asset, Google
   Photorealistic 3D Tiles, a local file, a share link.
3. For Cesium ion, paste your access token.
4. Leave the origin mode on *Auto*: the first tileset centres the scene.
5. Press **Start** and move around: tiles load as the camera moves, finer ones as you get closer.

![The add-on sidebar, shown here in three columns](/img/sidebar.jpg)

## What to try next

- **Imagery**: tick *Raster overlays* and add OpenStreetMap or Esri World Imagery from the bookmark
  button. See [Raster overlays](/features/raster-overlays).
- **Somewhere else**: Scene Origin, mode *Search place*, type a city. See
  [Scene origin](/features/scene-origin).
- **Less or more detail**: *Max SSE* in LOD / Streaming. Lower is finer and heavier; 8 is the default.
- **A cut**: add a mesh or a curve to a tileset's *Clipping* list. See [Clipping](/features/clipping).
- **A different look**: tick *Shared shader nodes* or *Beauty compositor nodes*. See
  [Nodes: Material Shader](/features/nodes-material) and [Nodes: Compositor](/features/nodes-compositor).
- **A render**: [Rendering](/features/rendering) waits for the tiles of each frame.

If the interface stutters while tiles pour in, lower *Imports / tick*. Every panel is described in
[The sidebar](/guide/sidebar).
