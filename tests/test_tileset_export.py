"""Copying a tileset into a folder, with cropping (io/tileset_export.py)."""
import gzip
import http.server
import json
import math
import os
import struct
import threading
from urllib.parse import parse_qs, urlsplit

import pytest

from blender_ogc3dtiles.io import tileset_export as te


def _box(cx, cy, cz, h):
    return {"box": [cx, cy, cz, h, 0, 0, 0, h, 0, 0, 0, h]}


def _write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


@pytest.fixture
def src(tmp_path):
    """root (ge 100, transform +1000 x) → west (x=-50) / east (x=+50) children;
    east → leaf; west → external tileset sub/ext.json with one gzipped tile."""
    d = tmp_path / "src"
    tileset = {
        "asset": {"version": "1.1"},
        "geometricError": 200,
        "root": {
            "boundingVolume": _box(0, 0, 0, 100),
            "geometricError": 100,
            "refine": "REPLACE",
            "transform": [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 1000, 0, 0, 1],
            "content": {"uri": "root.b3dm"},
            "children": [
                {"boundingVolume": _box(-50, 0, 0, 40), "geometricError": 50,
                 "content": {"uri": "sub/ext.json"}},
                {"boundingVolume": _box(50, 0, 0, 40), "geometricError": 50,
                 "content": {"uri": "east.glb"},
                 "children": [
                     {"boundingVolume": _box(60, 0, 0, 10), "geometricError": 0,
                      "content": {"uri": "tiles/east_leaf.b3dm"}},
                 ]},
            ],
        },
    }
    ext = {
        "asset": {"version": "1.1"},
        "geometricError": 50,
        "root": {"boundingVolume": _box(-50, 0, 0, 40), "geometricError": 20,
                 "content": {"uri": "west.b3dm"},
                 "children": [{"boundingVolume": _box(-60, 0, 0, 10), "geometricError": 0,
                               "content": {"uri": "../tiles/west_leaf.b3dm"}}]},
    }
    _write(str(d / "tileset.json"), json.dumps(tileset).encode())
    _write(str(d / "sub" / "ext.json"), json.dumps(ext).encode())
    _write(str(d / "root.b3dm"), b"b3dm-root")
    _write(str(d / "east.glb"), b"glTF-east")
    _write(str(d / "tiles" / "east_leaf.b3dm"), b"b3dm-east-leaf")
    _write(str(d / "sub" / "west.b3dm"), gzip.compress(b"b3dm-west"))
    _write(str(d / "tiles" / "west_leaf.b3dm"), b"b3dm-west-leaf")
    return d


def _files(root):
    out = set()
    for dp, _, fs in os.walk(root):
        for f in fs:
            out.add(os.path.relpath(os.path.join(dp, f), root).replace(os.sep, "/"))
    return out


def test_full_copy(src, tmp_path):
    dest = tmp_path / "out"
    r = te.export_tileset(str(src / "tileset.json"), str(dest))
    assert r["tiles_kept"] == 6 and r["tiles_dropped"] == 0
    assert _files(dest) == {"tileset.json", "export.json", "root.b3dm", "east.glb",
                            "tiles/east_leaf.b3dm", "sub/ext.json", "sub/west.b3dm",
                            "tiles/west_leaf.b3dm"}
    # gzip decoded on the way
    assert (dest / "sub" / "west.b3dm").read_bytes() == b"b3dm-west"
    # external tileset followed and its relative uris kept valid
    ext = json.loads((dest / "sub" / "ext.json").read_text())
    assert ext["root"]["children"][0]["content"]["uri"] == "../tiles/west_leaf.b3dm"
    root = json.loads((dest / "tileset.json").read_text())
    assert root["root"]["children"][0]["content"]["uri"] == "sub/ext.json"
    assert r["files"] == 8 - 1          # export.json is not counted
    assert os.path.isfile(r["tileset"])


def test_file_url_source(src, tmp_path):
    url = "file:///" + str(src / "tileset.json").replace("\\", "/").lstrip("/")
    r = te.export_tileset(url, str(tmp_path / "out"))
    assert r["tiles_kept"] == 6


