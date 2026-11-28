"""
addon_prefs.py — Blender Addon Preferences
------------------------------------------
Edit → Preferences → Add-ons → OGC 3D Tiles → Preferences

Sections
  cesium-native status and install button, at the top
  Cache / library, Place search, Beta features
  Developer (folded) — backend choice, direct mesh, wheel source, backend timing comparison
"""

from __future__ import annotations

import bpy
from bpy.types import AddonPreferences, Operator
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, StringProperty

from .tileset.backend import get_available_backends, probe_cesium

try:                        # absent from the zips built for extensions.blender.org, which carry the wheel
    from . import wheel_install
except ImportError:
    wheel_install = None


# ── Prefs class ───────────────────────────────────────────────────────────────

def _set_network_file_cache(on):
    from .tileset import asset_fixes  # noqa: PLC0415
    asset_fixes.NETWORK_FILE_CACHE[0] = bool(on)


def _on_network_file_cache(self, _context):
    _set_network_file_cache(self.cache_network_files)


def _get_prefs(context):
    """Safe prefs lookup — works for both legacy addon and Extension install."""
    for key in (__package__,
                "blender_ogc3dtiles",
                "bl_ext.user_default.blender_ogc3dtiles",
                "user_default.blender_ogc3dtiles"):
        try:
            return context.preferences.addons[key].preferences
        except (KeyError, AttributeError):
            pass
    return None


def _save_prefs(_self, context):
    context.preferences.is_dirty = True


