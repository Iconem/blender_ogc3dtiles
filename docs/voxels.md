# Voxel tilesets in Blender: what was measured

Status: prototype only, nothing in the add-on yet. Measured on 2026-11-03 on Blender 5.3
beta and the binding's cesium-native v0.59. Today voxel tiles produce no mesh and fall
through to the GLB import path, which was not tested.

## Test data

- [GeoTOP](https://bedrock.engineer/geotop-voxels/), the Dutch national geological model,
  hosted by Bedrock.engineer: public `geotop_amsterdam`, `geotop_utrecht_province` and
  `geotop_delft_10x` tilesets. Amsterdam is an implicit octree of 73 tiles on 3 levels,
  box shape, `SCALAR FLOAT32` `lithok` class per voxel, no-data -9999. The root is
  126 × 47 × 105 voxels, level 2 about 82 × 31 × 68.
- CesiumJS samples (`Apps/SampleData/Cesium3DTiles/Voxel`): a single tile of 2 × 3 × 4,
  with colours equal to XYZ, useful to check axes.

## Findings

**Streaming works like any other tile.** cesium-native does the selection: for one
narrow view of Amsterdam it visited 27 tiles, culled 48 and selected 16 of level 2.

**Blocker: `data:` URIs in subtrees.** GeoTOP's subtree JSON holds its availability in a
`data:application/octet-stream;base64` buffer. cesium-native v0.59 hands it to curl and
fails (`URL using bad/illegal format`), so no tile loads. The tests used a local copy of
`tileset.json` and the subtree, with the same availability written as `constant: 1`, and
tiles from the real server. Newer cesium-native versions were not tested.

**Binding gap.** `MeshPrimitive` has no `EXT_primitive_voxels` accessor, so the
prototype read the dimensions from the glTF JSON.

**Axes.** Tile X = glTF x, tile Y = -glTF z, tile Z = glTF y, checked on the colours of
the VoxelBox sample. `3DTILES_content_voxels` dimensions are therefore glTF x, z, y.
Dimensions and box size change per level and per tile (15 m or 15.5 m high at level 2).

**Three ways to show them:**

| | how | per tile | result |
|---|---|---|---|
| Exposed faces mesh | only faces next to empty space, with a class per face | about 7 ms numpy + 25 ms `bpy`, 20,000 faces for 170,000 voxels | crisp blocks, opaque, every existing tile feature applies. Best for classes |
| OpenVDB Volume | one `.vdb` per tile, `bpy.data.volumes` | 48 ms to write 620,000 voxels, 2.3 MB | soft. Suits continuous fields such as weather. Blender has no nearest sampling in the Volume shader |
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