def test_crop_extent_drops_west(src, tmp_path):
    # extent around the east half (world x = 1000 + 30..1000 + 90)
    extent = {"center": (1060, 0, 0), "half_axes": [(30, 0, 0), (0, 30, 0), (0, 0, 30)]}
    dest = tmp_path / "out"
    r = te.export_tileset(str(src / "tileset.json"), str(dest), extent=extent)
    files = _files(dest)
    assert "sub/ext.json" not in files and "tiles/west_leaf.b3dm" not in files
    assert "tiles/east_leaf.b3dm" in files and "root.b3dm" in files
    assert r["tiles_dropped"] == 1          # the west child (its external tileset is never read)
    root = json.loads((dest / "tileset.json").read_text())
    assert len(root["root"]["children"]) == 1


def test_crop_applies_inside_external(src, tmp_path):
    # small box on the west leaf: the west child, the external root and its leaf
    # intersect it, the east child does not
    extent = {"center": (940, 0, 0), "half_axes": [(5, 0, 0), (0, 5, 0), (0, 0, 5)]}
    dest = tmp_path / "out"
    te.export_tileset(str(src / "tileset.json"), str(dest), extent=extent)
    files = _files(dest)
    assert "tiles/west_leaf.b3dm" in files and "east.glb" not in files


def test_min_geometric_error_drops_children(src, tmp_path):
    dest = tmp_path / "out"
    r = te.export_tileset(str(src / "tileset.json"), str(dest), min_geometric_error=50)
    files = _files(dest)
    assert "tiles/east_leaf.b3dm" not in files
    # the external tileset is still followed (its root is the west content) but
    # its root (ge 20 <= 50) keeps no children
    assert "sub/west.b3dm" in files and "tiles/west_leaf.b3dm" not in files
    assert r["tiles_dropped"] == 2


def test_query_string_never_written(tmp_path, monkeypatch):
    tileset = {"asset": {"version": "1.0"}, "geometricError": 10,
               "root": {"boundingVolume": _box(0, 0, 0, 1), "geometricError": 0,
                        "content": {"uri": "a.b3dm?v=2"}}}
    calls = []

    def fake_fetch(url, headers):
        calls.append(url)
        if url.split("?")[0].endswith("tileset.json"):
            return json.dumps(tileset).encode()
        return b"b3dm"

    monkeypatch.setattr(te, "_fetch", fake_fetch)
    dest = tmp_path / "out"
    te.export_tileset("https://example.com/s/SECRET/t/tileset.json?key=TOKEN", str(dest))
    assert any("key=TOKEN" in c for c in calls)         # the token is used to fetch
    for f in _files(dest):
        text = (dest / f).read_bytes()
        assert b"TOKEN" not in text and b"SECRET" not in text, f
        assert "?" not in f
    root = json.loads((dest / "tileset.json").read_text())
    assert root["root"]["content"]["uri"] == "a.b3dm"


def test_resume_skips_existing(src, tmp_path):
    dest = tmp_path / "out"
    te.export_tileset(str(src / "tileset.json"), str(dest))
    r = te.export_tileset(str(src / "tileset.json"), str(dest))
    assert r["skipped_existing"] == 5


def test_cancel(src, tmp_path):
    with pytest.raises(te.ExportCancelled):
        te.export_tileset(str(src / "tileset.json"), str(tmp_path / "out"), cancel=lambda: True)


def test_cancel_during_downloads(src, tmp_path):
    seen = []

    def progress(done, total, msg):
        seen.append(done)

    def cancel():
        # let the walk finish, stop once the first download is done
        return bool(seen) and seen[-1] >= 1

    with pytest.raises(te.ExportCancelled):
        te.export_tileset(str(src / "tileset.json"), str(tmp_path / "out"), workers=1,
                          progress=progress, cancel=cancel)


def test_paths_and_file_urls():
    assert te.file_url_to_path("file:///C:/a/b.json") == "C:/a/b.json"
    assert te.file_url_to_path("file:////nas/share/a.json") == "//nas/share/a.json"
    assert te.file_url_to_path("file://nas/share/a.json") == "//nas/share/a.json"
    assert te._check_source(r"\\nas\share\t\tileset.json") == "file:////nas/share/t/tileset.json"
    assert te._check_source(r"C:\t\tileset.json") == "file:///C:/t/tileset.json"


def test_sphere_vs_obb():
    ext = {"center": (0, 0, 0), "half_axes": [(10, 0, 0), (0, 10, 0), (0, 0, 10)]}
    assert te.sphere_intersects_obb((15, 0, 0), 6, ext)
    assert not te.sphere_intersects_obb((15, 0, 0), 4, ext)
    assert not te.sphere_intersects_obb((15, 15, 0), 7, ext)     # corner distance 7.07


