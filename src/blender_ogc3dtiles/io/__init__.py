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

def addon_pref(name: str, default=None):
    """A field of the add-on preferences (default outside Blender / unregistered)."""
    try:
        ad = bpy.context.preferences.addons.get(__package__.rpartition(".")[0])
        return getattr(ad.preferences, name, default) if ad is not None else default
    except Exception:          # noqa: BLE001
        return default


def default_cache_dir() -> str:
    """Preferences' cache folder, else %LOCALAPPDATA%/blender_ogc3dtiles/cache
    (~/.cache/... elsewhere): local, per user and shared by Blender versions."""
    custom = (addon_pref("cache_dir", "") or "").strip()
    if custom:
        return os.path.abspath(bpy.path.abspath(custom))
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

_tls = threading.local()


def _session():
    """One keep-alive ``requests.Session`` per thread (Blender bundles
    requests/urllib3): the TCP + TLS handshake is paid once per worker, not
    once per tile. Falls back to urllib when requests is unavailable."""
    sess = getattr(_tls, "session", None)
    if sess is None:
        try:
            import requests  # noqa: PLC0415
            sess = requests.Session()
            sess.headers["User-Agent"] = USER_AGENT
        except Exception:                           # noqa: BLE001
            sess = False
        _tls.session = sess
    return sess or None


class _HTTPError(Exception):
    def __init__(self, code, reason):
        super().__init__(f"HTTP {code} {reason}")
        self.code, self.reason = code, reason


def http_get(url: str, headers: Optional[dict] = None) -> bytes:
    h = {"User-Agent": USER_AGENT, "Accept-Encoding": "gzip, deflate", "Accept": "*/*"}
    if headers:
        h.update(headers)
    sess = _session()
    if sess is not None:
        resp = sess.get(url, headers=h, timeout=TIMEOUT_S)
        if resp.status_code >= 400:
            raise _HTTPError(resp.status_code, resp.reason)
        data = resp.content                     # requests already un-gzips
    else:
        req = urllib.request.Request(url, headers=h)
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            data = resp.read()
    if data[:2] == b"\x1f\x8b":                # pre-gzipped files served raw
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
    payloads: List[Optional[dict]] = field(default_factory=list)   # per part, direct mesh
    raw_json: Optional[bytes] = None                  # for tileset.json
    error: Optional[str] = None
    from_cache: bool = False


class TileDownloadManager:
    """Thread pool: fetch → unwrap → cache. Results are drained on the main
    thread with ``tick()``. Nothing here touches bpy."""

    def __init__(self, max_concurrent: int = 6, token: str = "",
                 cache: Optional[DiskCache] = None, extra_headers: Optional[dict] = None,
                 direct_mesh: bool = True):
        self.max_concurrent = max(1, int(max_concurrent))
        self.token = token
        self.direct_mesh = bool(direct_mesh)   # parse GLBs to numpy payloads on the worker
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
            if self.direct_mesh and res.parts and not res.error:
                from ..tileset.gltf_payload import glb_to_payload  # noqa: PLC0415
                for part in res.parts:
                    try:
                        with open(part["path"], "rb") as fh:
                            res.payloads.append(glb_to_payload(fh.read()))
                    except Exception as exc:        # noqa: BLE001
                        print(f"[3DTiles] GLB parse failed ({url}): {exc!r}")
                        res.payloads.append(None)
        except (urllib.error.HTTPError, _HTTPError) as e:
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

def ensure_collection(scene: bpy.types.Scene, sub: Optional[str] = None) -> bpy.types.Collection:
    """``3D Tiles`` collection, or ``3D Tiles / <sub>`` child collection."""
    coll = bpy.data.collections.get(COLLECTION_NAME)
    if coll is None:
        coll = bpy.data.collections.new(COLLECTION_NAME)
    if scene.collection.children.get(coll.name) is None:
        scene.collection.children.link(coll)
    if not sub:
        return coll
    child = bpy.data.collections.get(sub)
    if child is None:
        child = bpy.data.collections.new(sub)
    if coll.children.get(child.name) is None:
        coll.children.link(child)
    return child


def ensure_root_empty(scene: bpy.types.Scene, name: str,
                      sub: Optional[str] = None) -> bpy.types.Object:
    """One Empty per tileset: move/rotate/scale it to transform the dataset."""
    coll = ensure_collection(scene, sub)
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
                    matrix_rows, hidden: bool = True,
                    coll: Optional[bpy.types.Collection] = None) -> Optional[Tuple[str, List[str]]]:
    """Import one GLB from disk under ``root`` into ``coll`` (defaults to the
    root's collection). Returns (holder_name, data names)."""
    from mathutils import Matrix

    if coll is None:
        coll = root.users_collection[0] if root.users_collection else ensure_collection(scene)
    before_o = set(bpy.data.objects.keys())
    before_m = set(bpy.data.meshes.keys())
    before_ma = set(bpy.data.materials.keys())
    before_i = set(bpy.data.images.keys())
    with _SelectionGuard():
        # The importer derives its log level from bpy.app.debug_value (0 → INFO,
        # three console lines per tile); raise it to WARNING while we import.
        old_dbg = bpy.app.debug_value
        if old_dbg == 0:
            bpy.app.debug_value = 1
        try:
            result = bpy.ops.import_scene.gltf(filepath=path, import_pack_images=True,
                                               merge_vertices=False)
        except Exception as e:                      # noqa: BLE001
            print(f"[3DTiles] glTF import failed for {key}: {e}")
            return None
        finally:
            bpy.app.debug_value = old_dbg
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
    new_mats = sorted(set(bpy.data.materials.keys()) - before_ma)
    if getattr(scene.ogc3dtiles, "auto_relight", False):
        from ..materials import apply_relight
        for n in new_mats:
            apply_relight(bpy.data.materials.get(n))
    _new_tile_hooks(scene, new_objs, [bpy.data.materials.get(n) for n in new_mats])
    data_names = (sorted(set(bpy.data.meshes.keys()) - before_m)
                  + new_mats
                  + sorted(set(bpy.data.images.keys()) - before_i))
    return holder.name, data_names


# ── Direct mesh construction (cesium-native payloads) ────────────────────────

def _image_from_payload(ip: dict, key: str):
    """bpy Image from packed file bytes (same recipe as Blender's glTF importer)."""
    name = f"{ip.get('name') or 'tex'}_{abs(hash(key)) % 10_000_000}"[:60]
    img = bpy.data.images.new(name, 8, 8)
    data = ip["data"]
    img.pack(data=data, data_len=len(data))
    img.source = "FILE"
    img.alpha_mode = "CHANNEL_PACKED"
    return img


def _material_from_payload(mp: dict, img, key: str):
    mat = bpy.data.materials.new(f"{mp.get('name') or 'mat'}_{abs(hash(key)) % 10_000_000}"[:60])
    mat.use_nodes = True
    mat.use_backface_culling = not mp.get("double_sided", True)
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    out = nt.nodes.get("Material Output")
    if bsdf is None or out is None:
        return mat
    # photogrammetry: lighting is baked, keep the surface matte
    for name, val in (("Roughness", 1.0), ("Specular IOR Level", 0.0), ("Metallic", 0.0)):
        if name in bsdf.inputs:
            bsdf.inputs[name].default_value = val
    bc = mp.get("base_color", (0.8, 0.8, 0.8, 1.0))
    if img is not None:
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = img
        tex.location = (-400, 300)
        nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
        if mp.get("unlit"):
            nt.links.new(tex.outputs["Color"], bsdf.inputs["Emission Color"])
            bsdf.inputs["Emission Strength"].default_value = 1.0
    else:
        bsdf.inputs["Base Color"].default_value = bc
    return mat


