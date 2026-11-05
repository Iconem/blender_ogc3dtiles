"""phase_strokes: an outline drawn on a surface becomes a closed prism."""
import math
from collections import Counter

import numpy as np

from blender_ogc3dtiles import phase_strokes as ps


def _edges(faces):
    return Counter(tuple(sorted(e)) for a, b, c in faces for e in ((a, b), (b, c), (c, a)))


def _volume(verts, faces):
    return abs(sum(np.dot(verts[a], np.cross(verts[b], verts[c])) for a, b, c in faces)) / 6.0


def test_square_outline_gives_a_closed_box():
    square = [(0, 0, 5), (4, 0, 5), (4, 3, 5), (0, 3, 5), (0, 0, 5)]      # closing point repeated
    verts, faces = ps.prism(square, toward_viewer=(0, 0, 1), front=0.5, back=1.5)
    assert len(verts) == 8
    assert set(_edges(faces).values()) == {2}                             # every edge shared by two faces
    assert math.isclose(_volume(verts, faces), 4 * 3 * 2.0, rel_tol=1e-9)
    assert math.isclose(verts[:, 2].max(), 5.5) and math.isclose(verts[:, 2].min(), 3.5)


def test_front_follows_the_viewer():
    square = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)]
    verts, _faces = ps.prism(square, toward_viewer=(0, 0, -1), front=0.5, back=0.0)
    assert math.isclose(verts[:, 2].min(), -0.5) and math.isclose(verts[:, 2].max(), 0.0)


def test_concave_outline_keeps_its_area_either_way_round():
    ell = [(0, 0), (4, 0), (4, 1), (1, 1), (1, 4), (0, 4)]                 # an L, area 7
    for poly in (ell, ell[::-1]):
        tris = ps.triangulate(poly)
        p = np.array(poly, float)
        area = sum(abs(np.linalg.det(np.stack([p[b] - p[a], p[c] - p[a]]))) for a, b, c in tris) / 2.0
        assert len(tris) == 4 and math.isclose(area, 7.0)
        verts, faces = ps.prism([(x, y, 0.0) for x, y in poly], front=1.0, back=0.0)
        assert set(_edges(faces).values()) == {2}
        assert math.isclose(_volume(verts, faces), 7.0, rel_tol=1e-9)


def test_wobbly_stroke_on_a_tilted_wall():
    rng = np.random.default_rng(1)
    t = np.linspace(0, 2 * math.pi, 400, endpoint=False)
    wall = np.stack([3 * np.cos(t), 0.02 * rng.standard_normal(400), 2 * np.sin(t)], axis=1)   # in x, z
    verts, faces = ps.prism(wall, toward_viewer=(0, -1, 0), front=0.2, back=0.8, min_step=0.02)
    assert len(verts) == 2 * ps.MAX_POINTS
    assert set(_edges(faces).values()) == {2}
    assert math.isclose(_volume(verts, faces), math.pi * 3 * 2 * 1.0, rel_tol=0.01)
    assert verts[:, 1].min() < -0.15 and verts[:, 1].max() > 0.75


def test_strokes_without_area_are_left_out():
    assert ps.prism([(0, 0, 0), (1, 0, 0)]) is None
    assert ps.prism([(0, 0, 0), (1, 0, 0), (2, 0, 0), (3, 0, 0)]) is None
    assert ps.prism([(0, 0, 0)] * 5) is None
