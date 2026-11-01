"""Clipping outlines, local / UNC tileset paths, tileset libraries, cache cap."""
import math
import os
import sqlite3
import types

import pytest

from blender_ogc3dtiles import cachectl, clipping, library, paths


# ── clipping ──────────────────────────────────────────────────────────────────

def test_edge_loops_square_and_polyline():
    square = [(0, 1), (1, 2), (2, 3), (3, 0)]
    loops = clipping.edge_loops(square)
    assert len(loops) == 1 and sorted(loops[0]) == [0, 1, 2, 3]
    # open polyline (curve drawn without its closing edge) is closed implicitly
    loops = clipping.edge_loops([(10, 11), (11, 12), (12, 13)])
    assert loops == [[10, 11, 12, 13]]
    # two islands in one object → two polygons
    two = square + [(4, 5), (5, 6), (6, 4)]
    assert sorted(len(lp) for lp in clipping.edge_loops(two)) == [3, 4]


def test_boundary_edges_of_grid():
    # 2 quads sharing edge (1, 4): boundary has 6 edges, the shared one dropped
    faces = [(0, 1, 4, 3), (1, 2, 5, 4)]
    b = clipping.boundary_edges([], faces)
    assert len(b) == 6 and (1, 4) not in b
    loops = clipping.edge_loops(b)
    assert len(loops) == 1 and len(loops[0]) == 6


def test_loops_to_lonlat_around_origin():
    origin = (41.9022, 12.4539, 30.0)
    loop = [(-50, -50, 0), (50, -50, 0), (50, 50, 0), (-50, 50, 0)]
    (poly,) = clipping.loops_to_lonlat([loop], origin)
    lons = [math.degrees(p[0]) for p in poly]
    lats = [math.degrees(p[1]) for p in poly]
    assert abs(sum(lons) / 4 - 12.4539) < 1e-6 and abs(sum(lats) / 4 - 41.9022) < 1e-6
    # 100 m east-west ≈ 0.0012° of longitude at 41.9° N
    assert 0.0011 < max(lons) - min(lons) < 0.0013


def test_clip_specs_modes():
    polys = [[[0, 0], [1, 0], [1, 1]], [[2, 2], [3, 2], [3, 3]]]
    item = types.SimpleNamespace(uid="abc", clip_mode="INSIDE_ANY")
    (s,) = clipping.clip_specs(item, polys)
    assert s["uid"] == "clip_abc_any" and not s["invert"] and s["exclude"] and len(s["polygons"]) == 2
    item.clip_mode = "OUTSIDE"
    (s,) = clipping.clip_specs(item, polys)
    assert s["invert"] and s["exclude"]
    item.clip_mode = "INSIDE_ALL"
    specs = clipping.clip_specs(item, polys)
    assert [x["uid"] for x in specs] == ["clip_abc_all_0", "clip_abc_all_1"]
    assert not any(x["exclude"] for x in specs)
    assert clipping.clip_specs(item, []) == []


# ── paths ─────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("src,url", [
    (r"C:\Data\site\tileset.json", "file:///C:/Data/site/tileset.json"),
    ("C:/Data/my site/tileset.json", "file:///C:/Data/my%20site/tileset.json"),
    (r"\\nas\share$\3d tiles\tileset.json", "file:////nas/share$/3d%20tiles/tileset.json"),
    ("https://example.com/s/tok/tileset.json?x=1", "https://example.com/s/tok/tileset.json?x=1"),
    ("file:///C:/x/tileset.json", "file:///C:/x/tileset.json"),
])
def test_path_to_url(src, url):
    assert paths.path_to_url(src) == url


def test_is_local_path():
    assert paths.is_local_path(r"C:\x\tileset.json")
    assert paths.is_local_path(r"\\nas\share\tileset.json")
    assert not paths.is_local_path("https://a/b.json")
    assert not paths.is_local_path("file:///C:/a.json")
    assert not paths.is_local_path("ion://123")


@pytest.mark.skipif(os.name != "nt", reason="Windows path forms")
def test_url_to_path_roundtrip():
    for p in (r"C:\Data\my site\tileset.json", r"\\nas\share\a b\tileset.json"):
        assert paths.url_to_path(paths.path_to_url(p)) == p