# ── implicit tiling ──────────────────────────────────────────────────────────

def _subtree_bin(js, binary=b""):
    """Binary .subtree: magic, version, JSON / binary lengths, chunks padded to 8."""
    head = json.dumps(js).encode()
    head += b" " * (-len(head) % 8)
    binary += b"\0" * (-len(binary) % 8)
    return b"subt" + struct.pack("<IQQ", 1, len(head), len(binary)) + head + binary


def _quadtree_src(tmp_path, version="1.1"):
    """Box quadtree, subtreeLevels 2, 4 levels.  Root subtree: root + level-1
    (0,0) and (1,1) (content on those two only), child subtrees under them at
    level 2 (0,0) and (3,3), each fully available (constant)."""
    d = tmp_path / "src"
    impl = {"subdivisionScheme": "QUADTREE", "subtreeLevels": 2,
            "subtrees": {"uri": "subtrees/{level}/{x}/{y}.subtree"}}
    if version == "1.1":
        impl["availableLevels"] = 4
        root = {"boundingVolume": _box(0, 0, 0, 100), "geometricError": 100, "refine": "REPLACE",
                "content": {"uri": "content/{level}/{x}/{y}.glb"}, "implicitTiling": impl}
        ts = {"asset": {"version": "1.1"}, "geometricError": 200, "root": root}
    else:
        impl["maximumLevel"] = 3
        root = {"boundingVolume": _box(0, 0, 0, 100), "geometricError": 100, "refine": "REPLACE",
                "content": {"uri": "content/{level}/{x}/{y}.glb"},
                "extensions": {"3DTILES_implicit_tiling": impl}}
        ts = {"asset": {"version": "1.0"}, "geometricError": 200, "root": root,
              "extensionsUsed": ["3DTILES_implicit_tiling"],
              "extensionsRequired": ["3DTILES_implicit_tiling"]}
    _write(str(d / "tileset.json"), json.dumps(ts).encode())
    view = "bitstream" if version == "1.1" else "bufferView"
    # bits: tiles 0 (root), 1 (L1 0,0), 4 (L1 1,1); content 1, 4; child subtrees 0, 15
    binary = bytes([0x13, 0x12, 0x01, 0x80])
    js = {"buffers": [{"byteLength": len(binary)}],
          "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": 1},
                          {"buffer": 0, "byteOffset": 1, "byteLength": 1},
                          {"buffer": 0, "byteOffset": 2, "byteLength": 2}],
          "tileAvailability": {view: 0},
          "contentAvailability": [{view: 1}] if version == "1.1" else {view: 1},
          "childSubtreeAvailability": {view: 2}}
    _write(str(d / "subtrees/0/0/0.subtree"), _subtree_bin(js, binary))
    full = {"tileAvailability": {"constant": 1},
            "contentAvailability": [{"constant": 1}] if version == "1.1" else {"constant": 1},
            "childSubtreeAvailability": {"constant": 0}}
    for x, y in ((0, 0), (3, 3)):
        _write(str(d / f"subtrees/2/{x}/{y}.subtree"), _subtree_bin(full))
    files = ["content/1/0/0.glb", "content/1/1/1.glb"]
    for x0, y0 in ((0, 0), (3, 3)):
        files.append(f"content/2/{x0}/{y0}.glb")
        files += [f"content/3/{2 * x0 + dx}/{2 * y0 + dy}.glb" for dy in (0, 1) for dx in (0, 1)]
    for f in files:
        _write(str(d / f), f.encode())
    return d, files


def _spy(monkeypatch):
    calls = []
    real = te._fetch

    def fetch(url, headers):
        calls.append(url)
        return real(url, headers)

    monkeypatch.setattr(te, "_fetch", fetch)
    return calls


