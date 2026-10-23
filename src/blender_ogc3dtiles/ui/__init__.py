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
from ..tileset.native_backend import GLOBE_URL
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
    items = [(i, it) for i, it in enumerate(props.tilesets)
             if it.enabled and (it.url.strip() or it.kind == "GLOBE")]
    if not items and props.tileset_url.strip():
        empty = next((x for x in props.tilesets if not x.url.strip() and x.kind != "GLOBE"), None)
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


def overlay_live_toggle(scene, ov) -> None:
    """OverlayItem.enabled changed: mirror it on the running backend."""
    props = scene.ogc3dtiles
    for it in props.tilesets:
        if any(o == ov for o in it.overlays):
            break
    else:
        return
    st = _state["streams"].get(it.uid) if it.uid else None
    backend = st.get("backend") if st else None
    if backend is None or not hasattr(backend, "add_overlay"):
        return
    if not ov.uid:
        ov.uid = f"ov_{uuid.uuid4().hex[:8]}"
    if ov.enabled:
        spec = _overlay_specs(it, only=ov)
        if spec:
            backend.add_overlay(spec[0])
    else:
        backend.remove_overlay(ov.uid)
    st["overlays"] = _overlay_specs(it)


def _overlay_specs(item, only=None) -> list:
    """Backend specs for the enabled overlays of a tileset list entry."""
    specs = []
    for ov in item.overlays:
        if not ov.enabled or (only is not None and ov != only):
            continue
        if not ov.uid:
            ov.uid = f"ov_{uuid.uuid4().hex[:8]}"
        specs.append({"uid": ov.uid, "kind": ov.kind, "url": ov.url, "key": ov.key,
                      "layer": ov.layer, "style": ov.style, "matrix_set": ov.matrix_set,
                      "image_format": ov.image_format, "min_level": ov.min_level,
                      "max_level": ov.max_level})
    return specs


def _overlay_alpha_lookup(props):
    table = {}
    for it in props.tilesets:
        for ov in it.overlays:
            if ov.uid:
                table[ov.uid] = float(ov.alpha)
    return lambda uid: table.get(uid, 1.0)


def _process_overlay_events(scene, props, st) -> bool:
    """Apply the native backend's raster attach / detach / free events to the
    tile objects; events for tiles not built yet wait in st['pending_overlays']."""
    from .. import overlays as ovl
    backend, tiles = st["backend"], st["tiles"]
    events = backend.pop_overlay_events() if hasattr(backend, "pop_overlay_events") else []
    if not events:
        return False
    pending = st.setdefault("pending_overlays", {})
    alpha_for = _overlay_alpha_lookup(props)
    for ev in events:
        if ev[0] == "free":
            img = bpy.data.images.get(ev[1])
            if img is not None and img.users == 0:
                bpy.data.images.remove(img)
            continue
        key, tid = ev[1], ev[2]
        rec = tiles.get(key)
        obj = bpy.data.objects.get(rec.holder) if rec is not None else None
        if obj is None or obj.type != "MESH":
            if ev[0] == "attach":
                pending.setdefault(key, {})[tid] = ev
            else:
                pending.get(key, {}).pop(tid, None)
            continue
        try:
            ovl.apply_event(obj, ev, alpha_for)
        except Exception as e:                       # noqa: BLE001
            print(f"[3DTiles] overlay {ev[0]} failed on {key}: {e}")
    return True


class OGC3D_OT_OverlayAdd(Operator):
    """Add a raster overlay to the selected tileset (applied on the next Start)"""
    bl_idname = "ogc3dtiles.overlay_add"
    bl_label = "Add Overlay"

    def execute(self, context):
        props = context.scene.ogc3dtiles
        if not (0 <= props.active_tileset < len(props.tilesets)):
            return {"CANCELLED"}
        it = props.tilesets[props.active_tileset]
        ov = it.overlays.add()
        ov.uid = f"ov_{uuid.uuid4().hex[:8]}"
        ov.name = f"overlay {len(it.overlays)}"
        it.active_overlay = len(it.overlays) - 1
        return {"FINISHED"}


