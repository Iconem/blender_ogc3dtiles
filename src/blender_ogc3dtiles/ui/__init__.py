"""
ui/__init__.py — Sidebar panel + modal streaming operator

Several tilesets stream at once (scene.ogc3dtiles.tilesets).  Each one is a
"stream": its own backend (pure Python or cesium-native), download manager,
root Empty and sub-collection ``3D Tiles / <name>``.  All streams share the
scene origin (ENU anchor) and the viewport camera.

Per tick (50 ms), per stream:
  1. drain worker results (graft external tilesets, queue ready GLBs),
  2. import at most ``imports_per_tick`` GLBs,
  3. re-run the selection only if the view (incl. the root Empty) changed,
     something arrived, or 0.5 s passed,
  4. submit loads in priority order,
  5. evict least-recently-wanted hidden tiles above ``max_loaded_tiles``.
"""
from __future__ import annotations

import json
import math
import time

import bpy
from bpy.types import Operator, Panel, UIList

from ..camera import CesiumCameraAdapter
from ..io import (
    DiskCache,
    TileDownloadManager,
    default_cache_dir,
    ensure_collection,
    ensure_root_empty,
    http_get,
    import_glb_file,
    remove_tile,
    set_tile_visible,
    tile_world_matrix,
)
from ..tileset.backend import PythonBackend, make_backend, probe_cesium
from ..tileset.traversal import (
    Tile,
    TileState,
    build_ecef_to_enu_matrix,
    ecef_to_geodetic,
    graft_external,
    parse_tileset,
)

SELECTION_MAX_AGE_S = 0.5
EVICT_PERIOD_S = 2.0
EVICT_GRACE_S = 10.0       # never evict something the traversal wanted recently
RETRY_AFTER_S = 5.0

# ── Cached backend probe ──────────────────────────────────────────────────────
_cesium_status: tuple = (False, "Not checked yet")


def _refresh_cesium_status():
    global _cesium_status
    _cesium_status = probe_cesium()


# ── Stream state ──────────────────────────────────────────────────────────────
class _Rec:
    __slots__ = ("holder", "data", "last_wanted", "visible", "tile")

    def __init__(self, holder, data, tile=None):
        self.holder = holder
        self.data = data
        self.last_wanted = time.monotonic()
        self.visible = False
        self.tile = tile


def _new_stream(key, name, url, token, max_sse) -> dict:
    return {
        "key": key, "name": name, "url": url, "token": token, "max_sse": max_sse,
        "backend": None, "mode": "python", "download_mgr": None,
        "root_tile": None, "root_obj": None, "coll": None,
        "tiles": {}, "ready": [], "failed_at": {},
        "last_sig": None, "last_sel_t": 0.0, "last_evict_t": 0.0,
        "render_keys": set(), "stats": {}, "error": None, "pending": 0,
    }


def _fresh_state() -> dict:
    return {"streams": {}, "camera_adapter": None, "origin_set": False}


_state: dict = _fresh_state()


class _FallbackPrefs:
    traversal_backend = "AUTO"
    dev_mode = False
    show_coord_debug = True
    cesium_install_path = ""


def _get_prefs(context):
    for key in ("blender_ogc3dtiles",
                "bl_ext.user_default.blender_ogc3dtiles",
                "user_default.blender_ogc3dtiles"):
        try:
            return context.preferences.addons[key].preferences
        except (KeyError, AttributeError):
            pass
    return _FallbackPrefs()


def _tile_key(tile: Tile) -> str:
    return tile.content_uri or f"tile@{id(tile)}"


def _enu_from_ecef(props):
    return build_ecef_to_enu_matrix(props.origin_lat, props.origin_lon, props.origin_height)


