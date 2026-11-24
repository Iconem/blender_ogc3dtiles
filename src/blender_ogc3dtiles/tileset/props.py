"""
Scene-level properties for the 3D Tiles plugin.
Stored on bpy.types.Scene so they persist with the .blend file.
"""
import bpy
from bpy.props import (
    StringProperty, FloatProperty, IntProperty,
    BoolProperty, EnumProperty, CollectionProperty, FloatVectorProperty,
)
from bpy.types import PropertyGroup


def _dataset_names(self, context, edit_text):
    try:
        from .. import dataset_empties
        return dataset_empties.names_matching(edit_text)
    except Exception:          # noqa: BLE001
        return []


def _on_origin_dataset(self, context):
    try:
        from ..ui import origin_to_dataset
        origin_to_dataset(context, self)
    except Exception as e:     # noqa: BLE001
        print(f"[3DTiles] origin at dataset: {e}")


def _on_item_url(self, context):
    """A typed or pasted path on a mapped network drive (Z:) becomes its share path, as a browsed one does
    (preference 'Mapped drives as UNC'). Comes back here once with the share path, which is left alone."""
    try:
        from .. import paths
        from ..io import addon_pref
        u = self.url.strip().strip('"')
        if paths.is_local_path(u) and addon_pref("mapped_drives_as_unc", True):
            unc = paths.mapped_drive_unc(u)
            if unc and unc != self.url:
                self.url = unc
    except Exception:          # noqa: BLE001
        pass


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


def _on_concurrent_requests(self, context):
    try:
        from ..ui import _state
        for st in _state["streams"].values():
            b = st.get("backend")
            if b is not None and hasattr(b, "set_max_loads"):
                b.set_max_loads(self.max_concurrent_requests)
    except Exception:          # noqa: BLE001
        pass


def _on_tile_bounds(self, context):
    try:
        from .. import tile_bounds
        tile_bounds.enable(self.tile_bounds != "OFF")
    except Exception:          # noqa: BLE001
        pass


def _on_tile_bounds_look(self, context):
    try:
        from .. import tile_bounds
        tile_bounds.invalidate()
    except Exception:          # noqa: BLE001
        pass


def _on_dataset_marker_size(self, context):
    try:
        from .. import dataset_empties
        dataset_empties.resize(context.scene)
    except Exception as e:                        # noqa: BLE001
        print(f"[3DTiles] dataset markers: {e}")


def _on_meta_color(self, context):
    try:
        from .. import materials
        materials.set_metadata_colors(context.scene)
    except Exception as e:                        # noqa: BLE001
        print(f"[3DTiles] metadata colors: {e}")


def _on_phase_year(self, context):
    try:
        from .. import phases
        phases.apply_year(context.scene)
    except Exception as e:                        # noqa: BLE001
        print(f"[3DTiles] phases: {e}")


def _on_voxel_project(self, context):
    try:
        from .. import voxel_lookup
        voxel_lookup.sync_materials(context.scene)
        voxel_lookup.update_settings(context.scene)
    except Exception as e:                        # noqa: BLE001
        print(f"[3DTiles] voxel colors: {e}")


def _on_voxel_opacity(self, context):
    try:
        from .. import materials
        materials.update_voxel_volume_material(context.scene)
    except Exception as e:                        # noqa: BLE001
        print(f"[3DTiles] voxel opacity: {e}")


def _on_meta_source(self, context):
    self["meta_range_custom"] = False
    self["meta_color"] = True                 # picking what to color by switches the coloring on
    try:
        from .. import materials
        if self.meta_source == "ELEVATION":
            materials.elevation_range(context.scene, rescan=True)
        if self.meta_color:
            materials.set_metadata_colors(context.scene)
        else:
            materials.update_metadata_group(context.scene)
    except Exception as e:                        # noqa: BLE001
        print(f"[3DTiles] color by: {e}")


def _on_meta_column(self, context):
    self["meta_range_custom"] = False
    try:
        from .. import materials, voxel_lookup
        from ..io import refresh_feature_attributes
        refresh_feature_attributes(context.scene)
        materials.update_metadata_group(context.scene)
        voxel_lookup.rebuild(context.scene)
    except Exception as e:                        # noqa: BLE001
        print(f"[3DTiles] metadata column: {e}")


def _on_meta_range(self, context):
    from .. import materials
    materials.update_metadata_group(context.scene)


