"""
ui/__init__.py — Sidebar panel + modal streaming operator

Per tick (50 ms):
  1. drain worker results (grafts external tilesets, queues ready GLBs),
  2. import at most ``imports_per_tick`` GLBs (keeps the UI responsive),
  3. re-run the selection only if the view changed, something arrived, or
     0.5 s passed,
  4. submit loads in priority order up to the download concurrency,
  5. evict least-recently-wanted tiles above ``max_loaded_tiles``.

The cesium-native backend follows the same loop; it just hands us ready
GLBs itself (see tileset/native_backend.py).
"""
from __future__ import annotations

import json
import math
import time

import bpy
from bpy.types import Operator, Panel

from ..camera import CesiumCameraAdapter
from ..io import (
    DiskCache,
    TileDownloadManager,
    default_cache_dir,
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


# ── Global stream state ───────────────────────────────────────────────────────
class _Rec:
    __slots__ = ("holder", "data", "last_wanted", "visible", "tile")

    def __init__(self, holder, data, tile=None):
        self.holder = holder
        self.data = data
        self.last_wanted = time.monotonic()
        self.visible = False
        self.tile = tile


def _fresh_state() -> dict:
    return {
        "backend": None,
        "mode": "python",          # or "native"
        "download_mgr": None,
        "camera_adapter": None,
        "root_tile": None,
        "root_obj": None,          # name of the per-tileset root Empty
        "tiles": {},               # key → _Rec (imported)
        "ready": [],               # python mode: [(tile, parts)] waiting for import
        "failed_at": {},           # key → monotonic time
        "last_sig": None,
        "last_sel_t": 0.0,
        "last_evict_t": 0.0,
        "render_keys": set(),
        "keep_keys": set(),
        "origin_set": False,
        "stats": {},
    }


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


# ── Operators ─────────────────────────────────────────────────────────────────

class OGC3D_OT_StartStream(Operator):
    """Start streaming the OGC 3D Tiles tileset"""
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
        if not props.tileset_url.strip():
            self.report({"ERROR"}, "No tileset URL")
            return {"CANCELLED"}

        _state = _fresh_state()
        props.status_text = "Connecting…"
        props.tiles_loaded = 0
        props.tiles_pending = 0
        prefs = _get_prefs(context)
        choice = getattr(prefs, "traversal_backend", "AUTO") or "AUTO"
        cache = DiskCache(default_cache_dir(), enabled=props.use_disk_cache)

        try:
            backend = make_backend(choice, max_sse=props.max_screen_space_error,
                                   max_tiles=props.max_loaded_tiles,
                                   detail_falloff=props.detail_falloff,
                                   max_dist=props.load_distance,
                                   cache_dir=cache.root if props.use_disk_cache else None)
        except ImportError as e:
            self.report({"ERROR"}, str(e).splitlines()[0])
            return {"CANCELLED"}

        if isinstance(backend, PythonBackend):
            root_tile = self._fetch_tileset_json(props)
            if root_tile is None:
                return {"CANCELLED"}
            backend.set_root(root_tile)
            _state["root_tile"] = root_tile
            if props.use_tileset_center:
                cx, cy, cz, _r = root_tile.sphere_ecef()
                _set_origin_from_ecef(props, cx, cy, cz)
            _state["origin_set"] = True
            _state["download_mgr"] = TileDownloadManager(
                max_concurrent=props.max_concurrent_requests,
                token=props.cesium_ion_token, cache=cache)
            _state["mode"] = "python"
        else:
            headers = {}
            if props.cesium_ion_token and not props.tileset_url.strip().isdigit():
                headers["Authorization"] = f"Bearer {props.cesium_ion_token}"
            try:
                backend.load_tileset(url=props.tileset_url, ion_token=props.cesium_ion_token,
                                     options={"request_headers": headers})
            except Exception as e:                   # noqa: BLE001
                self.report({"ERROR"}, f"cesium-native: {e}")
                return {"CANCELLED"}
            _state["mode"] = "native"
            _state["origin_set"] = not props.use_tileset_center

        _state["backend"] = backend
        _state["camera_adapter"] = CesiumCameraAdapter(scene)
        _state["root_obj"] = ensure_root_empty(scene, _root_name(props.tileset_url)).name
        _orient_viewport(context, props)
        _add_root_bbox(scene, _state.get("root_tile"))
        if bpy.app.background:
            props.is_streaming = True      # drive with ui.stream_tick() yourself
        else:
            bpy.ops.ogc3dtiles.modal_stream("INVOKE_DEFAULT")
        return {"FINISHED"}

    def _fetch_tileset_json(self, props):
        headers = {}
        if props.cesium_ion_token:
            headers["Authorization"] = f"Bearer {props.cesium_ion_token}"
        try:
            raw = http_get(props.tileset_url, headers)
            data = json.loads(raw.decode("utf-8"))
            return parse_tileset(data, props.tileset_url)
        except Exception as e:                       # noqa: BLE001
            self.report({"ERROR"}, f"Failed to fetch tileset.json: {e}")
            return None


class OGC3D_OT_StopStream(Operator):
    """Stop streaming"""
    bl_idname = "ogc3dtiles.stop_stream"
    bl_label = "Stop Streaming"
    bl_options = {"REGISTER"}

    def execute(self, context):
        context.scene.ogc3dtiles.is_streaming = False
        dm = _state.get("download_mgr")
        if dm:
            dm.cancel_all()
        b = _state.get("backend")
        if b is not None and _state.get("mode") == "native":
            try:
                b.teardown()
            except Exception:
                pass
        context.scene.ogc3dtiles.status_text = "Stopped"
        return {"FINISHED"}


class OGC3D_OT_ClearTiles(Operator):
    """Remove all loaded tile objects and their mesh data from scene"""
    bl_idname = "ogc3dtiles.clear_tiles"
    bl_label = "Clear All Tiles"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        if context.scene.ogc3dtiles.is_streaming:
            bpy.ops.ogc3dtiles.stop_stream()
        n = 0
        for rec in list(_state["tiles"].values()):
            remove_tile(rec.holder, rec.data)
            n += 1
        _state["tiles"].clear()
        # anything left over from earlier sessions
        for o in list(bpy.data.objects):
            if "tile_url" in o or o.get("tile_bbox") or o.get("ogc3dtiles_root"):
                for c in list(o.children_recursive):
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
                changed = self._tick(context)
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

    # ------------------------------------------------------------------
    def _tick(self, context) -> bool:
        return stream_tick(context)

    def _finish(self, context):
        if self._timer:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None


def stream_tick(context) -> bool:
    """One streaming step. Module-level so it can be driven without a window."""
    scene = context.scene
    props = scene.ogc3dtiles
    backend = _state["backend"]
    if backend is None:
        return False
    now = time.monotonic()
    if _state["mode"] == "native":
        return _tick_native(scene, props, backend, now)
    return _tick_python(scene, props, backend, now)


class _Ticks:
    # ---------------------------------------------------------- python
    def _tick_python(self, scene, props, backend, now) -> bool:
        dm = _state["download_mgr"]
        tiles = _state["tiles"]
        changed = False

        # 1. results from workers
        for res in dm.tick():
            tile = res.tile
            key = _tile_key(tile)
            if res.error:
                tile.state = TileState.FAILED
                _state["failed_at"][key] = now
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
            _state["ready"].append((tile, res.parts))
            changed = True

        # 2. budgeted imports
        imported = 0
        enu = _enu_from_ecef(props)
        root_obj = bpy.data.objects.get(_state["root_obj"]) or ensure_root_empty(
            scene, _root_name(props.tileset_url))
        while _state["ready"] and imported < max(1, props.imports_per_tick):
            tile, parts = _state["ready"].pop(0)
            key = _tile_key(tile)
            holders, data = [], []
            for part in parts:
                m = tile_world_matrix(tile.transform, part.get("rtc"), enu)
                r = import_glb_file(part["path"], key, scene, root_obj, m, hidden=True)
                if r:
                    holders.append(r[0])
                    data.extend(r[1])
            if holders:
                # several parts (cmpt) → one record per part under the same key
                for i, h in enumerate(holders):
                    tiles[key if i == 0 else f"{key}#{i}"] = _Rec(h, data if i == 0 else [], tile)
                tile.state = TileState.LOADED
                props.tiles_loaded += 1
            else:
                tile.state = TileState.FAILED
                _state["failed_at"][key] = now
            imported += 1
            changed = True

        # 3. selection
        cam = _state["camera_adapter"]
        view = cam.get_view_state(bpy.data.objects.get(_state["root_obj"] or ""))
        need = view is not None and (
            view.signature != _state["last_sig"]
            or changed
            or now - _state["last_sel_t"] > SELECTION_MAX_AGE_S
        )
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
            keep_ids = sel.keep if sel is not None else set()
            for k, rec in tiles.items():
                vis = k in render_keys
                if vis or (rec.tile is not None and id(rec.tile) in keep_ids):
                    rec.last_wanted = now
                if vis != rec.visible:
                    set_tile_visible(rec.holder, vis)
                    rec.visible = vis
                    changed = True
            _state["render_keys"] = render_keys
            _state["last_sig"] = view.signature
            _state["last_sel_t"] = now

            # 4. submit loads in priority order
            for t in load:
                if dm.inflight >= dm.max_concurrent:
                    break
                if t.state == TileState.FAILED:
                    if now - _state["failed_at"].get(_tile_key(t), 0) > RETRY_AFTER_S:
                        t.state = TileState.UNLOADED
                    else:
                        continue
                dm.enqueue(t)

        # 5. eviction
        if now - _state["last_evict_t"] > EVICT_PERIOD_S:
            _state["last_evict_t"] = now
            over = len(tiles) - props.max_loaded_tiles
            if over > 0:
                victims = sorted((rec.last_wanted, k) for k, rec in tiles.items()
                                 if not rec.visible and now - rec.last_wanted > EVICT_GRACE_S)
                for _t, k in victims[:over]:
                    rec = tiles.pop(k)
                    remove_tile(rec.holder, rec.data)
                    if rec.tile is not None:
                        rec.tile.state = TileState.UNLOADED
                    changed = True

        props.tiles_pending = dm.inflight + len(_state["ready"])
        st = dm.stats
        props.status_text = (f"Loaded {len(tiles)}  Visible {len(_state['render_keys'])}  "
                             f"Queue {props.tiles_pending}  Cache {st['hits']}/{st['downloads']}")
        return changed

    # ---------------------------------------------------------- native
    def _tick_native(self, scene, props, backend, now) -> bool:
        from ..tileset.native_backend import blender_matrix_for_tile

        tiles = _state["tiles"]
        changed = False
        backend.tick()

        if not _state["origin_set"]:
            c = backend.root_center_ecef()
            if c is None:
                props.status_text = "Waiting for tileset.json…"
                return False
            _set_origin_from_ecef(props, *c)
            _state["origin_set"] = True
            _state["last_sig"] = None

        for key in backend.pop_freed():
            rec = tiles.pop(key, None)
            if rec is not None:
                remove_tile(rec.holder, rec.data)
                changed = True

        imported = 0
        root_obj = bpy.data.objects.get(_state["root_obj"]) or ensure_root_empty(
            scene, _root_name(props.tileset_url))
        ready = backend.pop_ready()
        for rt in ready:
            if imported >= max(1, props.imports_per_tick):
                backend.push_back_ready(rt)
                continue
            m = blender_matrix_for_tile(rt.transform_ecef, props.origin_lat, props.origin_lon,
                                        props.origin_height, rt.rtc, rt.up_axis)
            r = import_glb_file(rt.glb_path, rt.key, scene, root_obj, m.tolist(), hidden=True)
            if r:
                tiles[rt.key] = _Rec(r[0], r[1])
                props.tiles_loaded += 1
            imported += 1
            changed = True

        cam = _state["camera_adapter"]
        view = cam.get_view_state(bpy.data.objects.get(_state["root_obj"] or ""))
        if view is None:
            return changed
        need = (view.signature != _state["last_sig"] or changed
                or now - _state["last_sel_t"] > SELECTION_MAX_AGE_S)
        if need:
            res = backend.update_view(view.position, view.direction, view.up,
                                      view.viewport_width, view.viewport_height,
                                      view.fov_x, view.fov_y,
                                      dt=now - _state["last_sel_t"])
            render_keys = set(res.to_render)
            for k, rec in tiles.items():
                vis = k in render_keys
                if vis:
                    rec.last_wanted = now
                if vis != rec.visible:
                    set_tile_visible(rec.holder, vis)
                    rec.visible = vis
                    changed = True
            _state["render_keys"] = render_keys
            _state["stats"] = res.stats
            _state["last_sig"] = view.signature
            _state["last_sel_t"] = now

        st = _state["stats"]
        props.tiles_pending = int(st.get("worker_queue", 0)) + int(st.get("main_queue", 0))
        props.status_text = (f"[native] Loaded {len(tiles)}  Visible {len(_state['render_keys'])}  "
                             f"Queue {props.tiles_pending}  {st.get('progress', 0):.0f}%")
        return changed


_tick_python = _Ticks()._tick_python
_tick_native = _Ticks()._tick_native


# ── Helpers ───────────────────────────────────────────────────────────────────

def _root_name(url: str) -> str:
    base = url.split("?", 1)[0].rstrip("/")
    parts = [p for p in base.split("/") if p]
    tail = "/".join(parts[-2:]) if len(parts) >= 2 else (parts[-1] if parts else "tileset")
    return ("3D Tiles · " + tail)[:60]


def _add_root_bbox(scene, root_tile):
    """Wireframe cube showing the tileset extent (immediate feedback)."""
    if root_tile is None:
        return
    try:
        from ..tileset.traversal import ecef_to_enu
        props = scene.ogc3dtiles
        cx, cy, cz, radius = root_tile.sphere_ecef()
        ex, ey, ez = ecef_to_enu((cx, cy, cz), props.origin_lat, props.origin_lon,
                                 props.origin_height)
        for obj in list(bpy.data.objects):
            if obj.get("tile_bbox"):
                bpy.data.objects.remove(obj, do_unlink=True)
        empty = bpy.data.objects.new("tileset_bbox", None)
        empty.empty_display_type = "CUBE"
        empty.empty_display_size = max(radius, 1.0)
        empty.location = (ex, ey, ez)
        empty["tile_bbox"] = True
        scene.collection.objects.link(empty)
        empty.hide_select = True
        root = bpy.data.objects.get(_state.get("root_obj") or "")
        if root is not None:
            empty.parent = root
            empty.matrix_parent_inverse = root.matrix_world.inverted()
        print(f"[3DTiles] BBox at ENU ({ex:.0f}, {ey:.0f}, {ez:.0f}) radius={radius:.0f}m")
    except Exception as e:                           # noqa: BLE001
        print(f"[3DTiles] BBox failed: {e}")


def _orient_viewport(context, props):
    """Only on first start: look at the origin from above with Z up."""
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

        layout.separator()
        layout.label(text="Source", icon="WORLD")
        layout.prop(props, "tileset_url", text="URL")
        layout.prop(props, "cesium_ion_token", text="Ion Token")

        # Backend: preference dropdown (AUTO / CESIUM / PYTHON) + what is running
        layout.separator()
        layout.label(text="Backend", icon="MOD_DYNAMICPAINT")
        prefs = _get_prefs(context)
        if hasattr(prefs, "bl_rna"):
            row = layout.row()
            row.enabled = not props.is_streaming
            row.prop(prefs, "traversal_backend", text="")
        ok, status = _cesium_status
        layout.label(text=f"cesium-native-python: {status}",
                     icon="CHECKMARK" if ok else "INFO")
        if _state.get("backend") is not None:
            mode = _state.get("mode")
            running = "cesium-native" if mode == "native" else "Pure Python"
            layout.label(text=f"Running: {running}" + ("" if props.is_streaming else " (stopped)"),
                         icon="PLAY" if props.is_streaming else "PAUSE")
            st = _state.get("stats") or {}
            if mode == "native" and st:
                layout.label(text=f"visited {st.get('tiles_visited', 0)}  culled {st.get('tiles_culled', 0)}  "
                                  f"queue {st.get('worker_queue', 0)}/{st.get('main_queue', 0)}  "
                                  f"{st.get('bytes', 0) / 1e6:.0f} MB")
            elif mode == "python":
                sel = _state["backend"].last_selection()
                if sel is not None:
                    layout.label(text=f"visited {sel.visited}  culled {sel.culled}  "
                                      f"render {len(sel.render)}  load {len(sel.load)}")

        layout.separator()
        layout.label(text="Scene Origin", icon="ORIENTATION_GLOBAL")
        layout.prop(props, "use_tileset_center")
        col = layout.column()
        col.enabled = not props.use_tileset_center
        col.prop(props, "origin_lat", text="Latitude °")
        col.prop(props, "origin_lon", text="Longitude °")
        col.prop(props, "origin_height", text="Height m")

        layout.separator()
        layout.label(text="LOD", icon="DRIVER_DISTANCE")
        layout.prop(props, "max_screen_space_error", text="Max SSE")
        layout.prop(props, "detail_falloff", text="Detail Falloff m")
        layout.prop(props, "load_distance", text="Max Distance m")
        layout.prop(props, "max_loaded_tiles", text="Max Tiles")

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
        if props.is_streaming:
            row2 = layout.row()
            row2.label(text=f"Loaded: {props.tiles_loaded}")
            row2.label(text=f"Queued: {props.tiles_pending}")
        root = bpy.data.objects.get(_state.get("root_obj") or "")
        if root is not None:
            layout.label(text=f"Root empty: {root.name}  (move/scale it to transform the tileset)",
                         icon="EMPTY_AXIS")


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
            sel = _state.get("backend").last_selection() if (
                _state.get("backend") is not None and _state.get("mode") == "python") else None
            if sel is not None:
                layout.label(text=f"Traversal: visited {sel.visited}  culled {sel.culled}  "
                                  f"render {len(sel.render)}  load {len(sel.load)}")
        except Exception:
            pass


# ── Registration ──────────────────────────────────────────────────────────────
_classes = [
    OGC3D_OT_StartStream,
    OGC3D_OT_StopStream,
    OGC3D_OT_ClearTiles,
    OGC3D_OT_ClearCache,
    OGC3D_OT_ModalStream,
    OGC3D_PT_MainPanel,
    OGC3D_PT_CoordPanel,
]


def register():
    _refresh_cesium_status()
    for cls in _classes:
        bpy.utils.register_class(cls)


def unregister():
    dm = _state.get("download_mgr")
    if dm:
        try:
            dm.shutdown()
        except Exception:
            pass
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