@pytest.mark.parametrize("version", ["1.1", "1.0"])
def test_implicit_quadtree_full(tmp_path, version):
    d, files = _quadtree_src(tmp_path, version)
    dest = tmp_path / "out"
    r = te.export_tileset(str(d / "tileset.json"), str(dest))
    assert r["tiles_kept"] == 13 and r["subtrees"] == 3
    assert _files(dest) == set(files) | {"tileset.json", "export.json"}
    out = json.loads((dest / "tileset.json").read_text())
    root = out["root"]
    assert "implicitTiling" not in root and "extensions" not in root
    assert "extensionsUsed" not in out and "extensionsRequired" not in out
    assert "content" not in root                      # root content not available
    assert root["refine"] == "REPLACE" and root["geometricError"] == 100
    a, b = root["children"]
    assert a["content"]["uri"] == "content/1/0/0.glb"
    assert a["boundingVolume"]["box"] == [-50, -50, 0, 50, 0, 0, 0, 50, 0, 0, 0, 100]
    assert a["geometricError"] == 50
    assert b["boundingVolume"]["box"][:3] == [50, 50, 0]
    l2 = b["children"][0]
    assert l2["content"]["uri"] == "content/2/3/3.glb" and l2["geometricError"] == 25
    assert l2["boundingVolume"]["box"][:6] == [75, 75, 0, 25, 0, 0]
    assert [c["content"]["uri"] for c in l2["children"]] == [
        "content/3/6/6.glb", "content/3/7/6.glb", "content/3/6/7.glb", "content/3/7/7.glb"]
    assert l2["children"][3]["boundingVolume"]["box"][:4] == [87.5, 87.5, 0, 12.5]


def test_implicit_crop_skips_subtrees(tmp_path, monkeypatch):
    d, _ = _quadtree_src(tmp_path)
    calls = _spy(monkeypatch)
    extent = {"center": (60, 60, 0), "half_axes": [(5, 0, 0), (0, 5, 0), (0, 0, 5)]}
    dest = tmp_path / "out"
    te.export_tileset(str(d / "tileset.json"), str(dest), extent=extent)
    assert not any("subtrees/2/0/0" in c for c in calls)
    assert any("subtrees/2/3/3" in c for c in calls)
    files = _files(dest)
    assert "content/1/0/0.glb" not in files and "content/3/7/7.glb" in files


def test_implicit_min_geometric_error(tmp_path, monkeypatch):
    d, _ = _quadtree_src(tmp_path)
    calls = _spy(monkeypatch)
    dest = tmp_path / "out"
    r = te.export_tileset(str(d / "tileset.json"), str(dest), min_geometric_error=50)
    assert r["subtrees"] == 1 and not any("subtrees/2/" in c for c in calls)
    assert _files(dest) == {"tileset.json", "export.json",
                            "content/1/0/0.glb", "content/1/1/1.glb"}
    assert r["tiles_dropped"] == 2


def test_implicit_octree_json_subtree_external_buffer(tmp_path):
    """Region octree, JSON subtree with an external .bin, two contents."""
    d = tmp_path / "src"
    region = [math.radians(2), math.radians(48), math.radians(2.01), math.radians(48.01), 0, 80]
    ts = {"asset": {"version": "1.1"}, "geometricError": 100,
          "root": {"boundingVolume": {"region": region}, "geometricError": 40, "refine": "ADD",
                   "contents": [{"uri": "a/{level}/{x}/{y}/{z}.glb"},
                                {"uri": "b/{level}/{x}/{y}/{z}.pnts", "group": 0}],
                   "implicitTiling": {"subdivisionScheme": "OCTREE", "subtreeLevels": 2,
                                      "availableLevels": 2,
                                      "subtrees": {"uri": "st/{level}.{x}.{y}.{z}.json"}}}}
    _write(str(d / "tileset.json"), json.dumps(ts).encode())
    # tiles: root (bit 0), octant 0 (bit 1), octant 7 (bit 8); content b: root only
    binary = bytes([0x03, 0x01, 0, 0, 0, 0, 0, 0, 0x01, 0x00])
    st = {"buffers": [{"uri": "../bin/avail.bin", "byteLength": len(binary)}],
          "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": 2},
                          {"buffer": 0, "byteOffset": 8, "byteLength": 2}],
          "tileAvailability": {"bitstream": 0, "availableCount": 3},
          "contentAvailability": [{"constant": 1}, {"bitstream": 1}],
          "childSubtreeAvailability": {"constant": 0}}
    _write(str(d / "st" / "0.0.0.0.json"), json.dumps(st).encode())
    _write(str(d / "bin" / "avail.bin"), binary)
    names = ["a/0/0/0/0.glb", "a/1/0/0/0.glb", "a/1/1/1/1.glb", "b/0/0/0/0.pnts"]
    for f in names:
        _write(str(d / f), b"x")
    dest = tmp_path / "out"
    r = te.export_tileset(str(d / "tileset.json"), str(dest))
    assert r["tiles_kept"] == 3
    assert _files(dest) == set(names) | {"tileset.json", "export.json"}
    root = json.loads((dest / "tileset.json").read_text())["root"]
    assert [c["uri"] for c in root["contents"]] == ["a/0/0/0/0.glb", "b/0/0/0/0.pnts"]
    assert root["contents"][1]["group"] == 0
    c0, c7 = root["children"]
    assert [c["uri"] for c in c7["contents"]] == ["a/1/1/1/1.glb"]
    w, s, e, n, h0, h1 = region
    assert c7["boundingVolume"]["region"] == pytest.approx(
        [(w + e) / 2, (s + n) / 2, e, n, 40, 80])
    assert c0["boundingVolume"]["region"] == pytest.approx(
        [w, s, (w + e) / 2, (s + n) / 2, 0, 40])
    assert c0["geometricError"] == 20


