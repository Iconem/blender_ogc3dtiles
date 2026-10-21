"""
Scene-level properties for the 3D Tiles plugin.
Stored on bpy.types.Scene so they persist with the .blend file.
"""
import bpy
from bpy.props import (
    StringProperty, FloatProperty, IntProperty,
    BoolProperty, EnumProperty, CollectionProperty,
)
from bpy.types import PropertyGroup


def _on_item_sse(self, context):
    """Push a live SSE edit to the running stream (both backends)."""
    try:
        from ..ui import apply_item_sse
        apply_item_sse(self)
    except Exception:          # noqa: BLE001 — UI not registered (tests)
        pass


def _on_global_sse(self, context):
    try:
        from ..ui import apply_global_sse
        apply_global_sse(self)
    except Exception:          # noqa: BLE001
        pass


def _on_clip_materials(self, context):
    try:
        from .. import materials
        materials.set_clip_materials(bool(self.clip_materials))
    except Exception as e:                        # noqa: BLE001
        print(f"[3DTiles] clip materials: {e}")


def _on_point_radius(self, context):
    from ..io import apply_point_radius
    apply_point_radius(context.scene)


def _on_relight_gold(self, context):
    from .. import materials
    materials.set_gold_enabled(self.relight_gold)


def _on_point_display(self, context):
    from ..io import apply_point_display
    apply_point_display(self.point_display)


def _on_point_scale(self, context):
    from ..io import apply_point_scale
    apply_point_scale(self.point_scale)


def _on_comp_stable(self, context):
    try:
        from .. import compositor
        compositor.set_stable_viewport(context.scene, self.comp_stable_viewport
                                       and compositor.is_built(context.scene))
    except Exception:          # noqa: BLE001
        pass


