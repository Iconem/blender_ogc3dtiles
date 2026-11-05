---
title: "Voxels"
description: "3D Tiles voxel tilesets as blocks or volumes"
---

A voxel tileset is a 3D grid of values: a geological model under a city, for one. It streams like
any other tileset, coarse grids from afar and finer ones up close, and needs the cesium-native
backend. Add its `tileset.json` and press Start: the values show as colours at the first voxel tile,
with the legend and ramp of [Nodes: Metadata](/features/nodes-metadata).

![The voxel tilesets below in Blender: Blocks on top, Volume underneath. Volume blends classes through the layers, so it is faint on GeoTOP, and VoxelBox doesn't show in it at this framing. Bedrock's region tiles can't be Volumes and stay blocks](/img/voxel_tilesets.jpg)

## Display

**Voxels**, in the Nodes: Metadata panel, picks how they show. Set it before Start.

- **Blocks**: a mesh of the cell faces next to empty space. Crisp and opaque. Best for
  classes. About 50,000 faces and 80 ms per tile on
  GeoTOP.
- **Volume (see-through)**: one OpenVDB Volume per tile, with **Volume opacity**. Soft,
  because Blender has no nearest sampling for Volumes, so better for continuous fields.
  Box tiles only, no clipping.

- **Color other tilesets**: nothing is drawn for the voxel tiles. Every other tile's
  material reads the voxel under each pixel from its world position, so a scan keeps its
  geometry and its texture or vertex color, and **Voxel color** mixes in the class. **Keep
  only inside voxels** makes the pixels outside transparent: a boolean intersect that
  doesn't touch the geometry. Box tiles only.

**Voxel height scale** stretches thin datasets vertically (GeoTOP is 62 m thick over
33 km); stretched tiles no longer line up with other data. Both settings apply at the
next Start. Box and region tiles work; cylinder tiles are skipped. See
[docs/voxels.md](/dev/notes/voxels) for the measurements.

## Tilesets tested

Tested on [GeoTOP](https://bedrock.engineer/geotop-voxels/), the Dutch geological model, with 73
tiles over Amsterdam, and on these:

| Tileset | Volume | Levels | Grid of the root tile | Values |
|---|---|---|---|---|
| [GeoTOP Amsterdam](https://bedrock.engineer/geotop-voxels/geotop_amsterdam/tileset.json) | box | 3 (73 tiles) | 126 × 105 × 47 | `lithok` classes |
| [GeoTOP Utrecht](https://bedrock.engineer/geotop-voxels/geotop_utrecht_province/tileset.json) | box | 3 (73 tiles) | 104 × 126 × 79 | `lithok` classes |
| [GeoTOP Delft](https://bedrock.engineer/geotop-voxels/geotop_delft_10x/tileset.json) | box | 1 | 101 × 101 × 89 | `lithok` classes |
| [Bedrock Amsterdam](https://bedrock.engineer/nl-amsterdam-noord/amsterdam_ellipsoid/tileset.json) | region | 3 (73 tiles) | 83 × 69 × 32 | `lithology`, `stratigraphy` |
| [Cesium VoxelBox](https://raw.githubusercontent.com/CesiumGS/cesium/main/Apps/SampleData/Cesium3DTiles/Voxel/VoxelBox3DTiles/tileset.json) | box | 1 | 2 × 4 × 3 | RGBA, to check axes |
| [bertt voxeldam](https://raw.githubusercontent.com/bertt/3dtiles_voxels/main/demos/voxeldam/tileset.json) | box | 1 | 10 × 10 × 10 | RGBA |
| [bertt voxelgorinchem](https://raw.githubusercontent.com/bertt/3dtiles_voxels/main/demos/voxelgorinchem/tileset.json) | box | 1 | 4 × 4 × 4 | RGBA |

All seven are implicit octrees. Those with several levels stream as pyramids, finer tiles
replacing coarser ones as you get closer. VoxelBox is Earth-sized and the bertt demos
sit at the Earth's centre, so **Auto** origin can't place them on a site.
