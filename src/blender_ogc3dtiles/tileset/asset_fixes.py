"""asset_fixes.py — requests cesium-native v0.59 cannot do by itself  (no bpy).

Subtree JSON can hold its availability in a ``data:`` URI, which cesium-native
hands to curl, and writers also leave out ``byteLength``, which it then reads as
"nothing available": no tile of such a tileset ever loads. A wrapper around the
asset accessor answers ``data:`` requests itself and completes the subtree JSON.
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
    """Subtree JSON with every buffer's ``byteLength`` set, ``data`` itself when
    nothing is missing or it isn't a subtree."""
    if _SUBTREE_KEY not in data:
        return data
    try:
        doc = json.loads(data)
    except ValueError:
        return data
    buffers, views = doc.get("buffers") or [], doc.get("bufferViews") or []
    changed = False
    for i, buf in enumerate(buffers):
        if "byteLength" in buf:
            continue
        ends = [v.get("byteOffset", 0) + v.get("byteLength", 0) for v in views if v.get("buffer") == i]
        buf["byteLength"] = max(ends, default=0)
        changed = True
    return json.dumps(doc).encode("utf-8") if changed else data


def _is_json_url(url: str) -> bool:
    return url.split("?", 1)[0].lower().endswith(".json")


def _finish_json(aio, future, promise):
    try:
        request = future.wait()
        response = request.response
        data = bytes(response.data) if response is not None else b""
        note_tileset_json(request.url, data)
        fixed = complete_subtree_json(data)
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