class OGC3D_OT_OverlayRemove(Operator):
    """Remove the selected overlay (its rasters are dropped from loaded tiles)"""
    bl_idname = "ogc3dtiles.overlay_remove"
    bl_label = "Remove Overlay"

    def execute(self, context):
        props = context.scene.ogc3dtiles
        if not (0 <= props.active_tileset < len(props.tilesets)):
            return {"CANCELLED"}
        it = props.tilesets[props.active_tileset]
        i = it.active_overlay
        if not (0 <= i < len(it.overlays)):
            return {"CANCELLED"}
        uid = it.overlays[i].uid
        st = _state["streams"].get(it.uid) if it.uid else None
        if st is not None and st.get("backend") is not None and hasattr(st["backend"], "remove_overlay"):
            st["backend"].remove_overlay(uid)
        it.overlays.remove(i)
        it.active_overlay = min(i, len(it.overlays) - 1)
        return {"FINISHED"}


class OGC3D_UL_Overlays(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "enabled", text="")
        row.prop(item, "name", text="", emboss=False)
        row.label(text=item.kind)


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
    url = GLOBE_URL if getattr(item, "kind", "TILESET") == "GLOBE" else item.url.strip()
    st = _new_stream(_item_key(item), item.name or (_short_label(url) if url != GLOBE_URL else "WGS84 globe"),
                     url, item.ion_token, effective_sse(props, item))
    st["overlays"] = _overlay_specs(item)
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
        if st["url"] == GLOBE_URL:
            raise RuntimeError("The WGS84 globe needs the cesium-native backend")
        headers = {}
        if st["token"]:
            headers["Authorization"] = f"Bearer {st['token']}"
        raw = http_get(st["url"], headers)
        data = json.loads(raw.decode("utf-8"))
        root_tile = parse_tileset(data, st["url"])
        backend.set_root(root_tile)
        st["root_tile"] = root_tile
        cx, cy, cz, root_r = root_tile.sphere_ecef()
        _decide_origin(props, (cx, cy, cz), root_r)
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
                             options={"request_headers": headers,
                                      "overlays": st.get("overlays") or []})
        st["mode"] = "native"
    st["backend"] = backend


def _decide_origin(props, center_ecef, radius_m=None) -> None:
    """Scene-origin policy, evaluated when a tileset's centre becomes known.
    Only the first tileset of a session can move the origin; afterwards every
    stream shares it."""
    if _state["origin_set"]:
        return
    cx, cy, cz = center_ecef
    near_centre = math.dist((cx, cy, cz), (0.0, 0.0, 0.0)) < LOCAL_TILESET_RADIUS_M
    if near_centre and (radius_m is None or radius_m >= LOCAL_TILESET_RADIUS_M):
        # a global tileset (Google, a terrain layer): its centre is the Earth's
        # centre, which is no origin. Keep whatever origin is set, else the
        # lat/lon/h in the panel (use Custom to pick the place of interest)
        print("[3DTiles] Global tileset: origin kept at "
              f"{props.origin_lat:.4f}, {props.origin_lon:.4f} (set a Custom origin to move)")
        props.origin_valid = True
        _state["origin_set"] = True
        for other in _state["streams"].values():
            other["last_sig"] = None
        return
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
    if near_centre:
        _set_origin_local(props, cz)
    else:
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
            for area in context.screen.areas:
                if area.type != "VIEW_3D":
                    continue
                if changed:
                    area.tag_redraw()
                else:
                    for r in area.regions:        # sidebar status only
                        if r.type == "UI":
                            r.tag_redraw()
        return {"PASS_THROUGH"}

    def invoke(self, context, event):
        props = context.scene.ogc3dtiles
        props.is_streaming = True
        props.status_text = "Streaming…"
        _state["status"] = None
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
    # kept in _state, not in scene properties: a scene property write tags the
    # scene for update and restarts the Cycles viewport render every tick
    _state["status"] = f"Visible {visible}  Loaded {loaded}  Queue {pending}  |  " + "  ".join(parts)
    _state["counts"] = (loaded, pending)
    _state["pending_total"] = pending
    _state["last_tick_t"] = now
    if changed:
        _state["last_change_t"] = now
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
            if want and (st["url"] != (GLOBE_URL if item.kind == "GLOBE" else item.url.strip())
                         or now - _state["start_failed"].get(key, 0) > START_RETRY_S):
                _state["streams"].pop(key, None)
                st = _start_item(scene, props, item)
                changed = True
            continue
        if st["url"] != (GLOBE_URL if item.kind == "GLOBE" else item.url.strip()):
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
    if props.clip_materials:
        from .. import materials as _materials
        _materials.update_clip_planes()
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
        waiting = st.get("pending_overlays", {}).pop(rt.key, None)
        if waiting:
            from .. import overlays as ovl
            obj = bpy.data.objects.get(r[0])
            if obj is not None and obj.type == "MESH":
                alpha_for = _overlay_alpha_lookup(props)
                for ev in waiting.values():
                    try:
                        ovl.apply_event(obj, ev, alpha_for)
                    except Exception as e:           # noqa: BLE001
                        print(f"[3DTiles] overlay attach failed on {rt.key}: {e}")
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
        _decide_origin(props, c, backend.root_radius_m())
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
        st.get("pending_overlays", {}).pop(key, None)
    if _process_overlay_events(scene, props, st):
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
        # camera objects default to a 100 m clip end: a render of a site-scale
        # tileset would come out empty (world colour only)
        for cam in bpy.data.cameras:
            if cam.clip_end < want:
                cam.clip_end = want
    except Exception as e:                           # noqa: BLE001
        print(f"[3DTiles] Clip range fit failed: {e}")


