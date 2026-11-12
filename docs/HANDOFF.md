# Handoff: blender_ogc3dtiles + cesium-native-python

**Newest first: section 6 (2026-11-12) is the current state. Sections 0 to 5 are
the 2026-11-04 handoff and still hold except where section 6 says otherwise.**

## 6. Handoff 2026-11-12

State: `main` is `7abb165` plus this note on both remotes (`origin` = jo-chemla, `iconem`),
tree clean. Written from the cnj machine (the Blender 5.3 beta there is under
`%LOCALAPPDATA%\Blender Launcher\experimental\`, not the path in section 0).

### Done since 2026-11-07

- `2c40e12` Streaming: Start reuses the live modal, orphaned tile objects dropped.
- `7abb165` `video/`: the screencast harness, per-take prep and scene scripts, mark
  files, the activity-based cutter and the Remotion reel. `video/PROCESS.md`
  explains the pipeline, the pitfalls and lists every take.
- **Videos**: the 6:17 reel (Google and Bing, Sacré-Coeur splat, clipping, shared
  nodes with EEVEE and Cycles, IGN points, classes, overlay on Clermont) and the
  final takes are on the **draft** release `videos-2026-11` of
  `jo-chemla/blender_ogc3dtiles` (hidden until Jonathan publishes it; nothing on
  Iconem yet). Originals: `C:\Users\cnj\Videos\blender_ogc3dtiles_screencasts\`.
  Not re-recorded: Strasbourg (library take, the origin never moved there).
- **Shramko Lublin, 103 M splats**: streams now. Cause of the earlier empty
  scene: splat-transform's lod-meta is a 15-deep k-d tree with 31,668 leaves and
  3dtiled mapped each leaf to its own tile chain. Fix in the 3dtiled worktree
  `C:\Dev\jonathan\3dtiled-to-3dtiles-wt` (branch `setup/worktree`), **local commit
  `5964eeb`, not pushed**: `packages/sog-to-3dtiles/src/index.js` collapses the
  tree per LOD level to the shallowest nodes whose splats fit `--splat-budget`
  (default 100 k, `0` = old 1:1). Lublin: 126,672 tiles to 2,570, Blender draws it
  in seconds. Another agent owns that repo: ask Jonathan before pushing.
- **William Liu's converter** (npm `3dgs-ply-3dtiles-converter` 0.6.5; the
  lzy-0618 GitHub copy is not his, and there is no jo-chemla fork) on the full
  6 GB PLY: the first run died after 3 h in "building tiles bottom-up" with no
  tileset (probably killed by a Blender restart); a second run started on
  2026-11-12 around 07:00 at low priority and was at the same stage at 09:00.
  Output `%OGC_SCRATCH%\dl\lublin\wl_tiles` (a Temp folder Windows may clean).
  Its planned tree: 12 levels, 4,250 leaves, comparable to the 3dtiled fix.
- **Raster overlay on COPC point tiles does not work** (and never did; the old
  take's colours were the classification): cesium-native upsamples about a
  thousand point tiles and attaches 1x1 to 3x3 px rasters, while the same WMTS
  on the Clermont mesh gets 343x395 px images. Not fixed; the demo uses the mesh.

### Upstream, posted on 2026-11-11 by Jonathan

- [issue 2, comment 6802160907](https://github.com/calebbuffa/cesium-native-python/issues/2#issuecomment-6802160907):
  status after the merges, closed table, six low-effort items (PyPI needs only
  the trusted publisher, the `pypi` environment and a `v0.1.0` tag; rename to
  `cesium-native-python` before the first tag; C5 and B2 already bound; GIL crash
  in continuations; `CachingAssetAccessor` taking a `SqliteCache`; CI on PRs), and
  the parked items B3, B4, C6, C10, C11, C12 in a details table.
- [issue 8](https://github.com/calebbuffa/cesium-native-python/issues/8): the
  v0.59 to v0.66 bump, what each version brings and costs, two-step proposal.
- Verified against upstream `main` (4b55c1a) and the add-on on 2026-11-12:
  - The package name `cesium-python` is Caleb's, from his initial commit e49c0ef
    (2026-03-17); our PRs never touched it. On PyPI `cesium` is taken by
    cesium-ml, a time-series feature-extraction library from Stefan van der
    Walt's group at Berkeley, last release 0.12.4 in January 2025, unrelated to
    Cesium; `cesium-python`, `cesium-native-python` and `cesium-native` are free.
  - All six parked items are live workarounds in the add-on: minimal load-thread
    preparer (B3), cache lock file in `native_backend.py` (B4), point radius from
    point spacing (C6), `cachectl.py` byte-budget trim (C10), 12 `callable()`
    checks (C11, the post says about 15), our own preparer (C12). The "about 8 ms
    per tile" figure is our own note in `gltf_payload.py`.
  - Issue 8's version table matches the upstream changelog line by line,
    including the v0.65 error delegate and setter removal. v0.59 and v0.61 share
    the same ezvcpkg commit; v0.62 moves it.
  - Thread numbering is B1 b3dm, B2 ortho, B3 GIL, B4 sqlite, consistent with the
    Oct 21 comment. **`docs/cesium-native-python-upstream-requests.md` numbers them
    differently (B1 ortho, B2 GIL, B3 sqlite): realign it.**
  - If Caleb accepts the rename, wheel filenames become `cesium_native_python-*`,
    which touches the add-on's `pyproject.toml` source key and
    `tests/test_wheel_pick.py`.
- **New: [issue 9](https://github.com/calebbuffa/cesium-native-python/issues/9)**
  (BenDyson-Arch, 2026-11-12): the Linux wheel from our fork fails every HTTPS
  request on Arch, Debian and Ubuntu because the manylinux curl only knows the Red
  Hat CA bundle path. Fixable in the add-on today: the binding exposes
  `CurlAssetAccessorOptions.certificate_file` (curl `CAINFO`), and Blender's
  Python ships `certifi`. Set it when building the accessor in
  `tileset/native_backend.py` (next to `user_agent`). Then reply on issue 9 so
  Caleb does not treat it as a binding bug.

### Done 2026-11-12 (later the same day, from Jonathan's machine)

- certifi CA bundle set on `CurlAssetAccessorOptions.certificate_file` (issue 9).
- Real orthographic views: `camera.get_view_state` keeps the eye on the pivot and
  exposes `ViewState.ortho_extents`; `native_backend.update_view(..., ortho=)`
  builds the binding's orthographic `ViewState`. The 1-degree pulled-back camera
  is gone. Checked on the Clermont mesh, top view at 600, 300 and 150 m: full-detail
  tiles across the frame (at 300 m: 117 visited, 61 culled, 61 rendered). Fog
  culling stays off: a wide orthographic frame has far tiles near its edges.
- `docs/cesium-native-python-upstream-requests.md` renumbered B1 b3dm, B2 ortho,
  B3 GIL, B4 sqlite, as in the thread.
- Drafts for issue 9 and for the issue 2 follow-up ("item 3 done") were shown to
  Jonathan; not posted by the agent.

### Lublin and the 3dtiled branch, 2026-11-12 (Jonathan's laptop)

- **Branch `sog-splat-budget` is superseded**: jo-chemla `main` (`fe7f705`) holds the same
  commit as `7cd5821` plus `6c658f7` (collapse moved to `lodMeta.js`, shared with the
  live route, `test/collapse.test.js`, docs; Lublin 259 M and Itaka Stadium from
  SuperSplat's CDN in the viewer library). Delete the branch rather than merge it.
  The root transform question: neither path ever wrote an ENU transform; the offline
  converter writes RX(-90°) with zero translation on both paths, and only the
  tile-server's `applyPlacement` (`&lon=&lat=`) composes a globe placement.
- **Lublin live**: `3dtiled.iconem.com/stream/tileset.json?format=sog&url=<CDN lod-meta>`
  answers in 3 s with 7,169 tiles (2.3 MB); streams in Blender 5.3 (private library
  entry "Lublin 259M, Poland (Shramko, 3dtiled SOG live)").
- **Reproduced offline** in `C:\Users\jonathan\work\lublin\` (`pipeline.sh`, `pipeline.log`):
  103 M PLY from Drive; splat-transform 3.11.1: Morton 46 s, LOD1 14.5 min, LOD2
  16 min, LOD3 16 min, LOD build 6.5 min (106.4 M + 26.5 M + 6.36 M + 1.59 M, 271
  chunks); 3dtiled main `--format sog --verify counts`: 1.8 min, 2,568 tiles, 2.1 GB,
  141 M points, 0 missing; draws in Blender (library entry "Lublin 106M merged").
- **William Liu's converter 0.6.5** on the same PLY: 7.9 min end to end (scan 1.5 min,
  tree 12 levels / 4,657 leaves, build 6.2 min), 9,313 nodes, 3.8 GB; draws in Blender
  (library entry "Lublin 103M (Shramko, William Liu converter, local)"). The 15-hour
  run on cnj was the exception. This laptop had also run it on 2026-11-05 on the
  259 M `Lublin-Poland.ply` (178 M kept): 17 min, 22,904 nodes, 6.3 GB, which is the
  "Lublin 178M (local)" library entry.
- The 3dtiled clone used for this is `C:\Users\jonathan\work\3dtiled-sog-budget` (on main).

### Next steps, in order

1. Done: certifi fix (see above); the issue 9 reply waits for Jonathan to post it.
2. Done: real orthographic views (see above). Original recipe kept for reference: **Real orthographic views**: the binding has
   `ViewState(position, direction, up, viewport_size, left, right, bottom, top)`
   since Caleb's first commit. On v0.59 it culls with the four side planes only
   and its SSE is `ge * viewport_height / (top - bottom)`, distance independent.
   The add-on today fakes ortho with a 1 degree camera pulled back
   (`ortho_eye_offset`, `native_position` in `camera/__init__.py` and
   `tileset/traversal.py`) and disables fog culling for it. Change: in
   `camera.get_view_state` keep the eye on the pivot and carry the half extents
   (`1/p00`, `1/p11`, root scale folded in); in `native_backend.update_view` build
   the ortho overload when `is_persp` is false, else the fov overload; drop the
   offset and the fog workaround. About 30 lines; test on the Clermont mesh in top
   ortho view. Tiles behind the pivot are also selected, like Blender's own ortho
   viewport. Matrix overload caveat: cesium-native's projection has Y flipped, an
   OpenGL matrix must get row 1 negated or the SSE comes out negative. Then follow
   up on item 3 of the issue 2 comment with "done".
3. Done: B numbering realigned.
4. Done: `5964eeb` was pushed as branch `sog-splat-budget`, and main already has it (see above); delete the branch.
5. Done: William Liu result above.
6. Publish or copy the `videos-2026-11` release (Iconem too) when Jonathan says.
7. Strasbourg re-take if he still wants it (`video/harness/scene9.py`; the origin
   must actually move to Strasbourg).
8. Waiting on Caleb: the tag and PyPI registration, the rename, his pick on B3,
   and issue 8's one-step or two-step bump.

State on 2026-11-04, at `bc872f7` plus this note. For the next agent picking
this up. It holds no tokens or keys; the files that do are named below and stay
out of git.

**Where things stand:** nothing is in progress. Everything is on `main` on both
remotes. `main` is ahead of the last release, v0.5.0, by quantized-mesh terrain
entries and point intensity. Section 4 lists what to do next.

### Later on 2026-11-12: disk cleanup and the second video workflow

- Deleted, to free the laptop's C: drive: the Lublin intermediates
  (`shramko_poland_103M.ply`, `morton.ply`, `lod1-3.ply`, 13 GB) and the
  `C:\Users\jonathan\work\3dtiled-sog-budget` clone (clean, on main), then on
  Jonathan's word the William Liu tiles (`wl_tiles`, 3.8 GB, library entry removed)
  and the 3dtiled input (`lod\`, 1.6 GB). Kept: only
  `C:\Users\jonathan\work\lublin\3dtiles_merged` (2.1 GB, the 3dtiled SOG
  tiles). `pipeline.sh` there rebuilds everything from the Google Drive file in
  about 10 min of download plus 40 min of splat-transform.
- Why Blender crawled after three or four takes on cnj's machine (10 GB): memfile
  undo. Every click on a property pushes an undo step, and each step keeps a copy
  of every tile mesh created since the previous one, for 32 steps. Measured on the
  Clermont mesh at 2 px SSE with one undo-pushing operator per second: working set
  6.2 GB at 310 tiles with undo on, 3.4 GB at 345 tiles with undo off. Stop and
  Clear free the meshes themselves (0 orphans). For long takes set
  Preferences > System > Undo Steps to 0, or restart between take chains.
- The frame-stepped screencast scripts are in `video/evsim/` with a README that
  compares them with `video/harness/`. Their 14 clips are on the `videos-2026-11`
  draft release with workflow prefixes (`evsim_`, `drawnptr_`, `scripted_`).
  Three of them show private-library datasets (Geghard, Hayravank, Bayon): Jonathan
  decides whether they stay when the release is published. The Google URL field is
  blurred in every Rome clip.
- The add-on's HTTP cache, `%LOCALAPPDATA%\blender_ogc3dtiles\cache\http-cache.sqlite`,
  is 8.1 GB, mostly from the test sessions. Not deleted: it is also Jonathan's
  working cache. Clearing it is his call.

### Evening of 2026-11-12: 0.6.2, exact origin, William Liu tiles back

- **Issue 7 (origin precision) fixed and released as 0.6.2** on both repos:
  `tileset/origin.py` keeps the exact doubles in the scene ID property
  `ogc3dtiles_origin`; every reader goes through `origin_lla(props)`, every
  writer through `set_origin()`; the three fields' update callback copies an
  edited field into the store; a *Paste* field (`origin_text`) takes
  `lat, lon[, h]` exactly. Checked live on 5.3 (paste, edit, junk input, a
  Clermont stream). `tests/test_origin.py` covers the fallbacks.
- **Issue 6 (BlenderGIS georeference)** is not started: the reply posted on the
  issue describes the plan (one fitted root transform per tileset when `SRID`,
  `crs x`, `crs y` exist; pyproj, else BlenderGIS's parser, else no sync).
- Jonathan wanted the **William Liu** Lublin tiles kept, not the 3dtiled output:
  `work/lublin/regen_wl.sh` re-downloads the PLY and rebuilds `wl_tiles`
  (log `regen_wl.log`), then deletes the PLY; the library entry is restored
  (`tilesets_library.json.before-wl-restore.bak` is the state before).
  `3dtiles_merged` (3dtiled output) and the live 3dtiled entry are still there
  for him to drop.
- Screencast notes now live on the docs page *Development > Screencasts*
  (`site/content/docs/dev/screencasts.md`): both workflows, finding buttons,
  animated demos, the undo cause. The `evsim/` capture functions step the scene
  frame (`animate=True`) so Scene Time demos move, and run with Undo Steps 0.
- The cesium-native-python issue 9 reply carries an appended line saying 0.6.1
  ships the certifi bundle.

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
  - Install: `blender -b --command extension install-file -r user_default -e dist/ogc_3dtiles_streaming-0.6.2.zip`.
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
| [#4](https://github.com/calebbuffa/cesium-native-python/pull/4) | A3: cibuildwheel 3 OSes × CPython 3.11-3.13, Release + PyPI trusted-publishing jobs. | Merged (`0832a75`, 2026-11-05). No tag, release, workflow run or PyPI project upstream yet (checked 2026-11-07). |
| [#7](https://github.com/calebbuffa/cesium-native-python/pull/7) | One cast so Python subclasses of `GltfModifier` can override `apply`. | Merged (`4b55c1a`, 2026-11-05). |
| [#5](https://github.com/calebbuffa/cesium-native-python/pull/5) | C1, C2, C3, C4+C7 (docs), C8, C9. | Merged (`a8d3974`, 2026-11-05). |

- Waiting on Caleb: C6, C10, C11 (API shape, or need cesium-native changes),
  C12 (his), and his pick on the GIL (B3).
- Jonathan decided not to answer GeorgeS2019's metadata question on #5 (out
  of context).
- The fork's release `v0.1.0-wheels.1` holds wheels from #3 + #4 only. The
  add-on keeps its own workarounds so it runs on either build. The add-on's
  preferences have an "Install wheel from GitHub Release" button.
- 2026-11-05: Caleb merged #4, #5 and #7 and said contributions are welcome
  (issue #2). Upstream `main` is `4b55c1a`; it contains our Windows patch, so
  `third_party/` and the add-on's `cesium-native-wheel.yml` were deleted on
  2026-11-07. The fork's release `v0.1.0-wheels.1` predates #5 and #7: a wheel
  with them needs a run of the fork's `wheels.yml` on upstream `main` (or an
  upstream `v*` tag, which Caleb has not pushed).
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
- Install wheels from the upstream release or PyPI once Caleb tags one (the
  *Wheel release repo* preference already takes any `owner/name`); drop the
  workarounds #5 makes redundant (keep a version check).
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