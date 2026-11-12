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

## glTF extensions: honoured and ignored

What the add-on reads from a splat tile, through cesium-native, and what it leaves aside.

| Extension or attribute | Status | Notes |
|---|---|---|
| `KHR_gaussian_splatting` attributes `POSITION`, `COLOR_0`, `KHR_gaussian_splatting:ROTATION`, `KHR_gaussian_splatting:SCALE` | Honoured | Colour and opacity come from `COLOR_0`; the node transform rotates and scales the splats; the older `_ROTATION` / `_SCALE` names are accepted too. |
| `KHR_gaussian_splatting:SH_DEGREE_n_COEF_m` | Honoured | Degrees 1 to 3, in spec order, as `radiance:sh_n`. Degree 0 is the base colour. |
| `KHR_gaussian_splatting` primitive fields `kernel`, `colorSpace`, `projection`, `sortingMethod` | Ignored | Blender draws its own kernel and sorts within each object. |
| `KHR_gaussian_splatting_compression_spz_2` | Honoured | cesium-native decodes the SPZ payload as stored, with no axis conversion: the converter's node matrix is what places the splats, as in the 3D-Tiles-RendererJS plugin. |
| `EXT_splat_opacity` version 2 | Honoured | Draft extension of the 3DGS-PLY-3DTiles converter (William Liu). The converter merges splats into their coarse parents, which gives source opacities above 1; it then grows ("coverage boosts") the scales of those splats and clamps the opacity before writing SPZ, and records the source opacity and the pre-boost shape in this extension so a reader can undo the growth. The add-on removes the boost (the splats get their pre-boost scales back) and draws the source opacity, clamped to 1. Readers that ignore the extension, among them CesiumJS and the SPZ payload's own fallback, draw the grown splats, which look like soft blobs at coarse levels. The fraction of boost kept is `SPLAT_COVERAGE_BOOST_KEPT` in `tileset/native_mesh.py`, 0 by default. |
| `EXT_splat_opacity` version 1 | Ignored | Legacy form with a display-ready float accessor; the SPZ values are used. |
| `KHR_materials_unlit` | Not applicable | Splats carry no material. |
| `EXT_mesh_features`, `EXT_structural_metadata` on splat tiles | Ignored | Read on mesh and point tiles only. |

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
