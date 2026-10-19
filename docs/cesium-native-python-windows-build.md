# Draft issues for CognitoBit/CesiumForBlender (not posted)

Repo has issues enabled (0 open). Two issues proposed: one bug with a patch, one feature list.

---

## Issue 1 (bug + patch): b3dm tiles with 8-byte padded container fail with "Bad GLB: file size doesn't match"

**Environment:** CesiumForBlender v0.1 (commit 1b9e357), Blender 5.1.1, Windows 11.

**Symptom:** For tilesets whose b3dm files are padded to 8 bytes (RealityCapture exports, e.g. our photogrammetry tilesets), every b3dm child tile fails in `_build` with

```
RuntimeError: Error: Bad GLB: file size doesn't match
```

The root tile usually loads (it is often a plain .glb or a .json), nothing refines no matter how low the SSE is set, and after 4 retries the node is marked dead. It looks like a wrong `geometricError` but is a content bug.

**Cause:** `tiles3d.unwrap_content` slices the GLB as `data[offset:]`. The b3dm `byteLength` is the padded container length, so 4 trailing bytes follow the GLB. Blender's glTF importer (io_scene_gltf2) rejects any GLB whose header `length` field differs from the file size. The unwrapped GLB is also written to the disk cache, so the broken file keeps being re-imported after the unwrapper is fixed.

**Fix (two hunks, attached as `b3dm-padding.patch`):**

1. `core/tiles3d.py` `unwrap_content`: after the `glTF` magic check, read the GLB header length and trim `glb = glb[:declared]` when `12 <= declared < len(glb)`.
2. `core/tiles3d_streamer.py` `_build`: before `import_scene.gltf`, read the 12-byte header of the cached file and `os.truncate(path, declared)` when the file is longer, so stale cache entries heal themselves.

Tested with three RealityCapture tilesets (one nested external `tileset_lod4_*.json` tree): after the patch they refine normally (45 tiles / 396k polys for the largest one).

---

## Issue 2 (feature requests): multiple tilesets, per-tileset collection + root empty, keep user selection, document decoder requirements

Coming from streaming photogrammetry 3D Tiles (RealityCapture b3dm, meshopt/KTX2 glb variants) and Google Photorealistic into Blender 5.1/5.3. The streamer works well; these are the things that got in the way of using it in a real scene.

1. **Several 3D Tiles sources at once.** `tiles3d_streamer.get()` is a singleton with one URL. We regularly want Google Photorealistic as context plus one or more high-resolution site tilesets on top (and terrain). A list of sources in the panel, each with its own URL/ion id, enable toggle, SSE and budget, sharing the ENU origin, would cover it.

2. **One sub-collection per tileset.** Everything currently lands flat in `Cesium 3D Tiles`. With several sources (and hundreds of tile objects) it becomes impossible to fold, hide, or exclude one dataset from a view layer. Suggest `Cesium 3D Tiles / <source name>` and the same for terrain.

3. **A root empty per tileset that can be transformed.** `_build` bakes the ENU matrix into each tile's `matrix_world`. Parenting all tile objects of a source to an empty (named after the source) would let users move, rotate or scale a whole tileset interactively (align a site scan to Google tiles, lift it a few metres, scale a mis-unit export) and have later-streamed tiles inherit the same transform. Even better if the panel offsets (or the empty's delta) are written back so the correction is remembered with the file.

4. **Do not change the user's selection and active object on tile import.** `bpy.ops.import_scene.gltf` calls `select_all(action='DESELECT')` and selects/activates the imported objects. Because imports happen every tick while streaming, whatever the user was editing is deselected a few times per second, which makes it hard to work in the scene while tiles stream. Wrapping the import with save/restore of `context.selected_objects` and `view_layer.objects.active` (and tile objects created with `select_set(False)`) fixes it. Same remark for undo: consider `bl_options` / `undo_push` handling so the undo stack isn't flooded by imports.

5. **Document decoder requirements per Blender version.** Since the plugin relies on the bundled glTF importer, content with `EXT_meshopt_compression` needs Blender 5.2+ and `KHR_texture_basisu` (KTX2) needs Blender 5.3+ (io_scene_gltf2 ≥ 5.3.x). On 5.1 such tiles fail with "Extension ... is not available on this addon version". A note in the README and a clearer error in the panel would save people a lot of debugging. (Verified: both meshopt test tilesets stream on the 5.3.0 beta.)

Happy to send the patch for issue 1 as a PR.

---

## PR for calebbuffa/cesium-native-python (Windows build fixes) — to prepare later

Repo head (2026-04-09) does not compile on Windows/MSVC; needed changes (all in `cnp/src`, uncommitted, `git diff` there):

1. `cmake/Dependencies.cmake`: build `extern/libzip` *after* `extern/cesium-native` (ezvcpkg installs zlib) and set `ZLIB_ROOT`/`ZLIB_USE_STATIC_LIBS` to the vcpkg `installed/x64-windows-static-md` prefix on WIN32.
2. `csrc/CesiumNative/GeometryBindings.cpp`: missing `});` closing the `UpsampledQuadtreeNode.__repr__` lambda; `UpsampledQuadtreeNode` has no default ctor → drop `py::init<>()`; `AvailabilitySubtree.buffers` `def_property` must not carry `py::arg` (pybind11 static_assert).
3. `csrc/CesiumNative/IonClientBindings.cpp`: `GeocoderFeature` has no default ctor (variant member) → drop `py::init<>()`.
4. `csrc/CesiumNative/Tiles3dSelectionBindings.cpp`: specialise `pybind11::detail::is_copy_constructible/is_copy_assignable<TileChildrenResult> = false` (holds `std::vector<Tile>`, Tile is move-only; MSVC instantiates the implicit copy ctor).
5. Build notes for the README: pybind11 < 3 (3.x rejects the property annotations), `-Dpybind11_DIR=<site-packages>/pybind11/share/cmake/pybind11` with `--no-build-isolation`, `EZVCPKG_BASEDIR`, Build Tools 2022 + Windows 11 SDK; first build ≈ 75 min (vcpkg) + 15 min.
6. API notes worth documenting: callers must call `cesium.tiles.content.register_all_tile_content_types()` (otherwise every tile is "unknown content"); glm matrices are returned column-major (`arr[col, row]`); `Ellipsoid.cartographic_to_cartesian` returns a `Cartographic` holding x,y,z.

Wheel produced: `cesium_python-0.1.0-cp313-cp313-win_amd64.whl` (Blender 5.1 ABI).
