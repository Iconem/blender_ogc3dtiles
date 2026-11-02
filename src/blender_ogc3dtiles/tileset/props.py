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


def _on_backface_mode(self, context):
    try:
        from .. import materials
        materials.set_backface_mode(self.backface_mode)
    except Exception as e:                        # noqa: BLE001
        print(f"[3DTiles] backface mode: {e}")


def _on_tile_geometry(self, context):
    try:
        from .. import io
        io.set_tile_geometry(bool(self.tile_geometry))
    except Exception as e:                        # noqa: BLE001
        print(f"[3DTiles] tile geometry nodes: {e}")


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


def _on_overlay_alpha(self, context):
    from ..overlays import set_overlay_alpha
    set_overlay_alpha(self.uid, self.alpha)


def _on_overlay_edit(self, context):
    """Type / URL / key / layer / levels edited: re-create the overlay on a
    running tileset (cesium-native drops its rasters and loads the new ones)."""
    from ..ui import overlay_live_refresh
    overlay_live_refresh(context.scene, self)


def _on_overlay_enabled(self, context):
    """Ticking an overlay while its tileset streams adds it to the running
    cesium-native tileset (loaded tiles are reloaded with the new texture
    coordinates); unticking removes it."""
    from ..ui import overlay_live_toggle
    overlay_live_toggle(context.scene, self)


OVERLAY_KINDS = [
    ("URL", "URL template", "XYZ template with {z}/{x}/{y} (web mercator, y from the north: OSM, "
     "Esri, MapTiler...); write {-y} for TMS-ordered servers"),
    ("TMS", "TMS", "Tile Map Service root (tilemapresource.xml)"),
    ("WMTS", "WMTS", "OGC Web Map Tile Service (KVP or REST url, layer, style, tile matrix set)"),
    ("WMS", "WMS", "OGC Web Map Service (layers, format)"),
    ("ION", "Cesium ion", "ion imagery asset id + token"),
    ("BING", "Bing Maps", "Bing Maps imagery (key, style)"),
    ("GOOGLE", "Google Map Tiles", "Google Map Tiles API 2D imagery (API key)"),
    ("DEBUG", "Debug colours", "cesium-native's tile colouriser (no server)"),
]


def _on_place_query(self, context):
    from ..ui import _on_place_query as cb
    cb(self, context)


class OverlayItem(PropertyGroup):
    """A raster overlay draped on one tileset (cesium-native backend)."""
    name: StringProperty(name="Name", default="overlay")
    kind: EnumProperty(name="Type", items=OVERLAY_KINDS, default="URL", update=_on_overlay_edit)
    url: StringProperty(name="URL", description="Service URL / template / TMS root / WMTS "
                        "or WMS endpoint; ion asset id for Cesium ion", default="", update=_on_overlay_edit)
    key: StringProperty(name="Key / token", description="API key or access token",
                        subtype='PASSWORD', default="", update=_on_overlay_edit)
    layer: StringProperty(name="Layer", description="WMTS layer / WMS layers / Bing style "
                          "(Aerial, AerialWithLabels, Road) / Google map type (satellite, roadmap)",
                          default="", update=_on_overlay_edit)
    style: StringProperty(name="Style", description="WMTS style (default 'default')", default="default", update=_on_overlay_edit)
    matrix_set: StringProperty(name="Matrix set", description="WMTS tile matrix set id "
                               "(e.g. GoogleMapsCompatible, EPSG:3857)", default="", update=_on_overlay_edit)
    image_format: StringProperty(name="Format", description="WMTS / WMS image MIME type",
                                 default="image/png", update=_on_overlay_edit)
    min_level: IntProperty(name="Min level", default=0, min=0, max=30, update=_on_overlay_edit)
    max_level: IntProperty(name="Max level", default=19, min=0, max=30, update=_on_overlay_edit)
    detail_px: FloatProperty(
        name="Raster detail (px)",
        description="Imagery resolution target: one raster pixel covers at most this many screen "
                    "pixels (cesium-native's raster screen-space error; Cesium's default is 2). "
                    "Higher = coarser imagery, far fewer downloads, tiles show sooner. Live",
        default=4.0, min=1.0, max=64.0, update=_on_overlay_edit)
    enabled: BoolProperty(name="Use", description="Drape this overlay (live: loaded tiles are "
                          "reloaded with the overlay)", default=True, update=_on_overlay_enabled)
    alpha: FloatProperty(name="Opacity", description="Blend over the tile textures (live)",
                         default=1.0, min=0.0, max=1.0, update=_on_overlay_alpha)
    uid: StringProperty(default="", options={'HIDDEN'})


