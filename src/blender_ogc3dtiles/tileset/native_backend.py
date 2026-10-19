"""
tileset/native_backend.py
-------------------------
Real cesium-native backend for the OGC 3D Tiles extension, written against the
API actually exposed by github.com/calebbuffa/cesium-native-python
(``cesium.tiles.selection.Tileset`` + ``IPrepareRendererResources``).

Flow
----
* cesium-native does everything up to a decoded glTF ``Model`` per tile
  (tileset.json / implicit tiling / external tilesets, b3dm / i3dm / pnts /
  cmpt / glb unwrapping, Draco / meshopt / KTX2 decoding, SSE selection,
  LRU tile cache, sqlite HTTP cache).
* ``_GlbPreparer.prepare_in_load_thread`` (worker thread) serialises the Model
  back to a GLB with ``GltfWriter`` (textures re-encoded to PNG only when they
  were KTX2) and records the tile ECEF transform.
* ``prepare_in_main_thread`` hands the GLB to a queue that the modal operator
  drains and imports with ``bpy.ops.import_scene.gltf``.
* ``update_view`` returns the keys of the tiles cesium-native wants rendered,
  the modal operator toggles visibility, ``free_tile`` reports evictions.

Nothing in here imports bpy; the Blender side lives in ui/__init__.py.
"""
from __future__ import annotations

import json
import math
import os
import struct
import tempfile
import threading
from typing import NamedTuple

import numpy as np

_YUP_TO_ZUP = np.array([[1, 0, 0, 0],
                        [0, 0, -1, 0],
                        [0, 1, 0, 0],
                        [0, 0, 0, 1]], dtype=np.float64)   # glTF (x,y,z) -> (x,-z,y)
_ZUP_TO_YUP = _YUP_TO_ZUP.T                                 # inverse (rotation)


class ReadyTile(NamedTuple):
    key: str          # stable id (content URL or tile id)
    glb_path: str     # GLB on disk (plus side PNGs for ex-KTX2 textures)
    aux_files: list
    transform_ecef: list   # 4x4 row-major nested lists: tile frame -> ECEF
    n_primitives: int
    rtc: list = None       # CESIUM_RTC / b3dm RTC_CENTER, tile frame (metres)
    up_axis: int = 1       # glTF up axis of the content: 0=X, 1=Y (default), 2=Z
    mesh_payload: dict = None   # native_mesh payload (direct mesh path); glb_path unused then


class NativeViewResult(NamedTuple):
    to_render: list
    to_unload: list
    stats: dict


# Extensions cesium-native has already applied/decoded; Blender's importer
# refuses any GLB that *requires* an extension it does not know, so drop them.
_APPLIED_EXTENSIONS = ("CESIUM_RTC", "KHR_draco_mesh_compression",
                       "EXT_meshopt_compression", "KHR_texture_basisu",
                       "EXT_structural_metadata", "EXT_mesh_features",
                       "EXT_instance_features", "KHR_materials_variants")


_LAST_RTC = [None]   # side channel from _glb_strip_basisu (called on one thread at a time per GLB)