def _enabled_items(props):
    """Tileset list entries to stream; falls back to the single URL field."""
    items = [(i, it) for i, it in enumerate(props.tilesets) if it.enabled and it.url.strip()]
    if not items and props.tileset_url.strip():
        it = props.tilesets.add()
        it.name = _short_label(props.tileset_url)
        it.url = props.tileset_url.strip()
        it.ion_token = props.cesium_ion_token
        it.max_sse = props.max_screen_space_error
        props.active_tileset = len(props.tilesets) - 1
        items = [(len(props.tilesets) - 1, it)]
    return items


def _stream_key(index, item) -> str:
    return f"{index}:{item.url.strip()}"


# ── Operators ─────────────────────────────────────────────────────────────────

class OGC3D_OT_TilesetAdd(Operator):
    """Add a tileset entry (prefilled from the URL field)"""
    bl_idname = "ogc3dtiles.tileset_add"
    bl_label = "Add Tileset"

    def execute(self, context):
        props = context.scene.ogc3dtiles
        it = props.tilesets.add()
        it.url = props.tileset_url.strip()
        it.ion_token = props.cesium_ion_token
        it.max_sse = props.max_screen_space_error
        it.name = _short_label(it.url) if it.url else f"tileset {len(props.tilesets)}"
        props.active_tileset = len(props.tilesets) - 1
        return {"FINISHED"}


class OGC3D_OT_TilesetRemove(Operator):
    """Remove the selected tileset entry (and its objects)"""
    bl_idname = "ogc3dtiles.tileset_remove"
    bl_label = "Remove Tileset"

    def execute(self, context):
        props = context.scene.ogc3dtiles
        i = props.active_tileset
        if 0 <= i < len(props.tilesets):
            key = _stream_key(i, props.tilesets[i])
            st = _state["streams"].pop(key, None)
            if st is not None:
                _teardown_stream(st, remove_objects=True)
            props.tilesets.remove(i)
            props.active_tileset = max(0, min(i, len(props.tilesets) - 1))
        return {"FINISHED"}


class OGC3D_OT_StartStream(Operator):
    """Start streaming all enabled tilesets"""
    bl_idname = "ogc3dtiles.start_stream"
    bl_label = "Start Streaming"
    bl_options = {"REGISTER"}

    def execute(self, context):
        global _state
        scene = context.scene
        props = scene.ogc3dtiles
        if props.is_streaming:
            self.report({"WARNING"}, "Already streaming")
            return {"CANCELLED"}
        items = _enabled_items(props)
        if not items:
            self.report({"ERROR"}, "No tileset URL")
            return {"CANCELLED"}

        _state = _fresh_state()
        props.status_text = "Connecting…"
        props.tiles_loaded = 0
        props.tiles_pending = 0
        prefs = _get_prefs(context)
        choice = getattr(prefs, "traversal_backend", "AUTO") or "AUTO"
        cache = DiskCache(default_cache_dir(), enabled=props.use_disk_cache)
        _state["camera_adapter"] = CesiumCameraAdapter(scene)
        _state["origin_set"] = not props.use_tileset_center

        started = 0
        for index, item in items:
            st = _new_stream(_stream_key(index, item), item.name or _short_label(item.url),
                             item.url.strip(), item.ion_token, item.max_sse)
            try:
                ok = self._start_stream(scene, props, st, choice, cache)
            except Exception as e:                   # noqa: BLE001
                import traceback
                traceback.print_exc()
                ok = False
                st["error"] = str(e)
            if ok:
                _state["streams"][st["key"]] = st
                started += 1
            else:
                self.report({"WARNING"}, f"{st['name']}: {st['error']}")
        if not started:
            self.report({"ERROR"}, "No tileset could be started")
            return {"CANCELLED"}

        _orient_viewport(context, props)
        if bpy.app.background:
            props.is_streaming = True      # drive with ui.stream_tick() yourself
        else:
            bpy.ops.ogc3dtiles.modal_stream("INVOKE_DEFAULT")
        return {"FINISHED"}

    def _start_stream(self, scene, props, st, choice, cache) -> bool:
        backend = make_backend(choice, max_sse=st["max_sse"],
                               max_tiles=props.max_loaded_tiles,
                               detail_falloff=props.detail_falloff,
                               max_dist=props.load_distance,
                               cache_dir=cache.root if props.use_disk_cache else None)
        sub = _coll_name(st["name"])
        st["coll"] = ensure_collection(scene, sub).name
        st["root_obj"] = ensure_root_empty(scene, _root_name(st["name"]), sub).name

        if isinstance(backend, PythonBackend):
            headers = {}
            if st["token"]:
                headers["Authorization"] = f"Bearer {st['token']}"
            raw = http_get(st["url"], headers)
            data = json.loads(raw.decode("utf-8"))
            root_tile = parse_tileset(data, st["url"])
            backend.set_root(root_tile)
            st["root_tile"] = root_tile
            if not _state["origin_set"]:
                cx, cy, cz, _r = root_tile.sphere_ecef()
                _set_origin_from_ecef(props, cx, cy, cz)
                _state["origin_set"] = True
            st["download_mgr"] = TileDownloadManager(
                max_concurrent=props.max_concurrent_requests, token=st["token"], cache=cache)
            st["mode"] = "python"
            _add_root_bbox(scene, st)
        else:
            headers = {}
            if st["token"] and not st["url"].isdigit():
                headers["Authorization"] = f"Bearer {st['token']}"
            backend.load_tileset(url=st["url"], ion_token=st["token"],
                                 options={"request_headers": headers})
            st["mode"] = "native"
        st["backend"] = backend
        return True


