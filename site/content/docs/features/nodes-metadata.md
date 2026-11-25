---
title: "Nodes: Metadata"
description: "Colour tiles by class or by number, class opacity"
---

Tiles often carry data besides their geometry: a building's type and height, a LiDAR point's class
and intensity. The **Nodes: Metadata** panel reads it and colours the tiles with it.

![swissBUILDINGS3D over Bern colored by building type, with the per-class legend in the Metadata panel](/img/metadata_classes.jpg)

![swissBUILDINGS3D over Bern colored by building height through the Color Ramp](/img/metadata_ramp.jpg)

## Use it

1. Choose **Property** in *Color tiles by* and tick **Read feature metadata** under it, before pressing
   Start or while streaming: in that case a line under it
   offers **Reload Tiles with their Properties**, which loads the tiles on screen again. It needs the
   cesium-native backend. The
   *Color tiles by* row is always shown; its properties come with the metadata.
2. Once tiles are in, tick **Color tiles by**, leave the source on **Property** and pick one.
3. Text and class properties get a legend, numbers get a colour ramp.

*Color tiles by* has four sources. The last three need no metadata and work on any tileset:

| Source | Colours |
|---|---|
| **Property** | A property the tiles carry, read with their metadata: a LiDAR classification or intensity, a building's year or height, any vertex, feature or texture property. The list also has **feature id**, one colour per feature of each tile (per building in swissBUILDINGS3D, say). Without *Read feature metadata* the list is empty, and the checkbox is offered right there. |
| **Elevation** | Height above the ellipsoid, through the Color Ramp. The range is that of the loaded tiles and widens as tiles load; *Custom range* sets it by hand. The heights are true metres at any world scale of the Globe: the material undoes the Globe's scale, rotation and offset. Far from the scene origin the Earth curves away from the scene's vertical, about 8 m at 10 km. |
| **Tile** | One value per tile, picked on the row below: **Random** (a colour per tile: how the tileset is cut), **Level** or **Error** (through the Color Ramp: which level of detail is loaded where). See [Colour by level of detail](#colour-by-level-of-detail). |
| **Tileset** | One colour per tileset, and with *Markers - datasets locations* on, one per dataset of an aggregate: what comes from where. |

Clicking a source ticks *Color tiles by* if it was not.

| Setting | What it does |
|---|---|
| **Strength** | How much of the metadata colour replaces the tile's own. Lower it to see a raster overlay through the colours. |
| **Legend** (classes) | One colour and one opacity per class. Opacity 0 hides the class: the ground of a LiDAR cloud, for one. |
| **Color Ramp** (numbers) | Add, move and recolour its stops. Edits are kept. |
| **Custom range** (numbers) | Sets both ends of the ramp by hand, live. |
| **Keep every property as an attribute** | By default a tile only carries the property picked above, as a `meta_<name>` vertex attribute. This keeps them all, for your own shaders and Geometry Nodes. About 40 MB per property on 10 million vertices. Colouring does not need it. |

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

The **Tile** source has two values that come from the tileset's hierarchy instead of its content, one per
tile, through the Color Ramp. They need no metadata (cesium-native backend):

- **Level**: how deep the tile is in the hierarchy, 0 being the root. Tilesets that nest other
  tilesets count those levels too.
- **Error**: the geometric error the tile declares, on a log scale since it roughly halves at each
  level. The panel shows the range in metres. Tiles that declare none count as a millimetre.

They show which level of detail is on screen where, and where two levels meet. The range follows the
loaded tiles; *Custom range* sets it by hand (for Error, as base-2 logarithms of metres: 3 is 8 m).

**Random** gives every tile its own colour, to see the tiles themselves.

Before this version these were three entries of the property list (*tile level*, *tile error*, *tile
(random color)*) and needed *Read feature metadata*.

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
