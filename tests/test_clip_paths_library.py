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


def test_clip_specs_masks():
    polys = [[[0, 0], [1, 0], [1, 1]], [[2, 2], [3, 2], [3, 3]]]
    item = types.SimpleNamespace(uid="abc", clip_mode="CUT_ANY")
    uids = ["clip_abc_p0", "clip_abc_p1"]
    for mode in clipping.MODE_OPS:                    # a mode switch needs no new mask
        item.clip_mode = mode
        specs = clipping.clip_specs(item, polys)
        assert [x["uid"] for x in specs] == uids and not any(x["invert"] for x in specs)
    assert clipping.clip_specs(item, []) == []
    many = polys * 5                                  # over the GPU texture budget
    item.clip_mode = "KEEP_ANY"
    (s,) = clipping.clip_specs(item, many)
    assert s["uid"] == "clip_abc_u" and len(s["polygons"]) == 10
    item.clip_mode = "CUT_ALL"                        # an overlap can't use a union
    assert len(clipping.clip_specs(item, many)) == 10


def test_clip_excluders():
    polys = [[[0, 0], [1, 0], [1, 1]], [[2, 2], [3, 2], [3, 3]]]
    item = types.SimpleNamespace(uid="abc", clip_mode="CUT_ANY")
    (s,) = clipping.clip_excluders(item, polys, n_boxes=1)    # cut whatever the box says
    assert not s["invert"] and len(s["polygons"]) == 2
    item.clip_mode = "KEEP_ALL"
    ex = clipping.clip_excluders(item, polys, n_boxes=1)      # outside one is enough
    assert len(ex) == 2 and all(s["invert"] and len(s["polygons"]) == 1 for s in ex)
    item.clip_mode = "KEEP_ANY"
    (s,) = clipping.clip_excluders(item, polys)
    assert s["invert"] and len(s["polygons"]) == 2
    assert not s.get("and")
    (s,) = clipping.clip_excluders(item, polys, n_boxes=1)    # a box may keep the tile
    assert s["and"] and s["invert"]
    item.clip_mode = "CUT_ALL"
    ex = clipping.clip_excluders(item, polys)                 # every polygon must agree
    assert len(ex) == 2 and all(s["and"] and not s["invert"] for s in ex)
    (s,) = clipping.clip_excluders(item, polys[:1])
    assert not s["invert"] and not s.get("and")
    (s,) = clipping.clip_excluders(item, polys[:1], n_boxes=1)
    assert s["and"]
    assert clipping.clip_excluders(item, []) == []


def _inside_from_edges(edges, x, y):
    """The shader group's math (clip_nodes._edge_group), in plain Python."""
    above = [y - e[1] > 0 for e in edges]
    acc = 0.0
    for i, (ex, ey, k) in enumerate(edges):
        acc += (above[i] - above[(i + 1) % len(edges)]) * (x < (y - ey) * k + ex)
    return abs(acc) > 0.5


def test_polygon_edges_match_a_reference():
    concave = [(0, 0), (4, 0), (4, 4), (2, 1), (0, 4)]           # a notch from above
    edges = clipping.polygon_edges(concave)
    assert edges[0] == (0, 0, 0.0)                               # horizontal: never crosses
    cases = {(1, 1): True, (3, 1): True, (2, 0.5): True, (2, 3): False, (5, 1): False,
             (-1, 1): False, (1, -1): False, (0.5, 3): True, (3.5, 3): True}
    for (x, y), want in cases.items():
        assert _inside_from_edges(edges, x, y) is want, (x, y)
    # either winding, and a wide coordinate range with a near-horizontal edge
    big = [(1000.0, 5000.0), (9000.0, 5000.001), (9000.0, 9000.0), (1000.0, 9000.0)]
    for loop in (big, big[::-1]):
        e = clipping.polygon_edges(loop)
        assert _inside_from_edges(e, 5000.0, 7000.0) and not _inside_from_edges(e, 500.0, 7000.0)
        assert not _inside_from_edges(e, 5000.0, 4999.0)


def test_split_polygons():
    n = clipping.POLYGON_SHADER_EDGES
    assert clipping.split_polygons([[(0, 0)] * 3, [(0, 0)] * (n + 1), [(0, 0)] * n]) == ([0, 2], [1])
    # past what the attributes hold, outlines become masks
    many = [[(0, 0)] * n] * (clipping.SHADER_SLOTS // n + 1)
    small, dense = clipping.split_polygons(many)
    assert dense == [len(many) - 1] and small == list(range(len(many) - 1))


def test_padded_edges_keep_the_winding():
    concave = [(0, 0), (4, 0), (4, 4), (2, 1), (0, 4)]
    edges = clipping.padded_edges(concave)
    assert len(edges) == clipping.edge_slots(len(concave)) == 8
    for (x, y), want in {(1, 1): True, (2, 3): False, (5, 1): False, (0.5, 3): True}.items():
        assert _inside_from_edges(edges, x, y) is want, (x, y)
    full = [(float(i), float(i * i % 7)) for i in range(8)]
    assert len(clipping.padded_edges(full)) == 8


I4 = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]