class OGC3D_OT_StopStream(Operator):
    """Stop streaming"""
    bl_idname = "ogc3dtiles.stop_stream"
    bl_label = "Stop Streaming"
    bl_options = {"REGISTER"}

    def execute(self, context):
        context.scene.ogc3dtiles.is_streaming = False
        for st in _state["streams"].values():
            _teardown_stream(st, remove_objects=False)
        context.scene.ogc3dtiles.status_text = "Stopped"
        return {"FINISHED"}


def _teardown_stream(st, remove_objects: bool):
    dm = st.get("download_mgr")
    if dm:
        dm.cancel_all()
    b = st.get("backend")
    if b is not None and st.get("mode") == "native":
        try:
            b.teardown()
        except Exception:
            pass
    st["backend"] = None
    if remove_objects:
        for rec in list(st["tiles"].values()):
            remove_tile(rec.holder, rec.data)
        st["tiles"].clear()
        root = bpy.data.objects.get(st.get("root_obj") or "")
        if root is not None:
            for c in list(root.children_recursive):
                if c.name in bpy.data.objects:
                    bpy.data.objects.remove(c, do_unlink=True)
            bpy.data.objects.remove(root, do_unlink=True)
        coll = bpy.data.collections.get(st.get("coll") or "")
        if coll is not None and not coll.objects and not coll.children:
            bpy.data.collections.remove(coll)


class OGC3D_OT_ClearTiles(Operator):
    """Remove all loaded tile objects and their mesh data from scene"""
    bl_idname = "ogc3dtiles.clear_tiles"
    bl_label = "Clear All Tiles"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        if context.scene.ogc3dtiles.is_streaming:
            bpy.ops.ogc3dtiles.stop_stream()
        n = 0
        for st in list(_state["streams"].values()):
            n += len(st["tiles"])
            _teardown_stream(st, remove_objects=True)
        _state["streams"].clear()
        # anything left over from earlier sessions
        for o in list(bpy.data.objects):
            if "tile_url" in o or o.get("tile_bbox") or o.get("ogc3dtiles_root"):
                for c in list(o.children_recursive):
                    if c.name in bpy.data.objects:
                        bpy.data.objects.remove(c, do_unlink=True)
                if o.name in bpy.data.objects:
                    bpy.data.objects.remove(o, do_unlink=True)
                n += 1
        bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=False, do_recursive=True)
        context.scene.ogc3dtiles.tiles_loaded = 0
        self.report({"INFO"}, f"Removed {n} tile objects")
        return {"FINISHED"}


