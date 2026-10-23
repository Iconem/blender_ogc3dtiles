# cesium-native versions: what the Python binding ships vs upstream

The native backend runs on [cesium-native-python](https://github.com/calebbuffa/cesium-native-python),
which vendors cesium-native as a git submodule. This note tracks what changed
upstream since the vendored version, to know what a submodule bump would bring
to the add-on (and what it would cost the binding).

| | version | date |
|---|---|---|
| vendored by cesium-native-python (submodule `extern/cesium-native`) | v0.59.0 | 2026-03-31 |
| latest cesium-native release at the time of writing (2026-10-23) | v0.65.0 | 2026-10-01 |

Already in v0.59.0 and used by the add-on: `KHR_gaussian_splatting` with SPZ
decoding (v0.56.0, release-candidate classes in v0.58.0), raster overlays
(TMS / WMTS / WMS / URL template / ion / Bing / Google / Azure), the
ellipsoid tileset loader, Draco / meshopt / KTX2 decoding.

## Upstream changes since v0.59.0

| release | for the add-on | details |
|---|---|---|
| v0.60.0 (2026-05) | — | `MAXAR_content_geojson` (GeoJSON content in 3D Tiles, Maxar vendor extension), `BoundingRegionBuilder::expandToIncludeBoundingRegion`, GeoJSON overlay style fix. |
| v0.61.0 (2026-06) | vector overlays | `VectorTilesRasterOverlay` (a 3D Tiles vector tileset rasterised with a style, draped like imagery), overlays can draw points, `3DTILES_content_conditional`, `EXT_mesh_primitive_edge_visibility`, MAXAR feature ids. Breaking: `GeoJsonDocumentRasterOverlay` moved to `CesiumVectorOverlays`. |
| v0.62.0 (2026-07) | **binding work** | Breaking: vcpkg baseline upgrade, image types moved to a new `CesiumImage` library, position / normal / accessor APIs changed (variant types, `normalized` argument). Adds accessor visitors (position, normal, quaternion, colour), primitive-mode retopologising, `KHR_billboard`, `KHR_mesh_quantization` texcoord types, GeoJSON properties as structural metadata. |
| v0.63.0 (2026-08) | — | `KHR_lights_punctual`, Bentley line / point style materials, GeoJSON point rasterising fix, MAXAR string offsets fix. |
| v0.64.0 (2026-09) | **orthographic views** | `ViewState` accepts general culling volumes (not only a perspective frustum), intersection tests on `BoundingVolume`, "area paging" for fixed-LOD terrain regions. |
| v0.65.0 (2026-10) | **orthographic views**, robustness | Breaking: `ViewState` takes a delegate for the tile screen-space error (replaces the fixed geometric-error setter), which lets a renderer define LOD for an orthographic camera. Fixes: Draco out-of-bounds read, PNTS section length check. `GS_3DT` iTwin reality data, styling provider for `VectorTilesRasterOverlay`. |
| unreleased | security fix | Integer overflow / out-of-bounds write when decoding `EXT_meshopt_compression`; experimental glTF 2.1 and 3D Tiles 2.0; `CESIUM_DISABLE_SPZ` build option; `KHR_implicit_shapes` classes renamed. |

Reading: the add-on's orthographic emulation (a far perspective eye) could be
replaced by a real orthographic `ViewState` once the binding is on v0.65+;
the meshopt fix is a reason to bump even without new features; v0.62 is the
release that makes the bump expensive (vcpkg baseline, image and accessor
API changes touch most of the binding).

Source: [cesium-native CHANGES.md](https://github.com/CesiumGS/cesium-native/blob/main/CHANGES.md).