def _glb_strip_basisu(glb: bytes, png_files: dict) -> bytes:
    """Rewrite the JSON chunk: textures point at plain PNGs instead of
    KHR_texture_basisu sources (Blender < 5.3 cannot read KTX2) and already
    applied extensions are removed from the extension lists."""
    if len(glb) < 20 or glb[:4] != b"glTF":
        return glb
    json_len = struct.unpack_from("<I", glb, 12)[0]
    doc = json.loads(glb[20:20 + json_len].decode("utf-8"))
    rest = glb[20 + json_len:]
    changed = False
    for k in ("extensionsRequired", "extensionsUsed"):
        lst = doc.get(k)
        if lst:
            kept = [e for e in lst if e not in _APPLIED_EXTENSIONS]
            if len(kept) != len(lst):
                changed = True
                if kept:
                    doc[k] = kept
                else:
                    doc.pop(k)
    rtc = None
    if "CESIUM_RTC" in doc.get("extensions", {}):
        # cesium-native leaves the model in glTF space; RTC is applied by the
        # renderer (us) as ENU · T_tile · Translate(rtc) · Yup→Zup · v
        c = doc["extensions"].pop("CESIUM_RTC").get("center")
        if isinstance(c, list) and len(c) == 3:
            rtc = [float(v) for v in c]
        if not doc["extensions"]:
            doc.pop("extensions")
        changed = True
    _LAST_RTC[0] = rtc
    for tex in doc.get("textures", []):
        ext = tex.get("extensions", {}).pop("KHR_texture_basisu", None)
        if ext is not None:
            tex["source"] = ext.get("source", tex.get("source", 0))
            changed = True
        if not tex.get("extensions"):
            tex.pop("extensions", None)
    for idx, path in png_files.items():
        if idx < len(doc.get("images", [])):
            img = doc["images"][idx]
            img.pop("bufferView", None)
            img["uri"] = os.path.basename(path)
            img["mimeType"] = "image/png"
            changed = True
    for k in ("extensionsRequired", "extensionsUsed"):
        if "KHR_texture_basisu" in doc.get(k, []):
            doc[k].remove("KHR_texture_basisu")
            changed = True
    if not changed:
        return glb
    js = json.dumps(doc, separators=(",", ":")).encode("utf-8")
    js += b" " * ((4 - len(js) % 4) % 4)
    body = struct.pack("<I4s", len(js), b"JSON") + js + rest
    return struct.pack("<4sII", b"glTF", 2, 12 + len(body)) + body


def _val(x):
    """The binding exposes some accessors as properties, others as methods."""
    return x() if callable(x) else x


class _GlbPreparer:
    """IPrepareRendererResources implementation (mixed into the cesium base
    class at runtime, see CesiumNativeBackend._make_preparer)."""

    def _init_owner(self, owner):
        self._owner = owner

    # worker thread -------------------------------------------------------
    def prepare_in_load_thread(self, async_system, tlr, transform):
        cs = self._owner._cs
        model = tlr.model
        if model is None:
            return None
        req = tlr.completed_request
        url = _val(req.url) if req is not None else None
        try:
            up_axis = 1
            try:
                up_axis = int(tlr.gltf_up_axis)
            except Exception:
                pass
            T = np.asarray(transform, dtype=np.float64).reshape(4, 4).T.tolist()
            base = "tile_%d" % self._owner._next_id()
            key = url or base
            if self._owner.direct_mesh:
                try:
                    from . import native_mesh
                    payload = native_mesh.extract_mesh_payload(cs, model)
                except Exception as exc:          # noqa: BLE001
                    payload = None
                    print("[3DTiles/native] direct mesh failed for %s, using GLB: %r" % (url, exc))
                if payload is not None:
                    rtc = None
                    try:
                        ext = model.ext_cesium_rtc()
                        if ext is not None and len(ext.center) == 3:
                            rtc = [float(v) for v in ext.center]
                    except Exception:
                        pass
                    n_prims = int(len(payload["faces"])) if not payload["points"] else int(len(payload["verts"]))
                    return ReadyTile(key, "", [], T, n_prims, rtc, up_axis, payload)
            png_files = {}
            tmpdir = self._owner._tmpdir
            # KTX2 images were transcoded to RGBA8 by cesium-native (we set
            # no GPU targets); write them out as PNG for Blender.
            for i, img in enumerate(model.images):
                asset = img.asset
                if asset is None:
                    continue
                mime = (img.mime_type or "").lower()
                if "ktx" in mime or (img.buffer_view < 0 and not img.uri):
                    if int(asset.compressed_pixel_format) != 0:
                        continue
                    png = cs.gltf.content.ImageManipulation.save_png(asset)
                    p = os.path.join(tmpdir, "%s_img%d.png" % (base, i))
                    with open(p, "wb") as fh:
                        fh.write(bytes(png))
                    png_files[i] = p
            cs.gltf.content.GltfUtilities.collapse_to_single_buffer(model)
            buf = model.buffers[0].cesium.data if model.buffers else np.zeros(0, np.uint8)
            res = cs.gltf.writer.GltfWriter().write_glb(model, bytes(buf))
            glb = bytes(res.gltf_bytes)
            _LAST_RTC[0] = None
            glb = _glb_strip_basisu(glb, png_files)   # always: drops applied extensions
            rtc = _LAST_RTC[0]
            try:
                up_axis = int(tlr.gltf_up_axis)
            except Exception:
                up_axis = 1
            path = os.path.join(tmpdir, base + ".glb")
            with open(path, "wb") as fh:
                fh.write(glb)
            n_prims = sum(len(m.primitives) for m in model.meshes)
            # binding hands glm matrices over column-major (arr[col, row]):
            # transposed above into row-major with translation in column 3
            return ReadyTile(key, path, list(png_files.values()), T, n_prims, rtc, up_axis)
        except Exception as exc:  # never let an exception cross into C++
            print("[3DTiles/native] prepare failed for %s: %r" % (url, exc))
            return None

    # main thread ---------------------------------------------------------
    def prepare_in_main_thread(self, tile, load_result):
        if load_result is not None:
            with self._owner._lock:
                self._owner._ready.append(load_result)
        return load_result

    def free_tile(self, tile, load_result, main_result):
        rt = main_result or load_result
        if rt is not None:
            with self._owner._lock:
                self._owner._freed.append(rt.key)
            for p in [rt.glb_path] + list(rt.aux_files):
                if not p:
                    continue
                try:
                    os.unlink(p)
                except OSError:
                    pass

    # raster overlays: not wired into Blender yet ---------------------------
    def attach_raster_in_main_thread(self, *a, **k):
        pass

    def detach_raster_in_main_thread(self, *a, **k):
        pass

    def prepare_raster_in_load_thread(self, image):
        return None

    def prepare_raster_in_main_thread(self, raster_tile, load_result):
        return None

    def free_raster(self, raster_tile, load_result, main_result):
        pass


