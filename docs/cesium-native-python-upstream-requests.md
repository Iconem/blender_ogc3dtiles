# Upstream requests for calebbuffa/cesium-native-python

Collected while building the Blender backend (`tileset/native_backend.py`,
`tileset/native_mesh.py`). Ordered by how much each one would simplify a
renderer integration. Items 1–4 are already patched locally
(`third_party/cesium-native-python-windows.patch`).

## Bugs / build

1. **Windows / MSVC does not compile** — `GeometryBindings.cpp` missing `});`,
   `UpsampledQuadtreeNode` and `GeocoderFeature` bound with `py::init<>()`
   although they have no default constructor, `def_property` given a
   `py::arg`, `TileChildrenResult` needs
   `pybind11::detail::is_copy_constructible` specialised to false
   (pybind11 2.13; pybind11 3 changes the rules again).
2. **Dependencies.cmake**: libzip must come after cesium-native and needs
   `ZLIB_ROOT`, otherwise vcpkg's zlib is not found on Windows.
3. **No wheels / no release**: a cibuildwheel workflow (Linux, macOS,
   Windows × CPython 3.11–3.13) would remove the 75-minute vcpkg bootstrap
   for every user. Blender ships its own CPython (3.11 in 4.x, 3.13 in 5.x),
   so abi3 or per-version wheels both work; we build 3.13 win_amd64 in
   `.github/workflows/cesium-native-wheel.yml`.
4. **b3dm payload padding**: tiles whose GLB chunk is followed by container
   padding fail to parse (`GltfReader` reads the declared length but the
   b3dm converter passes the padded buffer). Trim to the GLB header length.

## API gaps (renderer integration)

5. `register_all_tile_content_types()` has to be called by hand or every
   tile is "unknown content". Call it in the module initialiser (or document
   it in the README's first example).
6. `for_each_primitive_in_scene` cannot hand the `glm::dmat4` node
   transform to a Python callback (it arrives as an opaque object). Expose it
   as a numpy array, or add `Model.primitives_with_transforms()` returning
   `[(node_index, mesh_index, primitive_index, 4×4 ndarray)]`. We re-implement
   the traversal in Python (`native_mesh._iter_primitives`).
7. **Matrix convention**: glm matrices come out column-major
   (`arr[col, row]`). Either transpose on the way out or state it in every
   docstring; `Tile.transform`, the preparer's `transform` argument and
   `ViewState` all differ in what callers expect.
8. **Properties vs methods**: `BoundingVolume.center`, `Request.url`,
   `Response.data` are properties while sibling accessors are methods;
   consistency (or `__getattr__` aliases) would avoid `'str' object is not
   callable` surprises.
9. `IPrepareRendererResources.prepare_in_load_thread` runs on the worker
   pool without any statement about the GIL. Document that the callback holds
   the GIL (it does, via pybind11) and that heavy numpy work there blocks the
   other workers; offer a `release_gil` option or a batch API that returns
   positions / indices / UVs / images for a whole model in one call (that is
   what `native_mesh.extract_mesh_payload` does in ~8 ms of Python).
10. `TileLoadResult` lacks the tile's `geometric_error` and bounding volume
    (useful for point-cloud display radius); only `Tile` has them, and the
    load-thread callback does not receive the `Tile`.
11. **Ktx2TranscodeTargets**: with no GPU targets set, KTX2 is transcoded to
    RGBA8 — good — but `ImageAsset.save_png` is the only way out; a
    `pixel_data` numpy view would avoid the PNG round trip.
12. `GltfWriter.write_glb` requires `collapse_to_single_buffer` first or the
    GLB references missing buffers; either call it internally or raise a
    clear error.
13. **SqliteCache locking**: two processes on the same cache file log
    `database is locked` every request. Open with `busy_timeout` or WAL, or
    expose the option.
14. `CachingAssetAccessor(inner, path)` has no way to set `maximum_items` /
    `request_options`; `TilesetOptions.request_headers` is a list of tuples
    while curl options take a dict — unify.
15. `Tileset.options` is a live reference (good, we rely on it for live SSE)
    but `TilesetOptions` fields set after construction are not all honoured
    (`maximum_simultaneous_tile_loads`, `main_thread_loading_time_limit`
    are read once by the loader). Document which ones are live.
16. `ViewState` from a 4×4 view matrix + projection (or from
    `position, direction, up, viewport, hfov, vfov` as now) — a helper
    `ViewState.from_matrices(view, proj, viewport)` would remove the most
    error-prone piece of every integration (we derive hfov/vfov from the
    Blender `window_matrix`).
17. Raster overlays: `attach_raster_in_main_thread` passes `TextureCoordinate`
    transforms only through the C++ struct; expose them as numpy so overlay
    draping can be wired to a UV layer in Blender.
18. A tiny `IPrepareRendererResources` reference implementation in Python
    (just storing the model) in `examples/` would have saved a day.
19. **Orthographic cameras.** `ViewState` only takes `(position, direction,
    up, viewport, hfov, vfov)`, i.e. a perspective frustum, so an orthographic
    viewport (Blender's numpad 5, CAD-style top views, plan renders) has no
    honest representation. Feeding it a narrow camera at the pivot gives a
    thin cone and an inflated screen-space error: in our bench tileset the
    same orthographic view rendered 35 tiles with 121 culled, versus 73
    rendered / 32 culled once emulated properly. The emulation we ship
    (`camera.get_view_state`, `ViewState.native_position`) places a 1-degree
    camera `(frame_height / 2) / tan(0.5 deg)` metres behind the pivot so its
    frame at the pivot equals the orthographic frame, and disables fog
    culling because that distant eye sits far above the fog table. It is
    only exact on the pivot plane: nearer tiles are slightly over-refined,
    farther ones under-refined, and the frustum is a sliver of a cone instead
    of a box. Requests, in order of preference:
    - `ViewState.create_orthographic(position, direction, up, viewport,
      frame_width, frame_height)` with SSE = `geometric_error * viewport_h /
      frame_height` (no distance term) and a box frustum. cesium-native's
      `ViewState` is perspective-only today (`CullingVolume` from
      `hfov`/`vfov`), so this needs a small upstream change there too; the
      `CullingVolume` already works on planes, only the SSE formula and the
      plane construction differ.
    - Failing that, `ViewState.from_matrices(view, projection, viewport)`
      (item 16) and let the culling volume come from the clip matrix via
      Gribb-Hartmann, so orthographic and off-axis projections fall out for
      free; `computeScreenSpaceError` can test `projection[3][3] == 1`.
    - At minimum, document that `ViewState` is perspective-only and that fog
      culling is on by default (height-based, it silently culls distant eyes).
20. **Typed accessor views are float-only.** `AccessorViewVec3` /
    `AccessorViewVec4` (and `get_*_accessor_view` helpers) return `float`
    data; `COLOR_0` stored as normalised `UNSIGNED_BYTE` / `UNSIGNED_SHORT`
    (the usual case for `pnts`-converted glb and 3D Tiles 1.1 point octrees)
    comes out as garbage or zeros. Either honour `normalized` + component
    type inside the view, or expose the raw `bufferView` slice with stride /
    component type so callers can decode with numpy (what
    `native_mesh._raw_accessor` does).