def _wire_point_colors(mat):
    """Point clouds: unlit vertex colours. Attribute node (not Color Attribute)
    so it also resolves on the point cloud produced by the Mesh→Points
    modifier; a second lookup of type Instancer reads the same attribute from
    the instance domain for disc splats (points instanced, not realised).
    The two are added: whichever domain exists carries the colour."""
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    if bsdf is None:
        return
    attr = nt.nodes.new("ShaderNodeAttribute")
    attr.attribute_name = "Col"
    attr.attribute_type = "GEOMETRY"
    attr.location = (-600, 0)
    bsdf.inputs["Base Color"].default_value = (0.0, 0.0, 0.0, 1.0)
    nt.links.new(attr.outputs["Color"], bsdf.inputs["Emission Color"])
    bsdf.inputs["Emission Strength"].default_value = 1.0
    _ensure_instancer_color(mat)


def _ensure_instancer_color(mat) -> bool:
    """Add the Instancer-domain colour lookup to a point material built by an
    older version (needed by disc splats)."""
    nt = mat.node_tree if mat and mat.use_nodes else None
    if nt is None:
        return False
    if any(n.type == "ATTRIBUTE" and n.attribute_type == "INSTANCER" for n in nt.nodes):
        return False
    bsdf = nt.nodes.get("Principled BSDF")
    geo = next((n for n in nt.nodes if n.type == "ATTRIBUTE" and n.attribute_name == "Col"), None)
    if bsdf is None or geo is None:
        return False
    inst = nt.nodes.new("ShaderNodeAttribute")
    inst.attribute_name = "Col"
    inst.attribute_type = "INSTANCER"
    inst.location = (-600, -200)
    add = nt.nodes.new("ShaderNodeMix")
    add.data_type = "RGBA"
    add.blend_type = "ADD"
    add.inputs["Factor"].default_value = 1.0
    add.location = (-350, -100)
    nt.links.new(geo.outputs["Color"], add.inputs[6])
    nt.links.new(inst.outputs["Color"], add.inputs[7])
    nt.links.new(add.outputs[2], bsdf.inputs["Emission Color"])
    return True


FEATURES_PROP = "ogc3d_features"     # per-tile lookup: {"columns": [...], "rows": [[...], ...]}
TILE_META_PROP = "ogc3d_tile_metadata"  # tile, group and content metadata of tileset.json


def _set_feature_attributes(me, feature_ids, table, columns):
    """The ``columns`` of a tile's table as point attributes, readable from
    shaders and Geometry Nodes."""
    import numpy as np
    from ..tileset import feature_meta
    for name, values in feature_meta.vertex_attributes(feature_ids, table, columns).items():
        attr = me.attributes.get(name)
        if attr is None:
            kind = "INT" if values.dtype.kind == "i" else "FLOAT"
            attr = me.attributes.new(name, kind, "POINT")
        attr.data.foreach_set("value", np.ascontiguousarray(values))


def _add_feature_attributes(me, features, scene):
    if not features:
        return
    import numpy as np
    from ..materials import metadata_columns
    from ..tileset.feature_meta import FEATURE_ID_ATTR
    me.attributes.new(FEATURE_ID_ATTR, "INT", "POINT").data.foreach_set(
        "value", np.ascontiguousarray(features["feature_id"], dtype=np.int32))
    _set_feature_attributes(me, features["feature_id"], features["table"],
                            metadata_columns(scene.ogc3dtiles))


_texels = {}      # material name -> what its tile's textures hold


def _set_texel_image(mat, texel, column):
    """The column as a per-pixel image in the material, sampled by the tile's UVs.
    Gray: a shader turns color into a number by luminance."""
    import numpy as np
    from ..materials import TEXEL_NODE
    from ..tileset.feature_meta import texel_values
    grid = texel_values(texel, column) if column else None
    node = mat.node_tree.nodes.get(TEXEL_NODE)
    if node is None:
        node = mat.node_tree.nodes.new("ShaderNodeTexImage")
        node.name = node.label = TEXEL_NODE
        node.interpolation = "Closest"
        node.extension = "EXTEND"
    old = node.image
    if grid is None:
        node.image = None
    else:
        height, width = grid.shape
        img = bpy.data.images.new(f"{TEXEL_NODE} {mat.name}"[:60], width, height, alpha=False, float_buffer=True)
        img.colorspace_settings.name = "Non-Color"
        rgba = np.ones((height, width, 4), np.float32)
        rgba[..., :3] = grid[::-1, :, None]    # the first row is the image's top
        img.pixels.foreach_set(rgba.ravel())
        img.update()
        img.pack()
        node.image = img
    if old is not None:
        bpy.data.images.remove(old)
    return node


def _add_texels(me, payload, scene):
    from ..materials import META_NODE
    props = scene.ogc3dtiles
    for slot, texel in (payload.get("texels") or {}).items():
        if slot < len(me.materials) and me.materials[slot] is not None:
            mat = me.materials[slot]
            _texels[mat.name] = texel
            _set_texel_image(mat, texel, props.meta_column)
            group = mat.node_tree.nodes.get(META_NODE)
            if group is not None:
                mat.node_tree.links.new(mat.node_tree.nodes["OGC3D Metadata Texel"].outputs["Color"], group.inputs["Texel"])


TILE_INFO_PROP = "ogc3d_tile_info"       # per-tile {"tile level": 3.0, ...}, as JSON


def _set_tile_attributes(obj, columns) -> None:
    """One value for the whole tile, as a point attribute like the other columns."""
    import numpy as np
    from ..tileset.feature_meta import attribute_name
    values = json.loads(obj[TILE_INFO_PROP])
    me = obj.data
    for column in columns:
        name = attribute_name(column)
        if column in values and name not in me.attributes:
            n = len(me.attributes.new(name, "FLOAT", "POINT").data)
            me.attributes[name].data.foreach_set("value", np.full(n, values[column], np.float32))


def set_tile_info(holder_name: str, values: dict, scene) -> None:
    """Level and geometric error of a tile just built, on its mesh objects."""
    from ..materials import metadata_columns
    holder = bpy.data.objects.get(holder_name)
    if holder is None or not values:
        return
    columns = metadata_columns(scene.ogc3dtiles)
    for obj in [holder, *holder.children_recursive]:
        if obj.type == "MESH" and obj.data is not None:
            obj[TILE_INFO_PROP] = json.dumps(values)
            _set_tile_attributes(obj, columns)


def refresh_feature_attributes(scene):
    """Give the tiles already loaded the columns now in use."""
    import numpy as np
    for name in [n for n in _texels if n not in bpy.data.materials]:
        del _texels[name]
    for name, texel in _texels.items():
        _set_texel_image(bpy.data.materials[name], texel, scene.ogc3dtiles.meta_column)
    from ..materials import metadata_columns
    from ..tileset.feature_meta import FEATURE_ID_ATTR, attribute_name
    columns = metadata_columns(scene.ogc3dtiles)
    for o in bpy.data.objects:
        if o.type == "MESH" and TILE_INFO_PROP in o:
            _set_tile_attributes(o, columns)
        if FEATURES_PROP not in o or o.type != "MESH":
            continue
        me = o.data
        missing = [c for c in columns if attribute_name(c) not in me.attributes]
        ids_attr = me.attributes.get(FEATURE_ID_ATTR)
        if not missing or ids_attr is None:
            continue
        ids = np.zeros(len(me.vertices), np.int32)
        ids_attr.data.foreach_get("value", ids)
        _set_feature_attributes(me, ids, json.loads(o[FEATURES_PROP]), missing)


def _voxel_colors_on(scene):
    """A voxel tile has no color of its own: its values show once, the user can
    turn them off after that."""
    if scene.get("ogc3d_voxel_colors"):
        return
    scene["ogc3d_voxel_colors"] = True
    props = scene.ogc3dtiles
    props["read_metadata"] = True
    props["meta_color"] = True


def _tileset_metadata_import():
    from ..tileset.feature_meta import TILESET_METADATA
    return TILESET_METADATA


