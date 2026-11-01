"""Copying a tileset into a folder, with cropping (io/tileset_export.py)."""
import gzip
import json
import os

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


def test_implicit_tiling_raises(tmp_path):
    d = tmp_path / "src"
    ts = {"asset": {"version": "1.1"}, "geometricError": 1,
          "root": {"boundingVolume": _box(0, 0, 0, 1), "geometricError": 1,
                   "content": {"uri": "{level}/{x}/{y}.glb"},
                   "implicitTiling": {"subdivisionScheme": "QUADTREE", "subtreeLevels": 2,
                                      "availableLevels": 2, "subtrees": {"uri": "s.subtree"}}}}
    _write(str(d / "tileset.json"), json.dumps(ts).encode())
    with pytest.raises(te.ExportError, match="Implicit"):
        te.export_tileset(str(d / "tileset.json"), str(tmp_path / "out"))


@pytest.mark.parametrize("url", ["https://tile.googleapis.com/v1/3dtiles/root.json?key=K",
                                 "ion://96188", "96188"])
def test_refused_sources(url, tmp_path):
    with pytest.raises(te.ExportError):
        te.export_tileset(url, str(tmp_path / "out"))


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
