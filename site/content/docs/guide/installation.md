---
title: "Installation"
description: "Install the extension and the cesium-native backend"
---

The add-on is a Blender extension, for Blender 4.2 or newer. It is tested on 4.5 LTS, 5.1 and
5.2 LTS. Gaussian splats need 5.3.

## Install the extension

1. Download `ogc_3dtiles_streaming-<version>.zip` from the
   [Releases](https://github.com/jo-chemla/blender_ogc3dtiles/releases) page.
2. In Blender: Preferences, Get Extensions, the drop-down arrow at the top right, *Install from Disk*.
3. Open the sidebar of the 3D viewport (**N**): there is a **3D Tiles** tab.

## Install the cesium-native backend

The add-on works at once with its pure Python backend, which streams mesh tilesets. The cesium-native
backend is faster, and raster overlays, point clouds, splats, voxels, Cesium ion, the globe and
terrain need it.

1. Open the add-on preferences: Preferences, Add-ons, OGC 3D Tiles. The same button is offered in red
   at the top of the sidebar while the backend is missing.
2. Press **Install wheel from GitHub Release**.
3. Restart Blender.

No compiler is needed: the button downloads the build that matches your Blender and your system
(Linux x86_64, Windows x64, macOS arm64) and installs it into Blender's own Python.

## From a terminal, or from a checkout

Install a zip from a terminal:

```text
blender --command extension install-file -r user_default -e ogc_3dtiles_streaming-0.6.1.zip
```

Build the zip from a checkout with Blender's own packager:

```text
blender --command extension build --source-dir src/blender_ogc3dtiles --output-dir dist
blender --command extension validate dist/ogc_3dtiles_streaming-0.6.1.zip
```

## Details

- The backend is the `cesium-python` wheel, built from
  [cesium-native-python](https://github.com/calebbuffa/cesium-native-python). By default the add-on
  takes it from the latest release of the
  [jo-chemla fork](https://github.com/jo-chemla/cesium-native-python/releases), whose CI builds
  wheels for CPython 3.11 to 3.13. The repository can be changed in the preferences; *Build / install
  from source* is there for a local checkout.
- Windows: Blender 4.2 to 4.5 bundle an old Microsoft C++ runtime. The released Windows wheels are
  built to work with it, on 4.5 and 5.x alike. A wheel built differently is refused on Blender older
  than 5.0, with a message, instead of crashing.