def test_obb_vs_box():
    box = clipping.ecef_to_unit_box(I4, I4, (10, 0, 0), (2, 3, 4))  # x 8..12, y -3..3, z -4..4
    small = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
    assert clipping.obb_vs_box((10, 0, 0), small, box) == 1
    assert clipping.obb_vs_box((12, 0, 0), small, box) == 0         # across a face
    assert clipping.obb_vs_box((20, 0, 0), small, box) == -1
    assert clipping.obb_vs_box((10, 0, 3.5), [[0, 0, 1], [1, 0, 0], [0, 1, 0]], box) == 0
    tall = [[1, 0, 0], [0, 1, 0], [0, 0, 100]]
    assert clipping.obb_vs_box((10, 0, 0), tall, box) == 0          # goes through it
    # the box's own transform is applied: moved 100 up and turned 90 degrees
    turned = [[0, -1, 0, 0], [1, 0, 0, 0], [0, 0, 1, 100], [0, 0, 0, 1]]
    box = clipping.ecef_to_unit_box(I4, turned, (10, 0, 0), (2, 3, 4))
    assert clipping.obb_vs_box((0, 10, 100), small, box) == 1
    assert clipping.obb_vs_box((10, 0, 100), small, box) == -1
    # and large ECEF-like coordinates stay exact
    far = [[1, 0, 0, 4.5e6], [0, 1, 0, 1e6], [0, 0, 1, 4.3e6], [0, 0, 0, 1]]
    box = clipping.ecef_to_unit_box(far, I4, (0, 0, 0), (1, 1, 1))
    assert clipping.obb_vs_box((4.5e6 + 0.5, 1e6, 4.3e6), [[.1, 0, 0], [0, .1, 0], [0, 0, .1]], box) == 1


def test_boxes_cut_per_mode():
    a = clipping.ecef_to_unit_box(I4, I4, (0, 0, 0), (2, 2, 2))
    b = clipping.ecef_to_unit_box(I4, I4, (10, 0, 0), (2, 2, 2))
    small = [[.5, 0, 0], [0, .5, 0], [0, 0, .5]]
    in_a, far = (0, 0, 0), (100, 0, 0)
    assert clipping.boxes_cut(in_a, small, [a, b], "CUT_ANY")        # inside one
    assert not clipping.boxes_cut(far, small, [a, b], "CUT_ANY")
    assert not clipping.boxes_cut(in_a, small, [a, b], "CUT_ALL")    # not in both
    assert clipping.boxes_cut(in_a, small, [a, a], "CUT_ALL")
    assert clipping.boxes_cut(far, small, [a, b], "KEEP_ANY")        # outside every one
    assert not clipping.boxes_cut(in_a, small, [a, b], "KEEP_ANY")
    assert clipping.boxes_cut(in_a, small, [a, b], "KEEP_ALL")       # outside one is enough
    assert not clipping.boxes_cut(in_a, small, [a, a], "KEEP_ALL")


def test_clip_mode_semantics():
    """Brute-force each mode on two overlapping intervals + the combine ops."""
    inside = {"A": lambda x: 0 <= x <= 2, "B": lambda x: 1 <= x <= 3}
    expect = {"CUT_ANY": {0.5, 1.5, 2.5}, "CUT_ALL": {1.5},
              "KEEP_ANY": {-1, 4}, "KEEP_ALL": {-1, 0.5, 2.5, 4}}
    for mode, cut_set in expect.items():
        op, outside = clipping.mode_op(mode)
        comb = max if op == "MAXIMUM" else min
        for x in (-1, 0.5, 1.5, 2.5, 4):
            terms = [(not f(x)) if outside else f(x) for f in inside.values()]
            assert bool(comb(terms)) == (x in cut_set), (mode, x)


def test_mode_attrs_match_modes():
    """The material chain (MAX or MIN of inside, then maybe invert) gives the
    same answer as the (op, per-volume term) definition of each mode."""
    cases = [(0, 0), (0, 1), (1, 0), (1, 1)]
    for mode in clipping.MODE_OPS:
        op, outside = clipping.mode_op(mode)
        any_, invert = clipping.mode_attrs(mode)
        for a, b in cases:
            terms = [1 - a, 1 - b] if outside else [a, b]
            want = (max if op == "MAXIMUM" else min)(terms)
            x = max(a, b) if any_ else min(a, b)
            assert abs(x - invert) == want, (mode, a, b)


def test_box_extent():
    c, h = clipping.box_extent([(-1, -2, 0), (3, 2, 0)] * 4)
    assert c == (1, 0, 0) and h[0] == 2 and h[1] == 2 and h[2] == 1e-6


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


def test_library_content_filter():
    splat = {"name": "Interior splat v3", "group": "San Pietro"}
    pts = {"name": "AkYum", "group": "Cambodia point clouds"}
    mesh = {"name": "Bench 50M", "group": "San Pietro meshes (CDN)"}
    told = {"name": "Saint-Roman", "content": "POINTS"}
    unknown = {"name": "Venice flyover"}
    assert [library.content_type(e) for e in (splat, pts, mesh, told, unknown)] == [
        "SPLATS", "POINTS", "MESH", "POINTS", ""]
    # the entry's own field wins over its words, and splats over a mesh2splat's "mesh"
    assert library.content_type({"name": "mesh tiles", "content": "SPLATS"}) == "SPLATS"
    assert library.content_type({"name": "Interior mesh2splat"}) == "SPLATS"
    assert library.content_type({"name": "Voxel mesh test"}) == "VOXELS"
    assert library.matches(splat, "SPLAT pietro") and not library.matches(splat, "splat rome")
    assert library.matches(unknown, "") and not library.matches(unknown, "", ("MESH",))
    assert library.matches(pts, "", ("MESH", "POINTS")) and not library.matches(pts, "", ("SPLATS",))


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
