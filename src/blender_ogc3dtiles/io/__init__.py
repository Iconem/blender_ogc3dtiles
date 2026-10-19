"""
io — tile fetching, unwrapping, disk cache and Blender import.

Design (mirrors what makes CesiumForBlender feel fast):
  * a small thread pool fetches content; the *worker* also unwraps
    b3dm/cmpt → GLB, trims the 8-byte container padding RealityCapture adds
    (Blender's importer rejects GLBs whose header length != file size),
    extracts RTC_CENTER / CESIUM_RTC, and writes the GLB(s) into a disk cache;
  * on a cache hit nothing is downloaded at all;
  * the main thread only ever runs ``bpy.ops.import_scene.gltf`` on a file,
    and the caller budgets how many imports happen per tick;
  * imports never touch the user's selection / active object, and every tile
    is parented to one root Empty per tileset inside a "3D Tiles" collection,
    so the whole dataset can be moved, hidden or folded as one.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import queue
import struct
import threading
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import bpy

from ..tileset.traversal import Tile, TileState, mat_mul, mat_translation

USER_AGENT = "blender-ogc3dtiles/0.3"
TIMEOUT_S = 30
COLLECTION_NAME = "3D Tiles"

# Blender's glTF importer converts glTF Y-up to Blender Z-up: (x, y, z) → (x, -z, y)
_YUP_TO_ZUP = [[1.0, 0.0, 0.0, 0.0], [0.0, 0.0, -1.0, 0.0],
               [0.0, 1.0, 0.0, 0.0], [0.0, 0.0, 0.0, 1.0]]


# ── disk cache ───────────────────────────────────────────────────────────────

def default_cache_dir() -> str:
    base = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), ".cache")
    return os.path.join(base, "blender_ogc3dtiles", "cache")


class DiskCache:
    """Content-addressed by sha1(url). ``<key>.glb`` (+ ``<key>_N.glb`` for
    cmpt parts) and ``<key>.meta.json`` describing them."""

    def __init__(self, root: str, enabled: bool = True):
        self.root = root
        self.enabled = enabled
        if enabled:
            os.makedirs(root, exist_ok=True)

    @staticmethod
    def key(url: str) -> str:
        return hashlib.sha1(url.encode("utf-8")).hexdigest()

    def meta_path(self, url: str) -> str:
        return os.path.join(self.root, self.key(url) + ".meta.json")

    def lookup(self, url: str) -> Optional[dict]:
        if not self.enabled:
            return None
        p = self.meta_path(url)
        if not os.path.isfile(p):
            return None
        try:
            with open(p, "r", encoding="utf-8") as fh:
                meta = json.load(fh)
            for part in meta.get("parts", []):
                if not os.path.isfile(part["path"]):
                    return None
            return meta
        except Exception:
            return None

    def store(self, url: str, parts: List[Tuple[bytes, Optional[list]]], kind: str) -> dict:
        key = self.key(url)
        out = []
        for i, (glb, rtc) in enumerate(parts):
            name = f"{key}.glb" if i == 0 else f"{key}_{i}.glb"
            path = os.path.join(self.root, name)
            tmp = path + ".tmp"
            with open(tmp, "wb") as fh:
                fh.write(glb)
            os.replace(tmp, path)
            out.append({"path": path, "rtc": rtc})
        meta = {"url": url, "kind": kind, "parts": out}
        if self.enabled:
            tmp = self.meta_path(url) + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(meta, fh)
            os.replace(tmp, self.meta_path(url))
        return meta

    def clear(self) -> int:
        n = 0
        if not os.path.isdir(self.root):
            return 0
        for name in os.listdir(self.root):
            try:
                os.unlink(os.path.join(self.root, name))
                n += 1
            except OSError:
                pass
        return n


# ── HTTP ─────────────────────────────────────────────────────────────────────

def http_get(url: str, headers: Optional[dict] = None) -> bytes:
    h = {"User-Agent": USER_AGENT, "Accept-Encoding": "gzip, deflate", "Accept": "*/*"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
        data = resp.read()
        enc = (resp.headers.get("Content-Encoding") or "").lower()
    if "gzip" in enc or data[:2] == b"\x1f\x8b":
        try:
            data = gzip.decompress(data)
        except Exception:
            pass
    return data


# ── unwrapping ───────────────────────────────────────────────────────────────

def _trim_glb(glb: bytes) -> bytes:
    """GLB header carries the real length; drop container padding after it."""
    if len(glb) >= 12 and glb[:4] == b"glTF":
        declared = struct.unpack_from("<I", glb, 8)[0]
        if 12 <= declared < len(glb):
            return glb[:declared]
    return glb


def _glb_cesium_rtc(glb: bytes) -> Optional[list]:
    """CESIUM_RTC center from the GLB's JSON chunk. Like b3dm RTC_CENTER it is
    applied in the tile frame: ECEF = T_tile · Translate(rtc) · Yup→Zup · v."""
    try:
        if glb[:4] != b"glTF" or len(glb) < 20:
            return None
        jlen = struct.unpack_from("<I", glb, 12)[0]
        doc = json.loads(glb[20:20 + jlen].decode("utf-8"))
        c = doc.get("extensions", {}).get("CESIUM_RTC", {}).get("center")
        if c and len(c) == 3:
            return [float(v) for v in c]
    except Exception:
        pass
    return None


def _b3dm_to_glb(data: bytes) -> Optional[Tuple[bytes, Optional[list]]]:
    if len(data) < 28 or data[:4] != b"b3dm":
        return None
    (_magic, _ver, _blen, ft_json, ft_bin, bt_json, bt_bin) = struct.unpack_from("<4s6I", data, 0)
    off = 28
    rtc = None
    if ft_json:
        try:
            ft = json.loads(data[off:off + ft_json].decode("utf-8"))
            c = ft.get("RTC_CENTER")
            if isinstance(c, list) and len(c) == 3:
                rtc = [float(v) for v in c]          # tile frame (Z-up), applied before glTF
        except Exception:
            pass
    off += ft_json + ft_bin + bt_json + bt_bin
    glb = _trim_glb(data[off:])
    if glb[:4] != b"glTF":
        return None
    if rtc is None:
        rtc = _glb_cesium_rtc(glb)               # CESIUM_RTC is in the tile frame too
    return glb, rtc


def unwrap_content(data: bytes, content_uri: str) -> Tuple[str, List[Tuple[bytes, Optional[list]]]]:
    """→ (kind, [(glb_bytes, rtc_tile_frame_or_None), ...]).
    kind ∈ {'glb', 'b3dm', 'cmpt', 'pnts', 'i3dm', 'json', 'unknown'}."""
    magic = data[:4]
    if magic == b"glTF":
        glb = _trim_glb(data)
        return "glb", [(glb, _glb_cesium_rtc(glb))]
    if magic == b"b3dm":
        r = _b3dm_to_glb(data)
        return "b3dm", ([r] if r else [])
    if magic == b"cmpt":
        parts = []
        n = struct.unpack_from("<I", data, 12)[0]
        off = 16
        for _ in range(n):
            if off + 12 > len(data):
                break
            inner_len = struct.unpack_from("<I", data, off + 8)[0]
            inner = data[off:off + inner_len]
            _k, ps = unwrap_content(inner, content_uri)
            parts.extend(ps)
            off += inner_len
        return "cmpt", parts
    if magic == b"pnts":
        return "pnts", []
    if magic == b"i3dm":
        return "i3dm", []
    s = data.lstrip()[:1]
    if s == b"{" or content_uri.split("?", 1)[0].lower().endswith((".json", ".gltf")):
        return "json", []
    return "unknown", []


def extract_gltf_from_tile(data: bytes, content_uri: str) -> Optional[bytes]:
    """Legacy helper: first GLB of the content, or None."""
    _kind, parts = unwrap_content(data, content_uri)
    return parts[0][0] if parts else None


# ── background fetch + unwrap ────────────────────────────────────────────────

@dataclass
class FetchResult:
    tile: Tile
    url: str
    kind: str = ""
    parts: List[dict] = field(default_factory=list)   # [{"path", "rtc"}]
    raw_json: Optional[bytes] = None                  # for tileset.json
    error: Optional[str] = None
    from_cache: bool = False


class TileDownloadManager:
    """Thread pool: fetch → unwrap → cache. Results are drained on the main
    thread with ``tick()``. Nothing here touches bpy."""

    def __init__(self, max_concurrent: int = 6, token: str = "",
                 cache: Optional[DiskCache] = None, extra_headers: Optional[dict] = None):
        self.max_concurrent = max(1, int(max_concurrent))
        self.token = token
        self.cache = cache or DiskCache(default_cache_dir())
        self.extra_headers = dict(extra_headers or {})
        self._pool = ThreadPoolExecutor(max_workers=self.max_concurrent,
                                        thread_name_prefix="ogc3dtiles")
        self._results: "queue.Queue[FetchResult]" = queue.Queue()
        self._inflight: Dict[str, Tile] = {}
        self._gen = 0
        self._lock = threading.Lock()
        self.stats = {"hits": 0, "downloads": 0, "bytes": 0, "errors": 0}

    # ------------------------------------------------------------------
    @property
    def inflight(self) -> int:
        return len(self._inflight)

    def _headers(self) -> dict:
        h = dict(self.extra_headers)
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    def enqueue(self, tile: Tile) -> bool:
        if not tile.content_uri or tile.state != TileState.UNLOADED:
            return False
        if tile.content_uri in self._inflight or len(self._inflight) >= self.max_concurrent:
            return False
        tile.state = TileState.LOADING
        self._inflight[tile.content_uri] = tile
        gen = self._gen
        self._pool.submit(self._work, tile, tile.content_uri, gen)
        return True

    def _work(self, tile: Tile, url: str, gen: int) -> None:
        res = FetchResult(tile=tile, url=url)
        try:
            is_json = url.split("?", 1)[0].lower().endswith(".json")
            meta = None if is_json else self.cache.lookup(url)
            if meta is not None:
                res.kind, res.parts, res.from_cache = meta["kind"], meta["parts"], True
                with self._lock:
                    self.stats["hits"] += 1
            else:
                data = http_get(url, self._headers())
                with self._lock:
                    self.stats["downloads"] += 1
                    self.stats["bytes"] += len(data)
                kind, parts = unwrap_content(data, url)
                res.kind = kind
                if kind == "json":
                    res.raw_json = data
                elif parts:
                    meta = self.cache.store(url, parts, kind)
                    res.parts = meta["parts"]
                else:
                    res.error = f"unsupported or empty content ({kind})"
        except urllib.error.HTTPError as e:
            res.error = f"HTTP {e.code} {e.reason}"
        except Exception as e:                      # noqa: BLE001
            res.error = f"{type(e).__name__}: {e}"
        if res.error:
            with self._lock:
                self.stats["errors"] += 1
        if gen == self._gen:
            self._results.put(res)

    def tick(self) -> List[FetchResult]:
        out = []
        while True:
            try:
                r = self._results.get_nowait()
            except queue.Empty:
                break
            self._inflight.pop(r.url, None)
            out.append(r)
        return out

    def cancel_all(self) -> None:
        self._gen += 1
        self._inflight.clear()
        while True:
            try:
                self._results.get_nowait()
            except queue.Empty:
                break

    def shutdown(self) -> None:
        self.cancel_all()
        self._pool.shutdown(wait=False, cancel_futures=True)


# ── Blender import ───────────────────────────────────────────────────────────

def ensure_collection(scene: bpy.types.Scene) -> bpy.types.Collection:
    coll = bpy.data.collections.get(COLLECTION_NAME)
    if coll is None:
        coll = bpy.data.collections.new(COLLECTION_NAME)
    if scene.collection.children.get(coll.name) is None:
        scene.collection.children.link(coll)
    return coll


def ensure_root_empty(scene: bpy.types.Scene, name: str) -> bpy.types.Object:
    """One Empty per tileset: move/rotate/scale it to transform the dataset."""
    coll = ensure_collection(scene)
    obj = bpy.data.objects.get(name)
    if obj is None or obj.type != "EMPTY":
        obj = bpy.data.objects.new(name, None)
        obj.empty_display_type = "PLAIN_AXES"
        obj.empty_display_size = 10.0
        obj["ogc3dtiles_root"] = True
    if coll.objects.get(obj.name) is None:
        coll.objects.link(obj)
    return obj


class _SelectionGuard:
    """Blender's glTF importer deselects everything and activates what it
    imported; restore the user's selection afterwards."""

    def __enter__(self):
        vl = bpy.context.view_layer
        self.active = vl.objects.active
        self.selected = [o for o in vl.objects if o.select_get()]
        return self

    def __exit__(self, *exc):
        vl = bpy.context.view_layer
        try:
            for o in vl.objects:
                if o.select_get():
                    o.select_set(False)
            for o in self.selected:
                try:
                    o.select_set(True)
                except RuntimeError:
                    pass
            if self.active is not None and self.active.name in vl.objects:
                vl.objects.active = self.active
        except Exception:
            pass
        return False


