"""
Copy a 3D Tiles tileset to a local folder, optionally cropped.

``export_tileset(url, dest_dir, extent=..., min_geometric_error=...)`` walks
the tileset (explicit tiling, external tilesets followed recursively,
implicit tiling expanded into explicit tiles), keeps the tiles whose bounding
volume intersects ``extent`` (an oriented box in ECEF) and stops descending
below ``min_geometric_error``, then downloads the content of the kept tiles
with a thread pool and writes rewritten tileset JSONs whose content URIs are
relative paths into the copy.

The source can be http(s) (the query string may carry an access token), a
``file:`` URL, a plain local / UNC path, or a Cesium ion asset (``ion://<id>``
or a bare id, with ``ion_token``).  Child URIs inherit the query parameters of
the file that references them (``key`` / ``session`` for Google Photorealistic
3D Tiles, SAS tokens...), like CesiumJS.  Nothing written to ``dest_dir``
carries the source's query string, path or tokens: saved file names and JSON
URIs are relative to the root tileset's directory (files outside it go to
``ext/<hash>/<name>``), and ``export.json`` only records the host and the
root file name (share links can carry their token in the path).

Implicit tiling (3D Tiles 1.1 ``implicitTiling`` and the 1.0
``3DTILES_implicit_tiling`` extension, quadtree / octree, region / box
volumes) is written out as explicit children; subtrees are only read where
the extent / geometric error cut lets the walk go.

No bpy here; the Blender operator drives it from a background thread.
"""
from __future__ import annotations

import copy
import datetime
import gzip
import hashlib
import json
import math
import os
import posixpath
import re
import struct
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from typing import Callable, Dict, List, Optional, Tuple
from urllib.parse import parse_qsl, quote, unquote, urlencode, urlsplit, urlunsplit

from ..tileset.traversal import (
    BoundingVolume,
    _geodetic_to_ecef,
    _resolve_uri,
    is_tileset_uri,
    mat_apply,
    mat_from_column_major,
    mat_identity,
    mat_mul,
)

TIMEOUT_S = 60
RETRIES = 3
ION_API = "https://api.cesium.com"
_RESERVED = {"tileset.json", "export.json"}
_BAD_CHARS = re.compile(r'[<>:"|?*\x00-\x1f]')
_SECRET_PARAMS = {"key", "access_token"}
_IMPLICIT_EXT = "3DTILES_implicit_tiling"
_MULTI_EXT = "3DTILES_multiple_contents"


class ExportCancelled(Exception):
    """The caller's ``cancel()`` returned True."""


class ExportError(Exception):
    """The tileset cannot be exported (unsupported source or content)."""

    def __init__(self, msg: str, status: Optional[int] = None):
        super().__init__(msg)
        self.status = status


# ── source URLs ──────────────────────────────────────────────────────────────

def _path_to_file_url(path: str) -> str:
    """Local path → file URL: ``C:\\a\\b`` → ``file:///C:/a/b``,
    ``\\\\server\\share\\x`` → ``file:////server/share/x``."""
    p = path.replace("\\", "/")
    if p.startswith("//"):
        return "file://" + quote(p, safe="/:$~")
    if re.match(r"^[A-Za-z]:/", p):
        return "file:///" + quote(p, safe="/:$~")
    return "file://" + quote(os.path.abspath(path).replace("\\", "/"), safe="/:$~")


def file_url_to_path(url: str) -> str:
    """file URL → path open() accepts (drive letter or UNC)."""
    parts = urlsplit(url)
    path = unquote(parts.path)
    host = parts.netloc
    if host and host.lower() != "localhost":
        return "//" + host + path                     # file://server/share/x
    if path.startswith("//"):
        return path                                   # file:////server/share/x
    if re.match(r"^/[A-Za-z]:", path):
        return path[1:]                               # file:///C:/x
    return path


def _normalise(url: str) -> str:
    """Resolve ``.`` / ``..`` in the URL path (keeps a UNC ``//`` prefix)."""
    p = urlsplit(url)
    path = posixpath.normpath(p.path) if p.path else "/"
    if p.path.endswith("/") and not path.endswith("/"):
        path += "/"
    return urlunsplit(p._replace(path=path))


def _strip(url: str) -> str:
    """URL without query, fragment or user info (dedup key, hashing)."""
    p = urlsplit(url)
    netloc = p.netloc.rsplit("@", 1)[-1]
    return urlunsplit((p.scheme, netloc, p.path, "", ""))


def _ion_asset_id(url: str) -> Optional[int]:
    u = url.strip()
    if u.startswith("ion://"):
        rest = u[6:].strip("/")
        if not rest.isdigit():
            raise ExportError(f"Bad Cesium ion asset '{u}'")
        return int(rest)
    return int(u) if u.isdigit() else None


