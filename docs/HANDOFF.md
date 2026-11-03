# Handoff: blender_ogc3dtiles + cesium-native-python

State on 2026-11-01. For the next agent picking this up. It holds no tokens
or keys; the files that do are named below and stay out of git.

## 0. Ground rules (from Jonathan, still in force)

- **Credentials.** Bearer credentials:
  - Iconem share links (`https://api.iconem.com/s/<token>/...`).
  - Google Map Tiles keys. The studio key lives only in the private library
    below.

  Keep both out of commits, screenshots, PR text and issue text. The private
  files live in `%LOCALAPPDATA%\blender_ogc3dtiles\private\` (outside every
  repo): `tileset_urls.md` (everything recovered, with notes) and
  `tilesets_library.json` (the add-on's library format: every streamable link,
  each checked to answer, including Google with the key; set in the 5.3 beta's
  add-on preferences). Label share-link entries by asset id, never by token.
  Mask the URL field in any screenshot of a Google entry.
- **Repos.**
  - `jo-chemla/blender_ogc3dtiles` and `Iconem/blender_ogc3dtiles` are public since
    2026-11-02, so anything committed is published.
    **Push directly to `main` on both remotes (`origin`, `iconem`). No PRs for
    the add-on.**
  - Upstream binding: `calebbuffa/cesium-native-python`. Our fork is
    `jo-chemla/cesium-native-python`. Upstream work goes through PRs.
- **Before every add-on push**, run the CI lint and the tests:
  - `ruff check --select E9,F src/blender_ogc3dtiles tests scripts` (don't pipe
    it through `tail`, that hides the exit code).
  - `PYTHONPATH=src pytest`.
- **Testing.**
  - Test in GUI Blender sessions that stay open, not headless. Jonathan likes
    to fly around in them afterwards.
  - Show screenshots in the thread before committing them, as one assembled
    image.
  - Blender 5.3 beta: `C:\tools\BlenderLauncherWinget\custom\blender-5.3.0-beta+v53.3db45062d058-windows.amd64-release\blender.exe`.
  - Extension id: `bl_ext.user_default.ogc_3dtiles_streaming`.
  - Build: `blender -b --command extension build --source-dir src/blender_ogc3dtiles --output-dir dist`
    (create `dist/` first).
  - Install: `blender -b --command extension install-file -r user_default -e dist/ogc_3dtiles_streaming-0.3.0.zip`.
  - Driving a GUI session from a shell: start Blender with a small script that
    polls a `cmd.py` file on a timer, `exec`s it and writes the output next to
    it; screenshots via `bpy.ops.screen.screenshot_area` under
    `context.temp_override`.
- **Anything posted publicly needs his OK.** Draft, show, then post.

## 1. Upstream: calebbuffa/cesium-native-python

| PR / issue | content | state |
|---|---|---|
| [#2 issue](https://github.com/calebbuffa/cesium-native-python/issues/2) | Meta issue: A1-A3 (build), B1-B4 (partial workarounds), C1-C12 (full workarounds). | Open. Caleb (2026-10-21) takes all of it and welcomes PRs. Our status reply (2026-10-22) and the v0.65 bump / orthographic note (posted by Jonathan, late October) have no answer yet. |
| [#3](https://github.com/calebbuffa/cesium-native-python/pull/3) | A1 + A2: `pip install .` on Windows, Linux, macOS. | Merged (`521956e`). |
| [#4](https://github.com/calebbuffa/cesium-native-python/pull/4) | A3: cibuildwheel 3 OSes × CPython 3.11-3.13, Release + PyPI trusted-publishing jobs. | Open, waiting for Caleb (he must set up PyPI publishing). Branch `ci/wheels` (`1ffdf92`). |
| [#7](https://github.com/calebbuffa/cesium-native-python/pull/7) | One cast so Python subclasses of `GltfModifier` can override `apply`. Branch `fix/gltf-modifier-subclass`, on `main`. | Open, waiting for Caleb. |
| [#5](https://github.com/calebbuffa/cesium-native-python/pull/5) | C1, C2, C3, C4+C7 (docs), C8, C9. Stacked on #4. | Open, waiting for Caleb. Branch `bindings/c-items` (`775d220`). After #4 merges, rebase if needed, `--force-with-lease` to the fork. |

- Waiting on Caleb: C6, C10, C11 (API shape, or need cesium-native changes),
  C12 (his), and his pick on the GIL (B3).
- Jonathan decided not to answer GeorgeS2019's metadata question on #5 (out
  of context).
- The fork's release `v0.1.0-wheels.1` holds wheels from #3 + #4 only. The
  add-on keeps its own workarounds so it runs on either build. The add-on's
  preferences have an "Install wheel from GitHub Release" button.
- Local cnp worktrees, venvs and wheels were in a scratch folder that has
  since been deleted; the branches are safe on the fork. The vcpkg tree is in
  `C:\Users\jonathan\.ezvcpkg` (a cold build takes ~75 min; needs VS 2022
  Build Tools and pybind11 < 3).

### Next upstream PRs, in order of effort

1. **`ViewState.from_matrices(view, projection, viewport)` (C5).** Binding
   only. Replaces the add-on's hand-written camera code (`camera/`).
   Perspective only on v0.59; raise on orthographic for now.
2. **`CachingAssetAccessor(..., max_items=...)`.** cesium-native's
   `SqliteCache` defaults to 4096 items, which a Google session fills fast;
   the binding doesn't expose the argument. Small, can ride with 1. The add-on
   trims the cache by size itself (`cachectl.py`).
3. **B3, the GIL.** `prepareInLoadThread` holds the GIL for the whole Python
   callback, where the add-on does all numpy mesh extraction, so cesium
   worker threads take turns. Proposal: a C++ "batch extract" returning
   per-primitive numpy arrays with the GIL released. Wait for Caleb's pick,
   measure before / after (load-thread ms per tile, tiles/s on Google Rome).
4. **Submodule bump v0.59 → v0.65** as its own PR, with exact orthographic
   views on top (v0.64 culling volumes + v0.65 SSE delegate), and
   `VectorTilesRasterOverlay` (v0.61). v0.62 is the expensive step (vcpkg
   baseline, `CesiumImage`, accessor APIs). Full table in the README section
   "cesium-native: versions and upgrade notes".
5. **B4, SQLite across processes**: needs a cesium-native change
   (`sqlite3_busy_timeout`); the add-on's lock file covers it. Low priority.

## 2. The add-on

### Done since 2026-10-23 (all on main)

- `66fb396`: clipping polygons, local / NAS tilesets (Browse button, mapped
  drives → UNC `file:////server/share/...` URLs), tileset libraries (JSON
  files listed in the preferences, e.g. on the NAS), cache folder + size cap,
  copy tileset into the project (cropped to an object, to a geometric error),
  b3dm `RTC_CENTER` fix.
