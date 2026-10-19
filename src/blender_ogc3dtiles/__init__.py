"""
OGC 3D Tiles Streaming — Blender Addon
=======================================
Requires: Blender 4.3+ (Python 3.12+)
"""

bl_info = {
    "name":     "OGC 3D Tiles Streaming",
    "author":   "Jonathan Chemla",
    "version":  (0, 3, 0),
    "blender":  (4, 3, 0),  # minimum; tested on 5.1,
    "location": "View3D > Sidebar > 3D Tiles",
    "description": "Stream OGC 3D Tiles with cesium-native-python and Cesium-compatible LOD",
    "category": "Import-Export",
}

import sys

if sys.version_info < (3, 11):
    raise RuntimeError(
        f"OGC 3D Tiles requires Python 3.11+ (Blender 4.2+). "
        f"Running: Python {sys.version_info.major}.{sys.version_info.minor}"
    )

# Only import bpy-dependent submodules when actually running inside Blender.
# When imported as a plain Python package (e.g. during tests), these are skipped.
# Testable logic lives in tileset/traversal.py and tileset/backend.py,
# neither of which imports bpy.
if "bpy" in sys.modules:
    import bpy  # noqa: F401
    from . import addon_prefs, tileset, camera, io, materials, ui

    def register():
        addon_prefs.register()
        tileset.register()
        camera.register()
        io.register()
        materials.register()
        ui.register()

    def unregister():
        ui.unregister()
        materials.unregister()
        io.unregister()
        camera.unregister()
        tileset.unregister()
        addon_prefs.unregister()
