"""
Scene-level properties for the 3D Tiles plugin.
Stored on bpy.types.Scene so they persist with the .blend file.
"""
import bpy
from bpy.props import (
    StringProperty, FloatProperty, IntProperty,
    BoolProperty, FloatVectorProperty, EnumProperty, CollectionProperty,
)
from bpy.types import PropertyGroup


class TilesetItem(PropertyGroup):
    """One streamed tileset (list entry in the sidebar)."""
    name: StringProperty(name="Name", default="tileset")
    url: StringProperty(name="Tileset URL", description="tileset.json URL or ion asset id", default="")
    ion_token: StringProperty(name="Ion Token", subtype='PASSWORD', default="")
    enabled: BoolProperty(name="Enabled", description="Stream this tileset", default=True)
    max_sse: FloatProperty(name="Max SSE", default=16.0, min=1.0, max=512.0)


class TilesSceneProps(PropertyGroup):
    """All tileset streaming settings, stored per-scene."""

    # --- Tileset source ---
    tileset_url: StringProperty(
        name="Tileset URL",
        description="URL to tileset.json (http/https) or local file path",
        default="https://assets.cesium.com/1/tileset.json",
    )

    cesium_ion_token: StringProperty(
        name="Cesium Ion Token",
        description="API token for Cesium Ion assets (leave blank for open tilesets)",
        subtype='PASSWORD',
        default="",
    )

    # --- Scene origin (ENU anchor) ---
    origin_lat: FloatProperty(
        name="Origin Latitude",
        description="WGS84 latitude of the Blender scene origin (degrees)",
        default=0.0, min=-90.0, max=90.0,
        precision=8,
    )
    origin_lon: FloatProperty(
        name="Origin Longitude",
        description="WGS84 longitude of the Blender scene origin (degrees)",
        default=0.0, min=-180.0, max=180.0,
        precision=8,
    )
    origin_height: FloatProperty(
        name="Origin Height",
        description="Height above WGS84 ellipsoid at scene origin (metres)",
        default=0.0,
    )
    use_tileset_center: BoolProperty(
        name="Auto-center from Tileset",
        description="Read origin from the tileset bounding volume centre on load",
        default=True,
    )

    # --- LOD / traversal ---
    max_screen_space_error: FloatProperty(
        name="Max Screen Space Error",
        description="Cesium SSE threshold — lower = more detail, more tiles",
        default=16.0, min=1.0, max=512.0,
    )
    max_concurrent_requests: IntProperty(
        name="Max Concurrent Downloads",
        description="Parallel HTTP tile downloads",
        default=6, min=1, max=32,
    )
    max_loaded_tiles: IntProperty(
        name="Max Loaded Tiles",
        description="Evict least-recently-wanted hidden tiles beyond this count",
        default=500, min=10, max=5000,
    )
    load_distance: FloatProperty(
        name="Load Distance (m)",
        description="Tiles beyond this distance from the camera are culled",
        default=20000.0, min=100.0,
    )
    detail_falloff: FloatProperty(
        name="Detail Falloff (m)",
        description=(
            "Dynamic SSE: the refinement threshold grows with distance, "
            "thr = SSE * (1 + dist / falloff). Lower = coarser far away"
        ),
        default=600.0, min=10.0, max=1_000_000.0,
    )
    imports_per_tick: IntProperty(
        name="Imports per tick",
        description="GLBs imported per 50 ms timer tick (1 keeps the UI smooth)",
        default=1, min=1, max=16,
    )
    use_disk_cache: BoolProperty(
        name="Disk cache",
        description="Keep unwrapped GLBs in %LOCALAPPDATA%/blender_ogc3dtiles/cache",
        default=True,
    )

    # --- Tileset list (several sources at once) ---
    tilesets: CollectionProperty(type=TilesetItem)
    active_tileset: IntProperty(default=0)

    # --- State (internal) ---
    is_streaming: BoolProperty(
        name="Streaming Active",
        default=False,
        options={'HIDDEN'},
    )
    status_text: StringProperty(
        name="Status",
        default="Idle",
        options={'HIDDEN'},
    )
    tiles_loaded: IntProperty(default=0, options={'HIDDEN'})
    tiles_pending: IntProperty(default=0, options={'HIDDEN'})


def register():
    print("[OGC3DTiles] registering TilesSceneProps...")
    bpy.utils.register_class(TilesetItem)
    bpy.utils.register_class(TilesSceneProps)
    bpy.types.Scene.ogc3dtiles = bpy.props.PointerProperty(type=TilesSceneProps)
    print("[OGC3DTiles] TilesSceneProps registered OK")


def unregister():
    del bpy.types.Scene.ogc3dtiles
    bpy.utils.unregister_class(TilesSceneProps)
    bpy.utils.unregister_class(TilesetItem)
