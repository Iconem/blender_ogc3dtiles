"""3dtiled aggregate sets: many datasets served as one tileset of tilesets. No bpy.

A 3dtiled server (https://github.com/Iconem/3dtiled-to-3dtiles) builds, on request, a tileset whose leaves are the
datasets of a *set*. An entry of type *3dtiled aggregate* names the set one of two ways:

  * a **set name** the server knows (``opendata``): the URL is ``<server>/aggregate/tileset.json?set=<name>``;
  * a **manifest file**, ``{"label": …, "entries": [{"url": …, "format": "potree" | "copc" | "3dtiles",
    "name": …}, …]}``, kept wherever the team keeps it (a NAS share). On Start the file is posted to
    ``<server>/aggregate/set``, which answers with a set name made of a hash of the entries
    (``upload-<32 hex>``). The server never lists such a set: whoever has the file can open it, nobody else.
    Posting again gives the same name, so the file is the up-to-date source: edit it, Start again.

The share links of a manifest are sent to that server and nowhere else; they never sit in the add-on.

One parameter is the add-on's own: ``max_km=20`` keeps the datasets up to 20 km wide. The server has no such
filter, so on Start the add-on reads the set's ``index.json`` (each dataset's radius) and hides the wider ones
with the server's ``hide=<ids>``. Datasets whose size the server does not know are kept.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from urllib.parse import quote

DEFAULT_SERVER = "https://3dtiled.iconem.com"
SET_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
MAX_BYTES = 10 * 1024 * 1024         # the server's own limit
_posted: dict = {}                   # (server, path, mtime, size) -> set name, this session
_stat: dict = {}                     # path -> (when looked at, key)
STAT_EVERY_S = 5.0


def is_set_name(value: str) -> bool:
    """A bare word is a set the server knows; anything else is a manifest file."""
    v = value.strip()
    return bool(SET_NAME.match(v)) and not v.lower().endswith(".json")


def _server(server: str) -> str:
    return (server or DEFAULT_SERVER).strip().rstrip("/")


def set_url(server: str, name: str, params: str = "") -> str:
    """The tileset URL of a set. ``params``: more of the server's query (``nest=geodetic&only=…``)."""
    p = params.strip().lstrip("?&")
    return f"{_server(server)}/aggregate/tileset.json?set={quote(name.strip(), safe='')}" + (f"&{p}" if p else "")


def read_manifest(path: str) -> bytes:
    """The manifest as the bytes to post; ValueError says what is wrong with it."""
    with open(path, "rb") as fh:
        data = fh.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("manifest over 10 MB")
    try:
        m = json.loads(data.decode("utf-8-sig"))
    except ValueError as e:
        raise ValueError(f"manifest is not JSON ({e})") from None
    entries = m if isinstance(m, list) else m.get("entries") if isinstance(m, dict) else None
    if not isinstance(entries, list) or not entries:
        raise ValueError('manifest needs {"entries": [{"url": …, "format": …}, …]}')
    for i, e in enumerate(entries):
        if not isinstance(e, dict) or not re.match(r"https?://", str(e.get("url", ""))):
            raise ValueError(f"manifest entry {i}: needs an http(s) url")
    return json.dumps(m, ensure_ascii=False).encode("utf-8")


def post_manifest(server: str, path: str, timeout: float = 30.0, opener=urllib.request.urlopen) -> str:
    """Send a manifest file to the server: the name of its set."""
    body = read_manifest(path)
    req = urllib.request.Request(f"{_server(server)}/aggregate/set", data=body, method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with opener(req, timeout=timeout) as resp:
            answer = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise ValueError(f"{_server(server)} refused the manifest: {e.code} {e.read()[:200].decode('utf-8', 'replace')}") from None
    name = answer.get("set") if isinstance(answer, dict) else None
    if not name:
        raise ValueError("the server did not name the set")
    return str(name)


def split_max_km(params: str):
    """(the server's own parameters, the width limit in km or None)."""
    keep, limit = [], None
    for part in params.strip().lstrip("?&").split("&"):
        k, _, v = part.partition("=")
        if k.strip().lower() == "max_km":
            try:
                limit = float(v) if float(v) > 0.0 else None
            except ValueError:
                limit = None
        elif part.strip():
            keep.append(part.strip())
    return "&".join(keep), limit


def wide_ids(index: dict, max_km: float) -> list:
    """Ids of the datasets of an index.json wider than ``max_km`` (twice their radius), and of those whose
    size the server does not know: they could be anything, and their place is not known either."""
    def small(r) -> bool:
        return isinstance(r, (int, float)) and not isinstance(r, bool) and 0.0 < 2.0 * r <= max_km * 1000.0
    return [str(d["id"]) for d in index.get("datasets") or () if d.get("id") and not small(d.get("radius"))]


def _with_limit(server: str, name: str, params: str, post: bool, opener) -> str:
    """The set's URL, with the datasets over ``max_km`` hidden. "" until a Start has read the index."""
    rest, limit = split_max_km(params)
    if limit is None:
        return set_url(server, name, rest)
    key = (_server(server), name, rest, limit)
    if post:
        url = set_url(server, name, rest).replace("/aggregate/tileset.json?", "/aggregate/index.json?", 1)
        try:
            with opener(urllib.request.Request(url), timeout=60.0) as resp:
                index = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, ValueError, OSError) as e:
            raise ValueError(f"max_km: could not read the set's index ({e})") from None
        _hidden[key] = ",".join(wide_ids(index, limit))
    if key not in _hidden:
        return ""
    return set_url(server, name, rest + (f"&hide={_hidden[key]}" if _hidden[key] else ""))


_hidden: dict = {}                   # (server, set, parameters, max_km) -> ids to hide, this session


def tileset_url(server: str, value: str, params: str = "", post: bool = False, opener=urllib.request.urlopen) -> str:
    """What an aggregate entry streams. A manifest file is posted when ``post`` (on Start); otherwise the set
    it got the last time this session, or "" when it was never posted."""
    v = value.strip().strip('"')
    if not v:
        return ""
    if is_set_name(v):
        return _with_limit(server, v, params, post, opener)
    seen = _stat.get(v)
    if not post and seen is not None and time.monotonic() - seen[0] < STAT_EVERY_S:
        key = seen[1]                                # a NAS path is not asked at every streaming tick
    else:
        try:
            stat = os.stat(v)
        except OSError:
            if post:
                raise ValueError(f"manifest not found: {v}") from None
            return ""
        key = (_server(server), os.path.abspath(v), stat.st_mtime_ns, stat.st_size)
        _stat[v] = (time.monotonic(), key)
    if post:
        _posted[key] = post_manifest(server, v, opener=opener)
    name = _posted.get(key)
    return _with_limit(server, name, params, post, opener) if name else ""
