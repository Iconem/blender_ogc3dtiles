# Voxel tilesets in Blender: what was measured

Status: blocks, Volumes and coloring other tilesets are in the add-on (`tileset/voxels.py`,
`tileset/asset_fixes.py`, `io.build_voxel_volume`, `voxel_lookup.py`). Measured on 2026-11-03 on Blender 5.3 beta and the
binding's cesium-native v0.59.

## Test data

- [GeoTOP](https://bedrock.engineer/geotop-voxels/), the Dutch national geological model,
  hosted by Bedrock.engineer: public `geotop_amsterdam`, `geotop_utrecht_province` and
  `geotop_delft_10x` tilesets. Amsterdam is an implicit octree of 73 tiles on 3 levels,
  box shape, `SCALAR FLOAT32` `lithok` class per voxel, no-data -9999. The root is
  126 × 47 × 105 voxels, level 2 about 82 × 31 × 68.
- [Bedrock's `amsterdam_ellipsoid`](https://bedrock.engineer/nl-amsterdam-noord/amsterdam_ellipsoid/tileset.json):
  the same area as region tiles, with `lithology` and `stratigraphy` as UINT8. Region
  tiles need no axis guess, which makes it the reference for GeoTOP's orientation.
- CesiumJS samples (`Apps/SampleData/Cesium3DTiles/Voxel`): a single tile of 2 × 3 × 4,
  with colours equal to XYZ, useful to check axes.
- [bertt/3dtiles_voxels](https://github.com/bertt/3dtiles_voxels) has small demos,
  `voxeldam` (loaded here, 10 × 10 × 10) and `voxelgorinchem`, in unit boxes.
- `Jastman/shizuoka-demo-cesium-BD` has no voxel tileset yet: its URL is empty and it
  draws an illustrative fallback. It does list open LiDAR data.
- [swissgeol](https://viewer.swissgeol.ch): its voxel layers are Cesium ion assets, listed in
  [`layers/special/voxels.json5`](https://github.com/swisstopo/swissgeol-viewer-suite/blob/develop/layers/special/voxels.json5).
  The API answers 401 without a token, so they need swisstopo's permission. Its open GOCAD
  download of the GMT15 temperature model loads when written as one voxel tile: 317 × 70 ×
  107 cells, 1 km × 100 m, on a grid rotated 30 degrees in LV95, 10 to 300 °C. A good
  continuous field, on the ramp as blocks and as a Volume.
- Not tried: [felipecarrillo100/vox3dt](https://github.com/felipecarrillo100/vox3dt)
  (LAS to voxel tiles).

## Findings

**Streaming works like any other tile.** cesium-native does the selection: for one
narrow view of Amsterdam it visited 27 tiles, culled 48 and selected 16 of level 2.

**Two subtree problems, worked around in Python.** GeoTOP's subtree JSON holds its
availability in a `data:application/octet-stream;base64` buffer. cesium-native v0.59 hands
it to curl and fails (`URL using bad/illegal format`). The buffer also has no
`byteLength`, which reads as "nothing available". `asset_fixes.make_accessor` wraps the
asset accessor: it answers `data:` requests and completes the JSON. Waiting for a response
needs a Python thread: `then_in_worker_thread` crashes the interpreter, because the
binding releases the Python callback without the GIL. Newer cesium-native versions were
not tested.

**Binding gaps.** `MeshPrimitive` has no `EXT_primitive_voxels` accessor, so the
dimensions come from the glTF JSON in the response. Mode values above int32 don't survive
the reader (Bedrock's region tiles use 2147483649), so voxel primitives are recognized by
having no `POSITION`.

**Placement.** The grid fills the tile's bounding volume, which only cesium-native knows
for implicit tiles, so the faces are built in a unit cube on the worker and placed in
`prepare_in_main_thread`. Dimensions change per level and per tile.

**Axes.** As in CesiumJS, the bounding volume decides. Box grids are Y-up: tile X = glTF x,
tile Y = -glTF z, tile Z = glTF y. Colors on VoxelBox: X, Y, Z correlate with R, G, B at
0.86, 0.94 and 0.91, and no other pair correlates. Regions are Z-up with no flip.

GeoTOP's box has a mirrored Y axis (it points south). There the data only fits with tile
Y = +glTF z, which is the same as requiring that the whole map never mirrors:

| GeoTOP Amsterdam | tile Y = -glTF z | tile Y = +glTF z |
|---|---|---|
| same class across neighbouring level 2 tiles (4 pairs) | 19-32 % | 65-80 % |
| column share of class 1 / 2 / 5 against the region tileset, root tile | 0.02 / 0.49 / -0.02 | 0.54 / 0.80 / 0.75 |

Whether Bedrock's viewer shows these tiles the same way was not checked: CesiumJS always
applies the flip for box tiles.

**Vertical stretch.** Use the geodetic normal: the geocentric direction leans 0.2° at this
latitude, which a stretch of 80 turns into about 4 km of slant.

**Three ways to show them:**

| | how | per tile | result |
|---|---|---|---|
| Exposed faces mesh | only faces next to empty space, with a class per face | about 7 ms numpy, then 65 to 80 ms on the main thread with hooks, about 50,000 faces per tile | crisp blocks, opaque. Best for classes. No raster overlays; clipping not tested |
| OpenVDB Volume | one `.vdb` per tile, `bpy.data.volumes` | 48 ms to write 620,000 voxels, 2.3 MB | soft. Suits continuous fields such as weather. Blender has no nearest sampling in the Volume shader. Self-lit: scattering washes the classes to white, and emission must be scaled by density or it adds up per metre |
| Volume, upsampled ×4 | nearest copy to fake blocks | 64× the voxels, 511 ms, 7.1 MB for a crop of 165,000 | sharper, still not blocks. Not worth it |

`openvdb` ships with the official Blender builds tested here (4.5, 5.1, 5.2, 5.3).
`Grid.copyFromArray` needs a contiguous array: a transposed view gives stripes with the
period of the leaf nodes. Use `np.ascontiguousarray`.

**Coloring a tileset from a voxel tileset.** `voxel_lookup.py` pastes the tiles, coarse
first, into one grid over the root box, kept as slices of one 2D atlas: 338 × 282 × 126
cells in a 4056 × 3102 image for GeoTOP, a budget of 12 M cells. A shared shader group goes
from world position to the root box's axes to the atlas, with Closest interpolation, to
the shared palette. The byte is 0 where no voxel exists, which drives the Mix Shader to
Transparent: the boolean intersect. New tiles and palette edits only rewrite pixels.

Checked in Cycles against the Python grid on a plane through the model: 99.97 % of 360,000
pixels have the expected color; the rest sit on borders. Colors, cut and mix also shown on
Google Photorealistic 3D Tiles in EEVEE. Points use the same group, not tested. The atlas
has to be gray, because a shader turns color into a number by luminance, and packed,
because Cycles doesn't see the pixels of a generated image otherwise.

Limits: the root box is the only region, so the cell size is the model's size over about
230, and tiles that go out of view stay in the grid. World position means a moved tileset
root needs a rebuild. A scan on top of the model mostly falls outside it: on GeoTOP only
low ground and canals are inside.

## One or several classes per cell

3D Tiles gives containers for values and leaves their meaning to the schema. It has no
bitmask concept, so several classes in one value is our own convention, and other viewers
only see a plain integer. Checked against
[`EXT_mesh_features`](https://github.com/CesiumGS/glTF/tree/3d-tiles-next/extensions/2.0/Vendor/EXT_mesh_features)
and [`EXT_structural_metadata`](https://github.com/CesiumGS/glTF/tree/3d-tiles-next/extensions/2.0/Vendor/EXT_structural_metadata):

| Where | One class | Several classes |
|---|---|---|
| Vertex or voxel attribute | a number | an integer bitmask, or one attribute per class |
| Texture | an enum, or a feature ID per texel | a fixed-length array, within the 4 channels, or a bitmask |
| Feature ID and property table | one row per feature | several feature ID sets on a primitive, or a richer type in the row |

Feature IDs are per vertex, per texel or implicit (the vertex index). The spec has nothing
per face: to class a face, give its three vertices their own copies with the same ID, or use a
texture. Above the geometry, 3D Tiles also has metadata per tileset, content group, tile and
content, which suits one class for a whole tile.

**Our convention, when we need several classes:** an unsigned integer property (`UINT8` to
`UINT32`) whose bit `n - 1` means class code `n`, and 0 means no class, with the meaning
written in the property's `description` in the schema. `FLOAT32` isn't safe for this, because
it loses exact values above 24 bits.

Not built yet. The add-on stores one class per cell: `phases.py` writes `FLOAT32` values,
later years winning, and `voxel_lookup` reads one byte per cell.

## Making a voxel tileset

We found no standard tiler for this format: a search for one from grids such as NetCDF or
OpenVDB came back empty, which isn't proof that none exists. The tilesets above each come
from their own pipeline. [vox3dt](https://github.com/felipecarrillo100/vox3dt) builds a
pyramid from LAS or LAZ, but its tiles are `.glb` cubes, not voxel content.

**Voxelizing.** `phases.py` casts one vertical ray per column with Blender's BVH and pairs the
crossings into inside spans, which needs closed meshes. A column where a ray grazes an edge
and gets an odd count is left out. Off-the-shelf alternatives, not tried here:
[OpenVDB's `meshToVolume`](https://openvdb.org/documentation/doxygen/MeshToVolume_8h.html)
and [trimesh](https://github.com/mikedh/trimesh).

**Storing the input.** Nothing is standard for 3D Tiles input. A dense array is enough for a
class grid. OpenVDB suits sparse grids, and comes with Blender.

**Tiling.** `tileset/voxels.py` `write_class_tileset` writes one tile, as an implicit octree of
one level. A real pyramid still needs coarser levels from the fine grid: for classes, the most
common class of each 2 × 2 × 2 block rather than an average, since a mean of class codes means
nothing. GeoTOP and Bedrock show the add-on already streams such pyramids of 3 levels.
Explicit trees of voxel tiles were not tried.

**Burning classes into point clouds.** Drafted in `scripts/pdal_burn_classes.py`, never run in PDAL.
PDAL's filter list has no stage for a lookup
in an external voxel grid: `filters.crop` takes boxes and polygons, `filters.overlay` takes
OGR data. `filters.python` can do it with a numpy lookup, writing `Classification`, and the LAS
then goes to Potree or any other viewer. numpy did 9 to 15 million lookups per second here,
without the file reading and writing.
