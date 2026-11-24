import numpy as np

from blender_ogc3dtiles.tileset import octree_mask as om


def cube(centre, half):
    return np.asarray(centre, float), np.eye(3) * half


def child(parent, octant):
    c, h = parent
    half = h[0, 0] / 2
    return cube(c + om._SIGNS[octant] * half, half)


def test_octant_bits_of_an_octree_child_is_its_one_octant():
    root = cube((10, 20, 30), 8)
    for o in range(8):
        assert om.octant_bits(root, child(root, o)) == 1 << o


def test_octant_bits_in_a_rotated_frame():
    a = 0.6
    r = np.array([[np.cos(a), -np.sin(a), 0], [np.sin(a), np.cos(a), 0], [0, 0, 1]])
    root = (np.array([1.0, 2.0, 3.0]), 8 * r)                      # rows are the half axes
    kid = (root[0] + 4 * (r[0] - r[1] + r[2]), 4 * r)               # +x -y +z: octant 0b101
    assert om.octant_bits(root, kid) == 1 << 0b101


def test_quadtree_child_covers_two_octants_and_a_tight_box_one():
    root = cube((0, 0, 0), 8)
    column = (np.array([4.0, 4.0, 0.0]), np.diag([4.0, 4.0, 8.0]))   # +x +y, full height
    assert om.octant_bits(root, column) == (1 << 0b011) | (1 << 0b111)
    tight = cube((-6, 5, 1), 0.5)                                    # holds no octant centre
    assert om.octant_bits(root, tight) == 1 << 0b110


def test_pack_round_trip_stays_exact_as_float32():
    depths = [7, 0, 3, 1, 7, 7, 2, 5]
    m = om.pack(depths)
    assert om.unpack(m) == depths and m < 2 ** 24
    assert int(np.float32(om.pack([7] * 8))) == om.pack([7] * 8)


def tree():
    """root > a (octant 0) > aa (octant 3) > aaa (octant 5), and root > b (octant 6)."""
    m = om.Masks()
    m.link("a", "root", 1 << 0)
    m.link("b", "root", 1 << 6)
    m.link("aa", "a", 1 << 3)
    m.link("aaa", "aa", 1 << 5)
    return m


def test_masks_follow_the_deepest_shown_chain():
    m = tree()
    out = m.update({"a"}, {"root", "a"})
    assert out == {"root": om.pack([1, 0, 0, 0, 0, 0, 0, 0])}
    out = m.update({"aa", "aaa", "b"}, {"root", "a", "aa", "aaa", "b"})
    assert om.unpack(out["root"]) == [3, 0, 0, 0, 0, 0, 1, 0]
    assert om.unpack(out["a"]) == [0, 0, 0, 2, 0, 0, 0, 0]
    assert om.unpack(out["aa"]) == [0, 0, 0, 0, 0, 1, 0, 0]


def test_only_the_ancestors_of_what_changed_are_touched():
    m = tree()
    m.update({"a", "aa", "aaa", "b"}, {"root", "a", "aa", "aaa", "b"})
    out = m.update({"b"}, {"root", "a", "aa", "aaa"})                # b went away
    assert set(out) == {"root"} and om.unpack(out["root"]) == [3, 0, 0, 0, 0, 0, 0, 0]
    out = m.update({"aaa"}, {"root", "a", "aa"})
    assert om.unpack(out["root"])[0] == 2 and om.unpack(out["a"])[3] == 1 and out["aa"] == 0
    assert m.update({"aaa"}, {"root", "a", "aa"}) == {}              # nothing new: nothing to write


def test_a_hidden_level_breaks_the_chain():
    m = tree()
    out = m.update({"a", "aa", "aaa"}, {"root", "a", "aaa"})         # aa is not shown
    assert om.unpack(out["root"])[0] == 1 and "a" not in out
