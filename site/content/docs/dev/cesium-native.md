---
title: "cesium-native: wheel and versions"
description: "Building the wheel, versions and upgrade notes"
---

## Building the wheel

The add-on installs pre-built wheels (see
[Installing the native backend](/guide/installation)).  The build
fixes for Windows, manylinux and macOS
([cesium-native-python#3](https://github.com/calebbuffa/cesium-native-python/pull/3),
October 2026) and the cibuildwheel workflow that builds wheels for the three
OSes and CPython 3.11 to 3.13
([#4](https://github.com/calebbuffa/cesium-native-python/pull/4), merged
5 November 2026) are both upstream, so `pip install .` works from a plain
checkout and a `v*` tag there builds and publishes wheels.  Upstream has not
tagged a release yet, so the add-on still installs from the jo-chemla fork's
release; once a release exists on the upstream repository, the
*Wheel release repo* preference can point there.  The add-on no longer
carries a patch or a wheel workflow of its own.

## What vcpkg is, and why the wheel takes hours to build the first time

[vcpkg](https://vcpkg.io) is Microsoft's C/C++ package manager: a recipe
("port") per library that downloads its sources and builds them for the
target platform and compiler.  cesium-native declares its dependencies in a
`vcpkg.json` and pulls them through vcpkg (via its `ezvcpkg` CMake wrapper):
thirty direct dependencies (Draco, meshoptimizer, KTX, libjpeg-turbo,
libwebp, zlib-ng, zstd, OpenSSL, curl, sqlite3, s2geometry, tinyxml2,
blend2d, glm, spz, ...) plus their own, such as abseil for s2geometry.  They are compiled from source, which is why a cold
wheel build takes one to three hours per OS, and why the CI caches the
built vcpkg tree (later builds only compile the bindings, about 15 minutes).
vcpkg pins all libraries together through a *baseline* (a commit of the
vcpkg ports registry): moving the baseline upgrades every dependency at once,
which is what makes some cesium-native upgrades expensive for the binding.

## Vendored version vs upstream

The Python binding vendors cesium-native as a git submodule.

| | version | date |
|---|---|---|
| vendored by cesium-native-python (`extern/cesium-native`) | v0.59.0 | 2026-03-31 |
| latest cesium-native release at the time of writing (2026-11-13) | v0.66.0 | 2026-11 |

Already in v0.59.0 and used by the add-on: `KHR_gaussian_splatting` with SPZ
decoding (v0.56.0, release-candidate classes in v0.58.0), raster overlays
(TMS / WMTS / WMS / URL template / ion / Bing / Google / Azure), the
ellipsoid tileset loader, Draco / meshopt / KTX2 decoding, quantized-mesh
terrain, implicit tiling.

| release | for the add-on | upstream changes |
|---|---|---|
| v0.60.0 (2026-05) | — | `MAXAR_content_geojson` (Maxar vendor extension: GeoJSON files as tile content, with a properties schema), `BoundingRegionBuilder::expandToIncludeBoundingRegion`, GeoJSON overlay style fix. |
| v0.61.0 (2026-06) | vector overlays | `VectorTilesRasterOverlay` (a 3D Tiles vector tileset rasterised with a style and draped like imagery), overlays draw points, `3DTILES_content_conditional`, `EXT_mesh_primitive_edge_visibility`, MAXAR feature ids. Breaking: `GeoJsonDocumentRasterOverlay` moved to `CesiumVectorOverlays`. |
| v0.62.0 (2026-07) | **binding work** | Breaking: vcpkg baseline upgrade, image types moved to a new `CesiumImage` library, position / normal / accessor APIs changed (variant types, `normalized` argument). Adds accessor visitors (position, normal, quaternion, colour), primitive-mode retopologising, `KHR_billboard`, `KHR_mesh_quantization` texcoord types, GeoJSON properties as structural metadata. |
| v0.63.0 (2026-08) | — | `KHR_lights_punctual`, Bentley line / point style materials, GeoJSON point rasterising fix, MAXAR string offsets fix. |
| v0.64.0 (2026-09) | general culling volumes | `ViewState` accepts general culling volumes (not only a perspective frustum), intersection tests on `BoundingVolume`, area paging for fixed-LOD terrain regions. |
| v0.65.0 (2026-10) | robustness | Breaking: `ViewState` takes a delegate computing the tile screen-space error (replaces the fixed geometric-error setter). Fixes: Draco out-of-bounds read, PNTS section length check. `GS_3DT` iTwin reality data, styling provider for `VectorTilesRasterOverlay`. |
| v0.66.0 (2026-11) | security fix | Integer overflow / out-of-bounds write when decoding `EXT_meshopt_compression`; experimental glTF 2.1 and 3D Tiles 2.0; `CESIUM_DISABLE_SPZ` build option; `KHR_implicit_shapes` classes renamed. |

Reading: the meshopt fix is a reason to bump even without new features;
v0.62 is the release that makes the bump expensive (vcpkg baseline, image
and accessor API changes touch most of the binding); v0.64 / v0.65 are the
ones the add-on would use first.  Source:
[cesium-native CHANGES.md](https://github.com/CesiumGS/cesium-native/blob/main/CHANGES.md).

### After the bump: what to recheck in the add-on

The binding plans the bump in two steps, v0.61 then v0.66
([issue 8](https://github.com/calebbuffa/cesium-native-python/issues/8)). Once a wheel
with v0.66 exists, check which add-on workarounds cesium-native makes unnecessary,
and what it unblocks:

- **Workarounds to retest**, all in `tileset/asset_fixes.py`: `data:` URIs, subtree
  JSON without `byteLength`, and content-less tiles whose error is below their
  parent's (rendered as holes).
- **Unblocked**: tiles with several `contents` (load nothing on v0.59, so they give
  no metadata either), `VEC3` metadata table columns (raise in the binding today),
  a `GltfModifier` combined with raster overlays (cesium-native#1307), and 3D Tiles
  2.0 (`*.tileset.gltf`, see the handoff notes).
- **Binding API changes to absorb**: `CesiumImage` (v0.62), accessor and position
  APIs (v0.62), the screen-space-error delegate replacing the geometric-error
  setter (v0.65).

## Non-perspective cameras (orthographic, panoramic)

Orthographic views are exact already on v0.59: the binding has had an
orthographic `ViewState(position, direction, up, viewport, left, right,
bottom, top)` since its first commit. It culls with the four side planes and
uses error = geometric error × viewport height / frame height, independent of
distance. The add-on builds it for orthographic viewports and cameras since
0.6.1 (eye on the pivot, half extents from the projection matrix).

Panoramic cameras, two ways:

- **v0.59, what the add-on does:** `update_view_group` takes several view
  states and selects for their union, so a panoramic camera becomes six 90°
  perspective views of a cube at its position (`camera.panorama_faces`).
  Each face gets the panorama's angular resolution at its centre: an
  equirectangular image W px wide over 360° gives W / 4 px per face. Fisheye
  cameras drop the faces outside their field of view.
- **v0.65 / v0.66, an alternative:** `ViewState(boundingVolume,
  measureDelegate)` takes a culling volume and a function computing each
  tile's error. It is meant for selecting a geographic area, so it puts its
  position at the area's centre on the ground, not at an eye. A panorama can
  still use it: a sphere around the eye does the culling, and the error
  function computes the distance from the real eye itself (an equirectangular
  error is geometric error / distance × width / 2π). Loading priority then
  follows the wrong point, and a Python error function would run once per
  visited tile, so the binding would rather offer built-in ones in C++.

## Tiled formats cesium-native reads, and what needs a converter

cesium-native loads 3D Tiles 1.0 / 1.1 (`tileset.json`, implicit tiling,
b3dm, i3dm, pnts, cmpt, glTF / GLB with Draco, meshopt, KTX2, SPZ splats),
quantized-mesh terrain (`layer.json`), Cesium ion assets, iTwin content and
its procedural ellipsoid.  It does not read Potree, COPC / LAZ, I3S / SLPK,
Bentley 3MX, or splat streaming formats (stream-SOG, RAD, LCC, ...): those
go through a converter that serves them as 3D Tiles, ahead of time or on the
fly (a middleware such as 3dtiled).  In process, the Python binding allows
`TilesetContentLoader` subclasses (a loader written in Python that returns
glTF models per tile), so a COPC or Potree loader could live in the add-on,
bounded by Python decoding speed; the content-type registry
(`GltfConverters.register_magic` / `register_file_extension`) only maps to
the converters compiled into cesium-native.
