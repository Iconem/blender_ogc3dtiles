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
import threading
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


def make_accessor(cs, inner):
    """An IAssetAccessor forwarding to ``inner``, with the fixes above."""
    aio = cs.async_

    class FixingAccessor(aio.IAssetAccessor):
        def get(self, async_system, url, headers):
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