TILESET_KINDS = [
    ("TILESET", "3D Tiles", "tileset.json URL or local path"),
    ("ION", "Cesium ion", "Cesium ion asset (asset id + access token; needs the cesium-native backend)"),
    ("GLOBE", "WGS84 globe", "cesium-native's procedural ellipsoid: a bare globe to drape raster "
     "overlays on (needs the cesium-native backend)"),
]


def _on_clip_edit(self, context):
    """Clipping list / mode edited: rebuild the masks of a running tileset."""
    from ..ui import clip_mark_dirty
    clip_mark_dirty(context.scene, self)


def _clip_object_poll(self, obj):
    return obj.type in {"MESH", "CURVE"} and "tile_url" not in obj


CLIP_SHAPES = [
    ("CLIP_POLYGON", "Clip-polygon", "Each closed outline of the object, seen from above, extruded "
     "along the tileset's Z without limit (like Cesium's clipping polygons)"),
    ("BOX", "Box", "The object's bounding box with its location, rotation and scale: "
     "clips in 3D, so it can cut the top of a building only"),
]


class ClipPolygonItem(PropertyGroup):
    """A Blender object that clips a tileset: its outline seen from above
    (clip-polygon) or its bounding box (box)."""
    obj: bpy.props.PointerProperty(
        name="Object", type=bpy.types.Object, poll=_clip_object_poll,
        description="Mesh or curve. Clip-polygon: each closed outline (boundary edges, or the edges "
                    "of a face-less mesh / curve), seen from above, is one polygon. Box: the "
                    "object's bounding box. Moving or editing it updates the cut",
        update=_on_clip_edit)
    enabled: BoolProperty(name="Use", default=True, update=_on_clip_edit)
    shape: EnumProperty(name="Shape", items=CLIP_SHAPES, default="CLIP_POLYGON", update=_on_clip_edit)


# value: (combine op over the volumes, term per volume)
CLIP_MODES = [
    ("CUT_ANY", "Cut inside any", "Remove what is inside at least one volume (their union)"),
    ("CUT_ALL", "Cut inside all", "Remove only what is inside every volume (their overlap)"),
    ("KEEP_ANY", "Keep inside any", "Keep what is inside at least one volume: removes what "
     "is outside all of them"),
    ("KEEP_ALL", "Keep inside all", "Keep only the overlap of the volumes: removes what is "
     "outside any of them"),
]


def _on_item_kind(self, context):
    # a bare globe is only useful with imagery on it
    if self.kind == "GLOBE":
        self.use_overlays = True


def _on_item_use_overlays(self, context):
    from ..ui import overlays_live_toggle
    overlays_live_toggle(context.scene, self)