def build_voxel_lookup(payload: dict, key: str, scene: bpy.types.Scene,
                       root: bpy.types.Object, matrix_rows, hidden: bool = True,
                       coll: Optional[bpy.types.Collection] = None) -> Optional[Tuple[str, List[str]]]:
    """A voxel tile that colors other tilesets: an Empty, its grid goes in the lookup.
    Blocks for what a lookup can't hold: regions."""
    from mathutils import Matrix

    from .. import voxel_lookup
    from ..materials import sync_metadata
    if payload.get("voxel_grid") is None or payload.get("voxel_matrix") is None:
        return build_tile_from_payload(payload, key, scene, root, matrix_rows, hidden, coll)
    if coll is None:
        coll = root.users_collection[0] if root.users_collection else ensure_collection(scene)
    _voxel_colors_on(scene)
    sync_metadata(scene)
    voxel_lookup.add_tile(payload, key, matrix_rows, scene)
    obj = bpy.data.objects.new(_short_name(key), None)
    obj["tile_url"] = key
    coll.objects.link(obj)
    obj.parent = root
    obj.matrix_parent_inverse = Matrix.Identity(4)
    obj.hide_viewport = hidden
    obj.hide_render = hidden
    return obj.name, []


def build_voxel_volume(payload: dict, key: str, scene: bpy.types.Scene,
                       root: bpy.types.Object, matrix_rows, hidden: bool = True,
                       coll: Optional[bpy.types.Collection] = None) -> Optional[Tuple[str, List[str]]]:
    """One OpenVDB Volume for a box voxel tile; blocks when that isn't possible
    (no openvdb module, or a region). Grids are written here: their colors follow
    the panel's column through ``meta_<column>``."""
    import tempfile

    import numpy as np
    from mathutils import Matrix

    from ..materials import sync_metadata, voxel_volume_material
    from ..tileset import voxels
    to_ecef = voxels.volume_matrix(payload)
    try:
        import openvdb
    except ImportError:
        openvdb = None
    if to_ecef is None or openvdb is None:
        return build_tile_from_payload(payload, key, scene, root, matrix_rows, hidden, coll)

    grid = payload["voxel_grid"]
    if coll is None:
        coll = root.users_collection[0] if root.users_collection else ensure_collection(scene)
    _voxel_colors_on(scene)
    sync_metadata(scene)
    world = np.asarray(matrix_rows, np.float64) @ to_ecef
    # 1 means an optical depth per cell, whatever the tile's level
    cell = np.linalg.norm(to_ecef[:3, :3], axis=0)
    density = grid["mask"].astype(np.float32) / float(np.cbrt(cell.prod()))
    arrays = {"density": density, **grid["grids"]}
    grids = []
    for name, values in arrays.items():
        g = openvdb.FloatGrid()
        g.copyFromArray(np.ascontiguousarray(values))
        g.name = name
        grids.append(g)
    if grid["colors"] is not None:
        g = openvdb.Vec3SGrid()
        g.copyFromArray(np.ascontiguousarray(grid["colors"]))
        g.name = "color"
        grids.append(g)
    folder = bpy.app.tempdir or tempfile.gettempdir()
    path = os.path.join(folder, f"ogc3d_voxel_{abs(hash(key)):x}.vdb")
    openvdb.write(path, grids=grids)

    if bpy.app.version < (5, 1, 0):
        # 4.5's EEVEE draws nothing past its volumetric range, 100 m by default (5.0 not tested)
        scene.eevee.volumetric_end = max(scene.eevee.volumetric_end, 100000.0)
    vol = bpy.data.volumes.new(_short_name(key))
    vol.filepath = path
    vol.materials.append(voxel_volume_material(scene))
    obj = bpy.data.objects.new(_short_name(key), vol)
    obj["tile_url"] = key
    coll.objects.link(obj)
    obj.parent = root
    obj.matrix_parent_inverse = Matrix.Identity(4)
    obj.matrix_world = root.matrix_world @ Matrix(world.tolist())
    obj.hide_viewport = hidden
    obj.hide_render = hidden
    obj.select_set(False)
    return obj.name, [vol.name]


def build_tile_from_payload(payload: dict, key: str, scene: bpy.types.Scene,
                            root: bpy.types.Object, matrix_rows, hidden: bool = True,
                            coll: Optional[bpy.types.Collection] = None,
                            image_cache: Optional[dict] = None) -> Optional[Tuple[str, List[str]]]:
    """Create one mesh object from a native_mesh payload (no glTF importer).
    Returns (object_name, data_names)."""
    import numpy as np
    from mathutils import Matrix

    if coll is None:
        coll = root.users_collection[0] if root.users_collection else ensure_collection(scene)
    V = np.ascontiguousarray(payload["verts"], dtype=np.float32)
    F = np.ascontiguousarray(payload["faces"], dtype=np.int32)
    n_v, n_f = len(V), len(F)
    me = bpy.data.meshes.new(_short_name(key))
    me.vertices.add(n_v)
    me.vertices.foreach_set("co", V.ravel())
    data_names = [me.name]
    if n_f:
        me.loops.add(n_f * 3)
        me.loops.foreach_set("vertex_index", F.ravel())
        me.polygons.add(n_f)
        me.polygons.foreach_set("loop_start", np.arange(0, n_f * 3, 3, dtype=np.int32))
        fm = payload.get("face_mat")
        if fm is not None and len(fm) == n_f:
            me.polygons.foreach_set("material_index", np.ascontiguousarray(fm, dtype=np.int32))
        me.polygons.foreach_set("use_smooth", np.ones(n_f, dtype=bool))
        uvs = payload.get("uvs")
        if uvs is not None and len(uvs) == n_f * 3:
            uv_layer = me.uv_layers.new(name="UVMap")
            uv_layer.data.foreach_set("uv", np.ascontiguousarray(uvs, dtype=np.float32).ravel())
        for tid, ouv in sorted((payload.get("overlay_uvs") or {}).items()):
            if len(ouv) != n_f * 3:
                continue
            layer = me.uv_layers.new(name=f"{OVERLAY_UV_PREFIX}{tid}", do_init=False)
            layer.data.foreach_set("uv", np.ascontiguousarray(ouv, dtype=np.float32).ravel())
    me.update(calc_edges=True)
    me.validate(verbose=False)
    nrm = payload.get("normals")
    if n_f and nrm is not None and len(nrm) == n_v:
        try:
            me.normals_split_custom_set_from_vertices(np.ascontiguousarray(nrm, dtype=np.float32))
        except Exception:
            pass
    if not n_f and payload.get("points") and nrm is not None and len(nrm) == n_v:
        try:                                    # oriented disc splats
            na = me.attributes.new(NORMAL_ATTR, "FLOAT_VECTOR", "POINT")
            na.data.foreach_set("vector", np.ascontiguousarray(nrm, dtype=np.float32).ravel())
        except Exception:
            pass
    overlay_points = {}
    if not n_f and payload.get("points") and not payload.get("splats"):
        overlay_points = payload.get("overlay_uvs") or {}
    for tid, ouv in sorted(overlay_points.items()):     # a mesh without faces has no UV maps
        layer = me.attributes.new(f"{OVERLAY_UV_PREFIX}{tid}", "FLOAT2", "POINT")
        layer.data.foreach_set("vector", np.ascontiguousarray(ouv, dtype=np.float32).ravel())
    if payload.get("splats"):
        _store_splat_attributes(me, payload)
    cols = payload.get("colors")
    if cols is not None and len(cols) == n_v:
        attr = me.color_attributes.new("Col", "FLOAT_COLOR", "POINT")
        attr.data.foreach_set("color", np.ascontiguousarray(cols, dtype=np.float32).ravel())
        me.color_attributes.render_color_index = 0
        me.color_attributes.active_color_index = 0

    if payload.get("voxel"):
        _voxel_colors_on(scene)
    _add_feature_attributes(me, payload.get("features"), scene)
    for name, values in (payload.get("vertex_columns") or {}).items():
        kind = "INT" if values.dtype.kind == "i" else "FLOAT"
        me.attributes.new(name, kind, "POINT").data.foreach_set("value", np.ascontiguousarray(values))

    # colorless points still take imagery or a metadata ramp
    point_source = bool(overlay_points or payload.get("vertex_columns"))

    # materials (one slot per payload material, textures packed from bytes)
    image_cache = image_cache if image_cache is not None else {}
    images = payload.get("images") or {}
    for mp in payload.get("materials") or []:
        img = None
        ii = mp.get("image")
        if ii is not None and images.get(ii) is not None:
            ck = (key, ii)
            img = image_cache.get(ck)
            if img is None:
                img = _image_from_payload(images[ii], key)
                image_cache[ck] = img
                data_names.append(img.name)
        mat = _material_from_payload(mp, img, key)
        if (payload.get("points") or payload.get("voxel")) and (cols is not None or point_source):
            _wire_point_colors(mat)
        me.materials.append(mat)
        data_names.append(mat.name)
    if payload.get("points") and not me.materials and (cols is not None or point_source):
        mat = _material_from_payload({"name": "points", "double_sided": True}, None, key)
        _wire_point_colors(mat)
        me.materials.append(mat)
        data_names.append(mat.name)

    if payload.get("texels"):
        _add_texels(me, payload, scene)
    obj = bpy.data.objects.new(_short_name(key), me)
    obj["tile_url"] = key
    if payload.get("features"):
        obj[FEATURES_PROP] = json.dumps(payload["features"]["table"], separators=(",", ":"))
    tile_meta = _tileset_metadata_import().by_content.get(key.split("?", 1)[0])
    if tile_meta:
        obj[TILE_META_PROP] = json.dumps(tile_meta, separators=(",", ":"))
    coll.objects.link(obj)
    obj.parent = root
    obj.matrix_parent_inverse = Matrix.Identity(4)
    obj.matrix_world = root.matrix_world @ Matrix(apply_payload_offset(matrix_rows, payload))
    if payload.get("splats") and splats_supported():
        obj["splats"] = True
        _add_splats_modifier(obj)
    elif payload.get("points"):
        if payload.get("splats"):
            obj["splats"] = True            # shown as coloured points below Blender 5.3
        spacing = float(payload.get("point_spacing") or 0.0)
        obj["point_radius_auto"] = min(max(0.6 * spacing, 0.01), 2.0) if spacing > 0 else 0.05
        _add_points_modifier(obj, point_radius_for(scene, payload),
                             getattr(scene.ogc3dtiles, "point_display", "POINTS"))
    elif getattr(scene.ogc3dtiles, "auto_relight", False):
        from ..materials import apply_relight
        for m in me.materials:
            apply_relight(m)
    _new_tile_hooks(scene, [obj], list(me.materials))
    obj.hide_viewport = hidden
    obj.hide_render = hidden
    obj.select_set(False)
    return obj.name, data_names


