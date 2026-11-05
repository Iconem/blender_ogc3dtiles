---
title: "Feature metadata"
description: "Colour tiles by class or by number, class opacity"
---

Tiles often carry a table with one row per feature: building type, year, height. With
**Read feature metadata** on (Metadata panel, before Start), the add-on reads these
`EXT_structural_metadata` tables, including b3dm batch tables, which cesium-native
converts. It needs the cesium-native backend and Direct mesh.

Each tile gets an `ogc3d_feature` vertex attribute (the row) and a `meta_<column>`
attribute for the active column, which shaders and Geometry Nodes can read. *All columns
as attributes* keeps the others too, at about 40 MB per column on 10 M vertices. Text
columns become integer classes shared by all tiles. The full table stays on the tile
object as JSON, in the `ogc3d_features` custom property, for lookups by feature id.

**Color tiles by** mixes colors into every tile material through the shared
'OGC3D Metadata' group: one editable color per class for text, a Color Ramp between the
column's min and max for numbers (the group's own 'Ramp' node, shown in the Metadata
panel: add, move and recolor its stops there; edits are kept). Each class also has an opacity
slider next to its color: 0 hides the class, the ground of a LiDAR cloud for one. Measured on swissBUILDINGS3D over Bern, 608 tiles:
about 10 ms per tile on the worker threads, 2.7 MB of JSON for 468 tiles on screen, and
0.5 s to switch to another column. Columns that differ on every row, like UUIDs, stay in
the table only.

![swissBUILDINGS3D over Bern colored by building type, with the per-class legend in the Metadata panel](/img/metadata_classes.jpg)

![swissBUILDINGS3D over Bern colored by building height through the Color Ramp](/img/metadata_ramp.jpg)

**Point clouds** work the same way, per point: `EXT_structural_metadata` property
attributes and `pnts` batch tables without `BATCH_ID` always become `meta_<column>`
attributes (a table of millions of rows wouldn't fit a Python list). Whole numbers with
few values and enums are classes, named when the schema has an enum; other values go
through the ramp. Batched `pnts` use the table path above.

**Intensity and other point values.** Scalar attributes of point tiles become number columns, with
or without `EXT_structural_metadata`: `_INTENSITY` is the column `intensity`. Their ramp spans the 1st
to 99th percentile, since LiDAR intensity has rare huge values. **Custom range** sets both ends, live.
A byte attribute with few values, such as `_CLASSIFICATION`, is a class column instead, with one
palette color per code. `classification` gets the LAS 1.4 names and the usual viewer colors
(2 Ground, 5 High vegetation, 6 Building...); 64 and above are user-defined and keep their number. Tested on an IGN LiDAR HD COPC tile streamed by 3dtiled, which sends both
when the tileset URL ends with `&attributes=intensity,classification`. *Read feature metadata* must
be on before Start.

**Tileset, group, tile and content metadata** are read from `tileset.json`. The tileset's
own values show in the Metadata panel; the others, merged per tile, are in the
`ogc3d_tile_metadata` custom property as JSON.

With raster overlays, the metadata colors stay on top: lower **Strength** to see the map
through them.

**Textures** can hold metadata per pixel: feature id textures point at table rows, and
property textures hold the values directly. The column in use becomes one image per tile,
sampled in its material with Closest interpolation, on the mesh's first UV set. Only 8-bit
channels are read.

Not read yet: vector columns (the binding can't convert them on v0.59), and tile metadata
stored in implicit subtrees.