- Clipping rework: four modes (cut / keep × inside any / all), clip-polygon or box
  per object, meshes via the material chain, points and splats via a Geometry
  Nodes delete. Fixed: overlays sharing a projection share one texture
  coordinate set in cesium-native, so clip nodes are keyed by overlay uid.
- Copy into project: Google, Cesium ion and implicit tilesets (converted to
  explicit) are no longer refused. A Google crop was copied for real with the
  studio key, the key ended up nowhere on disk, and the copy streams.
- Clipping, second pass (`docs/clipping.md`): mode switches touch no material
  (two view-layer attributes), masks always per polygon, optional Cut Geometry.
- Imagery overlays keyed by uid and mixed in list order: layers sharing a
  projection coexist.
- 3D Tiles of splats stream and clip, SPZ
  (`KHR_gaussian_splatting_compression_spz_2`) and uncompressed (normalised
  integer accessors read from the buffer; SH degree 0 is not a higher band).
  `EXT_splat_opacity` is ignored.
- Blender 5.3 moved Geometry Nodes modifier inputs to
  `mod.properties.inputs.<id>.value`: point clouds had lost their material and
  radius on 5.3.

### Known limitations and open threads

- **Feature metadata** (`tileset/feature_meta.py`, Metadata panel) is checked in a GUI
  session on 5.3 only, with swissBUILDINGS3D. Point clouds, raster overlays on top,
  and reopening a saved .blend are untested. `VEC3` table columns raise in the binding.