class OGC3DTilesPreferences(AddonPreferences):
    bl_idname = __package__

    # ── Backend selection ──────────────────────────────────────────────────────
    def _backend_items(self, _context):
        return [(id_, name, desc) for id_, name, desc in get_available_backends()]

    traversal_backend: EnumProperty(
        name="Traversal Backend",
        description=(
            "Which tile LOD engine to use.\n\n"
            "cesium-native-python: full spec compliance, async, ion, implicit tiling.\n"
            "Pure Python: no deps, good for debugging and perf baselining."
        ),
        items=_backend_items,
        default=0,
    )

    # ── Performance tracking (written by the modal operator each tick) ─────────
    # These are exposed in prefs so the panel can read them without a context ref.
    perf_cesium_ms: FloatProperty(
        name="cesium-native update_view (ms)",
        default=0.0, precision=3,
        options={"HIDDEN"},
    )
    perf_python_ms: FloatProperty(
        name="Python update_view (ms)",
        default=0.0, precision=3,
        options={"HIDDEN"},
    )
    perf_samples: IntProperty(
        name="Perf sample count",
        default=0,
        options={"HIDDEN"},
    )
    show_perf_compare: BoolProperty(
        name="Live Backend Comparison",
        description=(
            "Run both backends every tick and display timing.\n"
            "⚠  Doubles CPU usage — for profiling only."
        ),
        default=False,
    )

    # ── Developer ──────────────────────────────────────────────────────────────
    cesium_wheel_repo: StringProperty(
        name="Wheel release repo",
        description="GitHub repository whose latest Release carries cesium-native-python "
                    "wheels (owner/name); the matching CPython / platform wheel is "
                    "downloaded and pip-installed into Blender's Python",
        default="jo-chemla/cesium-native-python",
    )
    # ── Place search (Scene Origin > Search place) ────────────────────────────
    photon_url: StringProperty(
        name="Photon geocoder",
        description="Photon search endpoint (OpenStreetMap places; komoot's public instance or "
                    "a self-hosted one). Queries are sent there when you search a place",
        default="https://photon.komoot.io/api/",
    )
    terrain_tiles_url: StringProperty(
        name="Terrain tiles",
        description="Terrarium-encoded elevation tiles ({z}/{x}/{y}) used for the ground height "
                    "of a searched place (default: AWS open-data Terrain Tiles)",
        default="https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png",
    )
    aggregate_server: StringProperty(
        name="3dtiled server",
        description="The 3dtiled server that builds the tileset of entries of type 3dtiled aggregate. A "
                    "manifest file is sent to it on Start: it holds your share links",
        default="https://3dtiled.iconem.com",
    )
    geoid_url: StringProperty(
        name="EGM96 geoid grid",
        description="WW15MGH.DAC (2 MB, downloaded once into the cache): sea level to "
                    "ellipsoid height",
        default="https://raw.githubusercontent.com/CesiumGS/cesium-native/v0.59.0/data/WW15MGH.DAC",
    )
    # ── Cache, local tilesets, library ────────────────────────────────────────
    cache_dir: StringProperty(
        name="Cache folder",
        description="Where downloaded tiles are kept (cesium-native's sqlite HTTP cache and the "
                    "Python backend's GLBs). Empty = %LOCALAPPDATA%/blender_ogc3dtiles/cache. "
                    "Keep it on a local disk: sqlite locking is unreliable over SMB, and cache "
                    "entries are keyed by URL, share-link tokens included",
        subtype="DIR_PATH", default="")
    cache_network_files: BoolProperty(
        name="Cache files on network shares",
        description="Keep tiles read from a NAS (\\\\server\\share paths, mapped drives) in the cache "
                    "folder, read again from the share only when a file's date or size changed. "
                    "Worth it for a slow share; a fast one gains little. Files on a local disk "
                    "are never cached",
        default=False, update=_on_network_file_cache)
    cache_max_gb: FloatProperty(
        name="Cache size cap (GB)",
        description="Trimmed to this size, least recently used first, when the first stream of a "
                    "session starts. 0 = no cap. cesium-native also keeps at most 4096 responses",
        default=10.0, min=0.0, soft_max=200.0)
    mapped_drives_as_unc: BoolProperty(
        name="Mapped drives as UNC",
        description="A tileset path on a mapped network drive (Z:), browsed to, typed or pasted: store its "
                    "network share path (\\\\server\\share) instead, so the entry works on "
                    "machines that map the "
                    "share to another letter",
        default=True)
    library_files: StringProperty(
        name="Tileset libraries",
        description="Tileset library JSON files, separated by ';' (a personal one, a team one on "
                    "the NAS...). Entries keep their URLs and keys there, out of the add-on and "
                    "the repository",
        default="")
    library_show_mesh: BoolProperty(name="Mesh", default=False, update=_save_prefs)
    library_show_points: BoolProperty(name="Point cloud", default=False, update=_save_prefs)
    library_show_splats: BoolProperty(name="Splats", default=False, update=_save_prefs)
    library_show_voxels: BoolProperty(name="Voxels", default=False, update=_save_prefs)
    library_show_aggregate: BoolProperty(name="Aggregate", default=False, update=_save_prefs,
                                         description="The tilesets of tilesets: 3dtiled aggregate sets")
    # ── Beta features ──────────────────────────────────────────────────────────
    beta_phases: BoolProperty(
        name="Phases timeline",
        description="Sidebar panel: closed meshes of a 'Phases' collection become a class grid, "
                    "with a year slider over tilesets colored by it",
        default=False)
    beta_phase_strokes: BoolProperty(
        name="Phases from strokes",
        description="In the Phases panel: outlines drawn on the surface with Annotate or "
                    "Grease Pencil become phase volumes. Needs Phases timeline",
        default=False)
    beta_terrain_blend: BoolProperty(
        name="Terrain blending",
        description="A 'Terrain blending' box on globe, terrain, Google and Bing entries: the "
                    "terrain becomes transparent under the other tilesets, and their borders fade into it",
        default=False)
    beta_material_controls: BoolProperty(
        name="Material controls",
        description="Relight sliders in the Nodes: Material panel, gold transfer included. Off, the "
                    "shared 'OGC3D Relight' node group is the place to edit them",
        default=False)
    direct_mesh: BoolProperty(
        name="Direct mesh (numpy, both backends)",
        description="Build Blender meshes from numpy arrays instead of re-importing a GLB "
                    "(faster). Off = use the glTF importer, to compare or to work around a "
                    "tile the direct path gets wrong. Applies at the next Start",
        default=True)
    material_templates: BoolProperty(
        name="Tile materials from a template",
        description="A textured mesh tile starts from a copy of the finished material of an earlier tile of "
                    "its tileset, and only takes its own image (about 3 ms less per tile). Off = build and "
                    "dress every material node by node, to compare or to work around a tile it gets wrong",
        default=True)
    cesium_install_path: StringProperty(
        name="cesium-native-python source dir",
        description=(
            "Path to a locally-cloned cesium-native-python repo. "
            "Used by 'Install / Rebuild' button."
        ),
        subtype="DIR_PATH",
        default="",
    )

    # ── Draw ───────────────────────────────────────────────────────────────────
    def draw(self, context):
        layout = self.layout

        # ── cesium-native backend: status, and the install button while it is missing ──
        ok, status = probe_cesium()
        # centred in a column of fixed width, as Blender's own preference pages (CenterAlignMixIn)
        if context.region.width > 350 * context.preferences.system.ui_scale:
            row = layout.row()
            row.label(text="")
            layout = row.column()
            layout.ui_units_x = 50
            row.label(text="")
        layout.use_property_split = True
        layout.use_property_decorate = False
        box = layout.box()
        if ok:                                   # one row: status on the left, small buttons on the right
            row = box.row()
            row.label(text=f"cesium-native-python:  {status}", icon="CHECKMARK")
            sub = row.row(align=True)
            sub.alignment = "RIGHT"
            if wheel_install:
                sub.operator("ogc3dtiles.install_cesium_wheel", icon="IMPORT", text="Reinstall")
            sub.operator("ogc3dtiles.reload_cesium", icon="FILE_REFRESH", text="")
        else:
            col = box.column()
            col.alert = True
            col.label(text=f"cesium-native-python:  {status}", icon="ERROR")
            row = box.row(align=True)
            row.scale_y = 1.4
            if wheel_install:
                row.operator("ogc3dtiles.install_cesium_wheel", icon="IMPORT",
                             text="Install cesium-native-python library")
            row.operator("ogc3dtiles.reload_cesium", icon="FILE_REFRESH", text="")
        sub = box.row()
        sub.active = False
        if wheel_install is None:
            sub.label(text="Packaged build: the cesium-native wheel comes inside this extension", icon="PACKAGE")
        else:
            sub.label(text="Python-only build: the cesium-native wheel is downloaded from GitHub "
                           "(jo-chemla/cesium-native-python)", icon="URL")

        # ── Cache / library ───────────────────────────────────────────────────
        boxc = layout.box()
        boxc.label(text="Cache, local tilesets, library", icon="FILE_CACHE")
        col = boxc.column()
        col.prop(self, "cache_dir", text="Cache Folder")
        row = col.row(align=True)
        row.prop(self, "cache_max_gb", text="Size Cap (GB)")
        row.operator("ogc3dtiles.cache_trim", text="", icon="BRUSH_DATA")
        col.prop(self, "cache_network_files")
        col.prop(self, "mapped_drives_as_unc")
        row = col.row(align=True)
        row.prop(self, "library_files", text="Libraries")
        row.operator("ogc3dtiles.library_add_file", text="", icon="FILEBROWSER")
        import os
        from . import library as _library
        for p in _library.split_paths(self.library_files):
            split = col.split(factor=0.4)
            split.alignment = "RIGHT"
            split.label(text="")
            row = split.row()
            row.label(text=os.path.basename(p), icon="TEXT")
            sub = row.row()
            sub.alignment = "RIGHT"
            sub.operator("ogc3dtiles.library_edit", text="Edit", icon="GREASEPENCIL").path = p

        # ── Place search ───────────────────────────────────────────────────────
        boxp = layout.box()
        boxp.label(text="Place search (Scene Origin)", icon="VIEWZOOM")
        col = boxp.column()
        col.prop(self, "photon_url", text="Geocoder")
        col.prop(self, "terrain_tiles_url", text="Terrain Tiles")
        col.prop(self, "geoid_url", text="Geoid Grid")
        boxp.prop(self, "aggregate_server", text="3dtiled Server")

        # ── Beta features ──────────────────────────────────────────────────────
        boxb = layout.box()
        boxb.label(text="Beta features", icon="EXPERIMENTAL")
        col = boxb.column()
        col.prop(self, "beta_material_controls")
        col.prop(self, "beta_terrain_blend")
        col.prop(self, "beta_phases")
        sub = col.row()
        sub.active = self.beta_phases
        sub.prop(self, "beta_phase_strokes")

        # ── Developer, folded: backend choice, mesh path, wheel source, profiling ──
        head, body = layout.panel("ogc3d_prefs_developer", default_closed=True)
        head.label(text="Developer", icon="SCRIPT")
        if body is None:
            return
        body.prop(self, "traversal_backend", text="Backend")
        body.prop(self, "direct_mesh")
        body.prop(self, "material_templates")
        if wheel_install:
            body.prop(self, "cesium_wheel_repo", text="Wheel release repo")
            row = body.row(align=True)
            row.prop(self, "cesium_install_path", text="Source dir")
            row.operator("ogc3dtiles.install_cesium", icon="TOOL_SETTINGS", text="Build")
        body.prop(self, "show_perf_compare")
        if self.perf_samples > 0:
            col = body.column(align=True)
            col.scale_y = 0.9
            ref = max(self.perf_cesium_ms, self.perf_python_ms, 0.001)
            for label, ms in (("cesium-native-python", self.perf_cesium_ms), ("Pure Python", self.perf_python_ms)):
                col.label(text=f"{label:<22} {ms:6.3f} ms  ({ms / ref * 100:.0f}%)")
            row = col.row()
            row.label(text=f"Samples: {self.perf_samples}", icon="DRIVER")
            row.operator("ogc3dtiles.reset_perf_stats", icon="X", text="Reset")