# a tileset whose centre is this close to the ECEF origin is not georeferenced
# (it sits deep inside the Earth): local converter output such as 3dtiled
# splat tilesets, photogrammetry exported without a root transform, ...
LOCAL_TILESET_RADIUS_M = 1.0e6
_WGS84_B = 6356752.314245


def _set_origin_local(props, cz):
    """Origin at the north pole, longitude -90, height -b: the ENU frame is
    then the identity (E=X, N=Y, U=Z, origin at ECEF 0), so a non-georeferenced
    tileset keeps its own Z-up axes and metres in Blender; the height takes
    the tileset's vertical centre to z=0."""
    props.origin_lat = 90.0
    props.origin_lon = -90.0
    props.origin_height = -_WGS84_B + cz
    print(f"[3DTiles] Scene origin: local (tileset is not georeferenced), identity frame")


def is_local_origin(props) -> bool:
    return props.origin_lat >= 89.999 and props.origin_height < -6.0e6


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


class _OGC3DSidebar:
    """Every section is its own sidebar panel (boxed, collapsible, and
    re-orderable by its drag handle, like the Object Properties tabs)."""
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "3D Tiles"

    @classmethod
    def poll(cls, context):
        return hasattr(context.scene, "ogc3dtiles")


class OGC3D_PT_MainPanel(_OGC3DSidebar, Panel):
    bl_label = "OGC 3D Tiles"
    bl_idname = "OGC3D_PT_main"
    bl_order = 0

    @classmethod
    def poll(cls, context):
        return True

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
        box.label(text=(_state.get("status") if props.is_streaming and _state.get("status")
                        else props.status_text), icon=icon)

        # Tilesets
        row = layout.row()
        row.template_list("OGC3D_UL_Tilesets", "", props, "tilesets", props, "active_tileset", rows=3)
        col = row.column(align=True)
        col.operator("ogc3dtiles.tileset_add", icon="ADD", text="")
        col.operator("ogc3dtiles.tileset_remove", icon="REMOVE", text="")
        if 0 <= props.active_tileset < len(props.tilesets):
            it = props.tilesets[props.active_tileset]
            b = layout.box()
            b.prop(it, "kind", text="Type")
            if it.kind == "GLOBE":
                b.label(text="Bare WGS84 ellipsoid: add raster overlays below", icon="WORLD")
            else:
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
            # raster overlays draped on this tileset (cesium-native backend)
            hdr = b.row(align=True)
            hdr.label(text="Raster overlays", icon="IMAGE_DATA")
            row = b.row()
            row.template_list("OGC3D_UL_Overlays", "", it, "overlays", it, "active_overlay", rows=2)
            col = row.column(align=True)
            col.operator("ogc3dtiles.overlay_add", icon="ADD", text="")
            col.operator("ogc3dtiles.overlay_remove", icon="REMOVE", text="")
            if 0 <= it.active_overlay < len(it.overlays):
                ov = it.overlays[it.active_overlay]
                ob = b.box()
                ob.prop(ov, "kind", text="Type")
                if ov.kind in ("URL", "TMS", "WMTS", "WMS", "BING"):
                    ob.prop(ov, "url", text="URL")
                if ov.kind == "ION":
                    ob.prop(ov, "url", text="Asset id")
                if ov.kind in ("ION", "BING", "GOOGLE"):
                    ob.prop(ov, "key", text="Key / token")
                if ov.kind in ("WMTS", "WMS", "BING", "GOOGLE"):
                    ob.prop(ov, "layer", text={"WMTS": "Layer", "WMS": "Layers", "BING": "Style",
                                               "GOOGLE": "Map type"}[ov.kind])
                if ov.kind == "WMTS":
                    ob.prop(ov, "style", text="Style")
                    ob.prop(ov, "matrix_set", text="Matrix set")
                if ov.kind in ("WMTS", "WMS"):
                    ob.prop(ov, "image_format", text="Format")
                if ov.kind in ("URL", "TMS", "WMTS", "WMS"):
                    r = ob.row(align=True)
                    r.prop(ov, "min_level", text="Min level")
                    r.prop(ov, "max_level", text="Max level")
                ob.prop(ov, "alpha", text="Opacity", slider=True)
                if st is not None and st.get("mode") == "python":
                    ob.label(text="Overlays need the cesium-native backend", icon="INFO")
                elif st is not None:
                    ob.label(text="Tick / untick applies live; URL edits: untick, then tick", icon="INFO")
        else:
            layout.prop(props, "tileset_url", text="URL")
            layout.prop(props, "cesium_ion_token", text="Ion Token")

        row = layout.row(align=True)
        if not props.is_streaming:
            row.operator("ogc3dtiles.start_stream", icon="PLAY", text="Start")
        else:
            row.operator("ogc3dtiles.stop_stream", icon="PAUSE", text="Stop")
        row.operator("ogc3dtiles.clear_tiles", icon="TRASH", text="Clear All Tiles")


