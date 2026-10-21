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
import uuid

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
    build_tile_from_payload,
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
    geodetic_to_ecef,
    graft_external,
    parse_tileset,
)

SELECTION_MAX_AGE_S = 0.5
EVICT_PERIOD_S = 2.0
EVICT_GRACE_S = 10.0       # never evict something the traversal wanted recently
RETRY_AFTER_S = 5.0
START_RETRY_S = 15.0       # re-try a tileset whose start failed (bad URL, offline …)

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
    return {"streams": {}, "camera_adapter": None, "origin_set": False,
            "choice": "AUTO", "cache": None, "start_failed": {}}


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
        empty = next((x for x in props.tilesets if not x.url.strip()), None)
        it = empty if empty is not None else props.tilesets.add()
        it.name = _short_label(props.tileset_url)
        it.url = props.tileset_url.strip()
        it.ion_token = props.cesium_ion_token
        it.max_sse = props.max_screen_space_error
        it.enabled = True
        idx = next(i for i, x in enumerate(props.tilesets) if x == it)
        props.active_tileset = idx
        items = [(idx, it)]
    return items


def _item_key(item) -> str:
    """Stable per-entry id (survives list reordering / removal)."""
    if not item.uid:
        item.uid = uuid.uuid4().hex[:12]
    return item.uid


def _stream_key(index, item) -> str:      # kept for callers using the old signature
    return _item_key(item)


def effective_sse(props, item) -> float:
    """Global Max SSE is the live renderer setting; a tileset can override it."""
    return float(item.max_sse) if item.use_own_sse else float(props.max_screen_space_error)


def _push_sse(st, value):
    if st is None or st.get("backend") is None:
        return
    st["max_sse"] = value
    try:
        st["backend"].set_max_sse(float(value))
    except Exception as e:                           # noqa: BLE001
        print(f"[3DTiles] set_max_sse failed: {e}")
    st["last_sig"] = None                 # force a re-selection on the next tick


def apply_item_sse(item):
    """Live per-tileset SSE edit → its running backend."""
    props = bpy.context.scene.ogc3dtiles
    st = _state["streams"].get(item.uid) if item.uid else None
    _push_sse(st, effective_sse(props, item))


def apply_global_sse(props):
    """Live global SSE edit → every stream that does not override it."""
    for item in props.tilesets:
        if not item.use_own_sse and item.uid:
            _push_sse(_state["streams"].get(item.uid), float(props.max_screen_space_error))


# ── Operators ─────────────────────────────────────────────────────────────────

class OGC3D_OT_TilesetAdd(Operator):
    """Add a tileset entry (prefilled from the URL field)"""
    bl_idname = "ogc3dtiles.tileset_add"
    bl_label = "Add Tileset"

    def execute(self, context):
        props = context.scene.ogc3dtiles
        url = props.tileset_url.strip()
        if any(x.url.strip() == url for x in props.tilesets):
            url = ""                    # already in the list: new, empty entry
        it = props.tilesets.add()
        it.url = url
        it.ion_token = props.cesium_ion_token
        it.max_sse = props.max_screen_space_error
        it.name = _short_label(it.url) if it.url else f"tileset {len(props.tilesets)}"
        props.active_tileset = len(props.tilesets) - 1
        props.tileset_url = ""
        return {"FINISHED"}


