---
title: "OGC 3D Tiles for Blender"
description: "Stream 3D Tiles (meshes, point clouds, Gaussian splats, voxels) into Blender"
---

[cesium-native](https://github.com/CesiumGS/cesium-native) does the tile selection,
loading and decoding through the [cesium-native-python](https://github.com/calebbuffa/cesium-native-python)
bindings + some niceties like raster overlays or clips. Tiles load and unload around
the viewport camera, or around the render camera for animations. Different approach
than the pure-Python [CesiumForBlender](https://github.com/CognitoBit/CesiumForBlender)
([forum post](https://community.cesium.com/t/cesium-for-blender/46938))
although I keep a python native fallback.

The same tour as a [slide deck](https://jo-chemla.github.io/blender_ogc3dtiles/slides/s/blender-3dtiles/) ([PDF](https://jo-chemla.github.io/blender_ogc3dtiles/slides/pdf/blender-3dtiles.pdf)).

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

![Google Photorealistic 3D Tiles over the Colosseum in Blender: viewport with the add-on sidebar, then EEVEE, Cycles with a 10 kW lamp, and EEVEE through the beauty compositor (EDL 16)](/img/rome_google_3dtiles.jpg)

![Sidebar in three columns: main panel with raster overlays, clipping and viewport-region clip - Scene Origin, LOD / Streaming, Nodes: Material, Nodes: Geometry, Coordinate Info - Nodes: Compositing, Nodes: Metadata, Render](/img/sidebar.jpg)


## License


[MIT](https://github.com/jo-chemla/blender_ogc3dtiles/blob/main/LICENSE).
