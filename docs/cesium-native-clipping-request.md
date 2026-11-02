# Drafts: geometry clipping upstream

Posted: [cesium-native#1486](https://github.com/CesiumGS/cesium-native/issues/1486).
The optional comment on #1307 was dropped. Anything else public needs Jonathan's OK.

## Edit to the version comment on calebbuffa/cesium-native-python#2

To add to the [comment of 2026-10-23](https://github.com/calebbuffa/cesium-native-python/issues/2#issuecomment-6369381939).
Also change its "current is `v0.65`" to `v0.66`.

> - `v0.66` (2026-11-02) fixes memory-safety bugs on malformed files: a heap overflow in Draco decoding and an integer overflow in `EXT_meshopt_compression`. Tilesets using both are common, so they're a reason to bump for anyone opening third-party data.
> - `GltfModifier` needs no bump, it's been there since `v0.53`, but a Python subclass fails today with "Tried to call pure virtual function GltfModifier.apply": the trampoline in `Tiles3dSelectionBindings.cpp` calls `get_override` through `GltfModifier`, a type pybind11 doesn't know. Casting to `PyGltfModifier` there fixes it, in #7. cesium-native#1307, once merged, makes modifiers work with raster overlays, and would need a bump.