class OGC3D_OT_TilesetRemove(Operator):
    """Remove the selected tileset entry (and its objects)"""
    bl_idname = "ogc3dtiles.tileset_remove"
    bl_label = "Remove Tileset"

    def execute(self, context):
        props = context.scene.ogc3dtiles
        i = props.active_tileset
        if 0 <= i < len(props.tilesets):
            key = _item_key(props.tilesets[i])
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

        # tiles left on screen by Stop belong to a dead selection: drop them so
        # a restart never keeps stale geometry around
        for st in list(_state["streams"].values()):
            _teardown_stream(st, remove_objects=True)
        _state = _fresh_state()
        props.status_text = "Connecting…"
        props.tiles_loaded = 0
        props.tiles_pending = 0
        prefs = _get_prefs(context)
        _state["choice"] = getattr(prefs, "traversal_backend", "AUTO") or "AUTO"
        _state["cache"] = DiskCache(default_cache_dir(), enabled=props.use_disk_cache)
        _state["camera_adapter"] = CesiumCameraAdapter(scene)
        # CUSTOM: the user's lat/lon/h is the origin; KEEP: a previously set
        # origin stays; AUTO: decided per tileset in _decide_origin()
        if props.origin_mode == "CUSTOM":
            props.origin_valid = True
        _state["origin_set"] = props.origin_mode == "CUSTOM" or (
            props.origin_mode == "KEEP" and props.origin_valid)

        started = 0
        for index, item in items:
            st = _start_item(scene, props, item)
            if st.get("error"):
                self.report({"WARNING"}, f"{st['name']}: {st['error']}")
            else:
                started += 1
        if not started:
            self.report({"ERROR"}, "No tileset could be started")
            return {"CANCELLED"}

        _orient_viewport(context, props)
        if props.hide_relation_lines:
            _set_relationship_lines(context, False)
        if bpy.app.background:
            props.is_streaming = True      # drive with ui.stream_tick() yourself
        else:
            bpy.ops.ogc3dtiles.modal_stream("INVOKE_DEFAULT")
        return {"FINISHED"}



def _start_item(scene, props, item) -> dict:
    """Create and start the stream for one list entry; registers it in
    ``_state`` (with ``error`` set when the start failed)."""
    st = _new_stream(_item_key(item), item.name or _short_label(item.url),
                     item.url.strip(), item.ion_token, effective_sse(props, item))
    try:
        _start_stream(scene, props, st, _state["choice"], _state["cache"])
        if st["name"] != item.name:
            item.name = st["name"]
    except Exception as e:                           # noqa: BLE001
        import traceback
        traceback.print_exc()
        st["error"] = str(e)
        st["backend"] = None
        _state["start_failed"][st["key"]] = time.monotonic()
    _state["streams"][st["key"]] = st
    return st


def _start_stream(scene, props, st, choice, cache) -> None:
    backend = make_backend(choice, max_sse=st["max_sse"],
                           max_tiles=props.max_loaded_tiles,
                           detail_falloff=props.detail_falloff,
                           max_dist=props.load_distance,
                           cache_dir=cache.root if props.use_disk_cache else None,
                           direct_mesh=props.native_direct_mesh,
                           foveated_cone=props.foveated_cone,
                           foveated_relaxation=props.foveated_relaxation)
    # two entries can share a label (same share-link token, user-typed names):
    # give the second one its own collection + root Empty
    label = st["name"]
    taken = {o["name"] for k, o in _state["streams"].items() if k != st["key"] and o.get("coll")}
    if label in taken:
        n = 2
        while f"{label} - {n}" in taken:
            n += 1
        label = f"{label} - {n}"
    st["name"] = label
    sub = _coll_name(label)
    st["coll"] = ensure_collection(scene, sub).name
    st["root_obj"] = ensure_root_empty(scene, _root_name(label), sub).name

    if isinstance(backend, PythonBackend):
        headers = {}
        if st["token"]:
            headers["Authorization"] = f"Bearer {st['token']}"
        raw = http_get(st["url"], headers)
        data = json.loads(raw.decode("utf-8"))
        root_tile = parse_tileset(data, st["url"])
        backend.set_root(root_tile)
        st["root_tile"] = root_tile
        cx, cy, cz, root_r = root_tile.sphere_ecef()
        _decide_origin(props, (cx, cy, cz))
        if not bpy.app.background:
            fit_clip_range(root_r)
        st["download_mgr"] = TileDownloadManager(
            max_concurrent=props.max_concurrent_requests, token=st["token"], cache=cache,
            direct_mesh=props.native_direct_mesh)
        st["mode"] = "python"
        _add_root_bbox(scene, st)
    else:
        headers = {}
        if st["token"] and not st["url"].isdigit():
            headers["Authorization"] = f"Bearer {st['token']}"
        backend.main_thread_ms = max(4.0, 12.0 * props.imports_per_tick)
        backend.on_main_thread_ready = _make_native_builder(scene, props, st)
        backend.load_tileset(url=st["url"], ion_token=st["token"],
                             options={"request_headers": headers})
        st["mode"] = "native"
    st["backend"] = backend


