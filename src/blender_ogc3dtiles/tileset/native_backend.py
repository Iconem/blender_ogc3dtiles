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

from . import asset_fixes

_YUP_TO_ZUP = np.array([[1, 0, 0, 0],
                        [0, 0, -1, 0],
                        [0, 1, 0, 0],
                        [0, 0, 0, 1]], dtype=np.float64)   # glTF (x,y,z) -> (x,-z,y)
_ZUP_TO_YUP = _YUP_TO_ZUP.T                                 # inverse (rotation)


GLOBE_URL = "globe://wgs84"      # pseudo URL of the procedural ellipsoid tileset


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
            from . import voxels
            if voxels.is_voxel_model(model):
                # placed in prepare_in_main_thread, where the bounding volume is known
                raw = bytes(req.response.data) if req is not None and req.response is not None else b""
                shape = self._owner.root_shape()
                if shape == "cylinder":
                    print("[3DTiles/native] cylinder voxel tiles are not supported, skipped")
                    return None
                payload = voxels.tile_payload(cs, model, raw, shape == "box", self._owner.voxel_volume)
                if payload is not None:
                    return ReadyTile(key, "", [], np.eye(4).tolist(), 0, None, up_axis, payload) if payload else None
            if self._owner.direct_mesh:
                try:
                    from . import native_mesh
                    payload = native_mesh.extract_mesh_payload(cs, model, self._owner.read_metadata)
                except Exception as exc:          # noqa: BLE001
                    payload = None
                    print("[3DTiles/native] direct mesh failed for %s, using GLB: %r" % (url, exc))
                if payload is not None:
                    rtc = None
                    try:
                        # a property in the binding (calling it raised and
                        # dropped every b3dm RTC_CENTER on this path)
                        ext = model.ext_cesium_rtc
                        if callable(ext):
                            ext = ext()
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
        """Runs on Blender's main thread (inside our tick). If the UI installed
        ``on_main_thread_ready`` we build the Blender object right here, so
        cesium-native only considers the tile renderable once it really is on
        screen (no holes while our import queue catches up). Otherwise queue."""
        if load_result is None:
            return None
        payload = load_result.mesh_payload
        if payload is not None and "unit_verts" in payload:
            self._owner.place_voxels(tile, payload)
        cb = self._owner.on_main_thread_ready
        if cb is not None:
            try:
                if cb(load_result):
                    return load_result
            except Exception as exc:          # noqa: BLE001
                print("[3DTiles/native] main-thread build failed for %s: %r" % (load_result.key, exc))
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

    # raster overlays ------------------------------------------------------
    # cesium-native drapes an overlay by adding _CESIUMOVERLAY_<id> texture
    # coordinates to each tile's glTF (carried by native_mesh) and calling
    # these hooks with the raster tile that covers it; the Blender side (ui /
    # overlays.py) consumes the events queued here.
    def prepare_raster_in_load_thread(self, image):
        """Worker thread: decoded raster → float RGBA rows bottom-up (Blender
        image layout), no bpy here."""
        try:
            w, h, c = int(image.width), int(image.height), int(image.channels)
            if w <= 0 or h <= 0 or int(image.bytes_per_channel) != 1 or c not in (1, 2, 3, 4):
                return None
            px = np.asarray(image.pixel_data, dtype=np.uint8)
            if px.size < w * h * c:
                return None
            px = px[: w * h * c].reshape(h, w, c)
            if c == 1:
                px = np.repeat(px, 3, axis=2)
                c = 3
            elif c == 2:
                px = np.concatenate([np.repeat(px[:, :, :1], 3, axis=2), px[:, :, 1:2]], axis=2)
                c = 4
            if c == 3:
                px = np.concatenate([px, np.full((h, w, 1), 255, np.uint8)], axis=2)
            f = (px[::-1].astype(np.float32) / 255.0).ravel()
            return {"w": w, "h": h, "pixels": f}
        except Exception as exc:          # noqa: BLE001
            print("[3DTiles/native] raster prepare failed: %r" % (exc,))
            return None

    def prepare_raster_in_main_thread(self, raster_tile, load_result):
        """Main thread (inside tick): the raster becomes a bpy Image."""
        if not load_result:
            return None
        try:
            import bpy  # noqa: PLC0415
            name = "OGC3D Overlay %s" % self._owner._next_id()
            img = bpy.data.images.new(name, load_result["w"], load_result["h"], alpha=True)
            img.colorspace_settings.name = "sRGB"
            img.pixels.foreach_set(load_result["pixels"])
            try:
                img.pack()                # survives save / reload of the .blend
            except Exception:
                pass
            return {"image": img.name}
        except Exception as exc:          # noqa: BLE001
            print("[3DTiles/native] raster image failed: %r" % (exc,))
            return None

    @staticmethod
    def _tile_key(tile):
        try:
            rr = tile.content.render_content.render_resources
        except Exception:
            return None
        return rr.key if isinstance(rr, ReadyTile) else None

    def attach_raster_in_main_thread(self, tile, tex_id, raster_tile, main_res, translation, scale):
        key = self._tile_key(tile)
        if key is None or not main_res:
            return
        try:
            uid = raster_tile.overlay.name
        except Exception:
            uid = ""
        with self._owner._lock:
            self._owner._overlay_events.append(
                ("attach", key, int(tex_id), uid, main_res["image"],
                 (float(translation[0]), float(translation[1])),
                 (float(scale[0]), float(scale[1]))))

    def detach_raster_in_main_thread(self, tile, tex_id, raster_tile, main_res):
        key = self._tile_key(tile)
        if key is None:
            return
        try:
            uid = raster_tile.overlay.name
        except Exception:
            uid = ""
        with self._owner._lock:
            self._owner._overlay_events.append(("detach", key, int(tex_id), uid))

    def free_raster(self, raster_tile, load_result, main_result):
        if main_result:
            with self._owner._lock:
                self._owner._overlay_events.append(("free", main_result["image"]))