class CesiumNativeBackend:
    name = "cesium-native-python"

    def __init__(self, max_sse=16.0, cache_dir=None,
                 max_cached_mb=512, max_simultaneous_loads=20,
                 max_dist=float("inf"), detail_falloff=600.0, direct_mesh=True, **_ignored):
        self._max_sse = max_sse
        self.direct_mesh = bool(direct_mesh)   # numpy -> bpy mesh instead of GLB re-import
        self._max_dist = max_dist              # cesium-native culls by fog/frustum; kept for parity
        self._detail_falloff = detail_falloff
        self._cache_dir = cache_dir
        self._max_cached_bytes = int(max_cached_mb) * 1024 * 1024
        self._max_loads = max_simultaneous_loads
        self._cs = None
        self._tileset = None
        self._asys = None
        self._tp = None
        self._accessor = None
        self._prr = None
        self._lock = threading.Lock()
        self._ready = []
        self._freed = []
        self._rendered = set()
        self._counter = 0
        self._tmpdir = tempfile.mkdtemp(prefix="ogc3dtiles_native_")
        self.last_error = None

    def _next_id(self):
        with self._lock:
            self._counter += 1
            return self._counter

    # ---------------------------------------------------------------- setup
    def _import_cesium(self):
        if self._cs is None:
            import cesium  # noqa: PLC0415
            import cesium.tiles.selection  # noqa: F401
            import cesium.gltf.content  # noqa: F401
            import cesium.gltf.writer  # noqa: F401
            import cesium.curl  # noqa: F401
            import cesium.tiles.content  # noqa: F401
            # without this every tile is "unknown content" and fails to load
            cesium.tiles.content.register_all_tile_content_types()
            self._cs = cesium
        return self._cs

    def _make_preparer(self):
        cs = self._cs
        Base = cs.tiles.selection.IPrepareRendererResources

        class _Preparer(Base, _GlbPreparer):
            pass

        p = _Preparer()
        p._init_owner(self)
        return p

    def load_tileset(self, url, ion_token, options):
        cs = self._import_cesium()
        sel = cs.tiles.selection
        self._tp = cs.async_.NativeTaskProcessor()
        self._asys = cs.async_.AsyncSystem(self._tp)
        copts = cs.curl.CurlAssetAccessorOptions()
        copts.user_agent = "blender-ogc3dtiles/0.3 cesium-native-python"
        inner = cs.curl.CurlAssetAccessor(copts)
        # some hosts serve pre-gzipped .json/.b3dm without Content-Encoding
        inner = cs.async_.GunzipAssetAccessor(inner)
        if self._cache_dir:
            os.makedirs(self._cache_dir, exist_ok=True)
            self._accessor = cs.async_.CachingAssetAccessor(
                inner, os.path.join(self._cache_dir, "http-cache.sqlite"))
        else:
            self._accessor = inner
        self._prr = self._make_preparer()
        ext = sel.TilesetExternals(self._accessor, self._prr, self._asys)

        opts = sel.TilesetOptions()
        opts.maximum_screen_space_error = float(self._max_sse)
        opts.maximum_cached_bytes = self._max_cached_bytes
        opts.maximum_simultaneous_tile_loads = self._max_loads
        opts.enable_occlusion_culling = False
        opts.preload_siblings = False      # fewer speculative imports on the main thread
        opts.forbid_holes = True           # keep parents until children are in
        opts.enable_lod_transition_period = False
        # No GPU formats -> KTX2 is transcoded to plain RGBA8 we can PNG-encode
        opts.content_options.ktx2_transcode_targets = cs.gltf.Ktx2TranscodeTargets()
        if options.get("request_headers"):
            opts.request_headers = list(options["request_headers"].items())

        def _on_error(details):
            self.last_error = "%s: %s" % (details.status_code, details.message)
            print("[3DTiles/native] load error " + self.last_error)
        opts.load_error_callback = _on_error

        u = url.strip()
        if u.startswith("ion://"):
            self._tileset = sel.Tileset(ext, int(u[6:]), ion_token or "", opts)
        elif u.isdigit() and ion_token:
            self._tileset = sel.Tileset(ext, int(u), ion_token, opts)
        else:
            self._tileset = sel.Tileset(ext, u, opts)

    # ------------------------------------------------------------- per tick
    def tick(self):
        if self._asys is not None:
            self._asys.dispatch_main_thread_tasks()
        if self._accessor is not None:
            try:
                self._accessor.tick()
            except Exception:
                pass

    def update_view(self, position_ecef, direction_ecef, up_ecef,
                    viewport_w, viewport_h, hfov, vfov, dt=0.0):
        if self._tileset is None:
            return NativeViewResult([], [], {})
        sel = self._cs.tiles.selection
        view = sel.ViewState(np.asarray(position_ecef, np.float64),
                             np.asarray(direction_ecef, np.float64),
                             np.asarray(up_ecef, np.float64),
                             np.asarray([viewport_w, viewport_h], np.float64),
                             float(hfov), float(vfov))
        vg = self._tileset.default_view_group
        res = self._tileset.update_view_group(vg, [view], float(dt))
        self._tileset.load_tiles()
        keys = []
        for t in res.tiles_to_render:
            rc = t.content.render_content
            if rc is None:
                continue
            rr = rc.render_resources
            if isinstance(rr, ReadyTile):
                keys.append(rr.key)
        now = set(keys)
        to_unload = sorted(self._rendered - now)
        self._rendered = now
        stats = {
            "tiles_visited": res.tiles_visited,
            "tiles_culled": res.tiles_culled,
            "to_render": len(res.tiles_to_render),
            "worker_queue": res.worker_thread_tile_load_queue_length,
            "main_queue": res.main_thread_tile_load_queue_length,
            "loaded": self._tileset.number_of_tiles_loaded,
            "bytes": self._tileset.total_data_bytes,
            "progress": self._tileset.compute_load_progress(),
        }
        return NativeViewResult(keys, to_unload, stats)

    def pop_ready(self):
        with self._lock:
            out, self._ready = self._ready, []
        return out

    def push_back_ready(self, rt):
        """Re-queue a ReadyTile the caller could not import this tick."""
        with self._lock:
            self._ready.insert(0, rt)

    def last_selection(self):
        return None

    def pop_freed(self):
        with self._lock:
            out, self._freed = self._freed, []
        return out

    def set_max_sse(self, v):
        self._max_sse = v
        if self._tileset is not None:
            self._tileset.options.maximum_screen_space_error = float(v)

    def root_center_ecef(self):
        """ECEF centre of the root bounding volume once tileset.json is in."""
        if self._tileset is None or self._tileset.root_tile is None:
            return None
        root = self._tileset.root_tile
        # cesium-native wraps tileset.json in an extra root (ge=inf); use the
        # real root's volume when there is exactly one child
        if root.child_count == 1 and root.geometric_error == float("inf"):
            root = root.children[0]
        bv = root.bounding_volume
        try:
            c = bv.center            # ndarray property in the binding
            if callable(c):
                c = c()
        except Exception:
            return None
        return (float(c[0]), float(c[1]), float(c[2]))

    # ── coordinate helpers (cesium.geospatial) ───────────────────────────
    def cartographic_to_ecef(self, lat_deg, lon_deg, height_m):
        cs = self._import_cesium()
        wgs = cs.geospatial.Ellipsoid.WGS84
        cart = cs.geospatial.Cartographic(math.radians(lon_deg), math.radians(lat_deg), height_m)
        v = wgs.cartographic_to_cartesian(cart)
        if hasattr(v, "longitude"):          # binding quirk: xyz wrapped in a Cartographic
            return (float(_val(v.longitude)), float(_val(v.latitude)), float(_val(v.height)))
        return (float(v[0]), float(v[1]), float(v[2]))

    def ecef_to_cartographic(self, x, y, z):
        cs = self._import_cesium()
        wgs = cs.geospatial.Ellipsoid.WGS84
        c = wgs.cartesian_to_cartographic(np.array([x, y, z], dtype=np.float64))
        if hasattr(c, "longitude"):
            lon, lat, h = _val(c.longitude), _val(c.latitude), _val(c.height)
        else:                                 # ndarray [lon_rad, lat_rad, height]
            lon, lat, h = float(c[0]), float(c[1]), float(c[2])
        return (math.degrees(lat), math.degrees(lon), float(h))

    def teardown(self):
        self._tileset = None
        for _ in range(3):
            self.tick()
        self._asys = None
        if self._tp is not None:
            try:
                self._tp.shutdown()
            except Exception:
                pass
        self._tp = None
        self._accessor = None
        self._prr = None