def _decide_origin(props, center_ecef) -> None:
    """Scene-origin policy, evaluated when a tileset's centre becomes known.
    Only the first tileset of a session can move the origin; afterwards every
    stream shares it."""
    if _state["origin_set"]:
        return
    cx, cy, cz = center_ecef
    if props.origin_mode == "AUTO" and props.origin_valid:
        ox, oy, oz = geodetic_to_ecef(props.origin_lat, props.origin_lon, props.origin_height)
        d_km = math.dist((cx, cy, cz), (ox, oy, oz)) / 1000.0
        if d_km <= props.origin_reuse_km:
            print(f"[3DTiles] Scene origin kept (tileset centre {d_km:.1f} km away)")
            _state["origin_set"] = True
            for other in _state["streams"].values():
                other["last_sig"] = None
            return
        print(f"[3DTiles] Scene origin re-centred: tileset centre {d_km:.1f} km "
              f"> {props.origin_reuse_km:g} km")
    _set_origin_from_ecef(props, cx, cy, cz)
    props.origin_valid = True
    _state["origin_set"] = True
    for other in _state["streams"].values():
        other["last_sig"] = None


class OGC3D_OT_OriginReset(Operator):
    """Forget the stored origin so the next Start re-centres on the first tileset"""
    bl_idname = "ogc3dtiles.origin_reset"
    bl_label = "Reset Origin"

    def execute(self, context):
        props = context.scene.ogc3dtiles
        props.origin_valid = False
        _state["origin_set"] = False
        self.report({"INFO"}, "Origin will be re-centred on the next Start")
        return {"FINISHED"}


def _relationship_lines_shown(context) -> bool:
    sd = getattr(context, "space_data", None)
    if sd is not None and sd.type == "VIEW_3D":
        return bool(sd.overlay.show_relationship_lines)
    for area in context.screen.areas:
        if area.type == "VIEW_3D":
            return bool(area.spaces.active.overlay.show_relationship_lines)
    return True


class OGC3D_OT_RelationLines(Operator):
    """Toggle the dashed parent-relation lines overlay in every 3D viewport"""
    bl_idname = "ogc3dtiles.relation_lines"
    bl_label = "Toggle Relation Lines"

    def execute(self, context):
        _set_relationship_lines(context, not _relationship_lines_shown(context))
        return {"FINISHED"}


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

MODAL_RUNNING = [False]     # scripts/dev_watch.py waits for this before a reload


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
        MODAL_RUNNING[0] = True
        return {"RUNNING_MODAL"}

    def _finish(self, context):
        MODAL_RUNNING[0] = False
        if self._timer:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None


def stream_tick(context) -> bool:
    """One streaming step for every stream. Module-level so it can be driven
    without a window (``blender -b``)."""
    scene = context.scene
    props = scene.ogc3dtiles
    now = time.monotonic()
    changed = _sync_streams(scene, props, now)
    _update_view(scene, props)
    loaded = pending = visible = 0
    parts = []
    for st in _state["streams"].values():
        if st["backend"] is None:
            continue
        if st.get("paused"):
            parts.append(f"{st['name'][:14]} paused {len(st['tiles'])}")
            loaded += len(st["tiles"])
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


def _sync_streams(scene, props, now) -> bool:
    """Reconcile the tileset list with the running streams: start entries
    that were added or ticked while streaming, pause unticked ones, tear
    down removed ones."""
    changed = False
    by_key = {}
    for item in props.tilesets:
        by_key[_item_key(item)] = item
    for key in list(_state["streams"].keys()):
        if key not in by_key:
            st = _state["streams"].pop(key)
            _teardown_stream(st, remove_objects=True)
            changed = True
    for key, item in by_key.items():
        st = _state["streams"].get(key)
        want = bool(item.enabled and item.url.strip())
        if st is None:
            if not want:
                continue
            last_fail = _state["start_failed"].get(key)
            if last_fail is not None and now - last_fail < START_RETRY_S:
                continue
            st = _start_item(scene, props, item)
            changed = True
        elif st["backend"] is None:
            # failed earlier: retry when the entry changed or after a delay
            if want and (st["url"] != item.url.strip()
                         or now - _state["start_failed"].get(key, 0) > START_RETRY_S):
                _state["streams"].pop(key, None)
                st = _start_item(scene, props, item)
                changed = True
            continue
        if st["url"] != item.url.strip():
            _state["streams"].pop(key, None)
            _teardown_stream(st, remove_objects=True)
            if want:
                _start_item(scene, props, item)
            changed = True
            continue
        paused = not item.enabled
        if paused != bool(st.get("paused")):
            st["paused"] = paused
            if paused and st.get("download_mgr"):
                st["download_mgr"].cancel_all()
            st["last_sig"] = None
            changed = True
    return changed


