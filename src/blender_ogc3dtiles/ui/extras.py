"""Tileset entry tools: browse to a local / NAS tileset, tileset libraries,
copy (and crop) a tileset into the project, cache trim."""
from __future__ import annotations

import os
import threading

import bpy
from bpy.props import BoolProperty, CollectionProperty, EnumProperty, FloatProperty, IntProperty, StringProperty
from bpy.types import Operator, PropertyGroup, UIList

from .. import cachectl, library, paths
from ..addon_prefs import _get_prefs
from ..io import addon_pref, default_cache_dir


def _active_item(context):
    props = context.scene.ogc3dtiles
    if 0 <= props.active_tileset < len(props.tilesets):
        return props.tilesets[props.active_tileset]
    return None


def _redraw(context=None):
    wm = bpy.context.window_manager
    for w in wm.windows:
        for a in w.screen.areas:
            if a.type in ("VIEW_3D", "PREFERENCES"):
                a.tag_redraw()


# ── Browse to a local / network tileset ──────────────────────────────────────

class OGC3D_OT_TilesetBrowse(Operator):
    """Pick a tileset.json on disk, a mapped drive or a network share (type
    \\\\server\\share in the path field). Stored as a blend-relative path when
    'Relative Path' is ticked, else as a file: URL (mapped drives as their UNC
    share, see Preferences)"""
    bl_idname = "ogc3dtiles.tileset_browse"
    bl_label = "Select Tileset"
    bl_options = {"REGISTER", "UNDO"}

    filepath: StringProperty(subtype="FILE_PATH")
    filter_glob: StringProperty(default="*.json", options={"HIDDEN"})
    relative_path: BoolProperty(
        name="Relative Path", default=False,
        description="Store the path relative to the .blend (the project and its tilesets "
                    "move together)")

    def invoke(self, context, event):
        it = _active_item(context)
        if it is not None and it.url.strip():
            p = paths.url_to_path(bpy.path.abspath(it.url.strip()) if it.url.startswith("//")
                                  else it.url.strip())
            if os.path.isfile(p):
                self.filepath = p
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        it = _active_item(context)
        if it is None:
            return {"CANCELLED"}
        p = self.filepath
        if self.relative_path and bpy.data.filepath:
            try:
                url = bpy.path.relpath(p)
            except ValueError:                       # other drive than the .blend
                url = paths.path_to_url(p, bool(addon_pref("mapped_drives_as_unc", True)))
        else:
            url = paths.path_to_url(p, bool(addon_pref("mapped_drives_as_unc", True)))
        it.kind = "TILESET"
        it.url = url
        if not it.name or it.name.startswith("tileset"):
            base = os.path.basename(os.path.dirname(p)) or os.path.basename(p)
            it.name = base[:40]
        self.report({"INFO"}, f"Tileset: {url}")
        return {"FINISHED"}


# ── Cache ─────────────────────────────────────────────────────────────────────
_trimmed = set()


def trim_cache_once(root: str) -> None:
    """Size cap, applied when the first stream of the session starts (before
    cesium-native opens its database)."""
    if root in _trimmed:
        return
    _trimmed.add(root)
    cap = float(addon_pref("cache_max_gb", 10.0) or 0.0)
    try:
        r = cachectl.enforce(root, int(cap * 1024 ** 3))
        if r["http"] or r["glb"]:
            print(f"[3DTiles] cache trimmed to {cap:g} GB: "
                  f"{(r['http'] + r['glb']) / 1024 ** 2:.0f} MB freed")
    except Exception as e:                           # noqa: BLE001
        print(f"[3DTiles] cache trim failed: {e}")


class OGC3D_OT_CacheTrim(Operator):
    """Trim the cache folder to the size cap now (least recently used first)"""
    bl_idname = "ogc3dtiles.cache_trim"
    bl_label = "Trim Cache"

    def execute(self, context):
        root = default_cache_dir()
        cap = float(addon_pref("cache_max_gb", 10.0) or 0.0)
        if cap <= 0:
            self.report({"INFO"}, "No size cap set")
            return {"CANCELLED"}
        r = cachectl.enforce(root, int(cap * 1024 ** 3))
        self.report({"INFO"}, f"Freed {(r['http'] + r['glb']) / 1024 ** 2:.0f} MB in {root}")
        return {"FINISHED"}


# ── Libraries ────────────────────────────────────────────────────────────────
LIB_PICKER_WIDTH = 520      # px at resolution scale 1; a search popup can't be widened
LIB_PICKER_ROWS = 24
_lib_rows = []              # the library files as read when the picker opened
_lib_filter = ("", ())      # (query, kinds) the list shows, set when the picker draws