class OGC3D_OT_ClearCache(Operator):
    """Delete the on-disk GLB cache"""
    bl_idname = "ogc3dtiles.clear_cache"
    bl_label = "Clear Disk Cache"

    def execute(self, context):
        n = DiskCache(default_cache_dir(), enabled=False).clear()
        self.report({"INFO"}, f"Deleted {n} cached files")
        return {"FINISHED"}


# ── Modal operator ────────────────────────────────────────────────────────────

class OGC3D_OT_ModalStream(Operator):
    bl_idname = "ogc3dtiles.modal_stream"
    bl_label = "3D Tiles Modal Stream"
    INTERVAL = 0.05
    _timer = None

    def modal(self, context, event):
        props = context.scene.ogc3dtiles
        if not props.is_streaming:
            self._finish(context)
            return {"FINISHED"}
        if event.type == "TIMER":
            try:
                changed = stream_tick(context)
            except Exception as e:                   # noqa: BLE001
                import traceback
                traceback.print_exc()
                props.status_text = f"tick error: {e}"
                changed = True
            if changed:
                for area in context.screen.areas:
                    if area.type == "VIEW_3D":
                        area.tag_redraw()
        return {"PASS_THROUGH"}

    def invoke(self, context, event):
        props = context.scene.ogc3dtiles
        props.is_streaming = True
        props.status_text = "Streaming…"
        self._timer = context.window_manager.event_timer_add(self.INTERVAL, window=context.window)
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def _finish(self, context):
        if self._timer:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None


def stream_tick(context) -> bool:
    """One streaming step for every stream. Module-level so it can be driven
    without a window (``blender -b``)."""
    scene = context.scene
    props = scene.ogc3dtiles
    now = time.monotonic()
    changed = False
    loaded = pending = visible = 0
    parts = []
    for st in _state["streams"].values():
        if st["backend"] is None:
            continue
        if st["mode"] == "native":
            changed |= _tick_native(scene, props, st, now)
        else:
            changed |= _tick_python(scene, props, st, now)
        loaded += len(st["tiles"])
        pending += st.get("pending", 0)
        visible += len(st["render_keys"])
        parts.append(f"{st['name'][:14]} {len(st['render_keys'])}/{len(st['tiles'])}")
    props.tiles_loaded = loaded
    props.tiles_pending = pending
    props.status_text = f"Visible {visible}  Loaded {loaded}  Queue {pending}  |  " + "  ".join(parts)
    return changed


def _view_for(st):
    cam = _state["camera_adapter"]
    return cam.get_view_state(bpy.data.objects.get(st["root_obj"] or ""))


def _apply_visibility(st, render_keys, keep_ids, now) -> bool:
    changed = False
    for k, rec in st["tiles"].items():
        vis = k in render_keys
        if vis or (rec.tile is not None and id(rec.tile) in keep_ids):
            rec.last_wanted = now
        if vis != rec.visible:
            set_tile_visible(rec.holder, vis)
            rec.visible = vis
            changed = True
    st["render_keys"] = render_keys
    return changed


def _evict(st, props, now) -> bool:
    if now - st["last_evict_t"] < EVICT_PERIOD_S:
        return False
    st["last_evict_t"] = now
    tiles = st["tiles"]
    over = len(tiles) - props.max_loaded_tiles
    if over <= 0:
        return False
    victims = sorted((rec.last_wanted, k) for k, rec in tiles.items()
                     if not rec.visible and now - rec.last_wanted > EVICT_GRACE_S)
    changed = False
    for _t, k in victims[:over]:
        rec = tiles.pop(k)
        remove_tile(rec.holder, rec.data)
        if rec.tile is not None:
            rec.tile.state = TileState.UNLOADED
        changed = True
    return changed