def xyz_template(url: str) -> str:
    """XYZ convention ({y} = 0 at the north, as OSM / Esri / MapLibre templates
    use it) to cesium-native's placeholders, whose {y} is TMS order (0 at the
    south); the user writes {-y} for a TMS-ordered server."""
    return url.replace("{y}", "{reverseY}").replace("{-y}", "{y}")


def _volume_excluder(base, boxes, mode, joined):
    """ITileExcluder for what cesium-native can't test: boxes, and polygons
    that must agree with them (``joined``, native excluders). Python, called on
    the main thread for each tile visited."""
    from .. import clipping
    _want, every = clipping.box_rule(mode)

    class VolumeExcluder(base):
        def __init__(self):
            super().__init__()
            self.joined = joined                # kept alive with this excluder

        def start_new_frame(self):
            for j in joined:
                j.start_new_frame()

        def should_exclude(self, tile):
            if boxes:
                obb = tile.bounding_volume.as_oriented_bounding_box()
                cut = clipping.boxes_cut(obb.center.tolist(), obb.half_axes.tolist(), boxes, mode)
                if not (every and cut):         # settled by the boxes alone
                    return cut
            return all(j.should_exclude(tile) for j in joined)

    return VolumeExcluder()


def _make_overlay(cs, spec):
    """cesium-native RasterOverlay for an overlay list entry (see props.OVERLAY_KINDS)."""
    ro = cs.raster_overlays
    uid = spec["uid"]
    kind = spec.get("kind", "URL")
    url = (spec.get("url") or "").strip()
    key = (spec.get("key") or "").strip()
    layer = (spec.get("layer") or "").strip()
    lo, hi = int(spec.get("min_level", 0)), int(spec.get("max_level", 19))
    headers = [("User-Agent", "blender_ogc3dtiles (cesium-native)")]
    oo = ro.RasterOverlayOptions()
    oo.maximum_screen_space_error = float(spec.get("detail_px", 4.0))
    if kind == "DEBUG":
        return ro.DebugColorizeTilesRasterOverlay(uid, oo)
    if kind == "CLIP":
        # clipping mask: polygons rasterised to one channel, 255 inside (or
        # outside with "invert"); the tile material turns it into transparency
        geo = cs.geospatial
        polys = [geo.CartographicPolygon(np.asarray(p, np.float64)) for p in spec["polygons"]]
        oo.maximum_screen_space_error = float(spec.get("detail_px", 2.0))
        return ro.RasterizedPolygonsOverlay(uid, polys, bool(spec.get("invert")),
                                            geo.Ellipsoid.WGS84, geo.GeographicProjection(), oo)
    if kind == "URL":
        o = ro.UrlTemplateRasterOverlayOptions()
        o.minimum_level, o.maximum_level = lo, hi
        return ro.UrlTemplateRasterOverlay(uid, xyz_template(url), headers, o, oo)
    if kind == "TMS":
        o = ro.TileMapServiceRasterOverlayOptions()
        o.minimum_level, o.maximum_level = lo, hi
        return ro.TileMapServiceRasterOverlay(uid, url, headers, o, oo)
    if kind == "WMTS":
        o = ro.WebMapTileServiceRasterOverlayOptions()
        o.layer = layer
        o.style = spec.get("style") or "default"
        o.tile_matrix_set_id = spec.get("matrix_set") or "GoogleMapsCompatible"
        o.format = spec.get("image_format") or "image/png"
        o.minimum_level, o.maximum_level = lo, hi
        return ro.WebMapTileServiceRasterOverlay(uid, url, headers, o, oo)
    if kind == "WMS":
        o = ro.WebMapServiceRasterOverlayOptions()
        o.layers = layer
        o.format = spec.get("image_format") or "image/png"
        o.minimum_level, o.maximum_level = lo, hi
        return ro.WebMapServiceRasterOverlay(uid, url, headers, o, oo)
    if kind == "ION":
        return ro.IonRasterOverlay(uid, int(url), key, oo)
    if kind == "BING":
        return ro.BingMapsRasterOverlay(uid, url or "https://dev.virtualearth.net", key,
                                        layer or "Aerial", "", oo)
    if kind == "GOOGLE":
        p = ro.GoogleMapTilesNewSessionParameters()
        p.key = key
        p.map_type = layer or "satellite"
        p.language = "en-US"
        p.region = "US"
        return ro.GoogleMapTilesRasterOverlay(uid, p, oo)
    return None