def apply_payload_offset(matrix_rows, payload):
    """matrix · Translate(payload["offset"]) in float64 → row-major list."""
    import numpy as np
    off = payload.get("offset")
    if not off:
        return matrix_rows
    M = np.asarray(matrix_rows, dtype=np.float64).reshape(4, 4)
    T = np.eye(4)
    T[:3, 3] = off
    return (M @ T).tolist()


def point_radius_for(scene, payload) -> float:
    props = scene.ogc3dtiles
    if getattr(props, "point_radius_mode", "AUTO") == "UNIFORM":
        return float(props.point_radius)
    spacing = float(payload.get("point_spacing") or 0.0)
    return min(max(0.6 * spacing, 0.01), 2.0) if spacing > 0 else 0.05


def apply_point_radius(scene) -> int:
    """Re-apply the radius of every point tile (mode or uniform value changed)."""
    props = scene.ogc3dtiles
    mode = getattr(props, "point_radius_mode", "AUTO")
    uniform = mode == "UNIFORM"
    for display, name in _GROUP_FOR_MODE.items():
        ng = bpy.data.node_groups.get(name)
        if ng is None:
            continue
        ng = _points_nodegroup(display)            # upgrades an old group in place
        for node_name, val in ((SCREEN_MODE_NODE, 1.0 if mode == "SCREEN" else 0.0),
                               (ADAPT_MODE_NODE, 1.0 if mode == "ADAPTIVE" else 0.0),
                               (PX_SIZE_NODE, float(props.point_px) * 0.5),   # diameter → radius
                               (PX_MIN_NODE, float(props.point_px_min_m)),
                               (PX_MAX_NODE, float(props.point_px_max_m))):
            node = ng.nodes.get(node_name)
            if node is not None:
                node.outputs[0].default_value = val
    if mode in EYE_MODES:
        ensure_view_proxy(scene)
    if mode == "ADAPTIVE":
        update_adaptive(scene, force=True)
    # per-object Radius inputs only change to / from Uniform; touching them
    # otherwise would re-evaluate every point tile for nothing
    n = 0
    for o in bpy.data.objects:
        mod = o.modifiers.get("Points") if o.type == "MESH" else None
        if mod is None or mod.type != "NODES" or mod.node_group is None:
            continue
        r = float(props.point_radius) if uniform else float(o.get("point_radius_auto", o.get("point_radius", 0.05)))
        cur = _points_input(mod, mod.node_group, "Radius")
        if cur is None or abs(cur - r) > 1e-9:
            _set_points_inputs(mod, mod.node_group, r, None)
            o.update_tag()
            n += 1
    return n


_last_adapt = [None]
_last_dir = [None]


def update_adaptive(scene, dist=None, p11=None, height_px=None, force=False):
    """Adaptive mode: Adapt Min / Max M = pixel bounds × metres-per-pixel at
    ``dist`` (eye → view pivot in the viewport, camera → point tiles when
    rendering; 1 for orthographic views).  Written to the shared groups only
    when a bound moves by more than 15 %, so point tiles re-evaluate while
    zooming, not while orbiting."""
    props = scene.ogc3dtiles
    if dist is None:
        from ..camera import viewport_focus
        vf = viewport_focus()
        if vf is None:
            return False
        dist, p11, height_px = (vf.dist if vf.persp else 1.0), vf.p11, vf.height
    mpp = float(dist) * 2.0 / max(abs(float(p11)) * float(height_px), 1e-6)
    lo = 0.5 * float(props.point_adapt_min_px) * mpp
    hi = max(0.5 * float(props.point_adapt_max_px) * mpp, lo)
    last = _last_adapt[0]
    if (not force and last is not None
            and abs(lo - last[0]) <= 0.15 * max(last[0], 1e-9)
            and abs(hi - last[1]) <= 0.15 * max(last[1], 1e-9)):
        return False
    _last_adapt[0] = (lo, hi)
    for name in POINT_GROUPS:
        ng = bpy.data.node_groups.get(name)
        if ng is None:
            continue
        for node_name, val in ((ADAPT_MIN_NODE, lo), (ADAPT_MAX_NODE, hi)):
            node = ng.nodes.get(node_name)
            if node is not None:
                node.outputs[0].default_value = val
    return True


def update_view_dir(direction, force=False):
    """Disc splats without normals face the eye: one world-space direction for
    the whole scene (updated when it turns by more than ~2°)."""
    ng = bpy.data.node_groups.get(POINTS_DISC_NODEGROUP)
    node = ng.nodes.get(VIEW_DIR_NODE) if ng else None
    if node is None:
        return False
    d = tuple(float(v) for v in direction)
    n = (d[0] ** 2 + d[1] ** 2 + d[2] ** 2) ** 0.5
    if n < 1e-9:
        return False
    d = (d[0] / n, d[1] / n, d[2] / n)
    last = _last_dir[0]
    if not force and last is not None and (d[0] * last[0] + d[1] * last[1] + d[2] * last[2]) > 0.9994:
        return False
    _last_dir[0] = d
    node.vector = d
    return True


