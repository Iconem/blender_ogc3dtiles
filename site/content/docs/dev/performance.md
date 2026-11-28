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

## What holds a view from filling

Google Photorealistic 3D Tiles over Rome, disk cache off, Max SSE 16: the view over St Peter's (1,698 tiles),
then two more views across the city, 90 s each at most. cesium-native's queues say where tiles wait:

- after about 50 s, nothing waits for the network any more (worker queue at 0), while 400 to 1,300 loaded
  tiles wait for Blender's main thread to build them (main queue). The view fills at about 20 tiles a second.

So on that view the main thread is the limit, not the requests. Time to fill the first view, two runs each,
alternated:

| Setting | First view filled | Tiles built in 90 s on the next two views |
|---|---|---|
| As before: a redraw after every step that built a tile | 86 s, 69 s | 1,480 to 2,285 |
| **At most two redraws a second while tiles are built** (now the default) | 63 s, 59 s | 2,090 to 2,476 |
| Imports / tick at 8 instead of 4 | 59 s, 55 s | 2,350 to 3,123 |
| 64 load threads and 64 Concurrent Requests | 64 s, then a run that loaded 763 tiles only | not comparable |

- Blender redraws the viewport by itself while you navigate, so the limit only applies while the view is
  still and tiles pour in: the view updates twice a second instead of after every step.
- 8 imports per tick fills faster still but makes navigating stutter; it stays at 4.
- More request threads did not help here, and the second run suggests refused requests at 64 at once.
  With a slow server (a 300 ms round trip) the requests become the limit. There, Ben Dyson found that
  cesium-native's curl accessor holds a worker thread for each request in flight, so raising *Concurrent
  Requests* past the number of worker threads adds no requests
  ([issue 6](https://github.com/jo-chemla/blender_ogc3dtiles/issues/6)). That case was not measured here.

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
  1024 px texture kept with the tile, where a JPEG is 0.3 MB. Measured on a real tileset below.
- **JPEG** is handed over as the file: lightest in memory, 7 ms at the first draw. Handing JPEG over decoded
  as well was tried on the walk and showed no gain within the noise of the runs, at 14 times the memory.
- Blender's own texture size limit (Preferences > Viewport > Textures) does not help: the file is decoded
  whole first.

## KTX2, measured

On the Vestibolo of St Peter's (Iconem, meshopt and KTX2: BasisLZ textures of 1024 px and 2048 x 1024 px,
with mipmaps), 17 textures taken from its tiles, median per texture:

| Way of reading it | Where | Time |
|---|---|---|
| cesium-native, to RGBA pixels (what the add-on does) | load thread | 18 ms, every mip level |
| the same, wrapped in a TIFF without compression | load thread | 2.2 ms |
| Blender reads that TIFF at the first draw | main thread | 6.2 ms |
| cesium-native, to BC1 (DXT1), GPU-compressed | load thread | 7.0 ms |
| Blender reads that as a DDS file at the first draw | main thread | 6.8 ms |
| Blender 5.3's own KTX reader (its glTF importer's), from a file | main thread | 43 ms to decode, 7 ms to make the float image, 13 ms at the first draw |

Video memory, 48 of these textures loaded:

| As | Per texture |
|---|---|
| TIFF, RGBA pixels | 5.3 MB |
| DDS, BC1 compressed | 5.3 MB |
| Float image (Blender's KTX reader) | 16 MB |

So in Blender a texture takes the same video memory whatever the file it came from: Blender 5.3 decodes a
DDS too and uploads plain RGBA pixels with their mipmaps (5.3 MB for 1024 px). A JPEG takes the same once
drawn. KTX2 saves download size, not video memory; Blender's own reader takes three times more (float
pixels) and does all its work on the main thread.

The test also found that a KTX2 texture with mipmaps comes out of cesium-native with every level in one
buffer, which the add-on refused: such tiles showed without texture. The add-on now takes the first level.

## Raster overlay images

An overlay tile used to become a Blender image on the main thread through float pixels, `foreach_set` and
`pack()`, which encodes a PNG. It is now made in the load thread as a TIFF without compression, as tile
textures are, and only packed on the main thread. Same pixels:

| Overlay tile | Before, main thread | Now, main thread | First draw |
|---|---|---|---|
| 256 px | 7.5 ms | 0.06 ms | 0.1 then 0.5 ms |
| 512 px | 31 ms | 0.17 ms | 0.2 then 1.0 ms |

## Tile materials from a template

The first textured tile of a tileset gets its material built node by node and dressed by every setting
that is on (clip, color correction, terrain blending). A copy of it is kept. Each later tile starts from a
copy of that copy (0.2 ms) and takes its own image. The settings still run on it and find their nodes in
place. Points, splats, voxels, tiles with metadata, and scenes with Shared shader nodes, X-ray or Shadeless
are built the long way, and so is every tile when *Tile materials from a template* is off (LOD / Streaming >
Viewport Performance; also in Preferences > Developer).

Materials are not compared node by node. A template is filed under a key: the tileset, every checkbox and
mode of the panel (one hash, read at most four times a second), whether the material is double-sided and
whether it is unlit. A tile whose key has a template starts from it; any change to a checkbox or a mode gives
a new key, so the next tile is built the long way and becomes the new template.

Several textures: the add-on wires one texture per material, the base colour (photogrammetry tiles have no
other). A tile with several primitives gets one material per primitive, each from the template. Normal,
metallic-roughness or occlusion maps of a glTF are not used, by either path.

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