def _on_comp(self, context):
    """Compositor sliders drive Value nodes of the existing tree (no rebuild)."""
    try:
        from .. import compositor
        compositor.apply_settings(context.scene)
    except Exception:          # noqa: BLE001
        pass


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
    use_own_sse: BoolProperty(
        name="Own SSE", description="Override the global Max SSE for this tileset",
        default=False, update=_on_item_sse)
    max_sse: FloatProperty(name="Max SSE", description="Screen-space error threshold (px) for "
                           "this tileset when 'Own SSE' is ticked; lower = finer tiles. Live",
                           default=4.0, min=1.0, max=512.0, update=_on_item_sse)
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
        name="Max SSE",
        description="Screen-space error threshold in pixels for every tileset without "
                    "'Own SSE'; lower = finer tiles. Live while streaming",
        default=4.0, min=1.0, max=512.0,
        update=_on_global_sse,
    )
    max_concurrent_requests: IntProperty(
        name="Max Concurrent Downloads",
        description="Parallel HTTP tile downloads",
        default=16, min=1, max=64,
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
    foveated_cone: FloatProperty(
        name="Foveation cone",
        description="Fraction of the view half-angle around the view centre that gets "
                    "priority: tiles there load first and keep the full SSE (CesiumJS "
                    "foveatedConeSize). Python backend; cesium-native has its own",
        default=0.3, min=0.0, max=1.0,
    )
    foveated_relaxation: FloatProperty(
        name="Edge SSE relaxation",
        description="Python backend: how much the SSE threshold grows for tiles outside "
                    "the cone (0 = same detail everywhere, 2 = up to 3x coarser at the edges)",
        default=0.0, min=0.0, max=8.0,
    )
    hide_relation_lines: BoolProperty(
        name="Hide relation lines",
        description="Turn off the dashed object→parent lines overlay in every 3D viewport "
                    "when streaming starts (it is a per-viewport overlay, not per object)",
        default=True,
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
        description="Tiles built per 50 ms timer tick (lower keeps the UI smoother "
                    "while loading, higher fills the view faster)",
        default=4, min=1, max=16,
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
            ("DISCS", "Disc splats",
             "Each point becomes an 8-gon disc instance, oriented along the point's "
             "glTF normal when the tile has one, otherwise facing the view. Coloured "
             "in Material Preview / Rendered"),
        ],
        default="POINTS",
        update=_on_point_display,
    )
    point_radius_mode: EnumProperty(
        name="Point radius",
        description="How the display radius of points is chosen",
        items=[
            ("ADAPTIVE", "Adaptive (spacing, px clamp)",
             "Per-tile spacing x Point scale, then clamped between Min / Max pixels on "
             "screen: coarse tiles get bigger points, far points never vanish, near points "
             "never bloat (Potree-style adaptive size)"),
            ("AUTO", "Per tile (spacing)",
             "0.6 x the tile's mean point spacing x Point scale: coarse ADD-refined "
             "tiles get bigger points than fine ones"),
            ("UNIFORM", "Uniform", "One radius for every point of every tile"),
            ("SCREEN", "Screen pixels",
             "Constant size on screen: radius = pixels x distance to the eye (viewport while "
             "streaming, scene camera when rendering), clamped to Min / Max metres. "
             "Like 3DTilesRendererJS' point size with attenuation"),
        ],
        default="ADAPTIVE",
        update=_on_point_radius,
    )
    point_adapt_min_px: FloatProperty(
        name="Min size (px)", description="Adaptive mode: points never smaller than this on screen",
        default=2.0, min=0.0, max=64.0, update=_on_point_radius,
    )
    point_adapt_max_px: FloatProperty(
        name="Max size (px)", description="Adaptive mode: points never larger than this on screen",
        default=12.0, min=0.5, max=256.0, update=_on_point_radius,
    )
    point_px: FloatProperty(
        name="Point size (px)", description="Screen mode: point diameter in pixels",
        default=3.0, min=0.5, max=64.0, update=_on_point_radius,
    )
    point_px_min_m: FloatProperty(
        name="Min radius (m)", default=0.005, min=0.0, max=10.0, update=_on_point_radius,
    )
    point_px_max_m: FloatProperty(
        name="Max radius (m)", default=2.0, min=0.01, max=100.0, update=_on_point_radius,
    )
    comp_edges: EnumProperty(
        name="Edges",
        description="Edge darkening in the beauty compositor",
        items=[
            ("EDL", "Eye-dome lighting", "From the depth pass: silhouettes and concavities, "
                                         "ignores flat tile borders"),
            ("NORMAL", "Normal creases", "Sobel on the normal pass: ink-like creases, also traces "
                                         "tile borders where per-tile normals disagree"),
            ("BOTH", "Both", "Multiply both"),
        ],
        default="EDL",
        update=_on_comp,
    )
    comp_edl_strength: FloatProperty(
        name="EDL strength", description="Eye-dome lighting: how dark a pixel behind its "
                                         "neighbourhood gets (0 = off)",
        default=4.0, min=0.0, max=30.0, update=_on_comp,
    )
    comp_crease_strength: FloatProperty(
        name="Crease strength", description="Normal-pass Sobel creases: ink darkness (0 = off)",
        default=1.0, min=0.0, max=5.0, update=_on_comp,
    )
    comp_ao: FloatProperty(
        name="AO", description="Ambient-occlusion pass multiply (0 = off)",
        default=0.5, min=0.0, max=1.0, update=_on_comp,
    )
    comp_haze: FloatProperty(
        name="Haze", description="Mist-pass haze towards a pale sky colour (0 = off)",
        default=0.35, min=0.0, max=1.0, update=_on_comp,
    )
    point_radius: FloatProperty(
        name="Point radius (m)", description="Uniform point radius",
        default=0.08, min=0.001, max=50.0, update=_on_point_radius,
    )
    clip_materials: BoolProperty(
        name="Clip materials to viewport region",
        description="Copy the 3D viewport's clipping region (Alt+B) into every tile "
                    "material so Material Preview and Rendered clip too (EEVEE ignores "
                    "the region itself); follows Alt+B on / off while enabled",
        default=False, update=_on_clip_materials,
    )
    relight_gold: BoolProperty(
        name="Gold transfer",
        description="Relight: metallic / glossy treatment of yellow, saturated albedo",
        default=False, update=_on_relight_gold,
    )
    comp_stable_viewport: BoolProperty(
        name="Stable viewport",
        description="While the beauty compositor is on, render the viewport with a single "
                    "TAA sample: EEVEE jitters each accumulated sample by a sub-pixel offset "
                    "and the Depth / Normal passes are not accumulated, so EDL and creases "
                    "shimmer by 1 px until convergence. One sample = no shimmer, no AA",
        default=True, update=_on_comp_stable,
    )
    comp_prev_taa: IntProperty(default=0, options={'HIDDEN'})
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