def _update_view(scene, props):
    """View-dependent point display, refreshed from the 3D viewport (and from
    the scene camera when rendering, see io._render_pre):
    Screen pixels → eye proxy Empty + per-pixel scale (per-point distance);
    Adaptive → metre bounds from the pixel bounds at the view-pivot distance;
    Disc splats → towards-eye direction for normal-less points."""
    from ..camera import viewport_focus
    from ..io import update_view_proxy, update_adaptive, update_view_dir
    mode = props.point_radius_mode
    discs = props.point_display == "DISCS"
    if mode not in ("SCREEN", "ADAPTIVE") and not discs:
        return
    vf = viewport_focus()
    if vf is None:
        return
    if mode == "SCREEN":
        update_view_proxy(scene, vf.eye, vf.p11, vf.height, vf.persp)
    elif mode == "ADAPTIVE":
        update_adaptive(scene, vf.dist, vf.p11, vf.height)
    if discs:
        update_view_dir(vf.dir)


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
        st["ready"].append((tile, res.parts, res.payloads))
        changed = True

    # 2. budgeted imports
    imported = 0
    enu = _enu_from_ecef(props)
    root_obj, coll = _root_and_coll(scene, st)
    while st["ready"] and imported < max(1, props.imports_per_tick):
        tile, parts, payloads = st["ready"].pop(0)
        key = _tile_key(tile)
        holders, data = [], []
        t_imp = time.perf_counter()
        for i, part in enumerate(parts):
            m = tile_world_matrix(tile.transform, part.get("rtc"), enu)
            payload = payloads[i] if i < len(payloads) else None
            if payload is not None:
                r = build_tile_from_payload(payload, key, scene, root_obj, m, hidden=True, coll=coll)
            else:
                r = import_glb_file(part["path"], key, scene, root_obj, m, hidden=True, coll=coll)
            if r:
                holders.append(r[0])
                data.extend(r[1])
        st["import_s"] = st.get("import_s", 0.0) + (time.perf_counter() - t_imp)
        st["import_n"] = st.get("import_n", 0) + 1
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


def _build_native_tile(scene, props, st, rt) -> bool:
    """Create the Blender object for a native ReadyTile. Returns True on success."""
    from ..tileset.native_backend import blender_matrix_for_tile

    root_obj, coll = _root_and_coll(scene, st)
    m = blender_matrix_for_tile(rt.transform_ecef, props.origin_lat, props.origin_lon,
                                props.origin_height, rt.rtc, rt.up_axis)
    t_imp = time.perf_counter()
    if rt.mesh_payload is not None:
        # build_tile_from_payload folds payload["offset"] into the matrix (float64)
        r = build_tile_from_payload(rt.mesh_payload, rt.key, scene, root_obj, m.tolist(),
                                    hidden=True, coll=coll)
    else:
        r = import_glb_file(rt.glb_path, rt.key, scene, root_obj, m.tolist(), hidden=True, coll=coll)
    st["import_s"] = st.get("import_s", 0.0) + (time.perf_counter() - t_imp)
    st["import_n"] = st.get("import_n", 0) + 1
    if r:
        st["tiles"][rt.key] = _Rec(r[0], r[1])
        st["dirty"] = True
        return True
    return False


def _make_native_builder(scene, props, st):
    """Callback for CesiumNativeBackend.on_main_thread_ready: build immediately
    when the scene origin is known, otherwise let the backend queue it."""
    def cb(rt):
        if not _state["origin_set"]:
            return False
        return _build_native_tile(scene, props, st, rt)
    return cb