def tile_world_matrix(tile_transform, rtc, enu_from_ecef):
    """Matrix for a tile's holder Empty (parented under the tileset root):
    ENU_from_ECEF · T_tile · Translate(rtc).  The importer already applied
    the glTF Y-up → Z-up conversion to the objects."""
    m = tile_transform
    if rtc:
        m = mat_mul(m, mat_translation(rtc))
    return mat_mul(enu_from_ecef, m)


def import_glb_file(path: str, key: str, scene: bpy.types.Scene, root: bpy.types.Object,
                    matrix_rows, hidden: bool = True) -> Optional[Tuple[str, List[str]]]:
    """Import one GLB from disk under ``root``. Returns (holder_name, data names)."""
    from mathutils import Matrix

    coll = ensure_collection(scene)
    before_o = set(bpy.data.objects.keys())
    before_m = set(bpy.data.meshes.keys())
    before_ma = set(bpy.data.materials.keys())
    before_i = set(bpy.data.images.keys())
    with _SelectionGuard():
        try:
            result = bpy.ops.import_scene.gltf(filepath=path, import_pack_images=True,
                                               merge_vertices=False)
        except Exception as e:                      # noqa: BLE001
            print(f"[3DTiles] glTF import failed for {key}: {e}")
            return None
        if "FINISHED" not in result:
            return None
        new_objs = [bpy.data.objects[n] for n in bpy.data.objects.keys() if n not in before_o]
        if not new_objs:
            return None
        holder = bpy.data.objects.new(_short_name(key), None)
        holder.empty_display_size = 0.1
        holder["tile_url"] = key
        coll.objects.link(holder)
        holder.parent = root
        holder.matrix_parent_inverse = Matrix.Identity(4)
        holder.matrix_world = root.matrix_world @ Matrix(matrix_rows)
        for obj in new_objs:
            for c in list(obj.users_collection):
                if c is not coll:
                    c.objects.unlink(obj)
            if coll.objects.get(obj.name) is None:
                coll.objects.link(obj)
            if obj.parent is None:
                local = obj.matrix_world.copy()
                obj.parent = holder
                obj.matrix_parent_inverse = Matrix.Identity(4)
                obj.matrix_basis = local
            obj.hide_viewport = hidden
            obj.hide_render = hidden
            obj.select_set(False)
        holder.hide_viewport = hidden
        holder.hide_render = hidden
    data_names = (sorted(set(bpy.data.meshes.keys()) - before_m)
                  + sorted(set(bpy.data.materials.keys()) - before_ma)
                  + sorted(set(bpy.data.images.keys()) - before_i))
    return holder.name, data_names


