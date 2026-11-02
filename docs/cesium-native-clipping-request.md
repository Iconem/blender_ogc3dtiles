# Drafts: geometry clipping upstream

Nothing here is posted. Each one needs Jonathan's OK.

## 1. New issue on CesiumGS/cesium-native

**Title: Geometry clipping by box or polygon: a clipping `GltfModifier` and a box excluder**

### Problem

Polygon clipping in cesium-native is a raster mask: `RasterizedPolygonsOverlay` is
draped on tiles and the renderer hides pixels. That has known costs:

- Nothing else sees the cut: physics, picking, shadows, exports
  ([cesium-unreal#1644](https://github.com/CesiumGS/cesium-unreal/issues/1644)).
- Adding or replacing a clip overlay reloads the tileset's tiles, so moving a
  polygon interactively is expensive.
- Each integration has to rebuild the same mask-combining logic in its shaders.
- It only works on meshes with overlay texture coordinates, not on point clouds or
  Gaussian splats.

There is also no box volume, so clipping can't be limited in height. Each
integration has to write its own `ITileExcluder` and its own shader test.

`GltfModifier` looks like the right place for this, since it already runs in a
worker thread and can re-apply to loaded tiles.

### Proposal

1. **A clipping `GltfModifier`** that cuts the model in the worker thread, from a
   list of volumes:
   - Volumes: oriented boxes, and vertically extruded `CartographicPolygon`s.
   - Mode: keep or cut, inside any or all.
   - Triangles: split on the boundary, with attributes interpolated (including
     `_CESIUMOVERLAY_n`). Generalising `clipTriangleAtAxisAlignedThreshold` to
     arbitrary planes is one possible start.
   - Points and `KHR_gaussian_splatting` primitives: filtered per point.
   - `GltfModifier::trigger` re-cuts loaded tiles when a volume moves, without
     reloading them.
2. **`BoxTileExcluder`** (`OrientedBoundingBox`, `invert`): excludes tiles entirely
   inside, or entirely outside, a box. It's small, and has no rendering side.

Plane-based clipping doesn't need closed meshes, which is what stopped the Manifold
prototype in [cesium-unreal#1818](https://github.com/CesiumGS/cesium-unreal/issues/1818).

### Related

- [cesium-native#1307](https://github.com/CesiumGS/cesium-native/pull/1307), open:
  makes `GltfModifier` work with raster overlays.
- [cesium-native#384](https://github.com/CesiumGS/cesium-native/issues/384), open:
  accuracy of the `withinPolygons` test on non-region bounding volumes.
- CesiumJS moved `ClippingPolygonCollection` from a signed distance texture to a
  vector-tile-based technique in 1.145
  ([#13654](https://github.com/CesiumGS/cesium/pull/13654)). That's in its renderer,
  so native integrations can't reuse it.

### Questions

- Is this in scope for cesium-native, or do you see it as integration work?
- A tileset has a single `GltfModifier`: should clipping be one modifier that others
  can wrap, or should modifiers be chainable?

Our use: a Blender add-on on cesium-native through
[cesium-native-python](https://github.com/calebbuffa/cesium-native-python), clipping
meshes, point clouds and splats with boxes and polygons. Today that's shader tests,
Geometry Nodes and a Python `ITileExcluder`, and we'd rather bind a native modifier.

## 2. Comment on cesium-native#1307 (optional)

I wouldn't add this: the PR is in its last review and testing round. Opening the
issue above with its link already shows up in the PR's timeline. If you want to ask
anyway, post it after the issue exists:

> Thanks for this. Out of interest, does your modifier cut geometry by polygon? We're
> looking at box and polygon clipping as a `GltfModifier` (#NNNN,
> CesiumGS/cesium-unreal#1644), and it would rely on this PR for overlays after a
> re-trigger.

## 3. Lines to add to the version comment on calebbuffa/cesium-native-python#2

To add to the [comment of 2026-10-23](https://github.com/calebbuffa/cesium-native-python/issues/2#issuecomment-6369381939).
Also change its "current is `v0.65`" to `v0.66`.

> - `v0.66` (2026-11-02) fixes a heap overflow in Draco decoding and an integer overflow in `EXT_meshopt_compression` decoding, which is a reason to bump on its own.
> - `GltfModifier` needs no bump, it's been there since `v0.53`, but a Python subclass fails today with "Tried to call pure virtual function GltfModifier.apply": the trampoline in `Tiles3dSelectionBindings.cpp` calls `get_override` through `GltfModifier`, a type pybind11 doesn't know. Casting to `PyGltfModifier` there fixes it, in #7. cesium-native#1307, once merged, makes modifiers work with raster overlays, and would need a bump.
