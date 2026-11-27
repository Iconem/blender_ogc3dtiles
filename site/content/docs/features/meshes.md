---
title: "Meshes"
description: "Textured mesh tilesets: photogrammetry, city models, Google Photorealistic 3D Tiles"
---

![Google Photorealistic 3D Tiles over the Colosseum in Blender: viewport with the add-on sidebar, then EEVEE, Cycles with a 10 kW lamp, and EEVEE through the beauty compositor](/img/rome_google_3dtiles.jpg)

![Piazza San Marco in Venice, a photogrammetry mesh tileset, in the Solid view](/img/solid_venice.jpg)

![Khafre and Khufu at Giza, a photogrammetry mesh tileset, in the Solid view with the normal matcap](/img/mesh_gizeh_normal.jpg)

![One random colour per tile on Google Photorealistic 3D Tiles around Notre-Dame de Paris: every tile is its own object, at its own level of detail](/img/tiles_random_google.jpg)

Mesh tilesets are the most common kind: photogrammetry of a site, a city model, Google Photorealistic
3D Tiles. Add the `tileset.json` and press Start. Each tile becomes a Blender mesh with its own
material and texture.

![The sea off Nice on Google Photorealistic 3D Tiles in the Solid view. Left, before: every tile bulges like a pillow. Right, now: the water is flat, with only thin tile outlines left](/img/skirt_normals.jpg)

## What is read

| | |
|---|---|
| Tile formats | b3dm and glb, 3D Tiles 1.0 and 1.1, implicit tiling included |
| Geometry compression | Draco, meshopt |
| Textures | JPEG, PNG, WebP, KTX2 |

With the cesium-native backend all of these are decoded by cesium-native. The pure Python backend
goes through Blender's glTF importer, which on some Blender versions does not read meshopt or KTX2.

**Texture formats in Blender.** Blender keeps no texture compressed on the GPU: every image ends as plain
pixels. A JPEG goes to Blender as the file it is, and Blender decodes it at the tile's first draw (7 ms at
1024 px). A KTX2 or PNG texture is decoded by cesium-native in a load thread and handed over as pixels:
quicker at the first draw (2 ms), heavier in memory (4 MB at 1024 px against 0.3 MB for the JPEG). So KTX2
saves bandwidth, not memory, in Blender; JPEG is the light choice in memory, and PNG the one to avoid in a
dataset made for Blender. The figures are on the [Performance](/dev/performance) page.

## Things to know

- **Level of detail**: *Max SSE* in LOD / Streaming. Lower is finer and heavier.
- **Back faces**: most photogrammetry is single-sided. *Faces*, in Nodes: Material, is on *Force
  double-sided* by default, so cut or open meshes show their inside.
- **Normals**: most photogrammetry, Google Photorealistic 3D Tiles included, comes without normals,
  and Blender computes them. The skirt that hangs around each tile to hide cracks used to bend them
  along the tile's edges, so every tile shaded like a pillow. Edges sharper than 50 degrees now split
  the normals. The picture above shows the sea off Nice in the Solid view, before and after.
- **Lighting**: photogrammetry carries its light in its textures.
  [Nodes: Material Shader](/features/nodes-material) mixes it with Blender's lamps.
- **Edges and relief**: [Nodes: Compositor](/features/nodes-compositor) adds creases, ambient
  occlusion and haze.
- **Attributes**: building types, heights and other tables colour the tiles through
  [Nodes: Metadata](/features/nodes-metadata).
- **Editing**: tiles are ordinary meshes, but streaming replaces them as you move. One Geometry
  Nodes graph can edit them all: see [Nodes: Geometry](/features/nodes-geometry).