def set_tile_visible(holder_name: str, visible: bool) -> None:
    holder = bpy.data.objects.get(holder_name)
    if holder is None:
        return
    hidden = not visible
    if holder.hide_viewport != hidden:
        holder.hide_viewport = hidden
        holder.hide_render = hidden
        for child in holder.children_recursive:
            child.hide_viewport = hidden
            child.hide_render = hidden


def remove_tile(holder_name: str, data_names: List[str]) -> None:
    holder = bpy.data.objects.get(holder_name)
    if holder is not None:
        for child in list(holder.children_recursive):
            bpy.data.objects.remove(child, do_unlink=True)
        bpy.data.objects.remove(holder, do_unlink=True)
    for n in data_names:
        for store in (bpy.data.meshes, bpy.data.materials, bpy.data.images):
            d = store.get(n)
            if d is not None and d.users == 0:
                try:
                    store.remove(d)
                except Exception:
                    pass
                break


def import_gltf_bytes(glb_data: bytes, tile: Tile, scene: bpy.types.Scene,
                      transform_matrix=None) -> Optional[str]:
    """Legacy entry point (bytes → temp file → import under a root)."""
    import tempfile

    from ..tileset.traversal import build_ecef_to_enu_matrix
    if not glb_data:
        return None
    props = scene.ogc3dtiles
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".glb", prefix="tile_")
    tmp.write(glb_data)
    tmp.close()
    try:
        root = ensure_root_empty(scene, "3D Tiles Root")
        enu = build_ecef_to_enu_matrix(props.origin_lat, props.origin_lon, props.origin_height)
        m = tile_world_matrix(tile.transform, None, enu)
        r = import_glb_file(tmp.name, tile.content_uri or "tile", scene, root, m, hidden=False)
        return r[0] if r else None
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


def _short_name(url: str) -> str:
    name = url.split("?", 1)[0].rstrip("/").split("/")[-1] or "tile"
    return ("t_" + name)[:60]


def register():
    pass


def unregister():
    pass