class OGC3D_PT_OriginPanel(_OGC3DSidebar, Panel):
    bl_label = "Scene Origin"
    bl_idname = "OGC3D_PT_origin"
    bl_order = 1
    bl_options = {"DEFAULT_CLOSED"}

    def draw_header(self, context):
        self.layout.label(text="", icon="ORIENTATION_GLOBAL")

    def draw(self, context):
        layout = self.layout
        props = context.scene.ogc3dtiles
        layout.prop(props, "origin_mode", text="Mode")
        if props.origin_mode == "AUTO":
            layout.prop(props, "origin_reuse_km")
        col = layout.column()
        col.enabled = props.origin_mode == "CUSTOM"
        col.prop(props, "origin_lat", text="Latitude °")
        col.prop(props, "origin_lon", text="Longitude °")
        col.prop(props, "origin_height", text="Height m")
        row = layout.row()
        if props.origin_valid and is_local_origin(props):
            row.label(text="Local tileset (not georeferenced)", icon="CHECKMARK")
        else:
            row.label(text="Origin set" if props.origin_valid else "Origin not set yet",
                      icon="CHECKMARK" if props.origin_valid else "INFO")
        row.operator("ogc3dtiles.origin_reset", text="", icon="FILE_REFRESH")


class OGC3D_PT_LodPanel(_OGC3DSidebar, Panel):
    bl_label = "LOD / Streaming"
    bl_idname = "OGC3D_PT_lod"
    bl_order = 2

    def draw_header(self, context):
        self.layout.label(text="", icon="DRIVER_DISTANCE")

    def draw(self, context):
        layout = self.layout
        props = context.scene.ogc3dtiles
        col = layout.column(align=True)
        col.prop(props, "max_screen_space_error", text="Max SSE (live)")
        col.prop(props, "max_concurrent_requests", text="Parallel DL")
        col.prop(props, "imports_per_tick", text="Imports / tick")
        sub_h, sub = layout.panel("ogc3d_lod_advanced", default_closed=True)
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
                layout.label(text=f"{st['name'][:18]}: {running}  {extra}", icon=icon)


