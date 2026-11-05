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