def test_implicit_helpers():
    assert te._morton(0, 0, 0, 2) == 0
    assert te._morton(1, 0, 0, 2) == 1 and te._morton(0, 1, 0, 2) == 2
    assert te._morton(3, 3, 0, 2) == 15
    assert te._morton(1, 1, 1, 3) == 7 and te._morton(2, 0, 0, 3) == 8
    imp = te._Implicit({"boundingVolume": _box(0, 0, 0, 8), "geometricError": 1,
                        "implicitTiling": {"subdivisionScheme": "OCTREE", "subtreeLevels": 3,
                                           "availableLevels": 3, "subtrees": {"uri": "s"}}})
    assert imp.index(0, 0, 0, 0) == 0 and imp.index(1, 0, 0, 0) == 1
    assert imp.index(2, 0, 0, 0) == 9
    assert imp.volume(1, 1, 1, 1)["box"] == [4, 4, 4, 4, 0, 0, 0, 4, 0, 0, 0, 4]
    av = te._Avail(bits=bytes([0b10000001]))
    assert av(0) and not av(1) and av(7) and not av(8)


# ── remote sources (local mock server) ───────────────────────────────────────

class _Server:
    """http.server on 127.0.0.1; ``handler(path, query, headers)`` → (status, bytes)."""

    def __init__(self, handler):
        self.requests = []
        outer = self

        class H(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                p = urlsplit(self.path)
                q = {k: v[0] for k, v in parse_qs(p.query).items()}
                outer.requests.append((p.path, q, dict(self.headers)))
                status, body = handler(p.path, q, self.headers)
                self.send_response(status)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *a):
                pass

        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


GKEY = "AIzaFAKEGOOGLEKEY123"


def _google_handler(path, q, headers):
    """Google-like tree: key on every request, session on everything below root."""
    if q.get("key") != GKEY:
        return 403, b"no key"
    base = "/v1/3dtiles/datasets/CgA/files/"
    if path == "/v1/3dtiles/root.json":
        return 200, json.dumps({
            "asset": {"version": "1.0"}, "geometricError": 1000,
            "root": {"boundingVolume": _box(0, 0, 0, 1000), "geometricError": 1000,
                     "refine": "REPLACE",
                     "children": [{"boundingVolume": _box(0, 0, 0, 500), "geometricError": 500,
                                   "content": {"uri": base + "near.json?session=SESS"}}]}}).encode()
    if q.get("session") != "SESS":
        return 403, b"no session"
    if path == base + "near.json":
        return 200, json.dumps({
            "asset": {"version": "1.0"}, "geometricError": 500,
            "root": {"boundingVolume": _box(0, 0, 0, 500), "geometricError": 500,
                     "content": {"uri": "near.glb?session=SESS"},
                     "children": [
                         {"boundingVolume": _box(-400, 0, 0, 50), "geometricError": 50,
                          "content": {"uri": base + "far.json?session=SESS"}},
                         {"boundingVolume": _box(400, 0, 0, 50), "geometricError": 50,
                          "content": {"uri": base + "leaf.glb?session=SESS"}}]}}).encode()
    if path.endswith(".glb"):
        return 200, b"glTF" + path.encode()
    return 404, b""