_SHARED = {}          # cache_dir → (task_processor, async_system, accessor)
_LOCK_HANDLE = []     # keeps the cache lock file open for the process lifetime


def _cache_db_path(cache_dir):
    """One sqlite file per *process*: cesium-native's SqliteCache has no busy
    timeout, so a second Blender on the same file logs 'database is locked'
    for every request. Hold a lock file; if another process already holds it,
    use a pid-suffixed database instead."""
    os.makedirs(cache_dir, exist_ok=True)
    lock_path = os.path.join(cache_dir, "http-cache.lock")
    try:
        fh = open(lock_path, "a+")
        if os.name == "nt":
            import msvcrt  # noqa: PLC0415
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl  # noqa: PLC0415
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        _LOCK_HANDLE.append(fh)
        return os.path.join(cache_dir, "http-cache.sqlite")
    except OSError:
        print("[3DTiles/native] HTTP cache in use by another process, using a private one")
        return os.path.join(cache_dir, "http-cache-%d.sqlite" % os.getpid())


def _shared_externals(cs, cache_dir, max_loads):
    """Task processor, AsyncSystem and (caching) accessor shared by every
    tileset of this process: several CachingAssetAccessors on one sqlite file
    lock each other out ('database is locked' on every request)."""
    key = cache_dir or ""
    ent = _SHARED.get(key)
    if ent is not None:
        return ent
    tp = cs.async_.NativeTaskProcessor()
    asys = cs.async_.AsyncSystem(tp)
    copts = cs.curl.CurlAssetAccessorOptions()
    copts.user_agent = "blender-ogc3dtiles/0.3 cesium-native-python"
    inner = cs.curl.CurlAssetAccessor(copts)
    # some hosts serve pre-gzipped .json/.b3dm without Content-Encoding
    inner = cs.async_.GunzipAssetAccessor(inner)
    if cache_dir:
        accessor = cs.async_.CachingAssetAccessor(inner, _cache_db_path(cache_dir))
    else:
        accessor = inner
    accessor = asset_fixes.make_accessor(cs, accessor)
    ent = (tp, asys, accessor)
    _SHARED[key] = ent
    return ent