class OGC3D_PT_DisplayPanel(_OGC3DSidebar, Panel):
    bl_label = "Display"
    bl_idname = "OGC3D_PT_display"
    bl_order = 3

    def draw_header(self, context):
        self.layout.label(text="", icon="OUTLINER_DATA_POINTCLOUD")

    def draw(self, context):
        layout = self.layout
        props = context.scene.ogc3dtiles
        row = layout.row(align=True)
        row.prop(props, "point_display", text="Points")
        op = row.operator("ogc3dtiles.open_nodes", text="", icon="NODETREE")
        op.kind = "POINTS"
        layout.prop(props, "point_radius_mode", text="Radius")
        if props.point_radius_mode == "UNIFORM":
            layout.prop(props, "point_radius", text="Radius m")
        elif props.point_radius_mode == "ADAPTIVE":
            layout.prop(props, "point_scale", text="Point scale")
            row = layout.row(align=True)
            row.prop(props, "point_adapt_min_px", text="Min px")
            row.prop(props, "point_adapt_max_px", text="Max px")
        elif props.point_radius_mode == "SCREEN":
            row = layout.row(align=True)
            row.prop(props, "point_px", text="Pixels")
            row.prop(props, "point_px_min_m", text="Min m")
            row.prop(props, "point_px_max_m", text="Max m")
        else:
            layout.prop(props, "point_scale", text="Point scale")
        if any(o.get("splats") for o in bpy.data.objects):
            from ..io import splats_supported
            layout.label(text=("Gaussian splat tiles: native 3DGS point clouds" if splats_supported()
                               else "Splat tiles shown as points (Blender 5.3+ renders splats)"),
                         icon="OUTLINER_OB_POINTCLOUD" if splats_supported() else "INFO")
        if props.point_display == "MESH":
            layout.label(text="Solid mode: Shading → Color → Attribute", icon="INFO")
        elif props.point_display == "DISCS":
            layout.label(text="Discs follow glTF normals, else face the view", icon="INFO")
        else:
            layout.label(text="Colours in Material Preview / Rendered", icon="INFO")
        row = layout.row(align=True)
        row.prop(props, "tile_geometry", text="Shared geometry nodes")
        op = row.operator("ogc3dtiles.open_nodes", text="", icon="NODETREE")
        op.kind = "GEOMETRY"
        row = layout.row(align=True)
        row.prop(props, "hide_relation_lines", text="Hide relation lines")
        shown = _relationship_lines_shown(context)
        row.operator("ogc3dtiles.relation_lines", text="",
                     icon="HIDE_OFF" if shown else "HIDE_ON", depress=shown)


class OGC3D_PT_MaterialsPanel(_OGC3DSidebar, Panel):
    bl_label = "Materials"
    bl_idname = "OGC3D_PT_materials"
    bl_order = 4

    def draw_header(self, context):
        self.layout.label(text="", icon="MATERIAL")

    def draw(self, context):
        layout = self.layout
        props = context.scene.ogc3dtiles
        from .. import materials as _materials
        _materials.draw_panel(layout, props)


class OGC3D_PT_CompositorPanel(_OGC3DSidebar, Panel):
    bl_label = "Compositor"
    bl_idname = "OGC3D_PT_compositor"
    bl_order = 5

    def draw_header(self, context):
        self.layout.label(text="", icon="NODE_COMPOSITING")

    def draw(self, context):
        layout = self.layout
        props = context.scene.ogc3dtiles
        from .. import compositor as _compositor
        _compositor.draw_panel(layout, props)


