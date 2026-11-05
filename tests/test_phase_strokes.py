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


def test_painted_stroke_fills_a_tube_of_the_brush_radius():
    lo, cell, shape = np.array([0.0, 0.0, 0.0]), 0.25, (80, 40, 40)
    cells = ps.brush_cells([(2, 5, 5), (18, 5, 5)], [(0, 1)], 1.0, lo, cell, shape)
    centres = lo + (cells + 0.5) * cell
    off_axis = np.hypot(centres[:, 1] - 5, centres[:, 2] - 5)
    assert off_axis.max() < 1.0 + cell and centres[:, 0].min() < 1.3 and centres[:, 0].max() > 18.7
    volume = len(cells) * cell ** 3
    assert math.isclose(volume, math.pi * 16 + 4 / 3 * math.pi, rel_tol=0.1)      # tube and its two end caps


def test_painted_stroke_follows_a_bend_and_stays_in_the_grid():
    lo, cell, shape = np.array([0.0, 0.0, 0.0]), 0.5, (20, 20, 4)
    cells = ps.brush_cells([(1, 1, 1), (8, 1, 1), (8, 8, 1), (30, 8, 1)], [(0, 1), (1, 2), (2, 3)], 0.6, lo, cell, shape)
    grid = np.zeros(shape, bool)
    grid[cells[:, 0], cells[:, 1], cells[:, 2]] = True
    assert grid[10, 2, 2] and grid[16, 10, 2] and grid[19, 16, 2]      # along both legs, up to the grid edge
    assert not grid[4, 12, 2] and not grid[10, 10, 2]                   # the inside of the bend stays empty
    assert len(cells) == len(np.unique(cells, axis=0))


def test_brush_thinner_than_a_cell_still_marks_the_cells_it_crosses():
    cells = ps.brush_cells([(0.5, 0.5, 0.5), (4.5, 0.5, 0.5)], [(0, 1)], 0.01, np.zeros(3), 1.0, (5, 1, 1))
    assert cells[:, 0].tolist() == [0, 1, 2, 3, 4]