class CesiumNativeBackend:
    name = "cesium-native-python"

    def __init__(self, max_sse=16.0, cache_dir=None,
                 max_cached_mb=512, max_simultaneous_loads=20,
                 max_dist=float("inf"), detail_falloff=600.0, direct_mesh=True, read_metadata=False,
                 voxel_volume=False, voxel_exaggeration=1.0, **_ignored):
        self._max_sse = max_sse
        self.read_metadata = bool(read_metadata)
        self.voxel_volume = bool(voxel_volume)  # keep the whole grid of voxel tiles for a Volume
        self.voxel_exaggeration = float(voxel_exaggeration)
        self.direct_mesh = bool(direct_mesh)   # numpy -> bpy mesh instead of GLB re-import
        self.on_main_thread_ready = None        # UI callback: ReadyTile -> bool (built now?)
        self.main_thread_ms = 12.0              # cesium-native main-thread load budget per tick
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
        self._overlay_events = []
        self._overlays = {}                     # uid -> RasterOverlay
        self._excluders = {}                    # uid -> RasterizedPolygonsTileExcluder
        self._globe = False                     # procedural ellipsoid tileset
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
        self._tp, self._asys, self._accessor = _shared_externals(cs, self._cache_dir, self._max_loads)
        self._prr = self._make_preparer()
        ext = sel.TilesetExternals(self._accessor, self._prr, self._asys)

        opts = sel.TilesetOptions()
        opts.maximum_screen_space_error = float(self._max_sse)
        opts.maximum_cached_bytes = self._max_cached_bytes
        opts.maximum_simultaneous_tile_loads = self._max_loads
        opts.enable_occlusion_culling = False
        opts.enable_fog_culling = False    # height-based fog would cull the far ortho eye's view
        opts.preload_siblings = False      # fewer speculative imports on the main thread
        opts.forbid_holes = True           # keep parents until children are in
        # budget for prepare_in_main_thread work per update (ms); our mesh
        # build runs inside it, so this replaces the UI's imports_per_tick
        opts.main_thread_loading_time_limit = float(self.main_thread_ms)
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
        if u == GLOBE_URL:
            # procedural WGS84 ellipsoid (quadtree of ellipsoid patches), the
            # surface raster overlays are draped on when there is no tileset
            self._tileset = sel.EllipsoidTilesetLoader.create_tileset(ext, opts)
            self._globe = True
        elif u.startswith("ion://"):
            self._tileset = sel.Tileset(ext, int(u[6:]), ion_token or "", opts)
        elif u.isdigit() and ion_token:
            self._tileset = sel.Tileset(ext, int(u), ion_token, opts)
        else:
            self._tileset = sel.Tileset(ext, u, opts)
        for spec in options.get("overlays") or []:
            self.add_overlay(spec)

    # ------------------------------------------------------- raster overlays
    def add_overlay(self, spec):
        """spec: dict(uid, kind, url, key, layer, style, matrix_set,
        image_format, min_level, max_level). The overlay is named by its uid
        so raster tiles can be traced back to the list entry."""
        if self._tileset is None:
            return False
        try:
            ov = _make_overlay(self._cs, spec)
        except Exception as exc:          # noqa: BLE001
            self.last_error = "overlay %s: %r" % (spec.get("uid"), exc)
            print("[3DTiles/native] " + self.last_error)
            return False
        if ov is None:
            return False
        self._tileset.overlays.add(ov)
        self._overlays[spec["uid"]] = ov
        return True

    def remove_overlay(self, uid):
        ov = self._overlays.pop(uid, None)
        if ov is not None and self._tileset is not None:
            try:
                self._tileset.overlays.remove(ov)
            except Exception as exc:      # noqa: BLE001
                print("[3DTiles/native] overlay remove failed: %r" % (exc,))

    def set_excluders(self, specs, boxes=(), mode="CUT_ANY"):
        """Tiles entirely on the clipped side of these polygons and boxes
        (clipping.ecef_to_unit_box) are never loaded. The overlays only carry
        the polygons, they aren't added to the tileset, so changing them
        re-rasterises nothing."""
        if self._tileset is None:
            return
        try:
            sel = self._cs.tiles.selection
            exc = sel.RasterizedPolygonsTileExcluder
            made = {s["uid"]: exc(_make_overlay(self._cs, s)) for s in specs}
            joined = [made.pop(s["uid"]) for s in specs if s.get("and")]
            if boxes or joined:
                made["boxes"] = _volume_excluder(sel.ITileExcluder, boxes, mode, joined)
            self._excluders = made
            self._tileset.options.excluders = list(made.values())
        except Exception as exc:          # noqa: BLE001
            print("[3DTiles/native] excluders update failed: %r" % (exc,))

    def pop_overlay_events(self):
        with self._lock:
            out, self._overlay_events = self._overlay_events, []
        return out

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

    def set_main_thread_budget(self, ms):
        """Live: cesium-native's per-update budget for main-thread tile work
        (our mesh builds run inside it)."""
        ms = float(ms)
        if ms != self.main_thread_ms:
            self.main_thread_ms = ms
            if self._tileset is not None:
                self._tileset.options.main_thread_loading_time_limit = ms

    def set_max_sse(self, v):
        self._max_sse = v
        if self._tileset is not None:
            self._tileset.options.maximum_screen_space_error = float(v)

    def root_radius_m(self):
        """Bounding-sphere radius (m) of the root volume, None when unknown."""
        if self._tileset is None or self._tileset.root_tile is None:
            return None
        if self._globe:                 # the root region spans the whole ellipsoid
            return 6378137.0
        root = self._tileset.root_tile
        if root.child_count == 1 and root.geometric_error == float("inf"):
            root = root.children[0]
        bv = root.bounding_volume
        try:
            return float(self._cs.tiles.content.TileBoundingVolumes.bounding_sphere(bv).radius)
        except Exception:
            pass
        try:
            h = np.asarray(bv.as_oriented_bounding_box().half_axes, np.float64)
            return float(np.sqrt((h * h).sum()))
        except Exception:
            return None

    def place_voxels(self, tile, payload):
        """Fit a voxel tile into its bounding volume, in ECEF."""
        from . import voxels
        center = self.root_center_ecef()
        stretch = voxels.exaggeration_matrix(center, self.voxel_exaggeration) if center is not None else None
        bv = tile.bounding_volume
        region = bv.bounding_region
        if region is not None:
            r = region.rectangle
            voxels.place(payload, region=(r.west, r.south, r.east, r.north,
                                          region.minimum_height, region.maximum_height), stretch=stretch)
            return True
        obb = bv.as_oriented_bounding_box()
        voxels.place(payload, box=voxels.box_matrix(obb.center, obb.half_axes), stretch=stretch)
        return True

    def root_shape(self):
        """"box", "region" or "cylinder": the root's bounding volume, which also
        decides the cell order of voxel tiles. Fixed once the tiles load."""
        root = self._tileset.root_tile
        if root.child_count == 1 and root.geometric_error == float("inf"):
            root = root.children[0]
        bv = root.bounding_volume
        if bv.bounding_region is not None:
            return "region"
        return "cylinder" if "cylinder" in repr(bv).lower() else "box"

    def root_center_ecef(self):
        """ECEF centre of the root bounding volume once tileset.json is in."""
        if self._tileset is None or self._tileset.root_tile is None:
            return None
        if self._globe:
            return (0.0, 0.0, 0.0)      # a global tileset: the origin policy keeps the user's origin
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
        # task processor / async system / accessor are shared (see
        # _shared_externals) and stay alive for the next stream
        self._asys = None
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