def _on_meta_range_custom(self, context):
    from .. import materials
    from ..tileset.feature_meta import REGISTRY
    col = REGISTRY.get(self.meta_column)
    if self.meta_range_custom and self.meta_source == "ELEVATION":
        self["meta_range_min"], self["meta_range_max"] = materials.elevation_range(context.scene)
    elif self.meta_range_custom and self.meta_source == "OBJECT":
        self["meta_range_min"], self["meta_range_max"] = materials.tile_value_range(context.scene)
    elif self.meta_range_custom and col is not None and col.hi >= col.lo:
        self["meta_range_min"], self["meta_range_max"] = col.lo, col.hi     # no update per value
    materials.update_metadata_group(context.scene)


def _on_meta_strength(self, context):
    try:
        from .. import materials
        materials.update_metadata_group(context.scene)
    except Exception as e:                        # noqa: BLE001
        print(f"[3DTiles] metadata strength: {e}")


def _on_meta_class_color(self, context):
    try:
        from .. import materials
        materials.write_palette(context.scene)
    except Exception as e:                        # noqa: BLE001
        print(f"[3DTiles] metadata palette: {e}")


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


def _on_shadeless(self, context):
    from .. import materials
    materials.apply_shadeless(context.scene)


def _on_xray(self, context):
    from .. import xray
    xray.apply(context.scene)


def _on_xray_params(self, context):
    from .. import xray
    xray.update_params(self)


def _on_point_display(self, context):
    from ..io import apply_point_display
    apply_point_display(self.point_display)


def _on_point_scale(self, context):
    from ..io import apply_point_scale
    apply_point_scale(self.point_scale)


def _on_relight(self, context):
    try:
        from .. import materials
        materials.set_relight(bool(self.auto_relight))
        if self.auto_relight:                     # the shared nodes are for the lit look: leave Shadeless and X-ray
            if self.xray:
                self.xray = False
            if self.shadeless:
                self.shadeless = False
    except Exception as e:                        # noqa: BLE001
        print(f"[3DTiles] relight: {e}")


def _on_comp_enabled(self, context):
    try:
        from .. import compositor
        compositor.set_enabled(context, bool(self.comp_enabled))
    except Exception as e:                        # noqa: BLE001
        print(f"[3DTiles] compositor: {e}")


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
    from .native_backend import decode_braces
    url = decode_braces(self.url)
    if url != self.url:
        self.url = url      # shows the braces, and comes back here once
        return
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


def _on_origin_edit(self, context):
    from .origin import on_origin_edit
    on_origin_edit(self, context)


def _on_origin_text(self, context):
    from .origin import parse_origin_text, set_origin
    if not self.origin_text:
        self.origin_text_status = ""
        return
    lla = parse_origin_text(self.origin_text)
    if lla is None:
        self.origin_text_status = "Expected: latitude, longitude[, height]"
        return
    set_origin(self, *lla)
    self.origin_valid = True
    self.origin_text_status = f"Origin set: {lla[0]:.8f}, {lla[1]:.8f}, {lla[2]:.3f} m"


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
    ("TERRAIN", "Quantized-mesh terrain", "layer.json URL of a quantized-mesh server, streamed like a "
     "tileset (needs the cesium-native backend). For Cesium World Terrain, use a Cesium ion entry"),
]


def _on_relation_lines(self, context):
    from ..ui import _set_relationship_lines
    _set_relationship_lines(context, not self.hide_relation_lines)


def _on_clip_edit(self, context):
    """Clipping list / mode edited: rebuild the masks of a running tileset."""
    from ..ui import clip_mark_dirty
    clip_mark_dirty(context.scene, self)


def _camera_poll(self, obj):
    return obj.type == "CAMERA"


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
    # bare ground is only useful with imagery on it
    if self.kind in ("GLOBE", "TERRAIN"):
        self.use_overlays = True


def _on_item_use_overlays(self, context):
    from ..ui import overlays_live_toggle
    overlays_live_toggle(context.scene, self)


class MetaColumnItem(PropertyGroup):
    kind: StringProperty()         # "number" or "class"
    # range of a number column, kept in the file so a reopened .blend still
    # knows it (the registry the workers fill lives in memory only)
    lo: FloatProperty()
    hi: FloatProperty(default=-1.0)   # hi < lo: no range stored