def point_tiles_distance(scene, eye) -> float:
    """Distance from ``eye`` to the centre of the visible point tiles (render
    stand-in for the viewport's view distance); 100 m without any."""
    from mathutils import Vector
    lo = Vector((1e30, 1e30, 1e30))
    hi = -lo
    n = 0
    for o in scene.objects:
        if o.type != "MESH" or o.hide_render or o.modifiers.get("Points") is None:
            continue
        for c in o.bound_box:
            p = o.matrix_world @ Vector(c)
            lo = Vector((min(lo.x, p.x), min(lo.y, p.y), min(lo.z, p.z)))
            hi = Vector((max(hi.x, p.x), max(hi.y, p.y), max(hi.z, p.z)))
        n += 1
    if not n:
        return 100.0
    return max(((lo + hi) * 0.5 - Vector(eye)).length, 1e-3)


POINTS_NODEGROUP = "OGC3D Points"
POINTS_MESH_NODEGROUP = "OGC3D Points (Mesh)"
POINTS_DISC_NODEGROUP = "OGC3D Points (Discs)"
OVERLAY_UV_PREFIX = "_CESIUMOVERLAY_"
SPLATS_NODEGROUP = "OGC3D Splats"          # Mesh → Points → 3D Gaussian Splat (Blender 5.3+)
SPLAT_SH_C0 = 0.28209479177387814          # Y00: colour = 0.5 + C0 * dc


def splats_supported() -> bool:
    """Blender 5.3 added the Gaussian splat point cloud type and the Set
    Point Cloud Type node."""
    return tuple(bpy.app.version) >= (5, 3, 0) and hasattr(bpy.types, "GeometryNodePointsSetType")


def _store_splat_attributes(me, payload) -> None:
    """Blender's native splat attributes on the vertex-only mesh: they survive
    Mesh → Points. radiance:base = spherical-harmonic DC term + opacity, scale
    in metres, rotation as (w, x, y, z), radiance:sh_n for higher degrees."""
    import numpy as np
    n = len(me.vertices)
    rot, scl = payload.get("splat_rotation"), payload.get("splat_scale")
    cols = payload.get("colors")
    if rot is None or scl is None or len(rot) != n or len(scl) != n:
        return
    if cols is not None and len(cols) == n:
        rgb, alpha = cols[:, :3], cols[:, 3:4]
    else:
        rgb, alpha = np.full((n, 3), 0.5, np.float32), np.ones((n, 1), np.float32)
    base = np.concatenate([(rgb - 0.5) / SPLAT_SH_C0, alpha], axis=1).astype(np.float32)
    for name, dtype, key, arr in (("radiance:base", "FLOAT4", "vector", base),
                                  ("scale", "FLOAT_VECTOR", "vector", scl),
                                  ("rotation", "QUATERNION", "value", rot)):
        a = me.attributes.get(name) or me.attributes.new(name, dtype, "POINT")
        a.data.foreach_set(key, np.ascontiguousarray(arr, dtype=np.float32).ravel())
    for i, coef in enumerate(payload.get("splat_sh") or []):
        if len(coef) != n:
            break
        a = me.attributes.new(f"radiance:sh_{i}", "FLOAT_VECTOR", "POINT")
        a.data.foreach_set("vector", np.ascontiguousarray(coef, dtype=np.float32).ravel())


def _splats_nodegroup():
    ng = bpy.data.node_groups.get(SPLATS_NODEGROUP)
    if ng is not None:
        return ng
    ng = bpy.data.node_groups.new(SPLATS_NODEGROUP, "GeometryNodeTree")
    ng.is_modifier = True
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    gi = ng.nodes.new("NodeGroupInput")
    gi.location = (-400, 0)
    m2p = ng.nodes.new("GeometryNodeMeshToPoints")
    m2p.location = (-150, 0)
    st = ng.nodes.new("GeometryNodePointsSetType")
    st.location = (100, 0)
    st.inputs["Type"].default_value = "3D Gaussian Splat"
    go = ng.nodes.new("NodeGroupOutput")
    go.location = (350, 0)
    ng.links.new(gi.outputs[0], m2p.inputs["Mesh"])
    ng.links.new(m2p.outputs[0], st.inputs[0])
    ng.links.new(st.outputs[0], go.inputs[0])
    from ..node_layout import arrange
    arrange(ng)
    return ng


def _add_splats_modifier(obj) -> None:
    try:
        mod = obj.modifiers.new("Splats", "NODES")
        mod.node_group = _splats_nodegroup()
    except Exception as e:                           # noqa: BLE001
        print(f"[3DTiles] splats modifier failed: {e}")
POINT_GROUPS = (POINTS_NODEGROUP, POINTS_MESH_NODEGROUP, POINTS_DISC_NODEGROUP)
_GROUP_FOR_MODE = {"POINTS": POINTS_NODEGROUP, "MESH": POINTS_MESH_NODEGROUP,
                   "DISCS": POINTS_DISC_NODEGROUP}
POINT_SCALE_NODE = "Point Scale"


def _display_mode(mode) -> str:
    """Accept the legacy bool (mesh_mode) or the point_display enum string."""
    if mode is True:
        return "MESH"
    if mode is False or mode is None:
        return "POINTS"
    return mode if mode in _GROUP_FOR_MODE else "POINTS"


