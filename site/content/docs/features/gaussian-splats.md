---
title: "Gaussian splats"
description: "3D Tiles of Gaussian splats, as native Blender 5.3 splats"
---

![Gaussian splat tiles: Elevator sample streamed in Blender 5.3 (Solid and Rendered viewport), Cycles render, and a local 3dtiled tileset](/img/splat_tiles.jpg)

A tileset of Gaussian splats streams like any other: add its `tileset.json` and press Start. Coarse
splats show from far away, finer ones as you get closer.

- **Blender 5.3 or newer**: tiles are native Gaussian splats
  ([release notes](https://developer.blender.org/docs/release_notes/5.3/rendering/)), drawn in Solid,
  EEVEE and Cycles.
- **Older versions**: the same tiles show as coloured points, with the usual
  [point display](/features/point-clouds).
- It needs the cesium-native backend.

Scene origin, clipping, rendering and converged animations work as for other tilesets. Raster
overlays are not draped on splats.

## Which tilesets

Tiles whose glTF uses `KHR_gaussian_splatting`, compressed with SPZ or not. That is what
[3dtiled](https://github.com/Iconem/3dtiled-to-3dtiles), the Cesium tilers and the
3DGS-PLY-3DTiles converter write. Tested with 3dtiled output and with the Elevator sample of the
[3D-Tiles-RendererJS 3DGS plugin](https://github.com/WilliamLiu-1997/3D-Tiles-RendererJS-3DGS-Plugin),
which has degree-3 spherical harmonics.

## Tilesets without a location

Converters often write a splat tileset with no position on the globe. The add-on detects that at
Start: the tileset keeps its own axes and metres, Z up, centred vertically, and the Scene Origin
panel reads "Local tileset".

When the scene origin is already set (Custom, Keep, a place, or an earlier tileset with a location),
such a tileset lands at the Blender origin. Move its root Empty to place it.

## Known limits

Blender sorts splats inside one object, not between objects. Where a coarse tile and the finer ones
replacing it overlap for a moment, the blending between them can be wrong during that moment.

## How it works

- cesium-native decodes the SPZ payload; position, colour, opacity, rotation, scale and the
  spherical-harmonic coefficients go into the tile.
- The tile gets the shared `OGC3D Splats` Geometry Nodes group: Mesh to Points, then Set Point Cloud
  Type to 3D Gaussian Splat.
- Attributes follow Blender's SPZ importer: `radiance:base` (colour and opacity), `scale` in metres,
  `rotation` as a (w, x, y, z) quaternion, `radiance:sh_n` for higher degrees.
- Converter output often keeps its content under many levels of empty tiles, each with a smaller
  error than its parent. cesium-native would draw nothing at those levels, so the add-on gives such
  tiles their parent's error, which makes cesium-native refine through them.
