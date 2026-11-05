# OGC 3D Tiles Streaming — Blender Plugin

[cesium-native](https://github.com/CesiumGS/cesium-native) does the tile selection,
loading and decoding through the [cesium-native-python](https://github.com/calebbuffa/cesium-native-python)
bindings + some niceties like raster overlays or clips. Tiles load and unload around
the viewport camera, or around the render camera for animations. Different approach
than the pure-Python [CesiumForBlender](https://github.com/CognitoBit/CesiumForBlender)
([forum post](https://community.cesium.com/t/cesium-for-blender/46938))
although I keep a python native fallback.

**[Documentation](https://jo-chemla.github.io/blender_ogc3dtiles/)** · **[Slides](https://jo-chemla.github.io/blender_ogc3dtiles/slides/s/blender-3dtiles/)**
([PDF](https://jo-chemla.github.io/blender_ogc3dtiles/slides/pdf/blender-3dtiles.pdf)) · **[Releases](../../releases)**

What works today:

- **Content:** cesium-native brings for free all supported flavors of
  [3D Tiles](https://github.com/CesiumGS/3d-tiles)
  ([1.0](https://docs.ogc.org/cs/18-053r2/18-053r2.html) /
  [1.1](https://docs.ogc.org/cs/22-025r4/22-025r4.html)) and tile content:
  - Tiled meshes: b3dm, glb,
    [Draco](https://github.com/KhronosGroup/glTF/tree/main/extensions/2.0/Khronos/KHR_draco_mesh_compression),
    [meshopt](https://github.com/KhronosGroup/glTF/tree/main/extensions/2.0/Vendor/EXT_meshopt_compression),
    [KTX2](https://github.com/KhronosGroup/glTF/tree/main/extensions/2.0/Khronos/KHR_texture_basisu)
  - Tiled point clouds: `pnts`, glTF points
  - Tiled 3DGS splats:
    [`KHR_gaussian_splatting`](https://github.com/KhronosGroup/glTF/tree/main/extensions/2.0/Khronos/KHR_gaussian_splatting),
    SPZ or uncompressed, as native
    [Blender 5.3](https://developer.blender.org/docs/release_notes/5.3/rendering/) splats
  - Sources: [Google Photorealistic 3D Tiles](https://developers.google.com/maps/documentation/tile/3d-tiles),
    [Cesium ion](https://cesium.com/platform/cesium-ion/) assets, a WGS84 globe
- **One graph for all tiles:** Blender niceties there, a shared Geometry Nodes modifier,
  a shared shader group for relighting and a compositor tree (edges, AO, haze) apply to
  every tile, either content that has already been fetched and loaded or streamed later
- **Rendering:** EEVEE and Cycles, plus a "converged animation" render that waits for the
  tiles of each frame to finish loading before rendering it
- **Raster overlays** draped on tiles: URL template, TMS, WMTS, WMS, ion, Bing, Google,
  Azure, again feature-parity with all formats cesium maintains support for.
- **Clipping:** cut a tileset with Blender objects, either as clip-polygons or as 3D
  boxes, useful to combine overlapping tilesets like focus high-res drone scan into a
  coarser, larger extent, city-wide scan. It works on meshes, point clouds and splats,
  follows live as you move the objects, and can be keyframed for renders. Geometry-level
  clipping in cesium-native is requested in
  [#1486](https://github.com/CesiumGS/cesium-native/issues/1486).
- **Several tilesets at once,** placed around a scene origin usually auto-set at tileset
  centroid, or that you can set by searching for a place name; local and network-share
  tilesets, shared libraries of tilesets, and copying a tileset into the project,
  cropped to an area

![Google Photorealistic 3D Tiles over the Colosseum in Blender: viewport with the add-on sidebar, then EEVEE, Cycles with a 10 kW lamp, and EEVEE through the beauty compositor (EDL 16)](docs/img/rome_google_3dtiles.jpg)

![Sidebar in three columns: main panel with raster overlays, clipping and viewport-region clip - Scene Origin, LOD / Streaming, Nodes: Material, Nodes: Geometry, Coordinate Info - Nodes: Compositing, Nodes: Metadata, Render](docs/img/sidebar.jpg)

## Installation

The add-on is a Blender extension, for Blender 4.2 or newer (Gaussian splats need 5.3).

1. Download `ogc_3dtiles_streaming-<version>.zip` from the [Releases](../../releases) page.
2. In Blender: Preferences, Get Extensions, the drop-down arrow, *Install from Disk*.
3. For the cesium-native backend (faster; raster overlays, point clouds and Cesium ion
   entries need it): open the add-on preferences and press **Install wheel from GitHub
   Release**, then restart Blender. No compiler is needed. Without it, the pure Python
   backend streams mesh tilesets.

More in [Installation](https://jo-chemla.github.io/blender_ogc3dtiles/guide/installation/): building the zip from a checkout,
the Windows runtime note, the wheel repositories.

## Quick start

1. Open the sidebar of the 3D viewport (N), tab **3D Tiles**.
2. Add a tileset entry (+) and paste a `tileset.json` URL: a Cesium ion asset, Google
   Photorealistic 3D Tiles, a local file, a share link.
3. For Cesium ion, paste your access token.
4. Leave the origin mode on *Auto*: the first tileset centres the scene.
5. Press **Start** and navigate: tiles load as the camera moves.

The [Quick start](https://jo-chemla.github.io/blender_ogc3dtiles/guide/quick-start/) page describes every panel and node group.

## Features

Each one has its page in the [documentation](https://jo-chemla.github.io/blender_ogc3dtiles/):

- [Scene origin](https://jo-chemla.github.io/blender_ogc3dtiles/features/scene-origin/) and [place search](https://jo-chemla.github.io/blender_ogc3dtiles/features/place-search/)
- [Raster overlays](https://jo-chemla.github.io/blender_ogc3dtiles/features/raster-overlays/): OpenStreetMap, Esri and IGN presets, your own WMTS / WMS, Google, Bing
- [Clipping](https://jo-chemla.github.io/blender_ogc3dtiles/features/clipping/) with polygons, boxes and the viewport region
- [Several tilesets](https://jo-chemla.github.io/blender_ogc3dtiles/features/several-tilesets/), ion, globe and terrain entries
- [Libraries and local files](https://jo-chemla.github.io/blender_ogc3dtiles/features/libraries-and-local-files/): tileset libraries, the cache, copying a tileset into the project
- [Point clouds](https://jo-chemla.github.io/blender_ogc3dtiles/features/point-clouds/) and [feature metadata](https://jo-chemla.github.io/blender_ogc3dtiles/features/feature-metadata/): colour by class or number, class opacity
- [Gaussian splats](https://jo-chemla.github.io/blender_ogc3dtiles/features/gaussian-splats/) and [voxels](https://jo-chemla.github.io/blender_ogc3dtiles/features/voxels/)
- [Editing tile geometry](https://jo-chemla.github.io/blender_ogc3dtiles/features/editing-geometry/) with shared geometry nodes
- [Compositor](https://jo-chemla.github.io/blender_ogc3dtiles/features/compositor/), [rendering animations](https://jo-chemla.github.io/blender_ogc3dtiles/features/rendering-animations/), [Cycles](https://jo-chemla.github.io/blender_ogc3dtiles/features/cycles-viewport/) and [orthographic views](https://jo-chemla.github.io/blender_ogc3dtiles/features/orthographic-views/)
- [Beta features](https://jo-chemla.github.io/blender_ogc3dtiles/features/beta/): the phases timeline, material controls

## Development

```text
PYTHONPATH=src python -m pytest -q
ruff check --select E9,F src/blender_ogc3dtiles tests scripts
blender --command extension build --source-dir src/blender_ogc3dtiles --output-dir dist
```

[Setup and tests](https://jo-chemla.github.io/blender_ogc3dtiles/dev/setup-and-tests/), [architecture](https://jo-chemla.github.io/blender_ogc3dtiles/dev/architecture/),
[releasing](https://jo-chemla.github.io/blender_ogc3dtiles/dev/releasing/), the [cesium-native wheel](https://jo-chemla.github.io/blender_ogc3dtiles/dev/cesium-native-wheel/)
and its [versions](https://jo-chemla.github.io/blender_ogc3dtiles/dev/cesium-native-versions/), and the [roadmap](https://jo-chemla.github.io/blender_ogc3dtiles/dev/roadmap/)
are in the documentation. Its pages live in [`site/`](site), the slide deck in
[`slides/`](slides); both are built and deployed by
[`.github/workflows/docs.yml`](.github/workflows/docs.yml).

## License

[MIT](LICENSE).
