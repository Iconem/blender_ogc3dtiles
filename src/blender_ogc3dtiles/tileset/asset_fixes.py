"""asset_fixes.py — requests cesium-native v0.59 cannot do by itself  (no bpy).

Subtree JSON can hold its availability in a ``data:`` URI, which cesium-native
hands to curl. Writers also leave out ``byteLength``, or write ``contentAvailability``
as one object where the spec has an array, which it then reads as "nothing available":
no tile of such a tileset ever loads. A wrapper around the asset accessor answers
``data:`` requests itself and completes the subtree JSON.

Tileset JSON: cesium-native renders a tile without content as a hole when its
geometric error is below its parent's (``TilesetContentManager::
updateContentLoadedState``): by design, "nothing to render at this level of
detail", and CesiumJS stops at such a tile too. Converter output
such as 3dtiled's keeps its content under many levels of empty tiles with
halving errors, so cesium-native showed nothing once an empty level met the
screen-space error. The wrapper gives those tiles their parent's error, which
cesium-native takes as "refine unconditionally".
"""
from __future__ import annotations

import base64
import json
import os
import re
import threading
import zlib
from urllib.parse import unquote_to_bytes

from .feature_meta import note_tileset_json

_DATA = "data:"
_SUBTREE_KEY = b'"tileAvailability"'


def decode_data_uri(url: str):
    """(content type, bytes) of a ``data:`` URI, possibly behind a base URL that
    was resolved onto it. None when ``url`` holds none."""
    at = url.find(_DATA)
    if at < 0 or "," not in url[at:]:
        return None
    head, body = url[at + len(_DATA):].split(",", 1)
    try:
        raw = base64.b64decode(body) if head.lower().endswith(";base64") else unquote_to_bytes(body)
    except ValueError:
        return None
    return head.split(";", 1)[0] or "text/plain", raw


def complete_subtree_json(data: bytes) -> bytes:
    """Subtree JSON as the spec has it, ``data`` itself when it already is or it
    isn't a subtree."""
    if _SUBTREE_KEY not in data:
        return data
    try:
        doc = json.loads(data)
    except ValueError:
        return data
    buffers, views = doc.get("buffers") or [], doc.get("bufferViews") or []
    changed = False
    if isinstance(doc.get("contentAvailability"), dict):
        doc["contentAvailability"] = [doc["contentAvailability"]]
        changed = True
    for i, buf in enumerate(buffers):
        if "byteLength" in buf:
            continue
        ends = [v.get("byteOffset", 0) + v.get("byteLength", 0) for v in views if v.get("buffer") == i]
        buf["byteLength"] = max(ends, default=0)
        changed = True
    return json.dumps(doc).encode("utf-8") if changed else data


_TILESET_KEYS = (b'"root"', b'"geometricError"')


def refine_through_empty_tiles(data: bytes) -> bytes:
    """Tileset JSON where every tile without content refines to its children:
    such a tile takes its parent's geometric error when its own is smaller. ``data`` itself when nothing changes or it isn't a tileset."""
    if any(k not in data for k in _TILESET_KEYS):
        return data
    try:
        doc = json.loads(data)
    except ValueError:
        return data
    root = doc.get("root") if isinstance(doc, dict) else None
    if not isinstance(root, dict):
        return data
    changed = False
    stack = [(child, root.get("geometricError"))
             for child in root.get("children") or [] if isinstance(child, dict)]
    while stack:
        tile, parent_ge = stack.pop()
        ge = tile.get("geometricError")
        children = tile.get("children") or []
        empty = not any(k in tile for k in ("content", "contents", "implicitTiling"))
        if (empty and children and isinstance(ge, (int, float))
                and isinstance(parent_ge, (int, float)) and ge < parent_ge):
            tile["geometricError"] = ge = parent_ge
            changed = True
        stack.extend((child, ge) for child in children if isinstance(child, dict))
    return json.dumps(doc, separators=(",", ":")).encode("utf-8") if changed else data


def _is_json_url(url: str) -> bool:
    return url.split("?", 1)[0].lower().endswith(".json")