def _points_nodegroup(mesh_mode=False):
    """Shared Geometry Nodes group for vertex-only tiles.

    POINTS mode: Mesh → Points.  Cheapest; coloured in Material Preview /
    Rendered (the material reads the ``Col`` attribute) but Solid mode draws
    point clouds with the material colour only.

    MESH mode: each point becomes a tiny tetrahedron (4 verts) and the result
    is realised as a mesh whose active colour attribute is ``Col``, so Solid
    mode with Color → Attribute shows the point colours too.  The input mesh
    is joined first (that is what carries the active-colour name through
    Blender's realise step) and its loose vertices are deleted afterwards.

    DISCS mode: each point becomes an 8-gon disc instance (not realised),
    oriented along the point's glTF normal when the tile has one, otherwise
    facing the eye ("View Dir" vector, refreshed per tick / render).

    All groups take Geometry / Radius / Material and multiply the radius by
    a Value node named "Point Scale" that the sidebar exposes."""
    display = _display_mode(mesh_mode)
    mesh_mode = display == "MESH"
    name = _GROUP_FOR_MODE[display]
    ng = bpy.data.node_groups.get(name)
    if ng is not None:
        if ng.nodes.get(ADAPT_MIN_NODE) is not None:
            return ng
        # group saved by an older version: rebuild the nodes, keep the
        # interface sockets (modifiers reference them by identifier)
        for n in list(ng.nodes):
            ng.nodes.remove(n)
    else:
        ng = bpy.data.node_groups.new(name, "GeometryNodeTree")
    iface = ng.interface
    have = {it.name for it in iface.items_tree if getattr(it, "item_type", "") == "SOCKET"}
    if "Geometry" not in have:
        iface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
        iface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    if "Radius" not in have:
        radius = iface.new_socket("Radius", in_out="INPUT", socket_type="NodeSocketFloat")
        radius.default_value = 0.04
        radius.min_value = 0.0
    if "Material" not in have:
        iface.new_socket("Material", in_out="INPUT", socket_type="NodeSocketMaterial")
    N, L = ng.nodes.new, ng.links.new
    n_in = N("NodeGroupInput")
    n_out = N("NodeGroupOutput")
    scale = N("ShaderNodeValue")
    scale.name = scale.label = POINT_SCALE_NODE
    scale.outputs[0].default_value = 1.0
    mul0 = N("ShaderNodeMath")
    mul0.operation = "MULTIPLY"
    L(n_in.outputs["Radius"], mul0.inputs[0])
    L(scale.outputs[0], mul0.inputs[1])
    mul = _screen_radius_nodes(ng, mul0.outputs[0])     # metres ↔ screen-pixel radius
    m2p = N("GeometryNodeMeshToPoints")
    m2p.mode = "VERTICES"
    L(n_in.outputs["Geometry"], m2p.inputs["Mesh"])
    setmat = N("GeometryNodeSetMaterial")   # points do not inherit the mesh material
    n_in.location, scale.location, mul.location = (-700, 0), (-700, -200), (-500, -150)
    m2p.location, setmat.location, n_out.location = (-300, 0), (500, 0), (750, 0)
    if display == "POINTS":
        L(mul.outputs[0], m2p.inputs["Radius"])
        L(m2p.outputs["Points"], setmat.inputs["Geometry"])
    elif display == "DISCS":
        circle = N("GeometryNodeMeshCircle")
        circle.fill_type = "NGON"
        circle.inputs["Vertices"].default_value = 8
        circle.inputs["Radius"].default_value = 1.0
        L(circle.outputs["Mesh"], setmat.inputs["Geometry"])     # material on the disc mesh
        iop = N("GeometryNodeInstanceOnPoints")
        L(m2p.outputs["Points"], iop.inputs["Points"])
        L(setmat.outputs["Geometry"], iop.inputs["Instance"])
        L(mul.outputs[0], iop.inputs["Scale"])
        # orientation: glTF normal when the tile carries one, else the eye
        named = N("GeometryNodeInputNamedAttribute")
        named.data_type = "FLOAT_VECTOR"
        named.inputs["Name"].default_value = NORMAL_ATTR
        vdir = N("FunctionNodeInputVector")
        vdir.name = vdir.label = VIEW_DIR_NODE
        vdir.vector = (0.0, 0.0, 1.0)
        self_obj = N("GeometryNodeSelfObject")
        info = N("GeometryNodeObjectInfo")
        L(self_obj.outputs[0], info.inputs["Object"])
        inv = N("FunctionNodeInvertMatrix")
        L(info.outputs["Transform"], inv.inputs[0])
        tdir = N("FunctionNodeTransformDirection")     # world view dir → object space
        L(vdir.outputs[0], tdir.inputs["Direction"])
        L(inv.outputs[0], tdir.inputs["Transform"])
        nlen = N("ShaderNodeVectorMath")
        nlen.operation = "LENGTH"
        L(named.outputs["Attribute"], nlen.inputs[0])
        has_n = N("FunctionNodeCompare")
        has_n.data_type = "FLOAT"
        has_n.operation = "GREATER_THAN"
        has_n.inputs[1].default_value = 0.5
        L(nlen.outputs["Value"], has_n.inputs[0])
        sw = N("GeometryNodeSwitch")
        sw.input_type = "VECTOR"
        L(has_n.outputs["Result"], sw.inputs["Switch"])
        L(tdir.outputs[0], sw.inputs["False"])
        L(named.outputs["Attribute"], sw.inputs["True"])
        align = N("FunctionNodeAlignRotationToVector")
        align.axis = "Z"
        align.pivot_axis = "AUTO"
        L(sw.outputs[0], align.inputs["Vector"])
        L(align.outputs["Rotation"], iop.inputs["Rotation"])
        L(iop.outputs["Instances"], n_out.inputs["Geometry"])
        circle.location, iop.location, named.location = (-300, -300), (100, 0), (-300, 300)
        vdir.location, tdir.location, align.location = (-500, 450), (-300, 450), (-100, 350)
    else:
        cone = N("GeometryNodeMeshCone")            # 3 side vertices → tetrahedron
        cone.inputs["Vertices"].default_value = 3
        cone.inputs["Radius Bottom"].default_value = 1.0
        cone.inputs["Depth"].default_value = 1.6
        iop = N("GeometryNodeInstanceOnPoints")
        L(m2p.outputs["Points"], iop.inputs["Points"])
        L(cone.outputs["Mesh"], iop.inputs["Instance"])
        L(mul.outputs[0], iop.inputs["Scale"])
        real = N("GeometryNodeRealizeInstances")
        L(iop.outputs["Instances"], real.inputs["Geometry"])
        tag = N("GeometryNodeStoreNamedAttribute")
        tag.domain, tag.data_type = "POINT", "BOOLEAN"
        tag.inputs["Name"].default_value = "ogc3d_orig"
        tag.inputs["Value"].default_value = True
        L(n_in.outputs["Geometry"], tag.inputs["Geometry"])
        join = N("GeometryNodeJoinGeometry")
        L(real.outputs["Geometry"], join.inputs[0])
        L(tag.outputs["Geometry"], join.inputs[0])     # linked last = first input
        dele = N("GeometryNodeDeleteGeometry")
        dele.domain, dele.mode = "POINT", "ALL"
        named = N("GeometryNodeInputNamedAttribute")
        named.data_type = "BOOLEAN"
        named.inputs["Name"].default_value = "ogc3d_orig"
        L(join.outputs["Geometry"], dele.inputs["Geometry"])
        L(named.outputs["Attribute"], dele.inputs["Selection"])
        L(dele.outputs["Geometry"], setmat.inputs["Geometry"])
        cone.location, iop.location, real.location = (-300, -300), (-100, 0), (100, 0)
        tag.location, join.location, dele.location = (-100, 250), (300, 0), (400, -150)
    L(n_in.outputs["Material"], setmat.inputs["Material"])
    if display != "DISCS":
        L(setmat.outputs["Geometry"], n_out.inputs["Geometry"])
    from ..node_layout import arrange
    arrange(ng)
    return ng


VIEW_PROXY = "OGC3D View"            # Empty following the eye (viewport / camera)
SCREEN_MODE_NODE = "Screen Mode"     # 0 = metres (Radius × Point Scale), 1 = screen pixels
VIEW_SCALE_NODE = "View Scale"       # metres per pixel at distance 1 (perspective)
VIEW_PERSP_NODE = "View Persp"       # 1 perspective, 0 orthographic
PX_SIZE_NODE = "Point Pixels"
PX_MIN_NODE = "Min Radius"
PX_MAX_NODE = "Max Radius"
ADAPT_MODE_NODE = "Adaptive Mode"   # 1 = metres radius clamped to [Adapt Min M, Adapt Max M]
ADAPT_MIN_NODE = "Adapt Min M"      # metres = pixel bound × metres-per-pixel at the view pivot
ADAPT_MAX_NODE = "Adapt Max M"
VIEW_DIR_NODE = "View Dir"          # unit vector towards the eye (world); disc splats face it
NORMAL_ATTR = "ogc3d_normal"        # per-point glTF NORMAL, kept for oriented disc splats
EYE_MODES = ("SCREEN",)             # modes that need the per-point eye proxy


def _value(ng, name, default):
    n = ng.nodes.new("ShaderNodeValue")
    n.name = n.label = name
    n.outputs[0].default_value = default
    return n


