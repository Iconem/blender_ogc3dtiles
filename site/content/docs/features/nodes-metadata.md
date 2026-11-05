---
title: "Nodes: Metadata"
description: "Colour tiles by class or by number, class opacity"
---

Tiles often carry data besides their geometry: a building's type and height, a LiDAR point's class
and intensity. The **Nodes: Metadata** panel reads it and colours the tiles with it.

![swissBUILDINGS3D over Bern colored by building type, with the per-class legend in the Metadata panel](/img/metadata_classes.jpg)

![swissBUILDINGS3D over Bern colored by building height through the Color Ramp](/img/metadata_ramp.jpg)

## Use it

1. Tick **Read feature metadata** before pressing Start. It needs the cesium-native backend.
2. Once tiles are in, tick **Color tiles by** and pick a **Column**.
3. Text and class columns get a legend, numbers get a colour ramp.

| Setting | What it does |
|---|---|
| **Strength** | How much of the metadata colour replaces the tile's own. Lower it to see a raster overlay through the colours. |
| **Legend** (classes) | One colour and one opacity per class. Opacity 0 hides the class: the ground of a LiDAR cloud, for one. |
| **Color Ramp** (numbers) | Add, move and recolour its stops. Edits are kept. |
| **Custom range** (numbers) | Sets both ends of the ramp by hand, live. |
| **All columns as attributes** | Keeps every column on the tiles, not only the active one, for your own shaders and Geometry Nodes. About 40 MB per column on 10 million vertices. |

## Point clouds

Point values work the same way, per point.

- **Intensity** and other numbers go through the ramp. The ramp spans the 1st to 99th percentile,
  since LiDAR intensity has rare huge values.
- **Classification** is a class column with the LAS 1.4 names and the colours LiDAR viewers use
  (2 Ground, 5 High vegetation, 6 Building...). Classes 64 and above are user-defined and keep their
  number.

Tested on an IGN LiDAR HD COPC tile streamed by 3dtiled, which sends both when the tileset URL ends
with `&attributes=intensity,classification`.

## Colour by level of detail

Two columns come from the tileset's hierarchy instead of its content, one value per tile, through the
Color Ramp:

- **tile level**: how deep the tile is in the hierarchy, 0 being the root. Tilesets that nest other
  tilesets count those levels too.
- **tile error (log2 m)**: the geometric error the tile declares, as a base-2 logarithm, since it
  roughly halves at each level. 3 means 8 m, 0 means 1 m, -10 stands for tiles that declare none.

They show which level of detail is on screen where, and where two levels meet.

## For your own nodes

- Each tile has an `ogc3d_feature` vertex attribute (the row of the table) and a `meta_<column>`
  attribute for the active column.
- The full table stays on the tile object, as JSON in the `ogc3d_features` custom property.
- Metadata of the tileset shows in the panel; that of groups, tiles and contents is in the
  `ogc3d_tile_metadata` custom property of each tile.

## The node group

*Color tiles by* is the `OGC3D Metadata` group, placed before the shared shader nodes in each tile's
material: a palette lookup for classes, a Color Ramp for numbers, and the mix with the tile's own
colour.

![OGC3D Metadata](/img/nodes_metadata.jpg)

## What is read

- `EXT_structural_metadata` tables, and b3dm batch tables, which cesium-native converts.
- Per-point attributes: `EXT_structural_metadata` property attributes, `pnts` batch tables, and plain
  scalar attributes such as `_INTENSITY` and `_CLASSIFICATION`.
- Metadata in textures: feature id textures and property textures, 8-bit channels only. The column in
  use becomes one image per tile.
- Text columns become classes shared by all tiles. Columns that differ on every row, like UUIDs, stay
  in the table only.
- Not read yet: vector columns, and tile metadata stored in implicit subtrees.

Measured on swissBUILDINGS3D over Bern, 608 tiles: about 10 ms per tile on the worker threads, 2.7 MB
of JSON for 468 tiles on screen, and 0.5 s to switch to another column.
