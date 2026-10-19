# OGC 3D Tiles Streaming — Blender Plugin

Stream OGC 3D Tiles tilesets directly into Blender with Cesium-compatible
Level-of-Detail and non-blocking HTTP downloads. Two interchangeable
backends: pure Python (always available) or cesium-native via
[cesium-native-python](https://github.com/calebbuffa/cesium-native-python).

## Architecture

```
blender_ogc3dtiles/
├── __init__.py              # bl_info, register/unregister
├── addon_prefs.py           # backend choice (AUTO / CESIUM / PYTHON), dev options
├── tileset/
│   ├── traversal.py         # Tile tree, transforms, SSE, culling, select()  (no bpy)
│   ├── backend.py           # PythonBackend + factory / probe
│   ├── native_backend.py    # cesium-native backend (real binding API)      (no bpy)
│   └── props.py             # bpy.types.Scene.ogc3dtiles PropertyGroup
├── camera/__init__.py       # viewport → ViewState (ECEF pos/dir/up, p00/p11, frustum)
├── io/__init__.py           # thread pool fetch + unwrap + disk cache, GLB import
└── ui/__init__.py           # sidebar panel + modal operator (stream_tick)
```

### Several tilesets at once

The sidebar holds a list of tilesets (add / remove, enable toggle, per-entry
URL, ion token and SSE).  Every enabled entry becomes its own stream with its
own backend instance, download manager, root Empty (`3D Tiles · <name>`) and
sub-collection (`Tiles · <name>`), all sharing the scene origin and the
viewport camera.  Moving, rotating or scaling a root Empty is honoured by
culling and SSE for that tileset only.

### Streaming loop (both backends)

Every 50 ms the modal operator runs `ui.stream_tick()`:

1. drain worker results (external `tileset.json` are grafted into the tree,
   ready GLBs are queued),
2. import at most `Imports / tick` GLBs with `bpy.ops.import_scene.gltf`
   (the only main-thread cost; 1 keeps the viewport smooth),
3. re-run the selection only when the view changed, something arrived, or
   0.5 s passed,
4. submit loads in priority order (largest screen-space error first) up to
   the download concurrency,
5. evict least-recently-wanted hidden tiles above `Max Tiles`.

Imports never touch the user's selection or active object. Every tile is
parented to one root Empty per tileset inside the `3D Tiles` collection, so
the whole dataset can be moved / rotated / scaled, hidden or folded as one.

### Pure Python backend (`tileset/traversal.py`)

- Tile `transform` matrices compose down the tree; `box`/`sphere` volumes
  are transformed, `region` is geodetic.
- Screen-space error `sse = ge · viewport_h · p11 / (2 · dist)` with `p11`
  read from the viewport projection matrix (exact FOV, orthographic aware).
- Frustum culling with the viewport's own planes (rotated into ECEF) plus a
  maximum distance (`Max Distance`).
- Dynamic SSE: `thr(d) = SSE · (1 + d / Detail Falloff)`, so detail
  concentrates near the camera and distant regions settle at coarse LODs.
- `REPLACE` keeps the parent visible until every visible child subtree is
  imported (no holes); `ADD` renders parent and children together.
- Workers unwrap `b3dm` / `cmpt` / `glb`, trim the 8-byte container padding
  some exporters (RealityCapture) add, extract `RTC_CENTER` / `CESIUM_RTC`,
  and write GLBs into `%LOCALAPPDATA%/blender_ogc3dtiles/cache`; a second
  session of the same tileset downloads nothing.
- Placement: tile Empty = `ENU_from_ECEF · T_tile · Translate(RTC)`; Blender's
  importer already converts glTF Y-up to Z-up.

### Direct mesh construction (cesium-native, default)

`tileset/native_mesh.py` turns the decoded cesium-native `Model` into numpy
arrays on the worker thread (positions with node transforms applied and
converted to Z-up, triangle indices, per-loop UVs, normals, COLOR_0, the
original JPEG/PNG bytes of the textures or PNG re-encoded from decoded
pixels for KTX2).  `io.build_tile_from_payload` then creates the mesh with
`foreach_set`, packs the textures from bytes and builds a matte Principled
material.  Point clouds (`pnts`, glTF POINTS) become vertex-only meshes with
a `Col` colour attribute and a shared "OGC3D Points" Geometry Nodes modifier
(Mesh → Points, radius exposed) so they render in EEVEE / Cycles with unlit
vertex colours.  Measured main-thread cost per tile: 8–9 ms direct vs 10–13 ms
through `bpy.ops.import_scene.gltf`; the direct path also needs no temp files
and works regardless of which glTF extensions Blender's importer knows.
Toggle: "Direct mesh (cesium-native)" in the sidebar (off = GLB re-import).

### cesium-native backend (`tileset/native_backend.py`)

Needs the `cesium` module (built from cesium-native-python, Python ≥ 3.12,
same minor version as Blender's interpreter). It constructs
`Tileset(TilesetExternals(CachingAssetAccessor(CurlAssetAccessor), preparer, AsyncSystem), url)`
and drives it with `update_view_group`. cesium-native does the traversal,
implicit tiling, `b3dm/i3dm/pnts/cmpt` conversion, Draco / meshopt / KTX2
decoding, the LRU tile cache (`maximum_cached_bytes`) and the sqlite HTTP
cache. Our `IPrepareRendererResources` subclass serialises each decoded
`Model` back to a GLB (`GltfUtilities.collapse_to_single_buffer` +
`GltfWriter.write_glb`, KTX2 textures re-encoded to PNG) which the same
import step consumes. Placement: Empty = `ENU_from_ECEF · T_tile · Zup→Yup`.

---

## Coordinate System

```
WGS84 (lat/lon/height)
        │  _geodetic_to_ecef()
        ▼
    ECEF (metres, geocentric)
        │  ecef_to_enu(origin_lat, origin_lon, origin_height)
        ▼
    ENU  (East / North / Up, origin-relative metres)
        │  direct mapping
        ▼
    Blender XYZ  (X=East, Y=North, Z=Up)
```

---

## Installation

1. Zip the `src/blender_ogc3dtiles/` folder → `blender_ogc3dtiles.zip`
   (or symlink it into `extensions/user_default/`)
2. Blender → Edit → Preferences → Add-ons → Install → select zip
3. Enable "OGC 3D Tiles Streaming"
4. View3D → Sidebar (N) → "3D Tiles" tab

### cesium-native (optional)

Build the binding for the CPython minor version Blender ships (Windows: see
`docs/cesium-native-python-windows-build.md` for the fixes the upstream repo needs)
(Blender 5.1 → 3.13) and install the wheel into Blender's own
`<blender>/5.1/python/Lib/site-packages`. Then pick **CESIUM** or **AUTO**
in the add-on preferences. The pure Python path is used otherwise.

## Quick Start

1. Paste a `tileset.json` URL (Cesium Ion, Google Maps 3D Tiles, local server…)
2. For Cesium Ion: paste your access token
3. Enable "Auto-center from Tileset" (reads origin from bounding volume)
4. Hit **Start**
5. Navigate the 3D viewport — tiles load as you move the camera

Headless smoke test: see `ui.stream_tick()`; in `blender -b` the operator
does not start a timer, call `stream_tick(bpy.context)` yourself with a
monkeypatched `CesiumCameraAdapter.get_view_state`.

## Building the cesium-native wheel

`.github/workflows/cesium-native-wheel.yml` (manual trigger) clones
calebbuffa/cesium-native-python, applies `third_party/cesium-native-python-windows.patch`,
builds the wheel for the requested CPython (3.13 for Blender 5.1/5.2) with a
cached vcpkg tree, and uploads it as an artifact or attaches it to a release.
Blender extensions can bundle platform wheels (`wheels = [...]` in
`blender_manifest.toml`), which is the intended distribution path.

## Development

```
uv venv && uv pip install -e . --group dev
PYTHONPATH=src pytest        # traversal + coordinate tests (bpy is stubbed)
```

## Roadmap

- [x] Frustum culling, dynamic SSE, REPLACE gating, priority loads
- [x] Disk cache, budgeted imports, selection preserved
- [x] cesium-native backend against the real binding API
- [ ] Several tilesets at once (one root Empty each)
- [ ] Raster overlays (cesium-native) draped on tiles
- [x] `pnts` point clouds on the native path (Angkor tilesets verified)
- [ ] `pnts` / `i3dm` on the pure Python path
- [ ] `3DTILES_metadata` → Blender custom attributes
