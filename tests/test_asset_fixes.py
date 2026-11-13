"""Tileset JSON fix: tiles without content refine to their children."""
import json

from blender_ogc3dtiles.tileset import asset_fixes


def _tile(ge, children=(), **extra):
    t = {"boundingVolume": {"box": [0] * 12}, "geometricError": ge, "children": list(children)}
    t.update(extra)
    if not t["children"]:
        del t["children"]
    return t


def _tileset(root):
    return json.dumps({"asset": {"version": "1.1"}, "geometricError": root["geometricError"],
                       "root": root}).encode()


def test_empty_levels_take_the_parent_error():
    leaf = _tile(1.0, content={"uri": "a.glb"})
    data = _tileset(_tile(8.0, [_tile(4.0, [_tile(2.0, [leaf])])]))
    out = json.loads(asset_fixes.refine_through_empty_tiles(data))
    l1 = out["root"]["children"][0]
    l2 = l1["children"][0]
    assert out["root"]["geometricError"] == 8.0          # the root keeps its own
    assert l1["geometricError"] == 8.0 and l2["geometricError"] == 8.0
    assert l2["children"][0]["geometricError"] == 1.0    # content tiles are untouched


def test_tiles_with_content_keep_their_error():
    data = _tileset(_tile(8.0, [
        _tile(4.0, [_tile(2.0, content={"uri": "a.glb"})], content={"uri": "b.glb"}),
        _tile(4.0, [_tile(2.0, content={"uri": "c.glb"})], contents=[{"uri": "d.glb"}]),
        _tile(4.0, content={"uri": "ext.json"}),
        _tile(4.0, [_tile(2.0)], implicitTiling={"subdivisionScheme": "QUADTREE"}),
    ]))
    out = asset_fixes.refine_through_empty_tiles(data)
    assert out is data


def test_empty_leaves_and_larger_errors_are_left_alone():
    data = _tileset(_tile(8.0, [_tile(4.0), _tile(9.0, [_tile(1.0, content={"uri": "a.glb"})])]))
    assert asset_fixes.refine_through_empty_tiles(data) is data


def test_non_tileset_json_passes_through():
    for raw in (b'{"tileAvailability": {"constant": 1}}', b"not json", b'{"root": 3}'):
        assert asset_fixes.refine_through_empty_tiles(raw) is raw


def test_network_file_urls():
    from blender_ogc3dtiles.tileset.asset_fixes import is_network_file_url
    assert is_network_file_url("file:////nas/share/tiles/tileset.json")
    assert is_network_file_url("file://nas/share/tiles/tileset.json")
    assert not is_network_file_url("file:///C:/tiles/tileset.json")   # a local drive
    assert not is_network_file_url("file://localhost/C:/tiles/tileset.json")
    assert not is_network_file_url("https://example.com/tileset.json")


def test_serve_file_etag_and_304(tmp_path):
    import os
    from blender_ogc3dtiles.tileset.asset_fixes import serve_file
    f = tmp_path / "tile.b3dm"
    f.write_bytes(b"b3dm" + bytes(24))
    status, ctype, headers, data = serve_file(str(f), None)
    assert status == 200 and data.startswith(b"b3dm") and ctype == "application/octet-stream"
    assert headers["Cache-Control"] == "max-age=0" and headers["ETag"].startswith('"')
    # unchanged: 304 without reading; changed: 200 with a new ETag
    assert serve_file(str(f), headers["ETag"])[0] == 304
    st = os.stat(f)
    os.utime(f, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000_000))
    status2, _c, headers2, _d = serve_file(str(f), headers["ETag"])
    assert status2 == 200 and headers2["ETag"] != headers["ETag"]
    assert serve_file(str(tmp_path / "missing.json"), None)[0] == 404