def enu_from_ecef_matrix(lat_deg, lon_deg, h):
    """4x4 matrix taking ECEF (m) to local ENU at the given WGS84 origin."""
    a, e2 = 6_378_137.0, 6.69437999014e-3
    lat, lon = math.radians(lat_deg), math.radians(lon_deg)
    sl, cl, so, co = math.sin(lat), math.cos(lat), math.sin(lon), math.cos(lon)
    N = a / math.sqrt(1 - e2 * sl * sl)
    ox, oy, oz = (N + h) * cl * co, (N + h) * cl * so, (N * (1 - e2) + h) * sl
    R = np.array([[-so,      co,     0],
                  [-sl * co, -sl * so, cl],
                  [cl * co,  cl * so, sl]], dtype=np.float64)
    M = np.eye(4)
    M[:3, :3] = R
    M[:3, 3] = -R @ np.array([ox, oy, oz])
    return M


def blender_matrix_for_tile(transform_ecef, origin_lat, origin_lon, origin_h,
                            rtc=None, up_axis=1):
    """World matrix for the parent Empty of a tile imported with
    bpy.ops.import_scene.gltf.

    cesium-native hands us the model untouched (glTF Y-up, CESIUM_RTC still a
    plain extension), the renderer composes  ECEF = T_tile · Translate(rtc) ·
    Yup→Zup · v.  Blender's importer already bakes Yup→Zup into the geometry,
    so the Empty gets  ENU_from_ECEF · T_tile · Translate(rtc)  (and an extra
    Zup→Yup only for legacy Z-up content, to undo the importer's conversion)."""
    T = np.asarray(transform_ecef, dtype=np.float64).reshape(4, 4)
    M = enu_from_ecef_matrix(origin_lat, origin_lon, origin_h) @ T
    if rtc:
        R = np.eye(4)
        R[:3, 3] = rtc
        M = M @ R
    if up_axis == 2:
        M = M @ _ZUP_TO_YUP
    return M
