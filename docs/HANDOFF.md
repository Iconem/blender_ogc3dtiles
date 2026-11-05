# Handoff: blender_ogc3dtiles + cesium-native-python

State on 2026-11-04, at `bc872f7` plus this note. For the next agent picking
this up. It holds no tokens or keys; the files that do are named below and stay
out of git.

**Where things stand:** nothing is in progress. Everything is on `main` on both
remotes. `main` is ahead of the last release, v0.5.0, by quantized-mesh terrain
entries and point intensity. Section 4 lists what to do next.

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
  - Test on Blender 5.3 only, unless he asks or the change is version-specific.
  - Open Blender windows may be closed and reopened with the latest add-on, but
    one may be his live session: check before closing it, and test in a separate
    window when he is working in one.
  - Show screenshots in the thread before committing them, as one assembled
    image.
  - Blender 5.3 beta: `C:\tools\BlenderLauncherWinget\custom\blender-5.3.0-beta+v53.3db45062d058-windows.amd64-release\blender.exe`.
  - Extension id: `bl_ext.user_default.ogc_3dtiles_streaming`.
  - Build: `blender -b --command extension build --source-dir src/blender_ogc3dtiles --output-dir dist`
    (create `dist/` first).
  - Install: `blender -b --command extension install-file -r user_default -e dist/ogc_3dtiles_streaming-0.5.1.zip`.
  - Driving a GUI session from a shell: start Blender with a small script that
    polls a `cmd.py` file on a timer, `exec`s it and writes the output next to
    it; screenshots via `bpy.ops.screen.screenshot_area` under
    `context.temp_override`.
- **Anything posted publicly needs his OK.** Draft, show, then post. Posting
  means the `jo-chemla` account through `gh`. PRs to other projects stay in his
  name, with no Claude mention unless he asks for one. `gh` can't upload images
  to an issue, so he pastes those himself. Don't host them elsewhere (a gist was
  declined).
- **Releases** go on both `jo-chemla` and `Iconem`. Iconem's workflows now run on
  push: `bc872f7` started one. A tag trigger is untested there since he enabled
  them, so check that the first tag releases on both.

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
- On 2026-11-04, #4, #5 and #7 have only a bot's review and no answer from Caleb.
  Check again before starting binding work.
- A local binding checkout with its build is in `C:\tmp\cnp` (1.4 GB, on
  `fix/gltf-modifier-subclass`), with a venv in `C:\tmp\cnpvenv` and a cp313 wheel
  in `C:\tmp\cnpwheel`. The vcpkg tree is in `C:\Users\jonathan\.ezvcpkg` (a cold
  build takes ~75 min; needs VS 2022 Build Tools and pybind11 < 3).

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
  (two view-layer attributes), masks always per polygon, optional geometry cut (*Slower: Also cut in solid view/exports*).
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
  session on 5.3 only: swissBUILDINGS3D, with an OSM overlay, and Cesium's point cloud
  samples. Texture metadata is checked on Cesium's three samples, 8-bit channels and UV
  set 0 only. Reopening a saved .blend is untested. `VEC3` table columns raise in the
  binding, and `contents` (several per tile) loads nothing on v0.59, so tiles of that
  kind give no metadata either.
- **Voxels** (`tileset/voxels.py`, see `docs/voxels.md`) are also checked on 5.3 only.
  Volumes are written on the main thread and aren't clipped. Blocks take no raster
  overlays: they have no overlay coordinates. Cylinder tiles are skipped.
- **Upstream candidates, nothing posted:** `data:` URIs and a missing `byteLength` in
  subtree JSON, Python continuations released without the GIL, no
  `EXT_primitive_voxels` accessor, voxel mode values above int32, and GeoTOP's flip,
  which may need raising with Bedrock.