def _library_paths():
    return [bpy.path.abspath(p) for p in library.split_paths(addon_pref("library_files", ""))]


def _entry_label(entry) -> str:
    return f"{entry['group']} / {entry['name']}" if entry.get("group") else entry["name"]


def _matching_entries(query, kinds=()) -> list:
    """Indices into _lib_rows of the entries that match."""
    return [i for i, (_path, e) in enumerate(_lib_rows)
            if "error" not in e and library.matches(e, query, kinds)]


class OGC3D_OT_LibraryPick(Operator):
    """Add this tileset to the list"""
    bl_idname = "ogc3dtiles.library_pick"
    bl_label = "Add Tileset"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    index: IntProperty(options={"HIDDEN"})

    @classmethod
    def description(cls, context, properties):
        i = properties.index
        return _lib_rows[i][1].get("notes", "") if 0 <= i < len(_lib_rows) else ""

    def execute(self, context):
        if not (0 <= self.index < len(_lib_rows)):
            return {"CANCELLED"}
        props = context.scene.ogc3dtiles
        it = props.tilesets.add()
        library.apply_entry(it, _lib_rows[self.index][1], add_overlay=lambda item: item.overlays.add())
        for ov in it.overlays:
            if not ov.uid:
                import uuid
                ov.uid = f"ov_{uuid.uuid4().hex[:8]}"
        props.active_tileset = len(props.tilesets) - 1
        self.report({"INFO"}, f"Added {it.name}")
        return {"FINISHED"}


class OGC3D_LibraryRow(PropertyGroup):
    """One row of the picker's list (a UIList needs a collection)."""
    index: IntProperty()