# ── library ───────────────────────────────────────────────────────────────────

def test_library_save_read_replace(tmp_path):
    lib = tmp_path / "team" / "tilesets.json"
    ov = types.SimpleNamespace(name="OSM", kind="URL", url="https://t/{z}/{x}/{y}.png", key="",
                               layer="", style="default", matrix_set="", image_format="image/png",
                               min_level=0, max_level=19, detail_px=4.0, enabled=True, alpha=1.0)
    item = types.SimpleNamespace(name="Site A", kind="TILESET", url="https://h/s/TOKEN/a.json",
                                 ion_asset_id=0, ion_token="", use_own_sse=True, max_sse=2.0,
                                 use_overlays=True, overlays=[ov])
    assert library.save_entry(str(lib), library.entry_from_item(item)) is False
    e = library.entry_from_item(item)
    e["group"] = "Rome"
    library.save_entry(str(lib), e)
    item.max_sse = 8.0
    assert library.save_entry(str(lib), library.entry_from_item(item)) is True   # replaced
    (got,) = library.read(str(lib))
    assert got["max_sse"] == 8.0 and got["group"] == "Rome" and got["overlays"][0]["name"] == "OSM"

    target = types.SimpleNamespace(overlays=[])

    def add_ov(it):
        o = types.SimpleNamespace()
        it.overlays.append(o)
        return o
    library.apply_entry(target, got, add_overlay=add_ov)
    assert target.url == item.url and target.overlays[0].url == ov.url
    rows = library.read_all([str(lib), str(tmp_path / "missing.json")])
    assert len(rows) == 1
    assert library.split_paths(' a.json ; "b c.json";') == ["a.json", "b c.json"]


# ── cache cap ─────────────────────────────────────────────────────────────────

def _make_cache(path, sizes):
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE CacheItemTable(key TEXT PRIMARY KEY NOT NULL, expiryTime DATETIME NOT NULL,"
                " lastAccessedTime DATETIME NOT NULL, responseHeaders TEXT NOT NULL,"
                " responseStatusCode INTEGER NOT NULL, responseData BLOB, requestHeader TEXT NOT NULL,"
                " requestMethod TEXT NOT NULL, requestUrl TEXT NOT NULL)")
    for i, n in enumerate(sizes):
        con.execute("INSERT INTO CacheItemTable VALUES(?,?,?,?,?,?,?,?,?)",
                    (f"k{i}", 0, 1000 + i, "{}", 200, b"x" * n, "{}", "GET", f"u{i}"))
    con.commit()
    con.close()


def test_trim_http_cache_lru(tmp_path):
    db = str(tmp_path / "http-cache.sqlite")
    _make_cache(db, [100] * 10)              # k9 most recently used
    assert cachectl.http_cache_bytes(db) == 1000
    removed = cachectl.trim_http_cache(db, 450)
    assert removed == 600 and cachectl.http_cache_bytes(db) == 400
    con = sqlite3.connect(db)
    keys = sorted(r[0] for r in con.execute("SELECT key FROM CacheItemTable"))
    con.close()
    assert keys == ["k6", "k7", "k8", "k9"]
    assert cachectl.trim_http_cache(db, 10_000) == 0


def test_enforce_splits_budget_and_drops_stale_dbs(tmp_path):
    root = str(tmp_path)
    _make_cache(os.path.join(root, "http-cache.sqlite"), [100] * 10)
    for i in range(4):
        (tmp_path / f"{'a' * 39}{i}.glb").write_bytes(b"g" * 250)
    stale = tmp_path / "http-cache-1234.sqlite"
    stale.write_bytes(b"")
    os.utime(stale, (0, 0))
    r = cachectl.enforce(root, 1000)
    assert r["stale_dbs"] == 1 and not stale.exists()
    left = cachectl.http_cache_bytes(os.path.join(root, "http-cache.sqlite")) + sum(
        p.stat().st_size for p in tmp_path.glob("*.glb"))
    assert left <= 1000
