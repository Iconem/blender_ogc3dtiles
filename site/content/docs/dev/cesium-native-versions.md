---
title: "cesium-native versions"
description: "Versions and upgrade notes"
---

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
| latest cesium-native release at the time of writing (2026-10-23) | v0.65.0 | 2026-10-01 |

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
| v0.64.0 (2026-09) | **orthographic views** | `ViewState` accepts general culling volumes (not only a perspective frustum), intersection tests on `BoundingVolume`, area paging for fixed-LOD terrain regions. |
| v0.65.0 (2026-10) | **orthographic views**, robustness | Breaking: `ViewState` takes a delegate computing the tile screen-space error (replaces the fixed geometric-error setter). Fixes: Draco out-of-bounds read, PNTS section length check. `GS_3DT` iTwin reality data, styling provider for `VectorTilesRasterOverlay`. |
| v0.66.0 (2026-11) | security fix | Integer overflow / out-of-bounds write when decoding `EXT_meshopt_compression`; experimental glTF 2.1 and 3D Tiles 2.0; `CESIUM_DISABLE_SPZ` build option; `KHR_implicit_shapes` classes renamed. |

Reading: the meshopt fix is a reason to bump even without new features;
v0.62 is the release that makes the bump expensive (vcpkg baseline, image
and accessor API changes touch most of the binding); v0.64 / v0.65 are the
ones the add-on would use first.  Source:
[cesium-native CHANGES.md](https://github.com/CesiumGS/cesium-native/blob/main/CHANGES.md).

## Non-perspective cameras (orthographic, panoramic)

cesium-native v0.59 selects tiles for perspective views only: a frustum for
culling and the perspective screen-space error formula.  The add-on emulates
an orthographic viewport with a far, narrow perspective eye.  With v0.64's
culling volumes and v0.65's screen-space-error delegate, a renderer defines
both itself, so a real orthographic view becomes possible (an oriented box
for culling, error = geometric error / ortho scale × pixels).  The same
applies to Blender's panoramic cameras: an equirectangular camera sees all
directions (cull nothing but distance) and has a constant angular
resolution, so its error is geometric error / distance × width / 2π; a
cylindrical camera mixes the two.  Until then, a panorama can already be
approximated with today's API, since `update_view_group` accepts several
view states: six 90° perspective views of a cube map, whose union is the
selection.

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