class OGC3D_PT_RenderPanel(_OGC3DSidebar, Panel):
    bl_label = "Render"
    bl_idname = "OGC3D_PT_render"
    bl_order = 6
    bl_options = {"DEFAULT_CLOSED"}

    def draw_header(self, context):
        self.layout.label(text="", icon="RENDER_ANIMATION")

    def draw(self, context):
        layout = self.layout
        props = context.scene.ogc3dtiles
        layout.prop(props, "view_source", text="Stream for")
        col = layout.column(align=True)
        col.prop(props, "render_warmup_s", text="Warm-up s (first frame)")
        col.prop(props, "render_settle_s", text="Settle s (every frame)")
        col.prop(props, "render_max_wait_s", text="Max wait s")
        layout.operator("ogc3dtiles.render_converged", icon="RENDER_ANIMATION",
                      text="Render converged animation")
        prog = _state.get("render_progress")
        if prog:
            layout.label(text=prog, icon="INFO")
        layout.label(text="Output: scene Output path, one file per frame", icon="FILE_FOLDER")


class OGC3D_PT_BackendPanel(_OGC3DSidebar, Panel):
    bl_label = "Backend"
    bl_idname = "OGC3D_PT_backend"
    bl_order = 7
    bl_options = {"DEFAULT_CLOSED"}

    def draw_header(self, context):
        self.layout.label(text="", icon="MOD_DYNAMICPAINT")

    def draw(self, context):
        layout = self.layout
        props = context.scene.ogc3dtiles
        prefs = _get_prefs(context)
        if hasattr(prefs, "bl_rna"):
            row = layout.row()
            row.enabled = not props.is_streaming
            row.prop(prefs, "traversal_backend", text="")
        ok, status = _cesium_status
        layout.label(text=f"cesium-native-python: {status}", icon="CHECKMARK" if ok else "INFO")
        if not ok:
            layout.operator("ogc3dtiles.install_cesium_wheel", icon="IMPORT",
                            text="Install cesium-native (release wheel)")


class OGC3D_OT_RenderConverged(Operator):
    """Render the frame range from the scene camera, waiting before each frame
    until the tile queue is empty and nothing changed for 'Settle time'
    (or 'Max wait' passed).  Streams for the scene camera while it runs."""
    bl_idname = "ogc3dtiles.render_converged"
    bl_label = "Render Converged Animation"
    bl_options = {"REGISTER"}

    _timer = None

    def invoke(self, context, event):
        scene = context.scene
        props = scene.ogc3dtiles
        if scene.camera is None:
            self.report({"ERROR"}, "No scene camera")
            return {"CANCELLED"}
        if not props.is_streaming:
            with context.temp_override(window=context.window, area=context.area, region=context.region):
                if "FINISHED" not in bpy.ops.ogc3dtiles.start_stream():
                    self.report({"ERROR"}, "Streaming could not start")
                    return {"CANCELLED"}
        self._prev_source = props.view_source
        self._prev_frame = scene.frame_current
        self._prev_filepath = scene.render.filepath
        props.view_source = "CAMERA"
        self._frames = list(range(scene.frame_start, scene.frame_end + 1, max(scene.frame_step, 1)))
        self._i = 0
        self._done = 0
        self._goto(scene, self._frames[0])
        self._timer = context.window_manager.event_timer_add(0.1, window=context.window)
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def _goto(self, scene, frame):
        scene.frame_set(frame)
        now = time.monotonic()
        self._t_frame = now
        self._min_wait = scene.ogc3dtiles.render_warmup_s if self._i == 0 else 0.0
        _state["last_change_t"] = now
        _state["last_tick_t"] = 0.0
        _state["render_progress"] = f"frame {frame}: waiting for tiles"

    def modal(self, context, event):
        scene = context.scene
        props = scene.ogc3dtiles
        if event.type == "ESC" or not props.is_streaming:
            self._finish(context, cancelled=True)
            return {"CANCELLED"}
        if event.type != "TIMER":
            return {"PASS_THROUGH"}
        now = time.monotonic()
        waited = now - self._t_frame
        ticked = _state.get("last_tick_t", 0.0) > self._t_frame
        quiet = now - _state.get("last_change_t", now)
        converged = (ticked and _state.get("pending_total", 1) == 0
                     and quiet >= props.render_settle_s
                     and waited >= max(props.render_settle_s, self._min_wait))
        if not converged and waited < props.render_max_wait_s:
            stage = "warm-up" if waited < self._min_wait else "settling"
            _state["render_progress"] = (f"frame {scene.frame_current}: {stage}, queue "
                                         f"{_state.get('pending_total', '?')}, quiet {quiet:.1f} s")
            return {"PASS_THROUGH"}
        frame = self._frames[self._i]
        path = scene.render.frame_path(frame=frame)
        scene.render.filepath = path
        _state["render_progress"] = f"frame {frame}: rendering"
        try:
            bpy.ops.render.render("EXEC_DEFAULT", write_still=True)
        except Exception as e:                       # noqa: BLE001
            self.report({"ERROR"}, f"Render failed at frame {frame}: {e}")
            self._finish(context, cancelled=True)
            return {"CANCELLED"}
        finally:
            scene.render.filepath = self._prev_filepath
        self._done += 1
        print(f"[3DTiles] rendered frame {frame} after {waited:.1f} s -> {path}")
        self._i += 1
        if self._i >= len(self._frames):
            self._finish(context, cancelled=False)
            self.report({"INFO"}, f"Rendered {self._done} frames")
            return {"FINISHED"}
        self._goto(scene, self._frames[self._i])
        return {"PASS_THROUGH"}

    def _finish(self, context, cancelled):
        scene = context.scene
        props = scene.ogc3dtiles
        if self._timer is not None:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None
        props.view_source = self._prev_source
        scene.render.filepath = self._prev_filepath
        scene.frame_set(self._prev_frame)
        _state["render_progress"] = (f"cancelled after {self._done} frames" if cancelled
                                     else f"done: {self._done} frames")


