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


def _on_item_sse(self, context):
    """Push a live SSE edit to the running stream (both backends)."""
    try:
        from ..ui import apply_item_sse
        apply_item_sse(self)
    except Exception:          # noqa: BLE001 — UI not registered (tests)
        pass


def _on_point_display(self, context):
    from ..io import apply_point_display
    apply_point_display(self.point_display)


def _on_point_scale(self, context):
    from ..io import apply_point_scale
    apply_point_scale(self.point_scale)


class TilesetItem(PropertyGroup):
    """One streamed tileset (list entry in the sidebar)."""
    name: StringProperty(name="Name", default="tileset")
    url: StringProperty(name="Tileset URL", description="tileset.json URL or ion asset id", default="")
    ion_token: StringProperty(name="Ion Token", subtype='PASSWORD', default="")
    enabled: BoolProperty(
        name="Stream",
        description="Stream this tileset. Unticked = paused: nothing is loaded or evicted "
                    "(use the eye to hide the loaded tiles)",
        default=True)
    max_sse: FloatProperty(name="Max SSE", description="Screen-space error threshold (px); "
                           "lower = finer tiles. Takes effect while streaming",
                           default=16.0, min=1.0, max=512.0, update=_on_item_sse)
    uid: StringProperty(default="", options={'HIDDEN'})


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
    origin_mode: EnumProperty(
        name="Origin",
        description="How the scene origin (ENU anchor) is chosen when streaming starts",
        items=[
            ("AUTO", "Auto",
             "Centre on the first tileset; later starts keep the current origin when the "
             "new tileset is within 'Reuse within' km of it (CloudCompare-style)"),
            ("KEEP", "Keep current", "Never move the origin once it has been set"),
            ("CUSTOM", "Custom", "Use the latitude / longitude / height entered below"),
        ],
        default="AUTO",
    )
    origin_reuse_km: FloatProperty(
        name="Reuse within (km)",
        description="Auto mode: keep the existing origin if the new tileset centre is "
                    "closer than this",
        default=10.0, min=0.0, max=20000.0,
    )
    origin_valid: BoolProperty(default=False, options={'HIDDEN'})

    # --- LOD / traversal ---
    max_screen_space_error: FloatProperty(
        name="SSE for new tilesets",
        description="Default screen-space error for tilesets added to the list "
                    "(edit the per-tileset Max SSE to change a running stream)",
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
    auto_relight: BoolProperty(
        name="Relight new tiles",
        description="Give every newly imported tile the shared 'OGC3D Relight' node group "
                    "(roughness / gold mask / shadow lift derived from the albedo)",
        default=False,
    )
    point_display: EnumProperty(
        name="Point display",
        description="How vertex-only (pnts / glTF POINTS) tiles are shown",
        items=[
            ("POINTS", "Point cloud",
             "Mesh → Points (cheapest). Coloured in Material Preview / Rendered; "
             "Solid mode draws them with the material colour only"),
            ("MESH", "Tiny tetrahedra",
             "Each point becomes a 4-vertex tetrahedron. Also coloured in Solid mode "
             "(set Viewport Shading → Color → Attribute); ~4x the geometry"),
        ],
        default="POINTS",
        update=_on_point_display,
    )
    point_scale: FloatProperty(
        name="Point scale",
        description="Multiplier on the per-tile point radius (radius = 0.6 x mean point spacing)",
        default=1.0, min=0.05, max=20.0,
        update=_on_point_scale,
    )
    native_direct_mesh: BoolProperty(
        name="Direct mesh (native)",
        description="cesium-native backend: build Blender meshes from numpy arrays "
                    "instead of re-importing a GLB (faster; off = use the glTF importer)",
        default=True,
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
