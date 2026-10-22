# cesium-native-python: feedback from a Blender integration

Draft for calebbuffa/cesium-native-python, written while building the
Blender backend (`tileset/native_backend.py`, `tileset/native_mesh.py`,
`camera/__init__.py`). Each item: symptom, what we do about it, the ask.

## A. Blocks Windows users, fix ready (PR material)

Patch: `third_party/cesium-native-python-windows.patch` (109 lines, 4 files).

| # | Symptom | Ask |
|---|---------|-----|
| A1 | Head does not compile with MSVC: `GeometryBindings.cpp` is missing a `});`; `UpsampledQuadtreeNode` and `GeocoderFeature` are bound with `py::init<>()` but have no default constructor; a `def_property` carries a `py::arg`; `TileChildrenResult` needs `pybind11::detail::is_copy_constructible` specialised to `false` (it holds move-only `Tile`s). | Merge the patch. Note pybind11 2.13 vs 3.x differ on the property annotations. |
| A2 | `Dependencies.cmake`: libzip is configured before cesium-native, so vcpkg's zlib is not found on Windows. | Order libzip after cesium-native, set `ZLIB_ROOT` to the vcpkg prefix on WIN32. |
| A3 | No wheels, no release: every user pays the 75-minute vcpkg bootstrap. | cibuildwheel for Linux, macOS, Windows on CPython 3.11 to 3.13 (Blender 4.x ships 3.11, 5.x ships 3.13). Our workflow: `.github/workflows/cesium-native-wheel.yml`. |

## B. Cannot be worked around from Python

| # | Symptom | What we do | Ask |
|---|---------|------------|-----|
| B1 | **Orthographic cameras.** `ViewState` takes `(position, direction, up, viewport, hfov, vfov)` only. An orthographic viewport fed a narrow camera at the pivot gets a thin frustum cone and an inflated SSE: bench tileset, same view, 35 tiles rendered / 121 culled. | Emulate: a 1-degree camera placed `(frame_height / 2) / tan(0.5 deg)` behind the pivot so its frame at the pivot equals the orthographic frame (73 rendered / 32 culled), fog culling off. Exact only on the pivot plane; the frustum stays a sliver, not a box. | `ViewState.create_orthographic(position, direction, up, viewport, frame_width, frame_height)`: SSE = `ge * viewport_h / frame_height`, box culling volume. cesium-native's `ViewState` is perspective-only, so this is a small upstream change too; `CullingVolume` already works on planes. Alternative: `ViewState.from_matrices(view, projection, viewport)` with Gribb-Hartmann planes, which covers orthographic and off-axis for free. |
| B2 | **GIL in the load-thread callback.** `prepare_in_load_thread` runs on the worker pool holding the GIL (pybind11 default), so numpy work there serialises every worker. | Keep that callback minimal and do the mesh extraction on the main thread (about 8 ms per tile). | Document the GIL behaviour; offer `release_gil` or a batch API returning positions, indices, UVs and images for a whole `Model` in one call. |
| B3 | **SqliteCache across processes.** Two processes on one cache file log `database is locked` on every request. | A lock file next to the db, else a pid-suffixed db per process. | Open with `busy_timeout` or WAL, or expose the option. |

## C. Worked around; an upstream fix would let us delete code

Ordered by impact, most first.

| # | Symptom | Workaround | Ask |
|---|---------|------------|-----|
| C1 | Every tile is "unknown content" until `register_all_tile_content_types()` is called. | We call it. | Call it in the module initialiser, or put it in the README's first example. |
| C2 | Typed accessor views are float-only: normalised `UNSIGNED_BYTE` / `UNSIGNED_SHORT` `COLOR_0` (pnts-converted glb, 3D Tiles 1.1 point octrees) decodes wrong. | Decode from the raw `bufferView` bytes with numpy (`native_mesh._raw_accessor`). | Honour `normalized` + component type in the view, or expose the raw slice with stride and component type. |
| C3 | `for_each_primitive_in_scene` cannot pass the `glm::dmat4` node transform to Python (opaque object). | Scene-graph traversal reimplemented in Python (`native_mesh._iter_primitives`). | Expose it as a 4x4 ndarray, or `Model.primitives_with_transforms()`. |
| C4 | glm matrices come out column-major (`arr[col, row]`); `Tile.transform`, the preparer argument and `ViewState` expect different conventions. | Transpose on our side. | Transpose on the way out, or state the convention in every docstring. |
| C5 | hfov / vfov must be derived from the projection matrix by every caller. | Done in `camera.get_view_state`. | `ViewState.from_matrices(view, projection, viewport)` (also covers B1). |
| C6 | `TileLoadResult` lacks `geometric_error` and the bounding volume; the load-thread callback never sees the `Tile`. | Point display radius estimated from point spacing instead. | Add both to `TileLoadResult`. |
| C7 | `Tileset.options` is live, but some fields set after construction are read once (`maximum_simultaneous_tile_loads`, `main_thread_loading_time_limit`). | Set them before the first `update_view_group`. | Document which fields are live. |
| C8 | KTX2 transcodes to RGBA8, but `ImageAsset.save_png` is the only way out. | PNG round trip per texture. | A `pixel_data` numpy view. |
| C9 | `GltfWriter.write_glb` without `collapse_to_single_buffer` first references missing buffers. | We call it first. | Do it internally or raise a clear error. |
| C10 | `CachingAssetAccessor(inner, path)` cannot set `maximum_items` / `request_options`; `TilesetOptions.request_headers` is a list of tuples while curl options take a dict. | Live with the defaults. | Expose the options; unify the header format. |
| C11 | `BoundingVolume.center`, `Request.url`, `Response.data` are properties, sibling accessors are methods. | `callable()` checks. | Consistency, or `__getattr__` aliases. |
| C12 | No minimal `IPrepareRendererResources` example. | Wrote our own. | A tiny Python implementation in `examples/` that just stores the model. |


> Retracted 2026-10-22: the b3dm container-padding item. cesium-native's
> `B3dmToGltfConverter` passes the span up to the b3dm `byteLength` and
> `GltfReader::readBinaryGltf` slices to the GLB header length, so padded
> tiles load fine. The failure was Blender's glTF importer rejecting GLBs
> with trailing bytes on the pure-Python path (fixed there by trimming).