class OGC3D_OT_OpenNodes(Operator):
    """Show the add-on's node tree in a node editor (an existing one, or a new
    one split off the 3D viewport) so it can be edited by hand"""
    bl_idname = "ogc3dtiles.open_nodes"
    bl_label = "Open in Node Editor"

    kind: bpy.props.EnumProperty(items=[
        ("RELIGHT", "Relight shader group", "'OGC3D Relight' shader node group"),
        ("COMPOSITOR", "Beauty compositor", "'OGC3D Beauty' compositor tree"),
        ("POINTS", "Point display nodes", "Geometry Nodes group of the current point display mode"),
        ("GEOMETRY", "Tile geometry nodes", "'OGC3D Tile Geometry' group applied to every tile"),
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
        elif self.kind == "GEOMETRY":
            from ..io import ensure_tile_geometry_group
            ng = ensure_tile_geometry_group()
            if not props.tile_geometry:
                props.tile_geometry = True
            ui_type = "GeometryNodeTree"
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


class OGC3D_PT_CoordPanel(_OGC3DSidebar, Panel):
    bl_label = "Coordinate Info"
    bl_idname = "OGC3D_PT_coord"
    bl_order = 9
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
    OGC3D_OT_RenderConverged,
    OGC3D_OT_TilesetAdd,
    OGC3D_OT_TilesetRemove,
    OGC3D_OT_OverlayAdd,
    OGC3D_OT_OverlayRemove,
    OGC3D_UL_Overlays,
    OGC3D_OT_StartStream,
    OGC3D_OT_StopStream,
    OGC3D_OT_OriginReset,
    OGC3D_OT_RelationLines,
    OGC3D_OT_ClearTiles,
    OGC3D_OT_ClearCache,
    OGC3D_OT_ModalStream,
    OGC3D_UL_Tilesets,
    OGC3D_PT_MainPanel,
    OGC3D_PT_OriginPanel,
    OGC3D_PT_LodPanel,
    OGC3D_PT_DisplayPanel,
    OGC3D_PT_MaterialsPanel,
    OGC3D_PT_CompositorPanel,
    OGC3D_PT_RenderPanel,
    OGC3D_PT_BackendPanel,
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
