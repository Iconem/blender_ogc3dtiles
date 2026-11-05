---
title: "Building the cesium-native wheel"
description: "Build cesium-native-python for Blender's Python"
---

The add-on installs pre-built wheels (see
[Installing the native backend](#installing-the-native-backend)).  The build
fixes for Windows, manylinux and macOS were merged upstream
([cesium-native-python#3](https://github.com/calebbuffa/cesium-native-python/pull/3),
October 2026), so `pip install .` works from a plain checkout; the
cibuildwheel workflow that publishes wheels
([#4](https://github.com/calebbuffa/cesium-native-python/pull/4)) is under
review, and the jo-chemla fork publishes them meanwhile.  This repository's
manual `cesium-native-wheel.yml` workflow predates both.