def _root_and_coll(scene, st):
    root = bpy.data.objects.get(st["root_obj"] or "")
    if root is None:
        sub = _coll_name(st["name"])
        root = ensure_root_empty(scene, _root_name(st["name"]), sub)
        st["root_obj"] = root.name
    coll = bpy.data.collections.get(st["coll"] or "") or ensure_collection(scene, _coll_name(st["name"]))
    return root, coll


# ---------------------------------------------------------- python
def _tick_python(scene, props, st, now) -> bool:
    if not _state["origin_set"]:
        return False
    backend, dm, tiles = st["backend"], st["download_mgr"], st["tiles"]
    changed = False

    # 1. results from workers
    for res in dm.tick():
        tile = res.tile
        key = _tile_key(tile)
        if res.error:
            tile.state = TileState.FAILED
            st["failed_at"][key] = now
            print(f"[3DTiles] {res.error}: {res.url}")
            changed = True
            continue
        if res.kind == "json":
            try:
                data = json.loads(res.raw_json.decode("utf-8"))
                n = graft_external(tile, data, res.url)
                tile.state = TileState.UNLOADED
                print(f"[3DTiles] grafted {n} children from {res.url}")
            except Exception as e:               # noqa: BLE001
                tile.state = TileState.FAILED
                print(f"[3DTiles] external tileset parse failed {res.url}: {e}")
            changed = True
            continue
        st["ready"].append((tile, res.parts))
        changed = True

    # 2. budgeted imports
    imported = 0
    enu = _enu_from_ecef(props)
    root_obj, coll = _root_and_coll(scene, st)
    while st["ready"] and imported < max(1, props.imports_per_tick):
        tile, parts = st["ready"].pop(0)
        key = _tile_key(tile)
        holders, data = [], []
        for part in parts:
            m = tile_world_matrix(tile.transform, part.get("rtc"), enu)
            r = import_glb_file(part["path"], key, scene, root_obj, m, hidden=True, coll=coll)
            if r:
                holders.append(r[0])
                data.extend(r[1])
        if holders:
            for i, h in enumerate(holders):
                tiles[key if i == 0 else f"{key}#{i}"] = _Rec(h, data if i == 0 else [], tile)
            tile.state = TileState.LOADED
        else:
            tile.state = TileState.FAILED
            st["failed_at"][key] = now
        imported += 1
        changed = True

    # 3. selection
    view = _view_for(st)
    need = view is not None and (
        view.signature != st["last_sig"] or changed or now - st["last_sel_t"] > SELECTION_MAX_AGE_S)
    if need:
        def is_ready(t: Tile) -> bool:
            if t.is_external_tileset:
                return t.grafted
            return t.state == TileState.LOADED

        load, render, _unload = backend.select(view, is_ready)
        render_keys = set()
        for t in render:
            k = _tile_key(t)
            render_keys.add(k)
            i = 1
            while f"{k}#{i}" in tiles:
                render_keys.add(f"{k}#{i}")
                i += 1
        sel = backend.last_selection()
        changed |= _apply_visibility(st, render_keys, sel.keep if sel else set(), now)
        st["last_sig"] = view.signature
        st["last_sel_t"] = now

        # 4. submit loads in priority order
        for t in load:
            if dm.inflight >= dm.max_concurrent:
                break
            if t.state == TileState.FAILED:
                if now - st["failed_at"].get(_tile_key(t), 0) > RETRY_AFTER_S:
                    t.state = TileState.UNLOADED
                else:
                    continue
            dm.enqueue(t)

    # 5. eviction
    changed |= _evict(st, props, now)
    st["pending"] = dm.inflight + len(st["ready"])
    return changed


