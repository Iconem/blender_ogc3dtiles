# Voxel tilesets in Blender: what was measured

Status: blocks and Volumes are in the add-on (`tileset/voxels.py`,
`tileset/asset_fixes.py`, `io.build_voxel_volume`). Coloring another tileset's mesh from
a voxel grid is still a prototype. Measured on 2026-11-03 on Blender 5.3 beta and the
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
- Not tried: [felipecarrillo100/vox3dt](https://github.com/felipecarrillo100/vox3dt)
  (LAS to voxel tiles), [viewer.swissgeol.ch](https://viewer.swissgeol.ch) (Swiss geology).

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

**Coloring a mesh from a voxel tileset.** A shader can look up the voxel under each pixel:
the voxel grid as slices in one 2D atlas image (882 × 735 built in 24 ms for the root),
sampled with Closest interpolation from the surface position. It works in EEVEE and
Cycles with blocky borders. The atlas alpha says whether a voxel exists, so it also
drives a Mix Shader to Transparent: that is the boolean intersect. Tested on a sphere and
a plane, with one tile. Several tiles need one atlas per tile, or one atlas rebuilt from
the tiles in use.
