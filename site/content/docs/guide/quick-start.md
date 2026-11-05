---
title: "Quick start"
description: "Stream a first tileset, the sidebar panels and the node groups"
---

1. Add a tileset entry (+) and paste a `tileset.json` URL (Cesium Ion, Google
   Maps 3D Tiles, local server, share link…)
2. For Cesium Ion: paste your access token
3. Leave the origin mode on *Auto* (first tileset centres the scene)
4. Hit **Start**
5. Navigate the 3D viewport — tiles load as you move the camera

Every section of the sidebar is its own panel (boxed, collapsible, and
re-orderable with the drag handle in its header, like the Object
Properties tabs; Blender remembers the order and the folded state).
Default order, top to bottom: the status line, Start / Stop / Clear, the
tileset list, the selected tileset's fields, then its **Raster overlays** and
**Clipping** each in a box of its own with the checkbox that switches it on,
and a third box for **Clip to viewport region (Alt+B)**, which applies to all
tilesets;
**Scene Origin** (collapsed), then **LOD / Streaming** (Max SSE, Parallel
DL, Imports / tick, Max points / vertices, and a collapsed *Advanced*
sub-panel: build time while navigating, disk cache, per-stream
backend stats, and with the pure Python backend its own settings: Max Tiles,
foveation, detail falloff, max distance; with cesium-native its cache size in
MB), **Nodes: Material** (shared shader nodes, a button that opens a tile's own
material, faces), **Nodes: Geometry** (shared geometry
nodes, point display and radius, relation lines),
**Nodes: Compositing** (beauty compositor nodes, edges and sliders, stable viewport),
**Nodes: Metadata** (collapsed), **Render** (collapsed), then the
collapsed **Coordinate Info** panel.  The backend is chosen in the add-on
preferences.  **Max points / vertices (M, beta)** caps what is shown, all tilesets
together: over the cap every tileset is streamed coarser (its SSE is
multiplied, the panel shows by how much) until the view fits, and detail
returns when there is room.  0, the default, means no cap; the coarsest tiles
of a tileset are always shown, so a cap below their size cannot be met.
Defaults: Max SSE 8 px, 16 parallel downloads, 4 imports per
tick (lower it if the UI stutters while tiles pour in).

The four shared node groups have the same row: *Shared geometry nodes*,
*Shared shader nodes*, *Beauty compositor nodes* and *Color tiles by*.  The
checkbox creates the group when missing and puts it on every tile, loaded or
streamed later (on the scene, for the compositor); unticking takes it off and
keeps the group in the file, so hand edits survive.  Its options show below
while it is ticked.  The arrow menu at the end of the row resets the group to
the add-on's default nodes or deletes it.  The node-tree
button of the row, and the one next to the point display, opens the
corresponding tree ('OGC3D Relight' shader group, 'OGC3D Beauty' compositor
tree, 'OGC3D Points…' geometry nodes) pinned in a node editor — an existing
one, or the 3D viewport split in two — so the shader or the compositor can
be adapted by hand; the sliders keep driving the same Value nodes.

There is no single material for all tiles: every tile keeps its own, with its
own texture.  The shared groups are nodes inside each of them, in this order:
tile texture (or vertex color) → `OGC3D Metadata` (*Color tiles by*) →
`OGC3D Relight` (*Shared shader nodes*) → Material Output.  *Open a tile's
material* shows it for the active tile, or the first one found.

Every node group the add-on builds is laid out in columns when it is built or
reset, and has a node-editor button next to the setting it belongs to: the
four rows above, the point display, splat tiles, the voxel display, a
tileset's clipping volumes and the viewport-region clip.  Raster overlays have
no group of their own: their nodes are in each tile's material.

A tile's material, here a point tile with a raster overlay, clipping, the
metadata colors and the shared shader nodes:

![A tile's own material](/img/nodes_tile_material.jpg)

Its parts: `OGC3D Clip` (viewport-region clip), `OGC3D Relight` (shared shader
nodes) and `OGC3D Metadata` (color tiles by):

![OGC3D Clip](/img/nodes_clip.jpg)
![OGC3D Relight](/img/nodes_relight.jpg)
![OGC3D Metadata](/img/nodes_metadata.jpg)

Geometry nodes of the point display (`OGC3D Points`; the shared geometry nodes
are a pass-through until edited) and the `OGC3D Beauty` compositor tree:

![OGC3D Points](/img/nodes_points.jpg)
![OGC3D Beauty](/img/nodes_compositor.jpg)

The glTF importer (Python backend, or "Direct mesh" off) is silenced to
WARNING while tiles import; the direct mesh path prints nothing per tile.