class OGC3D_UL_LibraryEntries(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if item.index < len(_lib_rows):
            row = layout.row(align=True)
            row.alignment = "LEFT"
            row.operator(OGC3D_OT_LibraryPick.bl_idname, text=_entry_label(_lib_rows[item.index][1]),
                         emboss=False).index = item.index

    def filter_items(self, context, data, propname):
        keep = set(_matching_entries(*_lib_filter))
        return [self.bitflag_filter_item if r.index in keep else 0
                for r in getattr(data, propname)], []


class OGC3D_OT_LibraryAdd(Operator):
    """Add a tileset from a library file (Preferences > Tileset libraries)"""
    bl_idname = "ogc3dtiles.library_add"
    bl_label = "Add from Library"

    query: StringProperty(name="Search", options={"TEXTEDIT_UPDATE", "SKIP_SAVE"})

    def invoke(self, context, event):
        if not _library_paths():
            self.report({"WARNING"}, "No tileset library: add one in the add-on preferences")
            return {"CANCELLED"}
        _lib_rows[:] = library.read_all(_library_paths())
        rows = context.window_manager.ogc3d_lib_rows
        rows.clear()
        for i in range(len(_lib_rows)):
            rows.add().index = i
        width = int(LIB_PICKER_WIDTH * context.preferences.system.ui_scale)
        return context.window_manager.invoke_popup(self, width=width)

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.activate_init = True
        row.prop(self, "query", text="", icon="VIEWZOOM", placeholder="Search tilesets")
        # the preferences remember these from one search to the next
        prefs = _get_prefs(context)
        row = layout.row()
        for name in ("library_show_mesh", "library_show_points", "library_show_splats", "library_show_voxels"):
            row.prop(prefs, name)
        kinds = [k for k, on in (("MESH", prefs.library_show_mesh), ("POINTS", prefs.library_show_points),
                                 ("SPLATS", prefs.library_show_splats), ("VOXELS", prefs.library_show_voxels)) if on]
        global _lib_filter
        _lib_filter = (self.query, kinds)
        found = len(_matching_entries(self.query, kinds))
        if not found:
            layout.label(text="No matching tileset" if _lib_rows else "The library is empty")
            return
        n = min(found, LIB_PICKER_ROWS)
        layout.template_list("OGC3D_UL_LibraryEntries", "", context.window_manager, "ogc3d_lib_rows",
                             context.window_manager, "ogc3d_lib_active", rows=n, maxrows=n)

    def execute(self, context):
        return {"FINISHED"}


def _target_items(self, context):
    _target_items.cache = [(p, os.path.basename(p), p) for p in _library_paths()] or [
        ("", "(no library)", "Add a library file in the preferences")]
    return _target_items.cache


class OGC3D_OT_LibrarySave(Operator):
    """Save the active tileset entry (URL, keys, overlays, SSE) to a library file;
    an entry of the same name is replaced"""
    bl_idname = "ogc3dtiles.library_save"
    bl_label = "Save to Library"

    target: EnumProperty(name="Library", items=_target_items)
    group: StringProperty(name="Group", description="Optional group shown in the picker", default="")

    def invoke(self, context, event):
        if not _library_paths():
            self.report({"WARNING"}, "No tileset library: add one in the add-on preferences")
            return {"CANCELLED"}
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        it = _active_item(context)
        if it is None or not self.target:
            return {"CANCELLED"}
        e = library.entry_from_item(it)
        if self.group.strip():
            e["group"] = self.group.strip()
        try:
            replaced = library.save_entry(self.target, e)
        except OSError as exc:
            self.report({"ERROR"}, f"Could not write {self.target}: {exc}")
            return {"CANCELLED"}
        self.report({"INFO"}, f"{'Updated' if replaced else 'Saved'} '{it.name}' in "
                              f"{os.path.basename(self.target)}")
        return {"FINISHED"}


_overlay_presets = []        # as read when the menu last drew


class OGC3D_OT_OverlayPreset(Operator):
    """Add this raster overlay to the selected tileset"""
    bl_idname = "ogc3dtiles.overlay_preset"
    bl_label = "Add Overlay Preset"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    index: IntProperty(options={"HIDDEN"})

    def execute(self, context):
        it = _active_item(context)
        if it is None or not (0 <= self.index < len(_overlay_presets)):
            return {"CANCELLED"}
        import uuid
        entry = _overlay_presets[self.index]
        ov = it.overlays.add()
        ov.uid = f"ov_{uuid.uuid4().hex[:8]}"
        ov.enabled = False               # one live reload, once every field is set
        library.apply_overlay(ov, entry)
        ov.enabled = entry.get("enabled", True)
        it.active_overlay = len(it.overlays) - 1
        self.report({"INFO"}, f"Added overlay {ov.name}")
        return {"FINISHED"}


class OGC3D_MT_OverlayLibrary(bpy.types.Menu):
    """Raster overlays ready to add: OpenStreetMap, Esri and IGN imagery, and the
    "overlays" of the library files (those that need a key)"""
    bl_idname = "OGC3D_MT_overlay_library"
    bl_label = "Overlay Library"

    def draw(self, context):
        _overlay_presets[:] = library.overlay_presets(_library_paths())
        for i, e in enumerate(_overlay_presets):
            self.layout.operator(OGC3D_OT_OverlayPreset.bl_idname, text=e["name"]).index = i


class OGC3D_OT_LibraryEdit(Operator):
    """Open this library file in the program your system opens .json files with"""
    bl_idname = "ogc3dtiles.library_edit"
    bl_label = "Edit Library File"

    path: StringProperty(options={"HIDDEN"})

    def execute(self, context):
        import subprocess
        import sys
        p = bpy.path.abspath(self.path)
        if not os.path.isfile(p):
            self.report({"ERROR"}, f"No such file: {p}")
            return {"CANCELLED"}
        try:
            if sys.platform == "win32":
                try:
                    os.startfile(p)                  # the program .json opens with
                except OSError:                      # no association at all
                    subprocess.Popen(["notepad.exe", p])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", p])
            else:
                subprocess.Popen(["xdg-open", p])
        except OSError as exc:
            self.report({"ERROR"}, f"Could not open {p}: {exc}")
            return {"CANCELLED"}
        return {"FINISHED"}


class OGC3D_OT_LibraryAddFile(Operator):
    """Add (or create) a tileset library JSON file to the preferences' list"""
    bl_idname = "ogc3dtiles.library_add_file"
    bl_label = "Add Library File"

    filepath: StringProperty(subtype="FILE_PATH", default="tilesets.json")
    filter_glob: StringProperty(default="*.json", options={"HIDDEN"})

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        p = self.filepath
        if not p.lower().endswith(".json"):
            p += ".json"
        if not os.path.exists(p):
            try:
                with open(p, "w", encoding="utf-8") as fh:
                    fh.write('{"version": 1, "tilesets": []}\n')
            except OSError as exc:
                self.report({"ERROR"}, str(exc))
                return {"CANCELLED"}
        ad = context.preferences.addons.get(__package__.rpartition(".")[0])
        if ad is None:
            return {"CANCELLED"}
        cur = library.split_paths(ad.preferences.library_files)
        if p not in cur:
            cur.append(p)
        ad.preferences.library_files = "; ".join(cur)
        return {"FINISHED"}


# ── Copy a tileset into the project ──────────────────────────────────────────
_export = {"thread": None, "done": 0, "total": 0, "msg": "", "result": None,
           "error": None, "cancel": False, "item_uid": "", "switch": None}


def export_status() -> str:
    if _export["thread"] is None:
        return ""
    d, t = _export["done"], _export["total"]
    return f"Copying {d}/{t}  {_export['msg']}"[:70] if t else f"Copying… {_export['msg']}"[:70]


def _extent_from_object(obj, props, root):
    """Oriented box (ECEF centre + half axes) of an object's bounding box, in
    the tileset's frame (inverse of its root Empty)."""
    from mathutils import Vector
    from ..tileset.traversal import blender_to_ecef, rotate_enu_to_ecef
    m = obj.matrix_world
    if root is not None:
        m = root.matrix_world.inverted() @ m
    if obj.type == "EMPTY":
        lo = Vector((-1.0, -1.0, -1.0)) * obj.empty_display_size
        hi = -lo
    else:
        bb = [Vector(c) for c in obj.bound_box]
        lo = Vector((min(c.x for c in bb), min(c.y for c in bb), min(c.z for c in bb)))
        hi = Vector((max(c.x for c in bb), max(c.y for c in bb), max(c.z for c in bb)))
    c = m @ ((lo + hi) * 0.5)
    half = (hi - lo) * 0.5
    if half.z * m.to_3x3().col[2].length < 1.0:
        # a flat outline (plane, drawn polygon): its footprint, any height
        half.z = 5000.0 / max(m.to_3x3().col[2].length, 1e-9)
    lat, lon, h = props.origin_lat, props.origin_lon, props.origin_height
    axes = [rotate_enu_to_ecef(tuple(m.to_3x3().col[i] * max(half[i], 1e-3)), lat, lon)
            for i in range(3)]
    return {"center": blender_to_ecef(tuple(c), lat, lon, h), "half_axes": axes}


class OGC3D_OT_TilesetCopy(Operator):
    """Copy the active tileset into a folder of the project (resumable), optionally
    cropped to an object's box and to a coarsest geometric error. Works for Google
    tiles and Cesium ion assets too (mind their terms on offline storage) and for
    implicit tilesets (written out as explicit ones)"""
    bl_idname = "ogc3dtiles.tileset_copy"
    bl_label = "Copy Tileset into Project"

    dest: StringProperty(name="Folder", subtype="DIR_PATH",
                         description="Destination (blend-relative // paths allowed)")
    crop_object: StringProperty(
        name="Crop to", description="Keep tiles touching this object's bounding box "
        "(a cube, an Empty, any mesh); empty = whole tileset")
    min_geometric_error: FloatProperty(
        name="Finest error (m)", min=0.0, default=0.0,
        description="Stop at tiles whose geometric error is at most this (coarser copy, "
                    "far fewer files); 0 = every level")
    switch_entry: BoolProperty(name="Stream the copy", default=True,
                               description="Point the entry at the copy when done")

    @classmethod
    def poll(cls, context):
        return _export["thread"] is None and _active_item(context) is not None

    def invoke(self, context, event):
        it = _active_item(context)
        safe = "".join(ch if ch.isalnum() or ch in "-_ ." else "_" for ch in it.name).strip() or "tileset"
        self.dest = f"//tilesets/{safe}" if bpy.data.filepath else ""
        sel = context.active_object
        if sel is not None and "tile_url" not in sel and sel.type in {"MESH", "EMPTY"}:
            self.crop_object = sel.name
        return context.window_manager.invoke_props_dialog(self, width=420)

    def draw(self, context):
        lay = self.layout
        lay.prop(self, "dest")
        lay.prop_search(self, "crop_object", bpy.data, "objects")
        lay.prop(self, "min_geometric_error")
        lay.prop(self, "switch_entry")
        if not bpy.data.filepath:
            lay.label(text="Save the .blend first for a project-relative folder", icon="INFO")

    def execute(self, context):
        from ..io.tileset_export import export_tileset
        from . import item_token, item_url, _state
        it = _active_item(context)
        props = context.scene.ogc3dtiles
        url = item_url(it)
        ion_token = item_token(it, props)
        if not self.dest.strip():
            self.report({"ERROR"}, "Choose a destination folder")
            return {"CANCELLED"}
        dest = os.path.abspath(bpy.path.abspath(self.dest))
        extent = None
        if self.crop_object:
            obj = bpy.data.objects.get(self.crop_object)
            if obj is None:
                self.report({"ERROR"}, f"No object '{self.crop_object}'")
                return {"CANCELLED"}
            st = _state["streams"].get(it.uid) if it.uid else None
            root = bpy.data.objects.get(st["root_obj"]) if st and st.get("root_obj") else None
            extent = _extent_from_object(obj, props, root)
        _export.update(done=0, total=0, msg="reading tileset", result=None, error=None,
                       cancel=False, item_uid=it.uid,
                       switch=self.dest if self.switch_entry else None)

        min_ge = float(self.min_geometric_error)      # the operator is gone once the thread runs

        def progress(done, total, msg):
            _export["done"], _export["total"], _export["msg"] = done, total, msg

        def run():
            try:
                _export["result"] = export_tileset(
                    url, dest, extent=extent, min_geometric_error=min_ge, ion_token=ion_token,
                    progress=progress, cancel=lambda: _export["cancel"])
            except Exception as exc:                 # noqa: BLE001
                _export["error"] = str(exc) or exc.__class__.__name__

        _export["thread"] = threading.Thread(target=run, name="ogc3d-export", daemon=True)
        _export["thread"].start()
        bpy.app.timers.register(_export_poll, first_interval=0.2)
        self.report({"INFO"}, f"Copying {it.name} to {dest}")
        return {"FINISHED"}


def _export_poll():
    th = _export["thread"]
    _redraw()
    if th is not None and th.is_alive():
        return 0.3
    _export["thread"] = None
    props = bpy.context.scene.ogc3dtiles
    if _export["error"]:
        props.status_text = f"Copy failed: {_export['error']}"[:120]
        print(f"[3DTiles] copy failed: {_export['error']}")
        return None
    r = _export["result"] or {}
    props.status_text = (f"Copied {r.get('tiles_kept', 0)} tiles, "
                         f"{r.get('bytes', 0) / 1024 ** 2:.1f} MB")
    print(f"[3DTiles] {props.status_text} -> {r.get('tileset')}")
    if _export["switch"] and r.get("tileset"):
        it = next((x for x in props.tilesets if x.uid == _export["item_uid"]), None)
        if it is not None:
            d = _export["switch"].rstrip("/\\")
            it.kind = "TILESET"
            it.url = (d + "/tileset.json") if d.startswith("//") else paths.path_to_url(r["tileset"])
            if not it.name.endswith(" (copy)"):
                it.name = (it.name + " (copy)")[:60]
    return None


class OGC3D_OT_TilesetCopyCancel(Operator):
    """Stop the running copy (re-run it later to resume)"""
    bl_idname = "ogc3dtiles.tileset_copy_cancel"
    bl_label = "Cancel Copy"

    def execute(self, context):
        _export["cancel"] = True
        return {"FINISHED"}


def draw_entry_tools(layout, it) -> None:
    """Row under an entry's URL: library save, copy into project."""
    row = layout.row(align=True)
    row.operator("ogc3dtiles.library_save", text="Save to library", icon="BOOKMARKS")
    if _export["thread"] is not None:
        row.label(text=export_status())
        row.operator("ogc3dtiles.tileset_copy_cancel", text="", icon="X")
    else:
        row.operator("ogc3dtiles.tileset_copy", text="Copy into project", icon="PACKAGE")


_classes = [
    OGC3D_OT_TilesetBrowse,
    OGC3D_OT_CacheTrim,
    OGC3D_LibraryRow,
    OGC3D_UL_LibraryEntries,
    OGC3D_OT_LibraryPick,
    OGC3D_OT_LibraryAdd,
    OGC3D_OT_LibrarySave,
    OGC3D_OT_LibraryAddFile,
    OGC3D_OT_LibraryEdit,
    OGC3D_OT_OverlayPreset,
    OGC3D_MT_OverlayLibrary,
    OGC3D_OT_TilesetCopy,
    OGC3D_OT_TilesetCopyCancel,
]


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    wm = bpy.types.WindowManager
    wm.ogc3d_lib_rows = CollectionProperty(type=OGC3D_LibraryRow)
    wm.ogc3d_lib_active = IntProperty(default=-1)


def unregister():
    _export["cancel"] = True
    del bpy.types.WindowManager.ogc3d_lib_active
    del bpy.types.WindowManager.ogc3d_lib_rows
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)