def _screen_radius_nodes(ng, metres_socket):
    """Screen mode:   radius = clamp(px × dist_eff × view_scale, min_m, max_m)
    Adaptive mode: radius = clamp(metres, min_px × m_per_px, max_px × m_per_px)
    with m_per_px = dist_eff × view_scale, dist_eff = |P_world − eye| in
    perspective, 1 in orthographic.  All parameters are Value nodes shared by
    every tile (set from the panel / the streaming tick), the eye is the
    'OGC3D View' Empty."""
    N, L = ng.nodes.new, ng.links.new
    mode = _value(ng, SCREEN_MODE_NODE, 0.0)
    amode = _value(ng, ADAPT_MODE_NODE, 0.0)
    amin = _value(ng, ADAPT_MIN_NODE, 0.01)
    amax = _value(ng, ADAPT_MAX_NODE, 1.0)
    vscale = _value(ng, VIEW_SCALE_NODE, 0.002)
    persp = _value(ng, VIEW_PERSP_NODE, 1.0)
    px = _value(ng, PX_SIZE_NODE, 3.0)
    rmin = _value(ng, PX_MIN_NODE, 0.005)
    rmax = _value(ng, PX_MAX_NODE, 2.0)
    self_obj = N("GeometryNodeSelfObject")
    info_self = N("GeometryNodeObjectInfo")
    L(self_obj.outputs[0], info_self.inputs["Object"])
    pos = N("GeometryNodeInputPosition")
    world = N("FunctionNodeTransformPoint")
    L(pos.outputs[0], world.inputs["Vector"])
    L(info_self.outputs["Transform"], world.inputs["Transform"])
    info_eye = N("GeometryNodeObjectInfo")
    info_eye.name = "Eye Info"
    info_eye.inputs["Object"].default_value = bpy.data.objects.get(VIEW_PROXY)
    dist = N("ShaderNodeVectorMath")
    dist.operation = "DISTANCE"
    L(world.outputs[0], dist.inputs[0])
    L(info_eye.outputs["Location"], dist.inputs[1])
    # dist_eff = dist × persp + (1 − persp)
    d_mul = N("ShaderNodeMath")
    d_mul.operation = "MULTIPLY_ADD"
    L(dist.outputs["Value"], d_mul.inputs[0])
    L(persp.outputs[0], d_mul.inputs[1])
    one_minus = N("ShaderNodeMath")
    one_minus.operation = "SUBTRACT"
    one_minus.inputs[0].default_value = 1.0
    L(persp.outputs[0], one_minus.inputs[1])
    L(one_minus.outputs[0], d_mul.inputs[2])
    r_px = N("ShaderNodeMath")
    r_px.operation = "MULTIPLY"
    L(d_mul.outputs[0], r_px.inputs[0])
    L(vscale.outputs[0], r_px.inputs[1])
    r_px2 = N("ShaderNodeMath")
    r_px2.operation = "MULTIPLY"
    L(r_px.outputs[0], r_px2.inputs[0])
    L(px.outputs[0], r_px2.inputs[1])
    clamp = N("ShaderNodeClamp")
    L(r_px2.outputs[0], clamp.inputs["Value"])
    L(rmin.outputs[0], clamp.inputs["Min"])
    L(rmax.outputs[0], clamp.inputs["Max"])
    # adaptive: the metres radius clamped to [Adapt Min M, Adapt Max M].  Both
    # are set from Python (pixel bounds × metres-per-pixel at the distance
    # eye → view pivot), so every tile of one LOD level gets the same radius
    # and the tiles only re-evaluate when the view distance changes, not on
    # every eye move
    aclamp = N("ShaderNodeClamp")
    L(metres_socket, aclamp.inputs["Value"])
    L(amin.outputs[0], aclamp.inputs["Min"])
    L(amax.outputs[0], aclamp.inputs["Max"])
    amix = N("ShaderNodeMix")
    amix.data_type = "FLOAT"
    L(amode.outputs[0], amix.inputs["Factor"])
    L(metres_socket, amix.inputs[2])
    L(aclamp.outputs[0], amix.inputs[3])
    mix = N("ShaderNodeMix")
    mix.data_type = "FLOAT"
    L(mode.outputs[0], mix.inputs["Factor"])
    L(amix.outputs[0], mix.inputs[2])
    L(clamp.outputs[0], mix.inputs[3])
    return mix


def ensure_view_proxy(scene):
    obj = bpy.data.objects.get(VIEW_PROXY)
    if obj is None:
        obj = bpy.data.objects.new(VIEW_PROXY, None)
        obj.empty_display_type = "SPHERE"
        obj.empty_display_size = 0.5
        obj.hide_viewport = True
        obj.hide_render = True
        obj.hide_select = True
        obj["ogc3dtiles_view_proxy"] = True
        ensure_collection(scene).objects.link(obj)
    for name in POINT_GROUPS:
        ng = bpy.data.node_groups.get(name)
        node = ng.nodes.get("Eye Info") if ng else None
        if node is not None and node.inputs["Object"].default_value is not obj:
            node.inputs["Object"].default_value = obj
    return obj


_last_eye = [None]


def update_view_proxy(scene, eye_world, p11, height_px, is_persp):
    """Called every streaming tick (viewport) and on render_pre (camera):
    radius_m = px × dist × 2 / (p11 × H)   →   View Scale = 2 / (p11 × H)."""
    key = (tuple(round(v, 3) for v in eye_world), round(p11, 5), height_px, is_persp)
    if key == _last_eye[0]:
        return
    _last_eye[0] = key
    obj = ensure_view_proxy(scene)
    obj.location = eye_world
    vscale = 2.0 / max(abs(p11) * float(height_px), 1e-6)
    for name in POINT_GROUPS:
        ng = bpy.data.node_groups.get(name)
        if ng is None:
            continue
        n = ng.nodes.get(VIEW_SCALE_NODE)
        if n is not None:
            n.outputs[0].default_value = vscale
        n = ng.nodes.get(VIEW_PERSP_NODE)
        if n is not None:
            n.outputs[0].default_value = 1.0 if is_persp else 0.0


def _mod_input_get(mod, identifier):
    """A Geometry Nodes modifier input. Blender 5.3 moved them from ID
    properties to ``mod.properties.inputs.<identifier>.value``."""
    props = getattr(mod, "properties", None)
    if props is not None:
        return getattr(props.inputs, identifier).value
    return mod[identifier]


def _mod_input_set(mod, identifier, value) -> None:
    props = getattr(mod, "properties", None)
    if props is not None:
        getattr(props.inputs, identifier).value = value
    else:
        mod[identifier] = value


def _points_input(mod, ng, name):
    for item in ng.interface.items_tree:
        if getattr(item, "in_out", "") == "INPUT" and item.name == name:
            try:
                return float(_mod_input_get(mod, item.identifier))
            except Exception:          # noqa: BLE001
                return None
    return None


def _set_points_inputs(mod, ng, radius, mat):
    for item in ng.interface.items_tree:
        if getattr(item, "in_out", "") != "INPUT":
            continue
        if item.name == "Material" and mat is not None:
            _mod_input_set(mod, item.identifier, mat)
        elif item.name == "Radius":
            _mod_input_set(mod, item.identifier, float(radius))


TILE_GEOMETRY_GROUP = "OGC3D Tile Geometry"
TILE_GEOMETRY_MOD = "OGC3D Geometry"


def ensure_tile_geometry_group():
    """Shared, user-editable Geometry Nodes group applied to every tile when
    'Shared geometry nodes' is on.  Created as a pass-through."""
    ng = bpy.data.node_groups.get(TILE_GEOMETRY_GROUP)
    if ng is not None:
        return ng
    ng = bpy.data.node_groups.new(TILE_GEOMETRY_GROUP, "GeometryNodeTree")
    ng.is_modifier = True
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    return _pass_through(ng)


def reset_tile_geometry_group():
    """Back to a pass-through, in place: the tiles' modifiers keep the group."""
    ng = bpy.data.node_groups.get(TILE_GEOMETRY_GROUP)
    if ng is None:
        return ensure_tile_geometry_group()
    ng.nodes.clear()
    return _pass_through(ng)


def _pass_through(ng):
    gi = ng.nodes.new("NodeGroupInput")
    gi.location = (-300, 0)
    go = ng.nodes.new("NodeGroupOutput")
    go.location = (300, 0)
    ng.links.new(gi.outputs[0], go.inputs[0])
    return ng


def apply_tile_geometry(obj) -> bool:
    """Add the shared modifier first in the stack (before the Points display)."""
    if obj is None or obj.type != "MESH" or obj.modifiers.get(TILE_GEOMETRY_MOD) is not None:
        return False
    mod = obj.modifiers.new(TILE_GEOMETRY_MOD, "NODES")
    mod.node_group = ensure_tile_geometry_group()
    try:
        with bpy.context.temp_override(object=obj):
            bpy.ops.object.modifier_move_to_index(modifier=mod.name, index=0)
    except Exception:
        try:
            obj.modifiers.move(len(obj.modifiers) - 1, 0)
        except Exception:
            pass
    return True


