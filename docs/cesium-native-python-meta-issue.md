# Meta issue draft: feedback from a Blender renderer integration

Paste as one GitHub issue on calebbuffa/cesium-native-python. Each line can
be split into its own issue if wanted; the long form with symptoms,
workarounds and asks is `cesium-native-python-upstream-requests.md`.

---

**Title:** Feedback from a Blender integration: Windows build, API gaps, orthographic cameras

Hi, we built a Blender 5.x extension that streams OGC 3D Tiles through
cesium-native-python (tile selection, loading and KTX2 decoding in
cesium-native, meshes rebuilt in Blender from numpy). It works well; the
Cesium Ion, Google and photogrammetry tilesets we tried all stream. Along
the way we collected the points below. This is one thread so you can decide
what deserves its own issue; happy to open any of them separately, and to
send the Windows PR right away.

### A. Windows build (PR ready, 109 lines in 4 files)

- [ ] **A1** Head does not compile with MSVC: a missing `});` in `GeometryBindings.cpp`, `py::init<>()` on `UpsampledQuadtreeNode` and `GeocoderFeature` which have no default constructor, a `def_property` with a `py::arg`, and `TileChildrenResult` needing `is_copy_constructible` specialised to `false`.
- [ ] **A2** `Dependencies.cmake`: libzip must come after cesium-native and needs `ZLIB_ROOT` on Windows, otherwise vcpkg's zlib is not found.
- [ ] **A3** Wheels: a cibuildwheel matrix (Linux, macOS, Windows; CPython 3.11 to 3.13, which is what Blender 4.x and 5.x embed) would remove the 75-minute vcpkg bootstrap for every user. We have a working Windows workflow to contribute.

### B. Cannot be worked around from Python

- [ ] **B1 Orthographic cameras.** `ViewState` is perspective-only (`hfov`, `vfov`). An orthographic viewport fed a narrow camera at the pivot yields a thin frustum cone and an inflated SSE (bench tileset: 35 tiles rendered, 121 culled). We emulate with a 1 degree camera placed `(frame_height / 2) / tan(0.5 deg)` behind the pivot (73 rendered, 32 culled) and fog culling off, but it is exact only on the pivot plane. Ask: `ViewState.create_orthographic(...)` with SSE = `ge * viewport_h / frame_height` and a box culling volume, or `ViewState.from_matrices(view, projection, viewport)` with planes from the clip matrix. cesium-native's own `ViewState` needs a small change for the first.
- [ ] **B2 GIL in `prepare_in_load_thread`.** The callback holds the GIL, so numpy work there serialises the worker pool. Document it, and offer `release_gil` or a batch call returning positions, indices, UVs and images for a whole `Model`.
- [ ] **B3 SqliteCache across processes** logs `database is locked` per request. `busy_timeout` or WAL, or expose the option.

### C. Worked around, an upstream fix would let integrators delete code (most impact first)

- [ ] **C1** `register_all_tile_content_types()` must be called by hand or every tile is "unknown content". Call it in the module initialiser or show it in the first README example.
- [ ] **C2** Typed accessor views are float-only; normalised `UNSIGNED_BYTE` / `UNSIGNED_SHORT` `COLOR_0` decodes wrong. Honour `normalized` and the component type, or expose the raw `bufferView` slice with stride and type.
- [ ] **C3** `for_each_primitive_in_scene` cannot pass the `glm::dmat4` node transform to Python. Expose it as a 4x4 ndarray, or add `Model.primitives_with_transforms()`.
- [ ] **C4** glm matrices arrive column-major (`arr[col, row]`) and `Tile.transform`, the preparer argument and `ViewState` disagree on convention. Transpose on the way out or document it everywhere.
- [ ] **C5** `ViewState.from_matrices(view, projection, viewport)` so callers stop deriving hfov / vfov by hand (also covers B1).
- [ ] **C6** `TileLoadResult` lacks `geometric_error` and the bounding volume; the load-thread callback never sees the `Tile`.
- [ ] **C7** Document which `TilesetOptions` fields are live after construction (`maximum_simultaneous_tile_loads` and `main_thread_loading_time_limit` are read once).
- [ ] **C8** KTX2 is transcoded to RGBA8 but only `ImageAsset.save_png` gets it out; a `pixel_data` numpy view would avoid the PNG round trip.
- [ ] **C9** `GltfWriter.write_glb` without `collapse_to_single_buffer` references missing buffers; do it internally or raise.
- [ ] **C10** `CachingAssetAccessor` cannot set `maximum_items` / `request_options`; `request_headers` is a list of tuples while curl options take a dict.
- [ ] **C11** `BoundingVolume.center`, `Request.url`, `Response.data` are properties while sibling accessors are methods.
- [ ] **C12** A minimal Python `IPrepareRendererResources` in `examples/` that just stores the model.

Thanks for the binding, it made a cesium-native renderer in Python feasible
in a few days rather than a port.