def _check_source(url: str) -> str:
    u = url.strip()
    if not u:
        raise ExportError("No tileset URL")
    if re.match(r"^[A-Za-z]:[\\/]", u) or u.startswith("\\\\") or u.startswith("//") \
            or (not re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", u)):
        u = _path_to_file_url(u)
    scheme = urlsplit(u).scheme.lower()
    if scheme not in ("http", "https", "file"):
        raise ExportError(f"Unsupported URL scheme '{scheme}'")
    return _normalise(u)


def _add_query(url: str, params: List[Tuple[str, str]]) -> str:
    p = urlsplit(url)
    q = parse_qsl(p.query, keep_blank_values=True)
    have = {k for k, _ in q}
    q += [(k, v) for k, v in params if k not in have]
    return urlunsplit(p._replace(query=urlencode(q)))


def _resolve_ion(asset_id: int, token: str) -> Tuple[str, dict]:
    """ion asset → (tileset url, headers for that url's host)."""
    if not token:
        raise ExportError("A Cesium ion access token is needed to copy an ion asset")
    ep_url = f"{ION_API}/v1/assets/{asset_id}/endpoint?access_token={quote(token, safe='')}"
    try:
        ep = json.loads(_fetch(ep_url, None).decode("utf-8-sig"))
    except ExportError as e:
        raise ExportError(f"Cesium ion asset {asset_id}: endpoint request failed "
                          f"(HTTP {e.status or '?'})", e.status) from None
    except ValueError:
        raise ExportError(f"Cesium ion asset {asset_id}: bad endpoint reply") from None
    if ep.get("type") not in (None, "3DTILES"):
        raise ExportError(f"Cesium ion asset {asset_id} is {ep.get('type')}, not 3D Tiles")
    if ep.get("externalType"):
        # e.g. Google Photorealistic 3D Tiles through ion: options.url (+ key)
        opts = ep.get("options") or {}
        u = opts.get("url")
        if not u:
            raise ExportError(f"Cesium ion asset {asset_id}: external asset without a URL")
        if opts.get("key"):
            u = _add_query(u, [("key", str(opts["key"]))])
        return u, {}
    if not ep.get("url"):
        raise ExportError(f"Cesium ion asset {asset_id}: endpoint has no URL")
    headers = {"Authorization": f"Bearer {ep['accessToken']}"} if ep.get("accessToken") else {}
    return ep["url"], headers


# ── secrets never written ────────────────────────────────────────────────────

def _scrub_str(s: str, secrets) -> str:
    for sec in secrets:
        if sec and sec in s:
            s = s.replace(sec, "")
    if "?" in s and "=" in s:
        p = urlsplit(s)
        if p.query:
            q = parse_qsl(p.query, keep_blank_values=True)
            kept = [(k, v) for k, v in q if k.lower() not in _SECRET_PARAMS]
            if len(kept) != len(q):
                s = urlunsplit(p._replace(query=urlencode(kept)))
    return s


def _scrub(obj, secrets):
    """Copy of a JSON value without ``key`` / ``access_token`` query params nor
    any of ``secrets`` in its strings."""
    if isinstance(obj, dict):
        return {k: _scrub(v, secrets) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_scrub(v, secrets) for v in obj]
    if isinstance(obj, str):
        return _scrub_str(obj, secrets)
    return obj


# ── fetching ─────────────────────────────────────────────────────────────────

def _fetch(url: str, headers: Optional[dict]) -> bytes:
    if urlsplit(url).scheme.lower() == "file":
        try:
            with open(file_url_to_path(url), "rb") as f:
                data = f.read()
        except OSError as e:
            raise ExportError(f"Cannot read {posixpath.basename(urlsplit(url).path)}: {e}") from e
    else:
        last = None
        status = None
        data = None
        for attempt in range(RETRIES + 1):
            try:
                req = urllib.request.Request(url, headers=dict(headers or {}))
                with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
                    data = resp.read()
                break
            except urllib.error.HTTPError as e:
                last = e
                status = e.code
                if e.code not in (408, 425, 429, 500, 502, 503, 504):
                    break
            except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
                last = e
            if attempt < RETRIES:
                time.sleep(0.5 * (2 ** attempt))
        if data is None:
            name = posixpath.basename(urlsplit(url).path)
            raise ExportError(f"Download failed for {name}: {last}", status)
    if data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    return data


# ── bounding volumes vs the extent ───────────────────────────────────────────

def _sphere(bv: dict, world) -> Tuple[Tuple[float, float, float], float]:
    """ECEF bounding sphere of a tile bounding volume under ``world``."""
    if bv.get("region"):
        w, s, e, n, h0, h1 = bv["region"]
        corners = [_geodetic_to_ecef(math.degrees(la), math.degrees(lo), h)
                   for la in (s, n) for lo in (w, e) for h in (h0, h1)]
        # the equator / mid-longitude bulge of wide regions: add the mid point
        corners.append(_geodetic_to_ecef(math.degrees((s + n) / 2),
                                         math.degrees((w + e) / 2), h1))
        c = tuple(sum(p[i] for p in corners) / len(corners) for i in range(3))
        r = max(math.dist(c, p) for p in corners)
        return c, r
    if bv.get("box"):
        b = bv["box"]
        c = mat_apply(world, b[:3])
        axes = []
        for k in range(3):
            v = b[3 + 3 * k: 6 + 3 * k]
            axes.append(tuple(sum(world[i][j] * v[j] for j in range(3)) for i in range(3)))
        r = 0.0
        for sx in (-1, 1):
            for sy in (-1, 1):
                for sz in (-1, 1):
                    d = [sx * axes[0][i] + sy * axes[1][i] + sz * axes[2][i] for i in range(3)]
                    r = max(r, math.sqrt(sum(x * x for x in d)))
        return c, r
    if bv.get("sphere"):
        s = bv["sphere"]
        v = BoundingVolume(sphere=s)
        return v.center_ecef(world), v.geometric_radius(world)
    return (0.0, 0.0, 0.0), float("inf")


def sphere_intersects_obb(center, radius, extent) -> bool:
    """Sphere vs oriented box (``extent`` = dict(center, half_axes))."""
    if radius == float("inf"):
        return True
    ec = extent["center"]
    d = [center[i] - ec[i] for i in range(3)]
    closest = list(ec)
    for a in extent["half_axes"]:
        length = math.sqrt(sum(x * x for x in a))
        if length <= 0.0:
            continue
        u = [x / length for x in a]
        t = max(-length, min(length, sum(d[i] * u[i] for i in range(3))))
        for i in range(3):
            closest[i] += t * u[i]
    return math.dist(center, closest) <= radius


def _count(tile: dict) -> int:
    return 1 + sum(_count(c) for c in tile.get("children") or [])


def _is_implicit(tile: dict) -> bool:
    return bool(tile.get("implicitTiling")) or \
        _IMPLICIT_EXT in (tile.get("extensions") or {})


# ── implicit tiling ──────────────────────────────────────────────────────────

def _morton(x: int, y: int, z: int, dims: int) -> int:
    """Interleave the bits of x, y (, z): x in the lowest bit."""
    m = 0
    bit = 0
    while (x >> bit) or (y >> bit) or (z >> bit):
        m |= ((x >> bit) & 1) << (dims * bit)
        m |= ((y >> bit) & 1) << (dims * bit + 1)
        if dims == 3:
            m |= ((z >> bit) & 1) << (dims * bit + 2)
        bit += 1
    return m


class _Avail:
    """One availability: a constant or a bitstream (bit i = byte i//8, LSB first)."""
    __slots__ = ("const", "bits")

    def __init__(self, const: Optional[int] = None, bits: bytes = b""):
        self.const = const
        self.bits = bits

    def __call__(self, i: int) -> bool:
        if self.const is not None:
            return bool(self.const)
        b = i >> 3
        return b < len(self.bits) and bool((self.bits[b] >> (i & 7)) & 1)


class _Subtree:
    __slots__ = ("tile", "content", "child")

    def __init__(self, tile: _Avail, content: List[_Avail], child: _Avail):
        self.tile = tile
        self.content = content
        self.child = child


def parse_subtree(data: bytes, url: str, fetch: Callable[[str], bytes]) -> _Subtree:
    """Binary ``.subtree`` (``subt`` magic, JSON + binary chunks) or JSON subtree
    → availabilities.  External buffers are fetched (``fetch(url)``) only when
    an availability bitstream lives in them."""
    if data[:4] == b"subt":
        if len(data) < 24:
            raise ExportError("Truncated subtree file")
        _, jlen, blen = struct.unpack_from("<IQQ", data, 4)
        head = data[24:24 + jlen]
        binary = data[24 + jlen:24 + jlen + blen]
    else:
        head, binary = data, b""
    try:
        js = json.loads(head.decode("utf-8-sig").rstrip(" \x00"))
    except ValueError as e:
        raise ExportError(f"Bad subtree: {posixpath.basename(urlsplit(url).path)}") from e
    buffers = js.get("buffers") or []
    views = js.get("bufferViews") or []
    loaded: Dict[int, bytes] = {}

    def buffer(i: int) -> bytes:
        if i not in loaded:
            b = buffers[i]
            loaded[i] = fetch(_normalise(_resolve_uri(b["uri"], url))) if b.get("uri") else binary
        return loaded[i]

    def avail(a) -> _Avail:
        if not isinstance(a, dict):
            return _Avail(const=0)
        if "constant" in a:
            return _Avail(const=int(a["constant"]))
        vi = a.get("bitstream", a.get("bufferView"))
        if vi is None:
            return _Avail(const=0)
        try:
            v = views[vi]
            off = int(v.get("byteOffset", 0))
            return _Avail(bits=bytes(buffer(int(v["buffer"]))[off:off + int(v["byteLength"])]))
        except (IndexError, KeyError, TypeError) as e:
            raise ExportError(f"Bad subtree buffer view in "
                              f"{posixpath.basename(urlsplit(url).path)}") from e

    ca = js.get("contentAvailability")
    if ca is None:
        ca = ((js.get("extensions") or {}).get(_MULTI_EXT) or {}).get("contentAvailability")
    if isinstance(ca, dict):
        ca = [ca]
    return _Subtree(avail(js.get("tileAvailability")), [avail(a) for a in ca or []],
                    avail(js.get("childSubtreeAvailability")))


class _Implicit:
    """The implicit tiling of one tile: scheme, levels, templates, root volume."""

    def __init__(self, tile: dict):
        ext = (tile.get("extensions") or {}).get(_IMPLICIT_EXT)
        it = tile.get("implicitTiling") or ext or {}
        scheme = str(it.get("subdivisionScheme", "")).upper()
        if scheme not in ("QUADTREE", "OCTREE"):
            raise ExportError(f"Unknown implicit subdivision scheme '{scheme}'")
        self.dims = 3 if scheme == "OCTREE" else 2
        self.n = 1 << self.dims
        self.sub_levels = int(it.get("subtreeLevels", 0))
        if "availableLevels" in it:
            self.levels = int(it["availableLevels"])
        else:
            self.levels = int(it.get("maximumLevel", 0)) + 1
        if self.sub_levels < 1 or self.levels < 1:
            raise ExportError("Implicit tiling without levels")
        self.subtree_uri = ((it.get("subtrees") or {}).get("uri")) or ""
        if not self.subtree_uri:
            raise ExportError("Implicit tiling without a subtree URI")
        bv = tile.get("boundingVolume") or {}
        if bv.get("region"):
            self.region, self.box = [float(v) for v in bv["region"]], None
        elif bv.get("box"):
            self.region, self.box = None, [float(v) for v in bv["box"]]
        else:
            raise ExportError("Implicit tiling needs a region or box bounding volume "
                              "(S2 volumes are not supported)")
        self.ge = float(tile.get("geometricError", 0.0))
        # content templates, in contentAvailability order
        multi = (tile.get("extensions") or {}).get(_MULTI_EXT)
        if isinstance(tile.get("content"), dict):
            self.contents, self.contents_field = [tile["content"]], "content"
        elif tile.get("contents"):
            self.contents, self.contents_field = list(tile["contents"]), "contents"
        elif multi and multi.get("content"):
            self.contents, self.contents_field = list(multi["content"]), "ext"
        else:
            self.contents, self.contents_field = [], "content"

    def index(self, level: int, x: int, y: int, z: int) -> int:
        """Level-order Morton index inside a subtree (subtree-local coords)."""
        return ((self.n ** level) - 1) // (self.n - 1) + _morton(x, y, z, self.dims)

    def volume(self, level: int, x: int, y: int, z: int) -> dict:
        size = 1 << level
        if self.region is not None:
            w, s, e, n, h0, h1 = self.region
            dx, dy = (e - w) / size, (n - s) / size
            r = [w + dx * x, s + dy * y, w + dx * (x + 1), s + dy * (y + 1), h0, h1]
            if self.dims == 3:
                dz = (h1 - h0) / size
                r[4], r[5] = h0 + dz * z, h0 + dz * (z + 1)
            return {"region": r}
        b = self.box
        u, v, w_ = b[3:6], b[6:9], b[9:12]
        fu = (2 * x + 1) / size - 1
        fv = (2 * y + 1) / size - 1
        fw = (2 * z + 1) / size - 1 if self.dims == 3 else 0.0
        c = [b[i] + u[i] * fu + v[i] * fv + w_[i] * fw for i in range(3)]
        sw = size if self.dims == 3 else 1
        return {"box": c + [a / size for a in u] + [a / size for a in v] + [a / sw for a in w_]}


def _expand(template: str, level: int, x: int, y: int, z: int) -> str:
    return (template.replace("{level}", str(level)).replace("{x}", str(x))
            .replace("{y}", str(y)).replace("{z}", str(z)))


# ── the export ───────────────────────────────────────────────────────────────

class _Exporter:
    def __init__(self, url, dest_dir, extent, min_ge, headers, workers, progress, cancel,
                 scoped_headers=None, secrets=(), refresh=None):
        self.root_url = url
        self.dest = os.path.abspath(dest_dir)
        self.extent = extent
        self.min_ge = float(min_geometric_error_or_zero(min_ge))
        self.headers = headers or {}
        # headers only sent to the root host (an ion bearer token)
        self.scoped_headers = dict(scoped_headers or {})
        self.secrets = tuple(s for s in secrets if s and len(s) >= 6)
        self.refresh = refresh            # () → new scoped headers (ion token expired)
        self.workers = max(1, int(workers))
        self.progress = progress or (lambda done, total, msg: None)
        self.cancel = cancel or (lambda: False)
        rp = urlsplit(url)
        self.root_key = (rp.scheme.lower(), rp.netloc.rsplit("@", 1)[-1].lower())
        self.root_dir = posixpath.dirname(rp.path).rstrip("/")
        self.kept = 0
        self.dropped = 0
        self.jobs: Dict[str, str] = {}          # out_rel → source url
        self.json_rels: Dict[str, str] = {}     # stripped json url → out_rel
        self.json_bytes = 0
        self.subtrees = 0
        self.lock = threading.Lock()

    # paths --------------------------------------------------------------
    def out_rel(self, url: str) -> str:
        """Relative output path (posix) of a source URL."""
        p = urlsplit(url)
        key = (p.scheme.lower(), p.netloc.rsplit("@", 1)[-1].lower())
        path = p.path
        if key == self.root_key and self.root_dir and path.startswith(self.root_dir + "/"):
            rel = unquote(path[len(self.root_dir) + 1:])
        elif key == self.root_key and not self.root_dir and path.startswith("/"):
            rel = unquote(path[1:])
        else:
            h = hashlib.sha1(_strip(url).encode("utf-8")).hexdigest()[:12]
            rel = f"ext/{h}/{unquote(posixpath.basename(path)) or 'content'}"
        parts = [_BAD_CHARS.sub("_", s) for s in rel.split("/") if s not in ("", ".", "..")]
        rel = "/".join(parts) or "content"
        for sec in self.secrets:
            rel = rel.replace(sec, "_")
        if rel in _RESERVED:
            rel = "_" + rel
        return rel

    def check_cancel(self):
        if self.cancel():
            raise ExportCancelled()

    def fetch(self, url: str) -> bytes:
        p = urlsplit(url)
        same_host = (p.scheme.lower(), p.netloc.rsplit("@", 1)[-1].lower()) == self.root_key
        scoped = self.scoped_headers if same_host else {}
        try:
            return _fetch(url, {**self.headers, **scoped})
        except ExportError as e:
            if e.status != 401 or not same_host or self.refresh is None:
                raise
        with self.lock:                 # the ion token expired: ask for a new one, retry once
            if self.scoped_headers is scoped or self.scoped_headers == scoped:
                self.scoped_headers = dict(self.refresh())
            scoped = self.scoped_headers
        return _fetch(url, {**self.headers, **scoped})

    # tileset walk -----------------------------------------------------------
    def read_json(self, url: str) -> dict:
        self.check_cancel()
        self.progress(0, 0, f"reading {posixpath.basename(urlsplit(url).path)}")
        data = self.fetch(url)
        try:
            return json.loads(data.decode("utf-8-sig"))
        except ValueError as e:
            raise ExportError(f"Not a tileset JSON: {posixpath.basename(urlsplit(url).path)}") from e

    def export_json(self, url: str, out_rel: str, parent_world, seen) -> None:
        key = _strip(url)
        if key in seen:
            raise ExportError("External tilesets reference each other in a cycle")
        seen = seen | {key}
        doc = self.read_json(url)
        root = doc.get("root")
        if not isinstance(root, dict):
            raise ExportError("Tileset JSON has no root tile")
        out = copy.deepcopy(doc)
        out_dir = posixpath.dirname(out_rel)
        schema = doc.get("schemaUri")
        if schema:
            s_url = _normalise(_resolve_uri(schema, url))
            out["schemaUri"] = self.add_job(s_url, out_dir)
        new_root = self.walk(root, parent_world, url, out_dir, seen)
        if new_root is None:
            # keep the file valid: a root without content or children
            new_root = {k: v for k, v in root.items()
                        if k not in ("children", "content", "contents", "implicitTiling")}
            _drop_ext(new_root, _IMPLICIT_EXT)
        out["root"] = new_root
        # implicit tiles are written out explicitly
        for k in ("extensionsUsed", "extensionsRequired"):
            if isinstance(out.get(k), list) and _IMPLICIT_EXT in out[k]:
                out[k] = [e for e in out[k] if e != _IMPLICIT_EXT]
                if not out[k]:
                    del out[k]
        out = _scrub(out, self.secrets)
        path = os.path.join(self.dest, *out_rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        data = json.dumps(out, indent=None, separators=(",", ":")).encode("utf-8")
        tmp = path + ".part"
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
        self.json_bytes += len(data)

    def add_job(self, src_url: str, out_dir: str) -> str:
        rel = self.out_rel(src_url)
        with self.lock:
            self.jobs.setdefault(rel, src_url)
        return quote(posixpath.relpath(rel, out_dir or "."), safe="/")

    def content(self, ct: dict, uri: Optional[str], world, base_url: str, out_dir: str,
                seen) -> dict:
        """A content object rewritten to point into the copy (external
        tilesets exported on the way)."""
        nc = {k: v for k, v in copy.deepcopy(ct).items() if k != "url"}
        if not uri or uri.startswith("data:"):
            return nc
        c_url = _normalise(_resolve_uri(uri, base_url))
        if is_tileset_uri(c_url):
            k = _strip(c_url)
            rel = self.json_rels.get(k)
            if rel is None:
                rel = self.out_rel(c_url)
                self.json_rels[k] = rel
                self.export_json(c_url, rel, world, seen)
            nc["uri"] = quote(posixpath.relpath(rel, out_dir or "."), safe="/")
        else:
            nc["uri"] = self.add_job(c_url, out_dir)
        return nc

    def missed(self, bv: dict, world) -> bool:
        if self.extent is None:
            return False
        c, r = _sphere(bv or {}, world)
        return not sphere_intersects_obb(c, r, self.extent)

    def walk(self, tile: dict, parent_world, base_url: str, out_dir: str, seen) -> Optional[dict]:
        self.check_cancel()
        world = parent_world
        if tile.get("transform"):
            world = mat_mul(world, mat_from_column_major(tile["transform"]))
        if self.missed(tile.get("boundingVolume"), world):
            self.dropped += _count(tile)
            return None
        if _is_implicit(tile):
            return self.walk_implicit(tile, world, base_url, out_dir, seen)
        out = {k: v for k, v in tile.items() if k not in ("children", "content", "contents")}
        out = copy.deepcopy(out)
        self.kept += 1
        if isinstance(tile.get("content"), dict):
            ct = tile["content"]
            out["content"] = self.content(ct, ct.get("uri") or ct.get("url"), world,
                                          base_url, out_dir, seen)
        for ct in tile.get("contents") or []:
            out.setdefault("contents", []).append(
                self.content(ct, ct.get("uri") or ct.get("url"), world, base_url, out_dir, seen))
        children = tile.get("children") or []
        if children and self.min_ge > 0.0 and float(tile.get("geometricError", 0.0)) <= self.min_ge:
            self.dropped += sum(_count(ch) for ch in children)
        elif children:
            kept = [k for k in (self.walk(ch, world, base_url, out_dir, seen) for ch in children)
                    if k is not None]
            if kept:
                out["children"] = kept
        return out

    # implicit tiling ----------------------------------------------------------
    def load_subtree(self, imp: _Implicit, base_url: str, level, x, y, z) -> _Subtree:
        self.check_cancel()
        url = _normalise(_resolve_uri(_expand(imp.subtree_uri, level, x, y, z), base_url))
        self.progress(0, 0, f"reading subtree {level}/{x}/{y}" + (f"/{z}" if imp.dims == 3 else ""))
        self.subtrees += 1
        return parse_subtree(self.fetch(url), url, self.fetch)

    def walk_implicit(self, tile: dict, world, base_url: str, out_dir: str, seen) -> dict:
        """The implicit root (already inside the extent) → explicit tile tree."""
        imp = _Implicit(tile)
        out = copy.deepcopy({k: v for k, v in tile.items()
                             if k not in ("children", "content", "contents", "implicitTiling")})
        _drop_ext(out, _IMPLICIT_EXT)
        _drop_ext(out, _MULTI_EXT)
        sub = self.load_subtree(imp, base_url, 0, 0, 0, 0)
        node = self.implicit_tile(imp, sub, (0, 0, 0, 0), 0, 0, 0, 0, world, base_url,
                                  out_dir, seen, root=True)
        out.update(node)
        return out

    def implicit_tile(self, imp: _Implicit, sub: _Subtree, s0, level, x, y, z, world,
                      base_url, out_dir, seen, root=False) -> dict:
        """An available implicit tile inside the extent → explicit tile dict
        (only content / children for the root, whose own fields are kept)."""
        self.check_cancel()
        self.kept += 1
        sl, sx, sy, sz = s0
        rl = level - sl
        lx, ly, lz = x - (sx << rl), y - (sy << rl), z - (sz << rl)
        idx = imp.index(rl, lx, ly, lz)
        ge = imp.ge / (1 << level)
        out = {} if root else {"boundingVolume": imp.volume(level, x, y, z), "geometricError": ge}
        contents = []
        for i, tmpl in enumerate(imp.contents):
            if i < len(sub.content) and sub.content[i](idx):
                ct = {k: v for k, v in tmpl.items() if k not in ("boundingVolume", "metadata")}
                uri = _expand(tmpl.get("uri") or tmpl.get("url") or "", level, x, y, z)
                contents.append(self.content(ct, uri, world, base_url, out_dir, seen))
        if contents:
            if imp.contents_field == "content":
                out["content"] = contents[0]
            elif imp.contents_field == "contents":
                out["contents"] = contents
            else:
                out.setdefault("extensions", {})[_MULTI_EXT] = {"content": contents}
        if level + 1 >= imp.levels:
            return out
        stop = self.min_ge > 0.0 and ge <= self.min_ge
        children = []
        for c in range(imp.n):
            cl = level + 1
            cx, cy = 2 * x + (c & 1), 2 * y + ((c >> 1) & 1)
            cz = 2 * z + ((c >> 2) & 1) if imp.dims == 3 else 0
            if rl + 1 < imp.sub_levels:
                if not sub.tile(imp.index(rl + 1, 2 * lx + (c & 1), 2 * ly + ((c >> 1) & 1),
                                          (2 * lz + ((c >> 2) & 1)) if imp.dims == 3 else 0)):
                    continue
                csub, cs0 = sub, s0
            else:
                m = _morton(2 * lx + (c & 1), 2 * ly + ((c >> 1) & 1),
                            (2 * lz + ((c >> 2) & 1)) if imp.dims == 3 else 0, imp.dims)
                if not sub.child(m):
                    continue
                csub, cs0 = None, (cl, cx, cy, cz)
            if stop or self.missed(imp.volume(cl, cx, cy, cz), world):
                self.dropped += 1
                continue
            if csub is None:                    # read the child subtree only now
                csub = self.load_subtree(imp, base_url, cl, cx, cy, cz)
                if not csub.tile(0):
                    continue
            children.append(self.implicit_tile(imp, csub, cs0, cl, cx, cy, cz, world,
                                               base_url, out_dir, seen))
        if children:
            out["children"] = children
        return out

    # downloads ----------------------------------------------------------------
    def download_all(self) -> Tuple[int, int, int]:
        """→ (files, bytes, skipped_existing)."""
        pending = dict(self.jobs)
        done_rels = set()
        total = [len(pending)]
        done = [0]
        nbytes = [0]
        skipped = [0]
        failures: List[str] = []
        stop = threading.Event()

        def one(rel: str, src: str) -> List[Tuple[str, str]]:
            if stop.is_set():
                return []
            path = os.path.join(self.dest, *rel.split("/"))
            extra: List[Tuple[str, str]] = []
            # a .gltf is re-read every time: it lists the buffers / images to copy
            if os.path.isfile(path) and os.path.getsize(path) > 0 \
                    and not rel.lower().endswith(".gltf"):
                with self.lock:
                    skipped[0] += 1
                    nbytes[0] += os.path.getsize(path)
            else:
                data = self.fetch(src)
                if rel.lower().endswith(".gltf"):
                    data, extra = self.rewrite_gltf(data, src, rel)
                os.makedirs(os.path.dirname(path), exist_ok=True)
                tmp = path + ".part"
                with open(tmp, "wb") as f:
                    f.write(data)
                os.replace(tmp, path)
                with self.lock:
                    nbytes[0] += len(data)
            return extra

        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            futures = {}

            def submit(rel, src):
                if rel in done_rels or rel in [r for r, _ in futures.values()]:
                    return
                futures[pool.submit(one, rel, src)] = (rel, src)

            for rel, src in pending.items():
                submit(rel, src)
            try:
                while futures:
                    if self.cancel():
                        stop.set()
                        for f in futures:
                            f.cancel()
                        raise ExportCancelled()
                    finished, _ = wait(list(futures), timeout=0.2, return_when=FIRST_COMPLETED)
                    for f in finished:
                        rel, src = futures.pop(f)
                        done_rels.add(rel)
                        try:
                            extra = f.result()
                        except ExportError as e:
                            failures.append(str(e))
                            extra = []
                        for x_rel, x_src in extra:
                            if x_rel not in done_rels:
                                total[0] += 1
                                submit(x_rel, x_src)
                        done[0] += 1
                        self.progress(done[0], total[0], posixpath.basename(rel))
            finally:
                stop.set()
        if failures:
            raise ExportError(f"{len(failures)} file(s) could not be copied "
                              f"(re-run to resume): {failures[0]}")
        return len(done_rels), nbytes[0], skipped[0]

    def rewrite_gltf(self, data: bytes, src: str, rel: str):
        """Point a .gltf's external buffers / images at their copies (query
        strings dropped) → (bytes, [(rel, url)])."""
        try:
            doc = json.loads(data.decode("utf-8-sig"))
        except ValueError:
            return data, []
        deps = []
        base_dir = posixpath.dirname(rel)
        for key in ("buffers", "images"):
            for item in doc.get(key) or []:
                uri = item.get("uri")
                if not uri or uri.startswith("data:"):
                    continue
                d_url = _normalise(_resolve_uri(uri, src))
                d_rel = posixpath.normpath(posixpath.join(base_dir, unquote(uri.split("?")[0])))
                if d_rel.startswith("..") or ":" in d_rel or d_rel.startswith("/"):
                    d_rel = self.out_rel(d_url)
                item["uri"] = quote(posixpath.relpath(d_rel, base_dir or "."), safe="/")
                deps.append((d_rel, d_url))
        return json.dumps(_scrub(doc, self.secrets)).encode("utf-8"), deps


def _drop_ext(tile: dict, name: str) -> None:
    ext = tile.get("extensions")
    if isinstance(ext, dict) and name in ext:
        del ext[name]
        if not ext:
            del tile["extensions"]


def min_geometric_error_or_zero(v) -> float:
    try:
        return max(0.0, float(v or 0.0))
    except (TypeError, ValueError):
        return 0.0


def export_tileset(url: str, dest_dir: str, *, extent=None, min_geometric_error: float = 0.0,
                   headers: dict | None = None, ion_token: str = "", workers: int = 8,
                   progress: Optional[Callable[[int, int, str], None]] = None,
                   cancel: Optional[Callable[[], bool]] = None) -> dict:
    """Copy ``url`` (and what it references) into ``dest_dir``; see module doc.

    ``url`` can be ``ion://<id>`` / ``<id>`` with ``ion_token`` (the ion
    access token; the asset's own bearer token is only sent to the asset
    host).  ``headers`` go with every request.

    Returns dict(tileset, tiles_kept, tiles_dropped, files, bytes,
    skipped_existing, subtrees).  Raises ExportError / ExportCancelled."""
    if not url or not url.strip():
        raise ExportError("No tileset URL")
    asset_id = _ion_asset_id(url)
    token = (ion_token or "").strip()
    scoped: dict = {}
    refresh = None
    secrets = [token]
    if asset_id is not None:
        resolved, scoped = _resolve_ion(asset_id, token)
        secrets += [v.split(" ", 1)[-1] for v in scoped.values()]

        def refresh():
            return _resolve_ion(asset_id, token)[1]
        src = _check_source(resolved)
    else:
        src = _check_source(url)
    # secret query values of the source (key, access_token) never land on disk
    secrets += [v for k, v in parse_qsl(urlsplit(src).query) if k.lower() in _SECRET_PARAMS]
    if extent is not None:
        extent = {"center": tuple(float(x) for x in extent["center"]),
                  "half_axes": [tuple(float(x) for x in a) for a in extent["half_axes"]]}
    ex = _Exporter(src, dest_dir, extent, min_geometric_error, headers, workers,
                   progress, cancel, scoped_headers=scoped, secrets=secrets, refresh=refresh)
    os.makedirs(ex.dest, exist_ok=True)
    ex.json_rels[_strip(src)] = "tileset.json"
    ex.export_json(src, "tileset.json", mat_identity(), frozenset())
    files, nbytes, skipped = ex.download_all()
    files += len(ex.json_rels)
    nbytes += ex.json_bytes
    sp = urlsplit(src)
    source = {
        "scheme": sp.scheme,
        "host": sp.hostname or "",
        "name": _scrub_str(unquote(posixpath.basename(sp.path)), ex.secrets),
    }
    if asset_id is not None:
        source["ion_asset_id"] = asset_id
    meta = {
        "source": source,
        "date": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "extent": ({"center": list(extent["center"]),
                    "half_axes": [list(a) for a in extent["half_axes"]]}
                   if extent is not None else None),
        "min_geometric_error": ex.min_ge,
        "tiles_kept": ex.kept,
        "tiles_dropped": ex.dropped,
        "files": files,
        "bytes": nbytes,
    }
    with open(os.path.join(ex.dest, "export.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    return {
        "tileset": os.path.join(ex.dest, "tileset.json"),
        "tiles_kept": ex.kept,
        "tiles_dropped": ex.dropped,
        "files": files,
        "bytes": nbytes,
        "skipped_existing": skipped,
        "subtrees": ex.subtrees,
    }