# ── Operators ─────────────────────────────────────────────────────────────────

class OGC3D_OT_ReloadCesium(Operator):
    """Reload cesium modules without restarting Blender (Python parts only)"""
    bl_idname = "ogc3dtiles.reload_cesium"
    bl_label  = "Reload cesium Module"

    def execute(self, context):
        from .tileset.backend import forget_failed_cesium_import
        forget_failed_cesium_import()
        ok, msg = probe_cesium()
        self.report({"INFO"} if ok else {"WARNING"}, f"cesium: {msg}")
        return {"FINISHED"}


class OGC3D_OT_ResetPerfStats(Operator):
    """Clear accumulated backend performance samples"""
    bl_idname = "ogc3dtiles.reset_perf_stats"
    bl_label  = "Reset Perf Stats"

    def execute(self, context):
        prefs = _get_prefs(context)
        if prefs is None:
            self.report({"ERROR"}, "Could not find addon preferences")
            return {"CANCELLED"}
        prefs.perf_cesium_ms = 0.0
        prefs.perf_python_ms = 0.0
        prefs.perf_samples   = 0
        return {"FINISHED"}


# ── Registration ──────────────────────────────────────────────────────────────

_classes = [
    *(wheel_install.classes if wheel_install else ()),
    OGC3DTilesPreferences,
    OGC3D_OT_ReloadCesium,
    OGC3D_OT_ResetPerfStats,
]


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