# ---------------------------------------------------------- native
def _tick_native(scene, props, st, now) -> bool:
    from ..tileset.native_backend import blender_matrix_for_tile

    backend, tiles = st["backend"], st["tiles"]
    changed = False
    backend.tick()

    if not _state["origin_set"]:
        c = backend.root_center_ecef()
        if c is None:
            st["pending"] = 0
            return False
        _set_origin_from_ecef(props, *c)
        _state["origin_set"] = True
        for other in _state["streams"].values():
            other["last_sig"] = None

    for key in backend.pop_freed():
        rec = tiles.pop(key, None)
        if rec is not None:
            remove_tile(rec.holder, rec.data)
            changed = True

    imported = 0
    root_obj, coll = _root_and_coll(scene, st)
    for rt in backend.pop_ready():
        if imported >= max(1, props.imports_per_tick):
            backend.push_back_ready(rt)
            continue
        m = blender_matrix_for_tile(rt.transform_ecef, props.origin_lat, props.origin_lon,
                                    props.origin_height, rt.rtc, rt.up_axis)
        r = import_glb_file(rt.glb_path, rt.key, scene, root_obj, m.tolist(), hidden=True, coll=coll)
        if r:
            tiles[rt.key] = _Rec(r[0], r[1])
        imported += 1
        changed = True

    view = _view_for(st)
    if view is None:
        return changed
    need = (view.signature != st["last_sig"] or changed
            or now - st["last_sel_t"] > SELECTION_MAX_AGE_S)
    if need:
        res = backend.update_view(view.position, view.direction, view.up,
                                  view.viewport_width, view.viewport_height,
                                  view.fov_x, view.fov_y, dt=now - st["last_sel_t"])
        changed |= _apply_visibility(st, set(res.to_render), set(), now)
        st["stats"] = res.stats
        st["last_sig"] = view.signature
        st["last_sel_t"] = now
    s = st["stats"]
    st["pending"] = int(s.get("worker_queue", 0)) + int(s.get("main_queue", 0))
    return changed


# ── Helpers ───────────────────────────────────────────────────────────────────

def _short_label(url: str) -> str:
    base = url.split("?", 1)[0].rstrip("/")
    parts = [p for p in base.split("/") if p]
    if parts and parts[-1].lower().endswith(".json") and len(parts) >= 2:
        return parts[-2][:40]
    return (parts[-1] if parts else "tileset")[:40]


def _root_name(name: str) -> str:
    return ("3D Tiles · " + name)[:60]


def _coll_name(name: str) -> str:
    return ("Tiles · " + name)[:60]


def _add_root_bbox(scene, st):
    """Wireframe cube showing the tileset extent (immediate feedback)."""
    root_tile = st.get("root_tile")
    if root_tile is None:
        return
    try:
        from ..tileset.traversal import ecef_to_enu
        props = scene.ogc3dtiles
        cx, cy, cz, radius = root_tile.sphere_ecef()
        ex, ey, ez = ecef_to_enu((cx, cy, cz), props.origin_lat, props.origin_lon,
                                 props.origin_height)
        root = bpy.data.objects.get(st.get("root_obj") or "")
        name = f"bbox · {st['name']}"[:60]
        old = bpy.data.objects.get(name)
        if old is not None:
            bpy.data.objects.remove(old, do_unlink=True)
        empty = bpy.data.objects.new(name, None)
        empty.empty_display_type = "CUBE"
        empty.empty_display_size = max(radius, 1.0)
        empty["tile_bbox"] = True
        empty.hide_select = True
        coll = bpy.data.collections.get(st.get("coll") or "") or scene.collection
        coll.objects.link(empty)
        if root is not None:
            empty.parent = root
        empty.location = (ex, ey, ez)
    except Exception as e:                           # noqa: BLE001
        print(f"[3DTiles] BBox failed: {e}")


def _orient_viewport(context, props):
    """Only when the view is clearly unset: look at the origin from above."""
    try:
        import mathutils
        for window in context.window_manager.windows:
            for area in window.screen.areas:
                if area.type != "VIEW_3D":
                    continue
                for space in area.spaces:
                    if space.type != "VIEW_3D":
                        continue
                    r3d = space.region_3d
                    if r3d.view_distance > 1e5 or r3d.view_distance < 1.0:
                        r3d.view_rotation = mathutils.Euler(
                            (math.radians(65), 0, 0), "XYZ").to_quaternion()
                        r3d.view_distance = 500.0
                        r3d.view_location = (0.0, 0.0, 0.0)
                    space.clip_end = max(space.clip_end, 1e6)
                    return
    except Exception as e:                           # noqa: BLE001
        print(f"[3DTiles] Viewport orient failed: {e}")