- **`GltfModifier` from Python fails** ("Tried to call pure virtual function
  GltfModifier.apply", tiles don't load) until #7 merges. Jonathan wants the clip
  modifier in cesium-native C++ and bound, not done in Python.
  Requested upstream: cesium-native#1486.
- **`is_job_running("SHADER_COMPILATION")`** stayed true for minutes on large
  scenes while the viewport was already correct. Don't use it to wait.
- **Content-less tiles** (fixed 2026-11-04): cesium-native renders a tile without
  content as a hole when its geometric error is below its parent's
  (`TilesetContentManager::updateContentLoadedState`; deliberate, the code
  comment calls it "nothing need be rendered at this level-of-detail"). CesiumJS
  does much the same: `canTraverse` stops at an empty tile that meets the SSE
  and selects nothing. So this is a writer problem, not a cesium-native bug.
  3dtiled output has nine such levels above its content, so the
  Vestibule and Interior splats showed nothing from most viewpoints (the "0 tiles
  away from the origin" symptom). `asset_fixes.refine_through_empty_tiles` gives
  those tiles their parent's error in the tileset JSON. A content-less *root*
  still renders as a hole once it meets the SSE (cesium compares it with twice
  its own error), i.e. from about 2 km on a 130 m tileset at 8 px. The real fix
  is in 3dtiled: write empty tiles with their parent's error, or put coarse
  content in them. Clipping those splats is still unchecked.
- **Non-georeferenced tilesets** (fixed 2026-11-04): a stream now carries its own
  frame (`st["frame"]`, `_decide_origin` returns it) when the origin is already
  fixed and the tileset sits at ECEF 0, so it lands at the Blender origin in its
  own axes with Custom / Keep / Search origins and as a second stream next to a
  georeferenced one. Checked on 5.3 with a Custom origin in Rome and with the CDN
  splats first. The Vestibule splats render as a tall column, about twice as
  high as wide: likely the converter's axes, not the add-on; not investigated.
- **Preparer errors at stop**: stopping a stream with loads in flight logs a
  burst of "Tried to call pure virtual function
  IPrepareRendererResources.prepare_in_load_thread" from cesium-native (the
  Python preparer is gone before the worker continuations run). Harmless so far.
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
- [cesium-unreal#1914](https://github.com/CesiumGS/cesium-unreal/issues/1914),
  adaptive point size: posted on 2026-11-04. Its image is a Blender render using
  Unreal's formula, not an Unreal capture.
- [3DTilesRendererJS#1783](https://github.com/NASA-AMMOS/3DTilesRendererJS/issues/1783):
  adaptive point size for implicit `ADD` octrees. Open, his issue.
- [cesium-native#1488](https://github.com/CesiumGS/cesium-native/pull/1488) and
  [awesome-3d-tiles#8](https://github.com/pka/awesome-3d-tiles/pull/8): PRs listing
  the add-on. Open, in his name.

## 4. What's next

**Needs his answer first**

1. **Tag v0.5.1** for terrain and intensity, once he has tried them. Bump the
   version in `blender_manifest.toml`. It also tests Iconem's tag trigger.
2. **Adaptive point size in the add-on?** Not on the roadmap and not asked for,
   but the formula and the deepest-node lookup already exist in the test script
   `gen_r9.py` (see below). It would need a per-point attribute refreshed when the
   selection changes.

**Can start on the add-on**

3. ~~Bugs in section 2~~ (fixed 2026-11-04, see Known limitations): content-less
   tiles rendered as holes, and non-georeferenced tilesets with a fixed origin.
4. **Reopening a saved .blend** with metadata is untested.
5. **Beta items from the README roadmap:** Grease Pencil phases (first version done
   2026-11-05: `phase_strokes.py` for the geometry, `phases.OGC3D_OT_PhaseFromStrokes`,
   pref `beta_phase_strokes`; painted areas (brush radius around the strokes) and outlines (prisms); the panel is in
   its own *Phases* sidebar tab; tested with generated strokes on the IGN COPC tile, never
   with a hand-drawn one, and Jonathan hasn't tried it), an octree pyramid
   for the class grid (most common class per 2×2×2 block, never an average),
   `meshToVolume` or trimesh as voxelizers, and the PDAL draft.
6. **`pnts` / `i3dm` on the pure Python path:** the last open non-beta roadmap
   item. Low value, since the native path handles them.

**Waiting on others**

- **Caleb:** everything in section 1. Items 1 and 2 of the upstream list are small
  and ready, but he hasn't answered since 2026-10-22, and Jonathan's rule is to
  wait before opening more.
- **3dtiled:** now sends intensity and classification, opt-in with
  `&attributes=intensity,classification` on the stream URL; checked on 2026-11-05
  with an IGN LiDAR HD COPC tile (classification as classes, intensity through the
  ramp with a custom range). Class names (Ground, Building...) are not shown, only
  codes. Another agent has that repo; don't touch it. 3dtiled's level 1 tiles also seem to overstate their geometric
  error (about 3.4 m declared against 1.3 m point spacing), so 16 to 32 px suits
  them for now.
- **Cesium:** #1486, #1914, #1488.

**His sample repo:** `lion_takanawa/implicit-octree/tileset-x100.json` in
`3dtiles-samples` scales its errors and also has a root transform of scale 100, so
cesium-native reports 750 m of error on a 464 m model and over-refines it. Mention
it to him rather than fixing it unasked.

## 5. Local test data

Copied to `.local/test_data/` in the worktree this note was handed to. `.local/` is
ignored by git, so copy it again for another worktree. The originals are in
`%TEMP%\ogc_tests`, which Windows may clean. Scripts there were searched for share
links and Google keys, and none were found. Keep it that way.

| Folder | What it is |
|---|---|
| `harness/` | Drives a GUI Blender from a shell: `gui_repl.py`, `run.sh`, `h.py`, `h_shot.py`. Paths inside point to `%TEMP%\ogc_tests\r9`. |
| `adaptive_point_size/` | The #1914 comparison image, its panels, `gen_r9.py` and the generated scripts. |
| `intensity/` | Hand-written tile with real IGN LiDAR HD `_INTENSITY` values, from before 3dtiled sent them. |
| `spz/` | Splat tiles, compressed and raw. |
| `nas_sample/`, `localmesh/` | Local and NAS-style tilesets. |
| `phases/`, `strokes/` | Voxel phases written from closed meshes and from strokes. |
| `swissgeol/`, `voxel/` | Voxel tilesets, including a GeoTOP mirror. |

Elsewhere on this machine: the private library in section 0, and the binding
checkout in section 1.