def remove_tile_geometry(obj) -> bool:
    mod = obj.modifiers.get(TILE_GEOMETRY_MOD) if obj is not None and obj.type == "MESH" else None
    if mod is None:
        return False
    obj.modifiers.remove(mod)
    return True


def tile_mesh_objects():
    from ..materials import _is_tile_object
    for o in bpy.data.objects:
        if o.type == "MESH" and o.data is not None and _is_tile_object(o):
            yield o


def set_tile_geometry(enabled: bool) -> int:
    n = 0
    for o in list(tile_mesh_objects()):
        n += bool(apply_tile_geometry(o) if enabled else remove_tile_geometry(o))
    return n


def _new_tile_hooks(scene, objs, mats):
    """Per-scene toggles that every newly built tile must honour."""
    props = scene.ogc3dtiles
    if getattr(props, "clip_materials", False):
        from ..materials import apply_clip
        for m in mats:
            apply_clip(m)
    if getattr(props, "read_metadata", False):
        from ..materials import apply_metadata, sync_metadata
        sync_metadata(scene)
        if getattr(props, "meta_color", False):
            for m in mats:
                apply_metadata(m)
    if getattr(props, "voxel_display", "") == "PROJECT":
        from ..voxel_lookup import apply_material
        for m in mats:
            apply_material(m)
    from ..materials import apply_backface
    for m in mats:
        apply_backface(m, getattr(props, "backface_mode", "DOUBLE"))
    if getattr(props, "tile_geometry", False):
        for o in objs:
            apply_tile_geometry(o)
    from ..clip_nodes import CFG_PROP, apply_to_tile
    for o in objs:
        if o is not None and o.parent is not None and CFG_PROP in o.parent:
            apply_to_tile(o)


def _add_points_modifier(obj, radius: float = 0.04, mesh_mode=False):
    try:
        display = _display_mode(mesh_mode)
        created = bpy.data.node_groups.get(_GROUP_FOR_MODE[display]) is None
        ng = _points_nodegroup(display)
        if created:
            apply_point_radius(bpy.context.scene)     # push the panel values into the new group
        mod = obj.modifiers.new("Points", "NODES")
        mod.node_group = ng
        obj["point_radius"] = float(radius)
        mat = obj.data.materials[0] if obj.data.materials else None
        _set_points_inputs(mod, ng, radius, mat)
    except Exception as e:                           # noqa: BLE001
        print(f"[3DTiles] points modifier failed: {e}")


def apply_point_display(mode: str) -> int:
    """Switch every point tile between the point / tetrahedra / disc groups
    (Gaussian splat tiles keep their own group)."""
    ng = _points_nodegroup(_display_mode(mode))
    n = 0
    for o in bpy.data.objects:
        mod = o.modifiers.get("Points") if o.type == "MESH" else None
        if mod is None or mod.type != "NODES" or mod.node_group is ng or o.get("splats"):
            continue
        mod.node_group = ng
        mat = o.data.materials[0] if o.data.materials else None
        if mat is not None:
            _ensure_instancer_color(mat)
        _set_points_inputs(mod, ng, o.get("point_radius", 0.05), mat)
        o.update_tag()
        n += 1
    return n


def apply_point_scale(scale: float) -> None:
    for name in POINT_GROUPS:
        ng = bpy.data.node_groups.get(name)
        node = ng.nodes.get(POINT_SCALE_NODE) if ng else None
        if node is not None:
            node.outputs[0].default_value = float(scale)


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


def remove_tiles(records, extra_objects=()) -> int:
    """Delete tile objects (and their descendants) plus the data they created,
    in one ``bpy.data.batch_remove``.  Removing IDs one by one is quadratic:
    every ``objects.remove(do_unlink=True)`` and ``children_recursive``
    scans all objects of the file, which froze Blender for seconds when a
    stream with ~1000 tiles was torn down.  ``records``: (holder name,
    data names) pairs."""
    objs = bpy.data.objects
    roots = [o for o in (objs.get(h) for h, _d in records) if o is not None]
    roots += [o for o in extra_objects if o is not None]
    if not roots and not any(d for _h, d in records):
        return 0
    ids, seen = [], set()

    def add(idb):
        if idb is not None and idb.as_pointer() not in seen:
            seen.add(idb.as_pointer())
            ids.append(idb)

    if roots:
        children = {}
        for o in objs:                               # one scan for the whole batch
            if o.parent is not None:
                children.setdefault(o.parent.as_pointer(), []).append(o)
        stack = list(roots)
        while stack:
            o = stack.pop()
            add(o)
            stack.extend(children.get(o.as_pointer(), ()))
    for _h, data_names in records:
        for n in data_names:
            for store in (bpy.data.meshes, bpy.data.volumes, bpy.data.materials, bpy.data.images):
                d = store.get(n)
                if d is not None:
                    add(d)
                    break
    if ids:
        bpy.data.batch_remove(ids)
    return len(roots)


def remove_tile(holder_name: str, data_names: List[str]) -> None:
    remove_tiles([(holder_name, data_names)])


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


def _render_pre(scene, _depsgraph=None):
    """Rendering: the eye is the scene camera, pixels are the render height."""
    try:
        cam = scene.camera
        if cam is None:
            return
        props = scene.ogc3dtiles
        import math
        h = max(int(scene.render.resolution_y * scene.render.resolution_percentage / 100), 1)
        data = cam.data
        if data.type == "ORTHO":
            p11 = 2.0 / max(data.ortho_scale, 1e-6)
            persp = False
        else:
            p11 = 1.0 / math.tan(data.angle_y / 2.0)
            persp = True
        eye = tuple(cam.matrix_world.translation)
        mode = props.point_radius_mode
        if mode == "SCREEN" and bpy.data.objects.get(VIEW_PROXY) is not None:
            update_view_proxy(scene, eye, p11, h, persp)
        elif mode == "ADAPTIVE":
            update_adaptive(scene, point_tiles_distance(scene, eye) if persp else 1.0, p11, h, force=True)
        if getattr(props, "point_display", "") == "DISCS":
            update_view_dir(tuple(cam.matrix_world.col[2].xyz), force=True)
    except Exception as e:                           # noqa: BLE001
        print(f"[3DTiles] render view update failed: {e}")


def _upgrade_points_groups(_dummy=None):
    """Files saved with older point groups get the current nodes on load."""
    try:
        for display, name in _GROUP_FOR_MODE.items():
            if bpy.data.node_groups.get(name) is not None:
                _points_nodegroup(display)
        if bpy.data.objects.get(VIEW_PROXY) is not None:
            ensure_view_proxy(bpy.context.scene)
    except Exception as e:                           # noqa: BLE001
        print(f"[3DTiles] points group upgrade failed: {e}")


def register():
    handlers = getattr(getattr(bpy, "app", None), "handlers", None)
    if handlers is not None:
        # @persistent: handlers without it are dropped when a .blend is loaded
        if not any(getattr(h, "__name__", "") == "_render_pre" for h in handlers.render_pre):
            handlers.render_pre.append(handlers.persistent(_render_pre))
        if not any(getattr(h, "__name__", "") == "_upgrade_points_groups" for h in handlers.load_post):
            handlers.load_post.append(handlers.persistent(_upgrade_points_groups))
    _register_rest()


def _register_rest():
    pass


def unregister():
    handlers = getattr(getattr(bpy, "app", None), "handlers", None)
    if handlers is not None:
        for h in list(handlers.render_pre):
            if getattr(h, "__name__", "") == "_render_pre":
                handlers.render_pre.remove(h)
        for h in list(handlers.load_post):
            if getattr(h, "__name__", "") == "_upgrade_points_groups":
                handlers.load_post.remove(h)
    _unregister_rest()


def _unregister_rest():
    pass