class MetaClassItem(PropertyGroup):
    column: StringProperty()
    code: IntProperty()
    color: FloatVectorProperty(
        name="Color", subtype="COLOR", size=3, min=0.0, max=1.0,
        update=_on_meta_class_color,
    )
    alpha: FloatProperty(
        name="Opacity", description="Opacity of this class: 0 hides it (the ground of a LiDAR "
                                    "cloud, for one)",
        subtype="FACTOR", default=1.0, min=0.0, max=1.0, update=_on_meta_class_color,
    )


class TilesetItem(PropertyGroup):
    """One streamed tileset (list entry in the sidebar)."""
    name: StringProperty(name="Name", default="tileset")
    kind: EnumProperty(name="Type", items=TILESET_KINDS, default="TILESET", update=_on_item_kind)
    url: StringProperty(name="Tileset URL", description="tileset.json URL or local path", default="",
                        update=_on_item_url)
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
        name="Override Max SSE", description="Stream this tileset with its own Max SSE instead of the "
                                             "scene's (LOD / Streaming)",
        default=False, update=_on_item_sse)
    max_sse: FloatProperty(name="Max SSE", description="Screen-space error threshold (px) for "
                           "this tileset when 'Override Max SSE' is ticked; lower = finer tiles. Live",
                           default=8.0, min=1.0, max=512.0, update=_on_item_sse)
    uid: StringProperty(default="", options={'HIDDEN'})
    # dataset_empties: {external tileset URL: the 16 numbers of its Empty's own matrix}, as JSON
    dataset_offsets: StringProperty(default="", options={'HIDDEN'})
    overlays: CollectionProperty(type=OverlayItem)
    active_overlay: IntProperty(default=0)
    use_clipping: BoolProperty(
        name="Clipping",
        description="Cut this tileset with Blender objects: vertical polygons from their "
                    "outlines, or 3D boxes. Meshes, point clouds and splats. Live",
        default=False, update=_on_clip_edit)
    clip_mode: EnumProperty(name="Mode", items=CLIP_MODES, default="KEEP_ANY",
                            update=_on_clip_edit)
    clip_geometry: BoolProperty(
        name="Slower: Also cut in solid view/exports",
        description="Also delete the mesh faces that are entirely cut (Geometry Nodes), so "
                    "Solid view, snapping and exports see the cut. Faces across the boundary "
                    "stay whole outside the Material and Rendered views. Costs some viewport "
                    "time per tile",
        default=True, update=_on_clip_edit)
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
        precision=8, update=_on_origin_edit,
    )
    origin_lon: FloatProperty(
        name="Origin Longitude",
        description="WGS84 longitude of the Blender scene origin (degrees)",
        default=0.0, min=-180.0, max=180.0,
        precision=8, update=_on_origin_edit,
    )
    origin_height: FloatProperty(
        name="Origin Height",
        description="Height above WGS84 ellipsoid at scene origin (metres)",
        default=0.0, update=_on_origin_edit,
    )
    origin_text: StringProperty(
        name="Paste",
        description="Paste 'latitude, longitude[, height]' with full precision: the three fields "
                    "above are single precision (up to 0.7 m at longitude 150), this is not",
        default="", update=_on_origin_text)
    origin_text_status: StringProperty(default="", options={'SKIP_SAVE'})
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
            ("DATASET", "Dataset", "Put the origin at a dataset of a tileset of tilesets, picked by the "
             "name of its Empty (cesium-native backend, 'An Empty per dataset'); until one is "
             "picked, behaves like Auto"),
        ],
        default="AUTO",
    )
    origin_dataset: StringProperty(
        name="Dataset",
        description="Name of a dataset's Empty: the scene origin goes to its centre, at its height "
                    "(the Empty's Location Z included), and a running stream restarts there. The list "
                    "holds the datasets loaded so far in this session",
        default="", search=_dataset_names, update=_on_origin_dataset)
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
                    "its own (Override Max SSE); lower = finer tiles. Live while streaming",
        default=8.0, min=1.0, max=512.0,
        update=_on_global_sse,
    )
    max_concurrent_requests: IntProperty(
        name="Concurrent Requests",
        description="Tiles requested at once, per tileset. cesium-native: tile loads in flight "
                    "(download and decoding), live; 20 is its own default. Python backend: "
                    "parallel downloads, applied at the next Start",
        default=20, min=1, max=64, update=_on_concurrent_requests,
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
        description="Turn off the dashed object→parent lines overlay in every 3D viewport, "
                    "now and when streaming starts (it is a per-viewport overlay, not per "
                    "object)",
        default=True, update=_on_relation_lines,
    )
    native_cache_mb: IntProperty(
        name="cesium-native cache (MB)",
        description="Not a cap on what is shown. cesium-native only uses it to decide how "
                    "many tiles to keep once they are no longer shown, so that returning to "
                    "a view is instant. Tiles in view are never dropped, even far over the "
                    "limit. Counts cesium-native's own copy in RAM, not Blender's meshes or "
                    "GPU memory. Applies at the next Start",
        default=512, min=0, soft_max=8192,
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
        description="Tiles built per 50 ms tick of the streaming loop (update and draw of the "
                    "viewport): lower keeps the UI smoother while loading, higher fills the view "
                    "faster. Converged renders wait for every tile whatever it is. Live",
        default=4, min=1, max=16,
    )
    max_elements_m: FloatProperty(
        name="Max points / vertices (millions)",
        description="Cap on the points and mesh vertices shown, all tilesets together. "
                    "Over it, every tileset is streamed coarser (its SSE is multiplied) until "
                    "the view fits; detail returns when there is room. 0 = no cap. Live",
        default=0.0, min=0.0, soft_max=100.0, step=50, precision=1,
    )
    nav_build_ms: FloatProperty(
        name="Build budget while navigating (ms)",
        description="While the view moves (and 0.3 s after), tile building gets this many "
                    "milliseconds per tick instead of the Imports / tick budget, so orbiting "
                    "stays fluid; loading catches up once the view rests. 0 = no change",
        default=8.0, min=0.0, max=200.0,
    )
    auto_relight: BoolProperty(
        name="Shared shader nodes",
        description="Put the shared 'OGC3D Relight' node group in every tile material, "
                    "loaded and streamed later (roughness / gold mask / shadow lift derived "
                    "from the albedo). Off restores the plain material and keeps the group",
        default=False, update=_on_relight,
    )
    comp_enabled: BoolProperty(
        name="Beauty compositor nodes",
        description="Use the 'OGC3D Beauty' compositor tree on this scene (edges, AO, grade, "
                    "haze, glare), shown in Rendered viewport shading. Off detaches it and "
                    "keeps the tree",
        default=False, update=_on_comp_enabled,
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
    shadeless: BoolProperty(
        name="Shadeless",
        description="Show every tile's colours as they are, without any light: lamps, sun and world do "
                    "nothing and nothing casts shadows. For photogrammetry and scans that already carry the "
                    "light they were captured in. With the shared shader nodes it sets their Baked Light to 1. "
                    "Live",
        default=False,
        update=_on_shadeless,
    )
    xray: BoolProperty(
        name="X-ray",
        description="Show point clouds and Gaussian splats (and meshes, with Meshes) as an X-ray: every point "
                    "adds a little light and hides nothing, so walls seen edge-on, vaults and the far side "
                    "of a building show through. Needs a dark background (World colour, or a transparent film over "
                    "black); best in Eevee. Live",
        default=False,
        update=_on_xray,
    )
    xray_strength: FloatProperty(
        name="Strength",
        description="Light added by each point, and by each mesh face seen edge-on. Lower it where the cloud is "
                    "dense, or many walls line up, and it burns to white",
        default=0.3, min=0.001, soft_max=2.0, max=50.0, precision=3, update=_on_xray_params,
    )
    xray_radius: FloatProperty(
        name="Splat radius (m)",
        description="Radius of the points Gaussian splats become while X-ray is on (point clouds keep the "
                    "size their display gives them)",
        default=0.05, min=0.001, soft_max=1.0, max=50.0, precision=3, update=_on_xray_params,
    )
    xray_meshes: BoolProperty(
        name="Meshes",
        description="X-ray the mesh tiles as well as points and splats: every face adds its texture colour as light and hides nothing, "
                    "front and back faces alike, so rooms, corridors and the far walls show through. Live",
        default=True,
        update=_on_xray,
    )
    xray_mesh_edge: FloatProperty(
        name="Mesh edges",
        description="0: every face adds the same light, as a double exposure of the textures. Higher: faces "
                    "seen edge-on (walls, outlines) stand out and faces turned to you fade",
        default=3.0, min=0.0, soft_max=4.0, max=16.0, precision=2, update=_on_xray_params,
    )
    xray_tint: FloatVectorProperty(
        name="Tint", subtype="COLOR", size=3, min=0.0, max=1.0, default=(0.55, 0.8, 1.0),
        description="Colour of the X-ray when Tint amount is above 0", update=_on_xray_params,
    )
    xray_tint_amount: FloatProperty(
        name="Tint amount",
        description="0: every tile keeps its own colours. 1: one colour for all, the tint, as on a radiograph. "
                    "In between: a mix of the two",
        default=0.0, min=0.0, max=1.0, subtype="FACTOR", update=_on_xray_params,
    )
    point_radius_mode: EnumProperty(
        name="Point radius",
        description="How the display radius of points is chosen",
        items=[
            ("ADAPTIVE", "Attenuated (spacing, px clamp)",
             "Per-tile spacing x Point scale, then clamped between Min / Max pixels on "
             "screen: coarse tiles get bigger points, far points never vanish, near points "
             "never bloat. One size per tile, as CesiumJS' point cloud attenuation; "
             "Potree's adaptive size goes per point"),
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
    point_adaptive: BoolProperty(
        name="Smaller under finer tiles (beta)",
        description="Point clouds that add detail (ADD refinement, as Potree octrees streamed by 3dtiled): a "
                    "coarse tile stays on screen under its finer tiles. With this on, its points shrink to the "
                    "finer spacing where finer tiles are shown, and keep their size where none is, so a dense "
                    "area is no longer speckled with large coarse points. Per point, as Potree's adaptive size. "
                    "Not in Uniform or Screen pixels mode. Live",
        default=True, update=_on_point_radius,
    )
    point_adapt_min_px: FloatProperty(
        name="Min size (px)", description="Attenuated mode: points never smaller than this on screen",
        default=4.0, min=0.0, max=64.0, update=_on_point_radius,
    )
    point_adapt_max_px: FloatProperty(
        name="Max size (px)", description="Attenuated mode: points never larger than this on screen",
        default=12.0, min=0.5, max=256.0, update=_on_point_radius,
    )
    point_px: FloatProperty(
        name="Point size (px)", description="Screen mode: point diameter in pixels",
        default=4.0, min=0.5, max=64.0, update=_on_point_radius,
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
    dataset_empties: BoolProperty(
        name="An Empty per dataset",
        description="In a tileset that only gathers other tilesets (an aggregate of datasets), give each "
                    "dataset an Empty under the tileset's root and parent its tiles to it. The Empty sits at "
                    "the dataset's centre with Z up: its Location Z is a height offset, kept with the scene. "
                    "Tiles are still selected where the dataset says it is. cesium-native backend; applies "
                    "to tiles loaded from now on",
        default=True)
    dataset_markers: BoolProperty(
        name="Markers for every dataset (beta)",
        description="Beta. In a tileset that only gathers other tilesets, an Empty for every dataset its "
                    "tileset.json lists, before any tile of it is loaded: a sphere of the dataset's size at its "
                    "centre, named after the dataset. Scene Origin > Dataset then lists them all, so the origin "
                    "can go to a dataset that is not loaded yet",
        default=False, update=_on_dataset_marker_size)
    dataset_marker_km: FloatProperty(
        name="Marker size km",
        description="Smallest radius a dataset's sphere is drawn with, in kilometres on the globe, so that a "
                    "small site still shows from far away. A dataset larger than this keeps its own size. Live",
        default=50.0, min=0.001, soft_max=500.0, update=_on_dataset_marker_size)
    read_metadata: BoolProperty(
        name="Read feature metadata",
        description="Keep each tile's feature table: columns become vertex attributes "
                    "(meta_<column>, usable in shaders and Geometry Nodes) and the text "
                    "goes in a per-tile lookup. Applies to tiles loaded after the next "
                    "Start, with the cesium-native backend and Direct mesh",
        default=False,
    )
    meta_color: BoolProperty(
        name="Color tiles by",
        description="Mix a per-class or per-value color into every tile material",
        default=False, update=_on_meta_color,
    )
    meta_source: EnumProperty(
        name="Color by",
        description="What drives the colors",
        items=[
            ("COLUMN", "Property", "A property of the tiles, read with their metadata: classification, "
                                   "intensity, any vertex, feature or texture property. Classes get a palette, "
                                   "numbers go through the Color Ramp, and 'feature id' gives one color per "
                                   "feature (a building, say)"),
            ("ELEVATION", "Elevation", "Height above the ellipsoid, through the Color Ramp. Read in the "
                                       "material, so it needs no metadata; true metres at any world scale of "
                                       "the Globe"),
            ("OBJECT", "Tile", "One random color per tile: shows how a tileset is cut into tiles and which "
                               "level of detail is loaded where"),
            ("TILESET", "Tileset", "One color per tileset, and per dataset of an aggregate (with An Empty per "
                                   "dataset): tells apart what comes from where"),
        ],
        default="COLUMN", update=_on_meta_source,
    )
    meta_tile_by: EnumProperty(
        name="Tile color",
        description="What a tile's color shows. None of these needs metadata",
        items=[
            ("RANDOM", "Random", "One random color per tile: how the tileset is cut into tiles"),
            ("LEVEL", "Level", "Depth of the tile below the root, through the Color Ramp: which level of "
                               "detail is loaded where"),
            ("ERROR", "Error", "The tile's geometric error in metres, through the Color Ramp on a log scale. "
                               "Leaves declare 0 and show as a millimetre"),
        ],
        default="RANDOM", update=_on_meta_source,
    )
    meta_column: StringProperty(
        name="Column", description="Metadata column that drives the colors",
        update=_on_meta_column,
    )
    meta_strength: FloatProperty(
        name="Strength", description="0 = the tile's own colors, 1 = metadata colors only",
        default=1.0, min=0.0, max=1.0, subtype="FACTOR", update=_on_meta_strength,
    )
    meta_range_custom: BoolProperty(
        name="Custom range",
        description="Set which values the Color Ramp spans, for a number column such as LiDAR "
                    "intensity. Live",
        default=False, update=_on_meta_range_custom,
    )
    meta_range_min: FloatProperty(name="Min", description="Value at the start of the ramp. Live",
                                  default=0.0, update=_on_meta_range)
    meta_range_max: FloatProperty(name="Max", description="Value at the end of the ramp. Live",
                                  default=1.0, update=_on_meta_range)
    meta_all_columns: BoolProperty(
        name="Keep every property as an attribute",
        description="Keep every property as a vertex attribute (meta_<name>), for Geometry Nodes or your "
                    "own shaders, not only the one picked above. One float per vertex per property: "
                    "about 40 MB per column on 10 M vertices",
        default=False, update=_on_meta_column,
    )
    voxel_display: EnumProperty(
        name="Voxels",
        description="How voxel tiles are shown. Applies to tiles loaded after the next Start",
        items=(("FACES", "Blocks", "Opaque mesh of the cell faces next to empty space: crisp. "
                                   "Best for classes"),
               ("VOLUME", "Volume (see-through)", "OpenVDB Volume per box tile: soft, see-through. "
                                                  "Best for continuous fields. No clipping"),
               ("PROJECT", "Color other tilesets", "Show nothing for the voxel tiles: every other "
                                                   "tile's material reads the voxel under each pixel. "
                                                   "Box tiles only")),
        default="FACES", update=_on_voxel_project,
    )
    phase_year: IntProperty(
        name="Year", description="Show the phases built by this year",
        default=2030, min=-5000, max=3000, update=_on_phase_year,
    )
    voxel_mix: FloatProperty(
        name="Voxel color",
        description="0 = the tile's own texture or vertex color, 1 = the voxel class only",
        default=0.6, min=0.0, max=1.0, subtype="FACTOR", update=_on_voxel_project,
    )
    voxel_cut: BoolProperty(
        name="Keep only inside voxels",
        description="Pixels outside all voxels turn transparent: a boolean intersect with "
                    "the voxel tileset, the geometry stays as it is",
        default=False, update=_on_voxel_project,
    )
    voxel_exaggeration: FloatProperty(
        name="Voxel height scale",
        description="Stretch voxel tiles vertically around the tileset's center, for thin "
                    "datasets. They no longer line up with other data. Applies after the next Start",
        default=1.0, min=0.01, soft_max=200.0,
    )
    voxel_opacity: FloatProperty(
        name="Volume opacity",
        description="Density of voxel Volumes: 1 is about one optical depth per cell",
        default=0.5, min=0.0, soft_max=5.0, update=_on_voxel_opacity,
    )
    meta_columns: CollectionProperty(type=MetaColumnItem)
    meta_classes: CollectionProperty(type=MetaClassItem)
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
            ("OBJECT", "Chosen camera", "A camera object of your choice, at the render resolution: "
                                        "tiles are selected for it while you look at the result "
                                        "from anywhere in the viewport"),
            ("COLLECTION", "Cameras of a collection",
             "Every camera of a collection at once, each at the render resolution (panoramic ones "
             "all around): the tiles each of them needs load together. For several panoramas, or "
             "cameras placed along an animation to keep the detail of a whole path. cesium-native only"),
        ],
        default="VIEWPORT",
    )
    view_collection: bpy.props.PointerProperty(
        name="Cameras", type=bpy.types.Collection,
        description="Collection whose cameras (children collections included, hidden ones too) all select "
                    "tiles when 'Stream for' is 'Cameras of a collection'",
    )
    view_collection_viewport: BoolProperty(
        name="And the viewport",
        description="Select tiles for the 3D viewport too, besides the cameras of the collection",
        default=False,
    )
    path_camera_count: IntProperty(
        name="Cameras",
        description="How many cameras Cameras Along the Animation places, spread evenly over the frame range",
        default=12, min=2, max=64,
    )
    view_camera: bpy.props.PointerProperty(
        name="Camera", type=bpy.types.Object, poll=_camera_poll,
        description="Camera that selects the tiles when 'Stream for' is 'Chosen camera'. Move it, "
                    "or animate it, and the tiles follow",
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
    render_converge_cli: BoolProperty(
        name="Wait for tiles in Blender renders",
        description="F12, Ctrl+F12 and blender -b file.blend -a (or -f): before each frame renders, stream "
                    "for the scene camera and wait until its tiles have loaded (Settle time, Max wait). "
                    "In the window a stream must be running; the command line starts one (Warm-up)",
        default=True,
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
    use_disk_cache: BoolProperty(
        name="Disk cache",
        description="Keep unwrapped GLBs in %LOCALAPPDATA%/blender_ogc3dtiles/cache",
        default=True,
    )

    # --- Tile bounds (debug overlay, tile_bounds.py) ---
    tile_bounds: EnumProperty(
        name="Tile Bounds",
        description="Draw a wire outline around every visible tile, in the 3D view only "
                    "(not in renders): shows how the tileset is cut into tiles and which "
                    "ones streaming keeps",
        items=[
            ("OFF", "Off", "No outlines"),
            ("OBJECT", "Tile objects", "Each tile object's bounding box: what the tile "
             "actually holds. Meshes, point clouds and splats"),
            ("VOLUME", "3D Tiles volumes", "The bounding volume the tileset declares for "
             "each tile (box, region or sphere), which can be larger than what it holds. "
             "cesium-native backend"),
        ],
        default="OFF", update=_on_tile_bounds,
    )
    tile_bounds_random: BoolProperty(
        name="Random Colours", description="One random colour per tile",
        default=False, update=_on_tile_bounds_look,
    )
    tile_bounds_color: FloatVectorProperty(
        name="Colour", subtype="COLOR", size=4, min=0.0, max=1.0,
        default=(1.0, 0.45, 0.05, 1.0), update=_on_tile_bounds_look,
    )
    tile_bounds_width: FloatProperty(
        name="Line Width", description="Line width in pixels",
        default=1.5, min=0.5, max=8.0, update=_on_tile_bounds_look,
    )
    tile_bounds_depth: BoolProperty(
        name="Hidden by Geometry", description="Boxes behind the tiles are hidden; off draws "
                    "every box in front",
        default=False, update=_on_tile_bounds_look,
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
    bpy.utils.register_class(MetaColumnItem)
    bpy.utils.register_class(MetaClassItem)
    bpy.utils.register_class(TilesetItem)
    bpy.utils.register_class(TilesSceneProps)
    bpy.types.Scene.ogc3dtiles = bpy.props.PointerProperty(type=TilesSceneProps)
    print("[OGC3DTiles] TilesSceneProps registered OK")


def unregister():
    del bpy.types.Scene.ogc3dtiles
    bpy.utils.unregister_class(TilesSceneProps)
    bpy.utils.unregister_class(MetaClassItem)
    bpy.utils.unregister_class(MetaColumnItem)
    bpy.utils.unregister_class(TilesetItem)
    bpy.utils.unregister_class(ClipPolygonItem)
    bpy.utils.unregister_class(OverlayItem)
