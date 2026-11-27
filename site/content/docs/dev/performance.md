---
title: "Performance"
description: "Where the time goes while tiles stream into Blender, what was measured, and which settings trade speed for smoothness"
---

Blender builds every tile on its main thread, the one that draws the interface. This page gathers what was
measured about it, on Blender 5.3 with an RTX A1000 laptop (4 GB of video memory) and a 4K screen. How the
measuring is done is on the [Architecture](/dev/architecture#measuring-it) page.

## What to change when the viewport stutters

| Change | Effect, on a walk through the Iconem datasets over Google 3D Tiles |
|---|---|
| **Solid** shading while tiles load | 460 redraws per 30 s instead of 160, no gap over 0.3 s, 60 % more tiles built. Textures are what Material Preview waits for. |
| Lower **Imports / tick** (LOD / Streaming > Viewport Performance) | At 1 instead of 4: 30 % more redraws, 40 % fewer tiles per second. |
| Navigate | While the view moves the build budget is already the small one (*Build ms while navigating*, 8 ms). |
| Higher **Max SSE** | Fewer and coarser tiles: everything above scales with the number of tiles. |
| *Tile materials*: **Lighter tiles** | 3 ms less per tile; ticking Color correction or Terrain blending later then freezes the view for seconds. |

## Where the time of a tile goes

On Blender's main thread, per mesh tile of that walk (3,400 triangles on average):

| Step | Before | Now |
|---|---|---|
| Normals of the tile, for the tiles that have them (a fifth) | 42 ms each, 8.4 ms on average | 0.4 ms on average |
| Material: nodes, clip mix, color group, blend mix | 6.5 ms | about 1 ms: a copy of a finished material |
| `validate()` | 0.9 ms | three array tests, 0.3 ms |
| Mesh arrays (positions, face corners, UVs) | about 2.5 ms | 1.5 ms |
| Image datablock and its packed file | 0.8 ms | 0.8 to 1.1 ms |
| **Whole tile** | **19.9 ms** | **7.0 ms** |

Then Blender itself, at the tile's first draw, reads its texture. That is outside the add-on and it is now
the larger part: with every tile sharing one small image, the same walk redraws 404 times per 30 s instead
of 160 to 220.

## Reading a texture, by format

Time on the main thread for Blender to read one texture from memory and make its GPU texture
(`image.gl_load()`, 12 images each):

| Size | JPEG | PNG | Pixels in a TIFF without compression |
|---|---|---|---|
| 512 px | 1.7 ms | 5.7 ms | 0.7 ms |
| 1024 px | 6.7 ms | 21 ms | 1.8 ms |
| 2048 px | 23 ms | 76 ms | 7.9 ms |

The upload to the GPU is under 1.3 ms of each; the rest is decoding. So:

- **PNG is the slow one.** A tile with PNG textures is now handed over as the pixels cesium-native already
  decoded in a load thread, in a TIFF without compression.
- **KTX2** arrives decoded too, so its first draw is the fast column. The price is memory: 4 MB per
  1024 px texture kept with the tile, where a JPEG is 0.3 MB.
- **JPEG** is handed over as the file: lightest in memory, 7 ms at the first draw. Handing JPEG over decoded
  as well was tried on the walk and showed no gain within the noise of the runs, at 14 times the memory.
- Blender's own texture size limit (Preferences > Viewport > Textures) does not help: the file is decoded
  whole first.

Blender 5.3 ships the KTX library, and its glTF importer reads KTX2 with it into a float image set pixel by
pixel from Python. It was not timed here; nothing in it keeps a texture compressed on the GPU.

## Tile materials from a template

The first textured tile of a tileset gets its material built node by node and dressed by every setting
that is on (clip, color correction, terrain blending). A copy of it is kept. Each later tile starts from a
copy of that copy (0.2 ms) and takes its own image. The settings still run on it and find their nodes in
place. Points, splats, voxels, tiles with metadata, and scenes with Shared shader nodes, X-ray or Shadeless
are built the long way, and so is every tile when *Tile materials from a template* is off (Preferences,
Developer). The template is made again whenever a checkbox or a mode of the panel changes.

## Lighter tiles or Instant switches

See [Tile materials](/features/lod-streaming#tile-materials-lighter-tiles-or-instant-switches) for the
table. In short: Instant switches costs 3 ms per tile built the long way, and makes ticking Color
correction or Terrain blending on a loaded view take under a second instead of 5 to 13 s.

## What did not help

- Hiding the Outliner, the Properties editor and the Timeline: 162 to 165 redraws per 30 s against 151.
- Blender's texture size limit at 512 or 256 px: 192 to 197 against 160 to 220.
- Mesh arrays written as attributes: 1 ms per tile at the size of real tiles (it is 10 ms at 33,000
  triangles).

## Not explained yet

Over 20 minutes of the walk the viewport slows from about 150 to 100 redraws per 30 s, with Blender at
6.9 GB of memory and 3.3 GB of video memory. Datablock counts stay level. It was measured before the
changes of this page and not again since.