def _finish_json(aio, future, promise):
    try:
        request = future.wait()
        response = request.response
        data = bytes(response.data) if response is not None else b""
        note_tileset_json(request.url, data)
        fixed = refine_through_empty_tiles(complete_subtree_json(data))
        if fixed is not data:
            request = aio.AssetRequest(request.method, request.url, request.headers,
                                       aio.AssetResponse(response.status_code, response.content_type,
                                                         response.headers, fixed))
        promise.resolve(request)
    except Exception as exc:      # noqa: BLE001
        promise.reject(str(exc))


# ── URL template tokens cesium-native can't fill ────────────────────────────
# UrlTemplateRasterOverlay substitutes {x} {y} {z} and a few more, nothing else,
# and its classes can't be extended from Python. The template carries a token
# made of placeholders it does know; every request passes through make_accessor,
# which turns the token into the quadkey or the subdomain.

_QUADKEY = re.compile(r"\{(?:q|quadkey)\}")
_RANGE = re.compile(r"\{([0-9a-z])-([0-9a-z])\}")
_QK_TOKEN = re.compile(r"~qk(\d+)\.(\d+)\.(\d+)~")
_SD_TOKEN = re.compile(r"~sd([0-9a-z])([0-9a-z])~")


def tile_tokens(template: str) -> str:
    """{q} / {quadkey} (Bing) and {0-3}-style subdomain ranges to tokens; {y}
    in the quadkey token is XYZ order, the caller maps it like any other {y}."""
    return _RANGE.sub(lambda m: f"~sd{m[1]}{m[2]}~", _QUADKEY.sub("~qk{z}.{x}.{y}~", template))


def quadkey(z: int, x: int, y: int) -> str:
    """Bing tile quadkey of an XYZ tile (y from the north); "" at level 0."""
    digits = []
    for i in range(z, 0, -1):
        mask = 1 << (i - 1)
        digits.append(str((1 if x & mask else 0) + (2 if y & mask else 0)))
    return "".join(digits)


def expand_tile_tokens(url: str) -> str:
    """A tile URL with its tokens filled in; ``url`` itself when it has none.
    The subdomain is picked from the tile, so a tile always gets the same one
    (and the same cache entry)."""
    if "~" not in url:
        return url
    url = _QK_TOKEN.sub(lambda m: quadkey(int(m[1]), int(m[2]), int(m[3])), url)

    def pick(m):
        lo, hi = ord(m[1]), ord(m[2])
        if hi < lo:
            return m[0]
        return chr(lo + zlib.crc32(url.encode("utf-8")) % (hi - lo + 1))
    return _SD_TOKEN.sub(pick, url)


def make_accessor(cs, inner):
    """An IAssetAccessor forwarding to ``inner``, with the fixes above."""
    aio = cs.async_

    class FixingAccessor(aio.IAssetAccessor):
        def get(self, async_system, url, headers):
            url = expand_tile_tokens(url)
            decoded = decode_data_uri(url)
            if decoded is not None:
                response = aio.AssetResponse(200, decoded[0], {}, decoded[1])
                return async_system.create_resolved_future_asset_request(
                    aio.AssetRequest("GET", url, {}, response))
            future = inner.get(async_system, url, headers)
            if not _is_json_url(url):
                return future
            # a thread, not then_in_worker_thread: the binding's continuations drop
            # their Python callback without the GIL, which crashes the interpreter
            promise = async_system.create_promise_asset_request()
            threading.Thread(target=_finish_json, args=(aio, future, promise), daemon=True).start()
            return promise.future

        def request(self, async_system, verb, url, headers, payload):
            return inner.request(async_system, verb, url, headers, payload)

        def tick(self):
            inner.tick()

    return FixingAccessor()


# ── network files through the HTTP cache ─────────────────────────────────────
# curl's file:// responses carry no Cache-Control, ETag or Last-Modified, so
# cesium-native's CachingAssetAccessor never stores them and a tileset on a NAS
# is read over the network every time it streams. Below the cache, this
# accessor serves network file: URLs itself with an ETag made of the file's
# modification time and size, and "max-age=0": the cache stores every read and
# asks again with If-None-Match each time; a stat then answers 304 (served from
# the cache) or 200 (the file changed, e.g. a re-exported tileset). Files on a
# local disk keep going through curl: a cache copy would not be faster.

