---
title: "Installation"
description: "Install the extension and the cesium-native backend"
---

The add-on is a Blender extension (Blender 4.2 or newer; tested on 4.5 LTS,
5.1 and 5.2 LTS, native backend included).  Get `ogc_3dtiles_streaming-<version>.zip` from the
[Releases](https://github.com/jo-chemla/blender_ogc3dtiles/releases) page, or build it from a checkout with Blender's
own packager:

```text
blender --command extension build --source-dir src/blender_ogc3dtiles --output-dir dist
blender --command extension validate dist/ogc_3dtiles_streaming-0.5.1.zip
```

Then either Preferences, Get Extensions, the drop-down arrow, *Install from
Disk*, or from a terminal:

```text
blender --command extension install-file -r user_default -e dist/ogc_3dtiles_streaming-0.5.1.zip
```

The sidebar tab "3D Tiles" appears in the 3D viewport (N).  The pure Python
backend works out of the box; for the cesium-native backend (faster, and the
only one that decodes meshopt / KTX2 content on Blender versions whose glTF
importer lacks those extensions) open the add-on preferences and press
**Install wheel from GitHub Release**, see "Installing the native backend"
below, then restart Blender.

Windows note: Blender 4.2-4.5 bundle an old MSVC runtime (14.29) and the
loader keeps it for the whole process, so a wheel linked against the dynamic
runtime of a current toolset crashes in its first mutex.  The released
Windows wheels link the runtime statically and work on 4.5 and 5.x alike; the
add-on refuses a dynamic-runtime wheel on Blender < 5.0 with a message
instead of crashing.

## Installing the native backend

The cesium-native backend is an optional wheel, `cesium-python`, built from
[cesium-native-python](https://github.com/calebbuffa/cesium-native-python).
No compiler is needed: Preferences, Add-ons, OGC 3D Tiles, **Install wheel
from GitHub Release** (also offered in red at the top of the sidebar's main
panel while the binding is missing) downloads the wheel matching Blender's CPython and
platform from the latest Release of the configured repository and
pip-installs it into Blender's Python.  The default repository is the
[jo-chemla fork](https://github.com/jo-chemla/cesium-native-python/releases)
whose CI builds Linux x86_64, Windows x64 and macOS arm64 wheels for CPython
3.11 to 3.13; switch it to the upstream repository (or to PyPI, with `pip
install cesium-python` in Blender's Python) once wheels are published there.
"Build / install from source" remains for a local checkout.