- **Voxels:** prototype only, see `docs/voxels.md`. `data:` URIs in subtree JSON fail on
  v0.59, which blocks GeoTOP without a local copy of its subtree.

- **`GltfModifier` from Python fails** ("Tried to call pure virtual function
  GltfModifier.apply", tiles don't load) until #7 merges. Jonathan wants the clip
  modifier in cesium-native C++ and bound, not done in Python.
  Requested upstream: cesium-native#1486.
- **`is_job_running("SHADER_COMPILATION")`** stayed true for minutes on large
  scenes while the viewport was already correct. Don't use it to wait.
- **Local splats loaded no tiles on 2026-11-02**, with clipping off too (Vestibule
  7.5M and Interior mesh2splat 200M, view pivot at the origin, 60 m): see below, so
  clipping them is unchecked. A local mesh tileset loads and clips.
- **Non-georeferenced tilesets** (3dtiled splat output, root near ECEF 0)
  only land at the scene origin when the origin is Auto. Seen on 2026-11-01
  with the San Pietro splats: with the view pivot at (5, -10, 0) and a 95 m
  view distance, cesium selected 0 tiles; at (0, 0, 0) and 60 m, 26. The
  local-placement camera conversion is the likely culprit; not investigated.
- **Orthographic viewports** use a far, narrow perspective emulation, exact
  only on the pivot plane, until the v0.65 bump.
- **Panoramic cameras**: not supported; a six-view cube-map union would work.
- `file:` reads (local / NAS tilesets) never enter the sqlite HTTP cache.

### Ideas (ask Jonathan before big ones)

- Which camera drives tile selection (picker) — Jonathan: "could be good".
- Origin shifting / one origin per sub-level (zoom out to the globe and back)
  — later.
- Install wheels from PyPI or bundle them once #4 ships; drop the workarounds
  #5 makes redundant (keep a version check).
- COPC / Potree loader as a Python content loader.

### Coming in cesium-native: 3D Tiles 2.0

Read on 2026-11-02, nothing merged. v0.66 only reads and writes the glTF 2.1 and
3D Tiles 2.0 classes. Streaming is cesium-native#1453, as a stack of PRs:
#1464 → #1467 → #1473 → #1477 → #1478 (loader, draft). #1465 tracks external assets.

- The add-on should need little: `Tileset` will take `*.tileset.gltf`.
- The binding pays: libraries renamed (`Cesium3DTiles*` → `CesiumTilesetJson*`,
  `Cesium3DTilesContent` split), `BoundingVolume` and `TileRefine` moved,
  `registerAllTileContentTypes` → `registerAllConverterTypes`. Bump to v0.66 first.

## 3. Public posts

- [cesium-native#1486](https://github.com/CesiumGS/cesium-native/issues/1486), geometry
  clipping: posted by Jonathan on 2026-11-02.
- Cesium community thread 47479 (Blender architectural models + Google 3D
  Tiles): reply posted by Jonathan on 2026-11-02, [post 5](https://community.cesium.com/t/integrating-blender-architectural-models-with-google-photorealistic-3d-tiles-in-unreal-engine/47479/5).
- calebbuffa/cesium-native-python#2: heads-up about the public add-on posted by
  Jonathan on 2026-11-02. Wait for Caleb before opening more binding PRs.