def _set_origin_from_ecef(props, ex, ey, ez):
    lat, lon, h = ecef_to_geodetic(ex, ey, ez)
    props.origin_lat = lat
    props.origin_lon = lon
    props.origin_height = h
    print(f"[3DTiles] Scene origin: lat={lat:.5f} lon={lon:.5f} h={h:.1f}m")


# ── Panels ────────────────────────────────────────────────────────────────────

class OGC3D_UL_Tilesets(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "enabled", text="")
        row.prop(item, "name", text="", emboss=False)
        st = _state["streams"].get(_stream_key(index, item))
        if st is not None and st["backend"] is not None:
            tag = "N" if st["mode"] == "native" else "P"
            row.label(text=f"{tag} {len(st['render_keys'])}/{len(st['tiles'])}")


class OGC3D_PT_MainPanel(Panel):
    bl_label = "OGC 3D Tiles"
    bl_idname = "OGC3D_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "3D Tiles"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        if not hasattr(scene, "ogc3dtiles"):
            layout.label(text="Properties not registered", icon="ERROR")
            layout.operator("script.reload", text="Reload Scripts")
            return
        props = scene.ogc3dtiles

        box = layout.box()
        icon = "RADIOBUT_ON" if props.is_streaming else "RADIOBUT_OFF"
        box.label(text=props.status_text, icon=icon)

        # Tilesets
        layout.separator()
        layout.label(text="Tilesets", icon="WORLD")
        row = layout.row()
        row.template_list("OGC3D_UL_Tilesets", "", props, "tilesets", props, "active_tileset", rows=3)
        col = row.column(align=True)
        col.operator("ogc3dtiles.tileset_add", icon="ADD", text="")
        col.operator("ogc3dtiles.tileset_remove", icon="REMOVE", text="")
        if 0 <= props.active_tileset < len(props.tilesets):
            it = props.tilesets[props.active_tileset]
            b = layout.box()
            b.prop(it, "url", text="URL")
            b.prop(it, "ion_token", text="Ion Token")
            b.prop(it, "max_sse", text="Max SSE")
            st = _state["streams"].get(_stream_key(props.active_tileset, it))
            if st is not None:
                root = bpy.data.objects.get(st["root_obj"] or "")
                if root is not None:
                    b.label(text=f"Root: {root.name}", icon="EMPTY_AXIS")
                if st.get("error"):
                    b.label(text=st["error"][:60], icon="ERROR")
        else:
            layout.prop(props, "tileset_url", text="URL")
            layout.prop(props, "cesium_ion_token", text="Ion Token")

        # Backend
        layout.separator()
        layout.label(text="Backend", icon="MOD_DYNAMICPAINT")
        prefs = _get_prefs(context)
        if hasattr(prefs, "bl_rna"):
            row = layout.row()
            row.enabled = not props.is_streaming
            row.prop(prefs, "traversal_backend", text="")
        ok, status = _cesium_status
        layout.label(text=f"cesium-native-python: {status}", icon="CHECKMARK" if ok else "INFO")
        for st in _state["streams"].values():
            if st["backend"] is None:
                continue
            running = "cesium-native" if st["mode"] == "native" else "Pure Python"
            if st["mode"] == "native":
                s = st.get("stats") or {}
                extra = (f"visited {s.get('tiles_visited', 0)} culled {s.get('tiles_culled', 0)} "
                         f"{s.get('bytes', 0) / 1e6:.0f} MB")
            else:
                sel = st["backend"].last_selection()
                extra = (f"visited {sel.visited} culled {sel.culled} render {len(sel.render)} "
                         f"load {len(sel.load)}") if sel else ""
            layout.label(text=f"{st['name'][:18]}: {running}  {extra}",
                         icon="PLAY" if props.is_streaming else "PAUSE")

        # Origin
        layout.separator()
        layout.label(text="Scene Origin", icon="ORIENTATION_GLOBAL")
        layout.prop(props, "use_tileset_center")
        col = layout.column()
        col.enabled = not props.use_tileset_center
        col.prop(props, "origin_lat", text="Latitude °")
        col.prop(props, "origin_lon", text="Longitude °")
        col.prop(props, "origin_height", text="Height m")

        # LOD
        layout.separator()
        layout.label(text="LOD", icon="DRIVER_DISTANCE")
        layout.prop(props, "max_screen_space_error", text="Default SSE")
        layout.prop(props, "detail_falloff", text="Detail Falloff m")
        layout.prop(props, "load_distance", text="Max Distance m")
        layout.prop(props, "max_loaded_tiles", text="Max Tiles / tileset")

        # Streaming
        layout.separator()
        layout.label(text="Streaming", icon="SORTTIME")
        layout.prop(props, "max_concurrent_requests", text="Parallel DL")
        layout.prop(props, "imports_per_tick", text="Imports / tick")
        row = layout.row(align=True)
        row.prop(props, "use_disk_cache", text="Disk cache")
        row.operator("ogc3dtiles.clear_cache", icon="TRASH", text="")

        layout.separator()
        row = layout.row(align=True)
        if not props.is_streaming:
            row.operator("ogc3dtiles.start_stream", icon="PLAY", text="Start")
        else:
            row.operator("ogc3dtiles.stop_stream", icon="PAUSE", text="Stop")
        layout.operator("ogc3dtiles.clear_tiles", icon="TRASH", text="Clear All Tiles")