class TilesetItem(PropertyGroup):
    """One streamed tileset (list entry in the sidebar)."""
    name: StringProperty(name="Name", default="tileset")
    kind: EnumProperty(name="Type", items=TILESET_KINDS, default="TILESET", update=_on_item_kind)
    url: StringProperty(name="Tileset URL", description="tileset.json URL or local path", default="")
    ion_asset_id: IntProperty(name="Asset id", description="Cesium ion asset id", default=0, min=0)
    ion_token: StringProperty(name="Ion Token", description="Cesium ion access token (only sent "
                              "to Cesium ion)", subtype='PASSWORD', default="")
    use_overlays: BoolProperty(
        name="Raster overlays",
        description="Drape raster imagery on this entry (cesium-native backend). Live",
        default=False, update=_on_item_use_overlays)
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
    overlays: CollectionProperty(type=OverlayItem)
    active_overlay: IntProperty(default=0)
    use_clipping: BoolProperty(
        name="Clipping",
        description="Cut this tileset with Blender objects: vertical polygons from their "
                    "outlines, or 3D boxes. Meshes, point clouds and splats. Live",
        default=False, update=_on_clip_edit)
    clip_mode: EnumProperty(name="Mode", items=CLIP_MODES, default="CUT_ANY",
                            update=_on_clip_edit)
    clip_geometry: BoolProperty(
        name="Cut Geometry",
        description="Also delete the mesh faces that are entirely cut (Geometry Nodes), so "
                    "Solid view, snapping and exports see the cut. Faces across the boundary "
                    "stay whole outside the Material and Rendered views. Costs some viewport "
                    "time per tile",
        default=False, update=_on_clip_edit)
    clip_polygons: CollectionProperty(type=ClipPolygonItem)
    active_clip: IntProperty(default=0)


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
            ("SEARCH", "Search place", "Find a place by name (Photon, OpenStreetMap) and put the "
             "origin on the ground there; until a place is picked, behaves like Auto"),
        ],
        default="AUTO",
    )
    place_query: StringProperty(
        name="Place", description="Place name to search (Enter runs the search)",
        default="", update=_on_place_query)
    place_status: StringProperty(default="", options={'SKIP_SAVE'})
    origin_place: StringProperty(name="Place", description="Name of the picked place", default="")
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
                    "while loading, higher fills the view faster). Live",
        default=4, min=1, max=16,
    )
    nav_build_ms: FloatProperty(
        name="Build budget while navigating (ms)",
        description="While the view moves (and 0.3 s after), tile building gets this many "
                    "milliseconds per tick instead of the Imports / tick budget, so orbiting "
                    "stays fluid; loading catches up once the view rests. 0 = no change",
        default=8.0, min=0.0, max=200.0,
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
        default=True, update=_on_clip_materials,
    )
    backface_mode: EnumProperty(
        name="Faces",
        description="Back-face handling of every tile material (EEVEE and Cycles)",
        items=[
            ("DOUBLE", "Force double-sided", "Never cull back faces: clipped or open meshes "
                                            "show their inside"),
            ("SINGLE", "Force single-sided", "Cull back faces everywhere"),
            ("MATERIAL", "Material setting", "Keep what the tile declared (glTF doubleSided; "
                                             "most photogrammetry exports are single-sided)"),
        ],
        default="DOUBLE", update=_on_backface_mode,
    )
    tile_geometry: BoolProperty(
        name="Shared geometry nodes",
        description="Put the shared 'OGC3D Tile Geometry' Geometry Nodes modifier on every "
                    "tile (loaded and streamed later), first in the stack, so one graph "
                    "edits the geometry of all tiles; starts as a pass-through",
        default=False, update=_on_tile_geometry,
    )
    view_source: EnumProperty(
        name="Stream for",
        description="Which view decides tile selection and LOD",
        items=[
            ("VIEWPORT", "3D viewport", "The largest 3D viewport (interactive use)"),
            ("CAMERA", "Scene camera", "The active scene camera at the render resolution "
                                       "(scrubbing the timeline re-selects tiles)"),
        ],
        default="VIEWPORT",
    )
    render_settle_s: FloatProperty(
        name="Settle time",
        description="Converged animation render: seconds without any tile change (and an "
                    "empty queue) before a frame is rendered",
        default=1.0, min=0.0, max=60.0,
    )
    render_warmup_s: FloatProperty(
        name="Warm-up",
        description="Converged animation render: minimum wait before the first frame (empty "
                    "scene, cold cache); later frames only need the settle time because a "
                    "smooth camera path changes little between frames",
        default=10.0, min=0.0, max=600.0,
    )
    render_max_wait_s: FloatProperty(
        name="Max wait",
        description="Converged animation render: render the frame anyway after this many "
                    "seconds, even if tiles are still arriving",
        default=120.0, min=1.0, max=3600.0,
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
    bpy.utils.register_class(OverlayItem)
    bpy.utils.register_class(ClipPolygonItem)
    bpy.utils.register_class(TilesetItem)
    bpy.utils.register_class(TilesSceneProps)
    bpy.types.Scene.ogc3dtiles = bpy.props.PointerProperty(type=TilesSceneProps)
    print("[OGC3DTiles] TilesSceneProps registered OK")


def unregister():
    del bpy.types.Scene.ogc3dtiles
    bpy.utils.unregister_class(TilesSceneProps)
    bpy.utils.unregister_class(TilesetItem)
    bpy.utils.unregister_class(ClipPolygonItem)
    bpy.utils.unregister_class(OverlayItem)