# ---------------------------------------------------------- native
def _tick_native(scene, props, st, now) -> bool:
    backend, tiles = st["backend"], st["tiles"]
    changed = False
    backend.tick()      # dispatches cesium-native main-thread work → builds tiles via callback

    if not _state["origin_set"]:
        c = backend.root_center_ecef()
        if c is None:
            st["pending"] = 0
            return False
        _decide_origin(props, c)
    if not st.get("clip_fit"):
        r = backend.root_radius_m()
        if r is not None:
            st["clip_fit"] = True
            if not bpy.app.background:
                fit_clip_range(r)

    for key in backend.pop_freed():
        rec = tiles.pop(key, None)
        if rec is not None:
            remove_tile(rec.holder, rec.data)
            changed = True

    # tiles that arrived before the origin was known (queued by the backend)
    imported = 0
    for rt in backend.pop_ready():
        if imported >= max(1, props.imports_per_tick):
            backend.push_back_ready(rt)
            continue
        try:
            _build_native_tile(scene, props, st, rt)
        except Exception as e:                       # noqa: BLE001
            import traceback
            traceback.print_exc()
            print(f"[3DTiles] tile build failed for {rt.key}: {e}")
        imported += 1
        changed = True
    if st.pop("dirty", False):
        changed = True

    view = _view_for(st)
    if view is None:
        return changed
    need = (view.signature != st["last_sig"] or changed
            or now - st["last_sel_t"] > SELECTION_MAX_AGE_S)
    if need:
        res = backend.update_view(view.native_position, view.direction, view.up,
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
        if len(parts) >= 3 and parts[-3] == "s":        # /s/<token>/<asset>.json
            return parts[-1][:-5][:40]
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


def _set_relationship_lines(context, show: bool):
    """Blender draws a dashed line from every tile to its parent Empty; the
    overlay toggle is per 3D viewport, not per object."""
    try:
        for window in context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == "VIEW_3D":
                    for space in area.spaces:
                        if space.type == "VIEW_3D":
                            space.overlay.show_relationship_lines = show
    except Exception as e:                           # noqa: BLE001
        print(f"[3DTiles] overlay toggle failed: {e}")


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
                    return
    except Exception as e:                           # noqa: BLE001
        print(f"[3DTiles] Viewport orient failed: {e}")


CLIP_END_MIN, CLIP_END_MAX = 1000.0, 2.0e5
CLIP_RATIO_MAX = 1.0e6      # far / near; Alt+B (clip region) breaks past ~1e7


def fit_clip_range(radius_m):
    """Size the 3D viewports' clip range to the tileset: far = a few times the
    root radius, near = far / 1e6.  A fixed far of 1e6 m (the old behaviour)
    made Blender's clipping region (Alt+B) degenerate in perspective and left
    orthographic depth at centimetre precision."""
    try:
        want = min(max(6.0 * float(radius_m or 0.0), CLIP_END_MIN), CLIP_END_MAX)
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type != "VIEW_3D":
                    continue
                for space in area.spaces:
                    if space.type != "VIEW_3D":
                        continue
                    if space.clip_end < want or space.clip_end > CLIP_END_MAX:
                        space.clip_end = want
                    space.clip_start = max(space.clip_start, space.clip_end / CLIP_RATIO_MAX)
                    area.tag_redraw()
    except Exception as e:                           # noqa: BLE001
        print(f"[3DTiles] Clip range fit failed: {e}")


def _set_origin_from_ecef(props, ex, ey, ez):
    lat, lon, h = ecef_to_geodetic(ex, ey, ez)
    props.origin_lat = lat
    props.origin_lon = lon
    props.origin_height = h
    print(f"[3DTiles] Scene origin: lat={lat:.5f} lon={lon:.5f} h={h:.1f}m")


# ── Panels ────────────────────────────────────────────────────────────────────

def _layer_collection(lc, name):
    if lc.collection.name == name:
        return lc
    for child in lc.children:
        r = _layer_collection(child, name)
        if r is not None:
            return r
    return None


class OGC3D_UL_Tilesets(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "enabled", text="")
        row.prop(item, "name", text="", emboss=False)
        st = _state["streams"].get(item.uid) if item.uid else None
        if st is not None and st["backend"] is not None:
            tag = "N" if st["mode"] == "native" else "P"
            if st.get("paused"):
                row.label(text=f"{tag} {len(st['tiles'])}", icon="PAUSE")
            else:
                row.label(text=f"{tag} {len(st['render_keys'])}/{len(st['tiles'])}")
        elif st is not None and st.get("error"):
            row.label(text="", icon="ERROR")
        lc = _layer_collection(context.view_layer.layer_collection, st["coll"])             if st and st.get("coll") else None
        if lc is not None:       # same eye as the outliner (per view layer)
            row.prop(lc, "hide_viewport", text="", emboss=False)


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
            row = b.row(align=True)
            row.prop(it, "use_own_sse", text="")
            sub = row.row(align=True)
            sub.enabled = it.use_own_sse
            sub.prop(it, "max_sse", text="Own SSE")
            st = _state["streams"].get(it.uid) if it.uid else None
            if st is not None:
                root = bpy.data.objects.get(st["root_obj"] or "")
                if root is not None:
                    b.label(text=f"Root: {root.name}", icon="EMPTY_AXIS")
                if st.get("error"):
                    b.label(text=st["error"][:60], icon="ERROR")
        else:
            layout.prop(props, "tileset_url", text="URL")
            layout.prop(props, "cesium_ion_token", text="Ion Token")

        row = layout.row(align=True)
        if not props.is_streaming:
            row.operator("ogc3dtiles.start_stream", icon="PLAY", text="Start")
        else:
            row.operator("ogc3dtiles.stop_stream", icon="PAUSE", text="Stop")
        row.operator("ogc3dtiles.clear_tiles", icon="TRASH", text="Clear All Tiles")

        # Scene origin — right under the list: it decides where tiles land
        header, body = layout.panel("ogc3d_origin", default_closed=True)
        header.label(text="Scene Origin", icon="ORIENTATION_GLOBAL")
        if body:
            body.prop(props, "origin_mode", text="Mode")
            if props.origin_mode == "AUTO":
                body.prop(props, "origin_reuse_km")
            col = body.column()
            col.enabled = props.origin_mode == "CUSTOM"
            col.prop(props, "origin_lat", text="Latitude °")
            col.prop(props, "origin_lon", text="Longitude °")
            col.prop(props, "origin_height", text="Height m")
            row = body.row()
            row.label(text="Origin set" if props.origin_valid else "Origin not set yet",
                      icon="CHECKMARK" if props.origin_valid else "INFO")
            row.operator("ogc3dtiles.origin_reset", text="", icon="FILE_REFRESH")

        # 1. LOD / Streaming — what is shown and how fast it gets here
        header, body = layout.panel("ogc3d_lod", default_closed=False)
        header.label(text="LOD / Streaming", icon="DRIVER_DISTANCE")
        if body:
            col = body.column(align=True)
            col.prop(props, "max_screen_space_error", text="Max SSE (live)")
            col.prop(props, "max_concurrent_requests", text="Parallel DL")
            col.prop(props, "imports_per_tick", text="Imports / tick")
            sub_h, sub = body.panel("ogc3d_lod_advanced", default_closed=True)
            sub_h.label(text="Advanced")
            if sub:
                sub.prop(props, "max_loaded_tiles", text="Max Tiles / tileset")
                row = sub.row(align=True)
                row.prop(props, "foveated_cone", text="Foveation cone")
                row.prop(props, "foveated_relaxation", text="Edge SSE relax")
                sub.prop(props, "detail_falloff", text="Detail Falloff m")
                sub.prop(props, "load_distance", text="Max Distance m")
                sub.prop(props, "native_direct_mesh", text="Direct mesh (numpy, both backends)")
                row = sub.row(align=True)
                row.prop(props, "use_disk_cache", text="Disk cache")
                row.operator("ogc3dtiles.clear_cache", icon="TRASH", text="")
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
                    if st.get("import_n"):
                        extra += f"  import {1000 * st['import_s'] / st['import_n']:.0f} ms/tile"
                    icon = "PAUSE" if (st.get("paused") or not props.is_streaming) else "PLAY"
                    body.label(text=f"{st['name'][:18]}: {running}  {extra}", icon=icon)

        # 2. Display — what the viewport shows (points, overlays)
        header, body = layout.panel("ogc3d_display", default_closed=False)
        header.label(text="Display", icon="OUTLINER_DATA_POINTCLOUD")
        if body:
            row = body.row(align=True)
            row.prop(props, "point_display", text="Points")
            op = row.operator("ogc3dtiles.open_nodes", text="", icon="NODETREE")
            op.kind = "POINTS"
            body.prop(props, "point_radius_mode", text="Radius")
            if props.point_radius_mode == "UNIFORM":
                body.prop(props, "point_radius", text="Radius m")
            elif props.point_radius_mode == "ADAPTIVE":
                body.prop(props, "point_scale", text="Point scale")
                row = body.row(align=True)
                row.prop(props, "point_adapt_min_px", text="Min px")
                row.prop(props, "point_adapt_max_px", text="Max px")
            elif props.point_radius_mode == "SCREEN":
                row = body.row(align=True)
                row.prop(props, "point_px", text="Pixels")
                row.prop(props, "point_px_min_m", text="Min m")
                row.prop(props, "point_px_max_m", text="Max m")
            else:
                body.prop(props, "point_scale", text="Point scale")
            if props.point_display == "MESH":
                body.label(text="Solid mode: Shading → Color → Attribute", icon="INFO")
            elif props.point_display == "DISCS":
                body.label(text="Discs follow glTF normals, else face the view", icon="INFO")
            else:
                body.label(text="Colours in Material Preview / Rendered", icon="INFO")
            row = body.row(align=True)
            row.prop(props, "hide_relation_lines", text="Hide relation lines")
            shown = _relationship_lines_shown(context)
            row.operator("ogc3dtiles.relation_lines", text="",
                         icon="HIDE_OFF" if shown else "HIDE_ON", depress=shown)

        # 3. Materials — relight shader (Material Preview / Rendered)
        header, body = layout.panel("ogc3d_materials", default_closed=False)
        header.label(text="Materials", icon="MATERIAL")
        if body:
            from .. import materials as _materials
            _materials.draw_panel(body, props)

        # 4. Compositor — screen-space beauty pass (Rendered / renders)
        header, body = layout.panel("ogc3d_compositor", default_closed=False)
        header.label(text="Compositor", icon="NODE_COMPOSITING")
        if body:
            from .. import compositor as _compositor
            _compositor.draw_panel(body, props)

        # 5. Backend (advanced)
        header, body = layout.panel("ogc3d_backend", default_closed=True)
        header.label(text="Backend", icon="MOD_DYNAMICPAINT")
        if body:
            prefs = _get_prefs(context)
            if hasattr(prefs, "bl_rna"):
                row = body.row()
                row.enabled = not props.is_streaming
                row.prop(prefs, "traversal_backend", text="")
            ok, status = _cesium_status
            body.label(text=f"cesium-native-python: {status}", icon="CHECKMARK" if ok else "INFO")


class OGC3D_OT_OpenNodes(Operator):
    """Show the add-on's node tree in a node editor (an existing one, or a new
    one split off the 3D viewport) so it can be edited by hand"""
    bl_idname = "ogc3dtiles.open_nodes"
    bl_label = "Open in Node Editor"

    kind: bpy.props.EnumProperty(items=[
        ("RELIGHT", "Relight shader group", "'OGC3D Relight' shader node group"),
        ("COMPOSITOR", "Beauty compositor", "'OGC3D Beauty' compositor tree"),
        ("POINTS", "Point display nodes", "Geometry Nodes group of the current point display mode"),
    ], default="RELIGHT")

    def execute(self, context):
        from .. import materials as _materials
        from .. import compositor as _compositor
        from ..io import _GROUP_FOR_MODE
        props = context.scene.ogc3dtiles
        if self.kind == "RELIGHT":
            ng = bpy.data.node_groups.get(_materials.GROUP_NAME)
            if ng is None:
                _materials.ensure_relight_group()
                ng = bpy.data.node_groups.get(_materials.GROUP_NAME)
            ui_type = "ShaderNodeTree"
        elif self.kind == "COMPOSITOR":
            ng = bpy.data.node_groups.get(_compositor.TREE_NAME)
            if ng is None:
                bpy.ops.ogc3dtiles.compositor_build()
                ng = bpy.data.node_groups.get(_compositor.TREE_NAME)
            ui_type = "CompositorNodeTree"
        else:
            ng = bpy.data.node_groups.get(_GROUP_FOR_MODE.get(props.point_display, "OGC3D Points"))
            if ng is None:
                self.report({"WARNING"}, "No point tile loaded yet (the group is created with the first one)")
                return {"CANCELLED"}
            ui_type = "GeometryNodeTree"
        if ng is None:
            self.report({"ERROR"}, "Node tree not available")
            return {"CANCELLED"}
        area = _node_editor_area(context, ui_type)
        if area is None:
            self.report({"ERROR"}, "Could not open a node editor")
            return {"CANCELLED"}
        space = area.spaces.active
        try:
            if ui_type == "ShaderNodeTree":
                space.shader_type = "OBJECT"
            space.pin = True
            space.node_tree = ng
        except Exception as e:                       # noqa: BLE001
            self.report({"WARNING"}, f"Editor opened, select the tree by hand ({e})")
        area.tag_redraw()
        _view_all_nodes(context, area)
        return {"FINISHED"}


def _node_editor_area(context, ui_type):
    """An existing node editor on this screen, else the 3D viewport split in
    two (bottom 45 % becomes the node editor)."""
    screen = context.screen
    for area in screen.areas:
        if area.type == "NODE_EDITOR":
            area.ui_type = ui_type
            return area
    view = context.area if context.area and context.area.type == "VIEW_3D" else None
    if view is None:
        view = next((a for a in screen.areas if a.type == "VIEW_3D"), None)
    if view is None:
        return None
    before = {a.as_pointer() for a in screen.areas}
    region = next((r for r in view.regions if r.type == "WINDOW"), None)
    try:
        with context.temp_override(area=view, region=region):
            bpy.ops.screen.area_split(direction="HORIZONTAL", factor=0.45)
    except Exception as e:                           # noqa: BLE001
        print(f"[3DTiles] area split failed: {e}")
        return None
    new = next((a for a in screen.areas if a.as_pointer() not in before), None)
    if new is None:
        return None
    new.type = "NODE_EDITOR"
    new.ui_type = ui_type
    return new


def _view_all_nodes(context, area):
    def _later():
        try:
            region = next((r for r in area.regions if r.type == "WINDOW"), None)
            with context.temp_override(area=area, region=region):
                bpy.ops.node.view_all()
        except Exception:
            pass
        return None
    try:
        bpy.app.timers.register(_later, first_interval=0.1)
    except Exception:
        pass


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
    OGC3D_OT_OpenNodes,
    OGC3D_OT_TilesetAdd,
    OGC3D_OT_TilesetRemove,
    OGC3D_OT_StartStream,
    OGC3D_OT_StopStream,
    OGC3D_OT_OriginReset,
    OGC3D_OT_RelationLines,
    OGC3D_OT_ClearTiles,
    OGC3D_OT_ClearCache,
    OGC3D_OT_ModalStream,
    OGC3D_UL_Tilesets,
    OGC3D_PT_MainPanel,
    OGC3D_PT_CoordPanel,
]


EYE_TIMER_S = 0.15


def _eye_tick():
    """Screen / adaptive point sizes depend on the eye position: while a
    stream runs the tick refreshes it, otherwise this timer does (navigating a
    stopped scene, or a .blend reopened later)."""
    try:
        if bpy.app.background:
            return None
        scene = bpy.context.scene
        props = getattr(scene, "ogc3dtiles", None)
        if props is None or props.is_streaming:
            return EYE_TIMER_S
        _update_view(scene, props)
    except Exception:          # noqa: BLE001 — no window / context during file load
        pass
    return EYE_TIMER_S


def register():
    _refresh_cesium_status()
    for cls in _classes:
        bpy.utils.register_class(cls)
    if not bpy.app.background and not bpy.app.timers.is_registered(_eye_tick):
        bpy.app.timers.register(_eye_tick, first_interval=1.0, persistent=True)


def unregister():
    if bpy.app.timers.is_registered(_eye_tick):
        bpy.app.timers.unregister(_eye_tick)
    for st in _state["streams"].values():
        dm = st.get("download_mgr")
        if dm:
            try:
                dm.shutdown()
            except Exception:
                pass
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