_DRIVE_REMOTE = 4
_CONTENT_TYPES = {".json": "application/json", ".glb": "model/gltf-binary",
                  ".gltf": "model/gltf+json", ".png": "image/png", ".jpg": "image/jpeg",
                  ".jpeg": "image/jpeg", ".ktx2": "image/ktx2", ".webp": "image/webp"}
_POOL = []
_POOL_LOCK = threading.Lock()
_KEEP = []          # accessors handed to cesium-native, see make_network_file_accessor
# add-on preference "Cache files on network shares", read on every request so a
# change applies at once; off: network files go through curl, uncached
NETWORK_FILE_CACHE = [False]


def _remote_drive(letter: str) -> bool:
    if os.name != "nt":
        return False
    try:
        import ctypes  # noqa: PLC0415
        return ctypes.windll.kernel32.GetDriveTypeW(letter + ":\\") == _DRIVE_REMOTE
    except Exception:          # noqa: BLE001
        return False


def is_network_file_url(url: str) -> bool:
    """A ``file:`` URL on a network share: UNC (``file:////server/share``, which
    is what the add-on writes for mapped drives too) or a mapped drive letter."""
    if not url.startswith("file:"):
        return False
    rest = url[5:]
    if rest.startswith("////") or (rest.startswith("//") and not rest.startswith("///")
                                   and not rest[2:].startswith("localhost/")):
        return True
    m = re.match(r"^///([A-Za-z]):", rest)
    return bool(m) and _remote_drive(m.group(1).upper())


def file_etag(st) -> str:
    return '"%x-%x"' % (st.st_mtime_ns, st.st_size)


def _header(headers, name):
    items = headers.items() if isinstance(headers, dict) else headers or ()
    for k, v in items:
        if k.lower() == name:
            return v
    return None


def serve_file(path: str, if_none_match):
    """(status, content type, headers, data) of a local read, HTTP style."""
    try:
        st = os.stat(path)
    except OSError:
        return 404, "", {}, b""
    etag = file_etag(st)
    headers = {"ETag": etag, "Cache-Control": "max-age=0"}
    if if_none_match == etag:
        return 304, "", headers, b""
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except OSError:
        return 404, "", {}, b""
    ext = os.path.splitext(path)[1].lower()
    return 200, _CONTENT_TYPES.get(ext, "application/octet-stream"), headers, data


def _pool():
    with _POOL_LOCK:
        if not _POOL:
            from concurrent.futures import ThreadPoolExecutor  # noqa: PLC0415
            _POOL.append(ThreadPoolExecutor(max_workers=8, thread_name_prefix="ogc3d-nas"))
        return _POOL[0]


def make_network_file_accessor(cs, inner):
    """An IAssetAccessor that answers network ``file:`` URLs itself (see above)
    and forwards everything else to ``inner``."""
    aio = cs.async_
    from ..paths import url_to_path  # noqa: PLC0415

    def finish(url, if_none_match, promise):
        try:
            status, ctype, headers, data = serve_file(url_to_path(url.split("?", 1)[0]), if_none_match)
            promise.resolve(aio.AssetRequest("GET", url, {}, aio.AssetResponse(status, ctype, headers, data)))
        except Exception as exc:      # noqa: BLE001
            promise.reject(str(exc))

    class NetworkFileAccessor(aio.IAssetAccessor):
        def get(self, async_system, url, headers):
            if not NETWORK_FILE_CACHE[0] or not is_network_file_url(url):
                return inner.get(async_system, url, headers)
            # off the calling thread (often Blender's main thread): a NAS read
            # can take a while
            promise = async_system.create_promise_asset_request()
            _pool().submit(finish, url, _header(headers, "if-none-match"), promise)
            return promise.future

        def request(self, async_system, verb, url, headers, payload):
            return inner.request(async_system, verb, url, headers, payload)

        def tick(self):
            inner.tick()

    accessor = NetworkFileAccessor()
    # cesium-native holds it through the C++ accessors wrapping it; without a
    # Python reference the object is collected and every get() fails with
    # "Pure virtual IAssetAccessor.get() not implemented"
    _KEEP.append(accessor)
    return accessor