class OGC3D_PT_CoordPanel(Panel):
    bl_label = "Coordinate Info"
    bl_idname = "OGC3D_PT_coord"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "3D Tiles"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        col = box.column(align=True)
        col.label(text="ENU ↔ Blender XYZ:  E→X  N→Y  U→Z")
        col.label(text="Tile Empty = ENU·T_tile·RTC; importer handles Y-up")
        scene = context.scene
        if not hasattr(scene, "ogc3dtiles"):
            return
        props = scene.ogc3dtiles
        cursor = scene.cursor.location
        try:
            from ..tileset.traversal import blender_to_ecef
            lat, lon, h = props.origin_lat, props.origin_lon, props.origin_height
            x, y, z = blender_to_ecef(tuple(cursor), lat, lon, h)
            clat, clon, ch = ecef_to_geodetic(x, y, z)
            layout.separator()
            layout.label(text=f"Origin: {lat:.5f}°, {lon:.5f}°, {h:.1f}m")
            layout.label(text=f"Cursor: {clat:.6f}°, {clon:.6f}°, {ch:.1f}m")
            layout.label(text=f"Cursor ECEF: ({x:.0f}, {y:.0f}, {z:.0f})")
        except Exception:
            pass


# ── Registration ──────────────────────────────────────────────────────────────
_classes = [
    OGC3D_OT_TilesetAdd,
    OGC3D_OT_TilesetRemove,
    OGC3D_OT_StartStream,
    OGC3D_OT_StopStream,
    OGC3D_OT_ClearTiles,
    OGC3D_OT_ClearCache,
    OGC3D_OT_ModalStream,
    OGC3D_UL_Tilesets,
    OGC3D_PT_MainPanel,
    OGC3D_PT_CoordPanel,
]


def register():
    _refresh_cesium_status()
    for cls in _classes:
        bpy.utils.register_class(cls)


def unregister():
    for st in _state["streams"].values():
        dm = st.get("download_mgr")
        if dm:
            try:
                dm.shutdown()
            except Exception:
                pass
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