def test_google_like_query_propagation(tmp_path):
    srv = _Server(_google_handler)
    try:
        extent = {"center": (400, 0, 0), "half_axes": [(20, 0, 0), (0, 20, 0), (0, 0, 20)]}
        dest = tmp_path / "out"
        r = te.export_tileset(f"{srv.base}/v1/3dtiles/root.json?key={GKEY}", str(dest),
                              extent=extent)
        paths = [p for p, _, _ in srv.requests]
        assert all(q.get("key") == GKEY for _, q, _ in srv.requests)
        assert not any(p.endswith("far.json") for p in paths)       # outside the extent
        files = _files(dest)
        assert files == {"tileset.json", "export.json", "datasets/CgA/files/near.json",
                         "datasets/CgA/files/near.glb", "datasets/CgA/files/leaf.glb"}
        for f in files:
            data = (dest / f).read_bytes()
            assert GKEY.encode() not in data and b"key=" not in data, f
        near = json.loads((dest / "datasets/CgA/files/near.json").read_text())
        assert near["root"]["content"]["uri"] == "near.glb"
        assert near["root"]["children"][0]["content"]["uri"] == "leaf.glb"
        meta = json.loads((dest / "export.json").read_text())
        assert meta["source"] == {"scheme": "http", "host": "127.0.0.1", "name": "root.json"}
        assert r["tiles_kept"] == 4
    finally:
        srv.close()


def test_ion_asset(tmp_path, monkeypatch):
    issued = []

    def handler(path, q, headers):
        if path == "/v1/assets/42/endpoint":
            if q.get("access_token") != "IONTOKEN":
                return 401, b""
            issued.append(f"ASSET{len(issued) + 1}")
            return 200, json.dumps({"type": "3DTILES", "url": srv.base + "/a/42/tileset.json?v=3",
                                    "accessToken": issued[-1]}).encode()
        if path == "/v1/assets/43/endpoint":
            return 200, json.dumps({"type": "3DTILES", "externalType": "3DTILES",
                                    "options": {"url": srv.base + "/v1/3dtiles/root.json",
                                                "key": GKEY}}).encode()
        if path.startswith("/v1/3dtiles/"):
            return _google_handler(path, q, headers)
        auth = headers.get("Authorization", "")
        if q.get("v") != "3":
            return 400, b""
        if path == "/a/42/tileset.json" and auth.startswith("Bearer ASSET"):
            return 200, json.dumps({"asset": {"version": "1.0"}, "geometricError": 1,
                                    "root": {"boundingVolume": _box(0, 0, 0, 1),
                                             "geometricError": 0,
                                             "content": {"uri": "t.b3dm"}}}).encode()
        if path == "/a/42/t.b3dm":
            # the first asset token "expired": a new one comes from the endpoint
            return (200, b"b3dm") if auth == "Bearer ASSET2" else (401, b"")
        return 404, b""

    srv = _Server(handler)
    monkeypatch.setattr(te, "ION_API", srv.base)
    try:
        dest = tmp_path / "out"
        r = te.export_tileset("ion://42", str(dest), ion_token="IONTOKEN")
        assert r["tiles_kept"] == 1 and issued == ["ASSET1", "ASSET2"]
        assert (dest / "t.b3dm").read_bytes() == b"b3dm"
        for f in _files(dest):
            data = (dest / f).read_bytes()
            for secret in (b"IONTOKEN", b"ASSET1", b"ASSET2", b"access_token"):
                assert secret not in data, f
        meta = json.loads((dest / "export.json").read_text())
        assert meta["source"]["ion_asset_id"] == 42 and meta["source"]["name"] == "tileset.json"

        # ion asset pointing at an external (Google-like) tileset
        dest2 = tmp_path / "out2"
        extent = {"center": (400, 0, 0), "half_axes": [(20, 0, 0), (0, 20, 0), (0, 0, 20)]}
        te.export_tileset("43", str(dest2), ion_token="IONTOKEN", extent=extent)
        assert "datasets/CgA/files/leaf.glb" in _files(dest2)
        for f in _files(dest2):
            assert GKEY.encode() not in (dest2 / f).read_bytes(), f
    finally:
        srv.close()


def test_ion_needs_token(tmp_path):
    with pytest.raises(te.ExportError, match="token"):
        te.export_tileset("ion://42", str(tmp_path / "out"))


def test_scrub():
    s = te._scrub({"a": ["https://h/x.glb?key=K&session=S"], "b": "has SECRETVALUE in it"},
                  ["SECRETVALUE"])
    assert s == {"a": ["https://h/x.glb?session=S"], "b": "has  in it"}
