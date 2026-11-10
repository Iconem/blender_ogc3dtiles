# Drafts: geometry clipping upstream

Posted: [cesium-native#1486](https://github.com/CesiumGS/cesium-native/issues/1486).
The optional comment on #1307 was dropped. Anything else public needs Jonathan's OK.

## Thread on cesium-native#1486

j9liu (Cesium) agreed it belongs in cesium-native, through `GltfModifier`, ideally
chainable. Their earlier prototype stalled on finding a mesh library that:
1. does booleans on non-manifold meshes,
2. ideally leaves clean lines along the cut,
3. has a licence compatible with Apache-2.0.

[Our reply (2026-11-10)](https://github.com/CesiumGS/cesium-native/issues/1486#issuecomment-6769509999):
box and polygon cuts need no general boolean.

- **Zigzag first step:** drop the triangles fully outside, as our Geometry Nodes group does.
- **Exact cut:** a box is the intersection of half-spaces, a polygon a 2D clip in the
  tileset frame. Each triangle is clipped on its own, so manifoldness doesn't matter, and
  the cut line is exact.
- **Dependencies:** mostly glm. For concave or holed polygons, Clipper2 (BSL-1.0) cuts each
  triangle, earcut triangulates the pieces, and attributes come from barycentric
  coordinates in the original triangle. meshoptimizer collapses the thin triangles at
  the cut. glm, earcut and meshoptimizer are already dependencies.
- **Survey:**

| Library | Licence | For this |
|---|---|---|
| [CDT](https://github.com/artem-ogre/CDT) | MPL-2.0 (file-level), in vcpkg | Optional: well-shaped triangles along the cut |
| [Manifold](https://github.com/elalish/manifold), [Geogram](https://github.com/BrunoLevy/geogram) | Apache-2.0, BSD-3 | True booleans; need closed meshes, which tiles rarely are |
| [MCUT](https://github.com/cutdigital/mcut), [CGAL](https://github.com/CGAL/cgal) PMP | LGPL-3, GPL-3 (or commercial) | Handle open meshes; licence rules them out |

## Edit to the version comment on calebbuffa/cesium-native-python#2

To add to the [comment of 2026-10-23](https://github.com/calebbuffa/cesium-native-python/issues/2#issuecomment-6369381939).
Also change its "current is `v0.65`" to `v0.66`.

> - `v0.66` (2026-11-02) fixes memory-safety bugs on malformed files: a heap overflow in Draco decoding and an integer overflow in `EXT_meshopt_compression`. Tilesets using both are common, so they're a reason to bump for anyone opening third-party data.
> - `GltfModifier` needs no bump, it's been there since `v0.53`, but a Python subclass fails today with "Tried to call pure virtual function GltfModifier.apply": the trampoline in `Tiles3dSelectionBindings.cpp` calls `get_override` through `GltfModifier`, a type pybind11 doesn't know. Casting to `PyGltfModifier` there fixes it, in #7. cesium-native#1307, once merged, makes modifiers work with raster overlays, and would need a bump.
