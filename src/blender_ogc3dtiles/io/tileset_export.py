"""
Copy a 3D Tiles tileset to a local folder, optionally cropped.

``export_tileset(url, dest_dir, extent=..., min_geometric_error=...)`` walks
the tileset (explicit tiling, external tilesets followed recursively),
keeps the tiles whose bounding volume intersects ``extent`` (an oriented box
in ECEF) and stops descending below ``min_geometric_error``, then downloads
the content of the kept tiles with a thread pool and writes rewritten
tileset JSONs whose content URIs are relative paths into the copy.

The source can be http(s) (the query string may carry an access token), a
``file:`` URL or a plain local / UNC path.  Nothing written to ``dest_dir``
carries the source's query string or path: saved file names and JSON URIs are
relative to the root tileset's directory (files outside it go to
``ext/<hash>/<name>``), and ``export.json`` only records the host and the
root file name (share links can carry their token in the path).

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
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from typing import Callable, Dict, List, Optional, Tuple
from urllib.parse import quote, unquote, urlsplit, urlunsplit

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
_RESERVED = {"tileset.json", "export.json"}
_BAD_CHARS = re.compile(r'[<>:"|?*\x00-\x1f]')


class ExportCancelled(Exception):
    """The caller's ``cancel()`` returned True."""


class ExportError(Exception):
    """The tileset cannot be exported (unsupported source or content)."""


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


def _check_source(url: str) -> str:
    u = url.strip()
    if not u:
        raise ExportError("No tileset URL")
    if u.startswith("ion://") or u.isdigit():
        raise ExportError("Cesium ion assets cannot be copied: copy only plain tileset URLs")
    if re.match(r"^[A-Za-z]:[\\/]", u) or u.startswith("\\\\") or u.startswith("//") \
            or (not re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", u)):
        u = _path_to_file_url(u)
    scheme = urlsplit(u).scheme.lower()
    if scheme not in ("http", "https", "file"):
        raise ExportError(f"Unsupported URL scheme '{scheme}'")
    host = (urlsplit(u).hostname or "").lower()
    if host == "tile.googleapis.com" or host.endswith(".tile.googleapis.com"):
        raise ExportError("Google Map Tiles terms forbid storing tiles offline")
    return _normalise(u)


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
        data = None
        for attempt in range(RETRIES + 1):
            try:
                req = urllib.request.Request(url, headers=dict(headers or {}))
                with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
                    data = resp.read()
                break
            except urllib.error.HTTPError as e:
                last = e
                if e.code not in (408, 425, 429, 500, 502, 503, 504):
                    break
            except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
                last = e
            if attempt < RETRIES:
                time.sleep(0.5 * (2 ** attempt))
        if data is None:
            name = posixpath.basename(urlsplit(url).path)
            raise ExportError(f"Download failed for {name}: {last}")
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
        "3DTILES_implicit_tiling" in (tile.get("extensions") or {})


# ── the export ───────────────────────────────────────────────────────────────

class _Exporter:
    def __init__(self, url, dest_dir, extent, min_ge, headers, workers, progress, cancel):
        self.root_url = url
        self.dest = os.path.abspath(dest_dir)
        self.extent = extent
        self.min_ge = float(min_geometric_error_or_zero(min_ge))
        self.headers = headers or {}
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
        if rel in _RESERVED:
            rel = "_" + rel
        return rel

    def check_cancel(self):
        if self.cancel():
            raise ExportCancelled()

    # tileset walk -----------------------------------------------------------
    def read_json(self, url: str) -> dict:
        self.check_cancel()
        self.progress(0, 0, f"reading {posixpath.basename(urlsplit(url).path)}")
        data = _fetch(url, self.headers)
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
                        if k not in ("children", "content", "contents")}
        out["root"] = new_root
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

    def walk(self, tile: dict, parent_world, base_url: str, out_dir: str, seen) -> Optional[dict]:
        self.check_cancel()
        if _is_implicit(tile):
            raise ExportError("Implicit tiling is not supported yet: this tileset cannot be copied")
        world = parent_world
        if tile.get("transform"):
            world = mat_mul(world, mat_from_column_major(tile["transform"]))
        if self.extent is not None:
            c, r = _sphere(tile.get("boundingVolume") or {}, world)
            if not sphere_intersects_obb(c, r, self.extent):
                self.dropped += _count(tile)
                return None
        out = {k: v for k, v in tile.items() if k not in ("children", "content", "contents")}
        out = copy.deepcopy(out)
        self.kept += 1
        contents = []
        if isinstance(tile.get("content"), dict):
            contents.append(("content", None, tile["content"]))
        for i, ct in enumerate(tile.get("contents") or []):
            contents.append(("contents", i, ct))
        new_contents = []
        for field_name, _, ct in contents:
            uri = ct.get("uri") or ct.get("url")
            nc = {k: v for k, v in copy.deepcopy(ct).items() if k != "url"}
            if not uri or uri.startswith("data:"):
                new_contents.append((field_name, nc))
                continue
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
            new_contents.append((field_name, nc))
        for field_name, nc in new_contents:
            if field_name == "content":
                out["content"] = nc
            else:
                out.setdefault("contents", []).append(nc)
        children = tile.get("children") or []
        if children and self.min_ge > 0.0 and float(tile.get("geometricError", 0.0)) <= self.min_ge:
            self.dropped += sum(_count(ch) for ch in children)
        elif children:
            kept = [k for k in (self.walk(ch, world, base_url, out_dir, seen) for ch in children)
                    if k is not None]
            if kept:
                out["children"] = kept
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
            if os.path.isfile(path) and os.path.getsize(path) > 0                     and not rel.lower().endswith(".gltf"):
                with self.lock:
                    skipped[0] += 1
                    nbytes[0] += os.path.getsize(path)
            else:
                data = _fetch(src, self.headers)
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
        return json.dumps(doc).encode("utf-8"), deps


def min_geometric_error_or_zero(v) -> float:
    try:
        return max(0.0, float(v or 0.0))
    except (TypeError, ValueError):
        return 0.0


def export_tileset(url: str, dest_dir: str, *, extent=None, min_geometric_error: float = 0.0,
                   headers: dict | None = None, workers: int = 8,
                   progress: Optional[Callable[[int, int, str], None]] = None,
                   cancel: Optional[Callable[[], bool]] = None) -> dict:
    """Copy ``url`` (and what it references) into ``dest_dir``; see module doc.

    Returns dict(tileset, tiles_kept, tiles_dropped, files, bytes,
    skipped_existing).  Raises ExportError / ExportCancelled."""
    src = _check_source(url)
    if extent is not None:
        extent = {"center": tuple(float(x) for x in extent["center"]),
                  "half_axes": [tuple(float(x) for x in a) for a in extent["half_axes"]]}
    ex = _Exporter(src, dest_dir, extent, min_geometric_error, headers, workers,
                   progress, cancel)
    os.makedirs(ex.dest, exist_ok=True)
    ex.json_rels[_strip(src)] = "tileset.json"
    ex.export_json(src, "tileset.json", mat_identity(), frozenset())
    files, nbytes, skipped = ex.download_all()
    files += len(ex.json_rels)
    nbytes += ex.json_bytes
    sp = urlsplit(src)
    meta = {
        "source": {
            "scheme": sp.scheme,
            "host": sp.hostname or "",
            "name": unquote(posixpath.basename(sp.path)),
        },
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
    }
