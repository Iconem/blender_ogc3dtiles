# Draft: feature request for CesiumGS/cesium-native

Not posted. Needs Jonathan's OK.

---

**Title: Geometry clipping by box or polygon: box excluder and a clipping `GltfModifier`**

## Problem

Polygon clipping in cesium-native is a raster mask: `RasterizedPolygonsOverlay`
is draped on tiles and the renderer hides pixels. That has known costs:

- Nothing else sees the cut: physics, picking, shadows, exports
  ([cesium-unreal#1644](https://github.com/CesiumGS/cesium-unreal/issues/1644)).
- Adding or replacing a clip overlay reloads the tileset's tiles, so moving a
  polygon interactively is expensive.
- Each integration has to rebuild the same mask-combining logic in its shaders.
- It only works on meshes with overlay texture coordinates, not on point clouds
  or Gaussian splats.

There is also no box volume, so clipping can't be limited in height. Each
integration has to write its own `ITileExcluder` and its own shader test.

## Proposal

1. **`BoxTileExcluder`** (`OrientedBoundingBox`, `invert`): excludes tiles entirely
   inside, or entirely outside, a box. It's small, and has no rendering side.
2. **A clipping `GltfModifier`** that cuts the model in the worker thread, using a
   list of volumes:
   - Volumes: oriented boxes, and vertically extruded `CartographicPolygon`s.
   - Mode: keep or cut, inside any or all.
   - Triangles: split on the boundary, with attributes interpolated (including
     `_CESIUMOVERLAY_n`). Generalising `clipTriangleAtAxisAlignedThreshold` to
     arbitrary planes is one possible start.
   - Points and `KHR_gaussian_splatting` primitives: filtered per point.
   - `GltfModifier::trigger` re-cuts loaded tiles when a volume moves, without
     reloading them.

Plane-based clipping doesn't need closed meshes, which is what stopped the
Manifold prototype in
[cesium-unreal#1818](https://github.com/CesiumGS/cesium-unreal/issues/1818).

## Related

- [cesium-native#1307](https://github.com/CesiumGS/cesium-native/pull/1307), open:
  makes `GltfModifier` work with raster overlays.
- [cesium-native#384](https://github.com/CesiumGS/cesium-native/issues/384), open:
  accuracy of the `withinPolygons` test on non-region bounding volumes.
- CesiumJS has `ClippingPlaneCollection` and `ClippingPolygonCollection`, whose
  polygon clipping moved from a signed distance texture to vector clipping in
  1.145. These are renderer-side, so native integrations can't reuse them.

## Questions

- Is this in scope for cesium-native, or do you see it as integration work?
- Should volumes be one modifier, given a tileset has a single `GltfModifier`, or
  should modifiers be chainable?

Our use: [blender_ogc3dtiles](https://github.com/Iconem/blender_ogc3dtiles)
(private for now), a Blender add-on on cesium-native through
[cesium-native-python](https://github.com/calebbuffa/cesium-native-python). It
clips meshes, point clouds and splats with boxes and polygons, today with masks,
shaders and Geometry Nodes.
