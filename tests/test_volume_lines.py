"""Outlines of 3D Tiles bounding volumes (tileset/volume_lines.py)."""
import numpy as np

from blender_ogc3dtiles.tileset import volume_lines as vl


def test_box_corners_and_edges():
    pts, segs = vl.box_lines((10, 0, 0), ((2, 0, 0), (0, 3, 0), (0, 0, 4)))
    assert pts.shape == (8, 3) and segs.shape == (12, 2)
    assert np.allclose(pts.min(0), (8, -3, -4)) and np.allclose(pts.max(0), (12, 3, 4))
    lengths = sorted(np.round(np.linalg.norm(pts[segs[:, 0]] - pts[segs[:, 1]], axis=1), 6))
    assert lengths == [4] * 4 + [6] * 4 + [8] * 4      # every edge runs along one axis


def test_region_on_the_ellipsoid():
    w, s, e, n = np.radians([12.45, 41.90, 12.46, 41.91])
    pts, segs = vl.region_lines(w, s, e, n, 0.0, 100.0)
    assert segs.max() < len(pts)
    r = np.linalg.norm(pts, axis=1)
    assert 6.36e6 < r.min() < r.max() < 6.37e6
    corner = vl.geodetic_to_ecef(w, s, 100.0)
    assert np.min(np.linalg.norm(pts - corner, axis=1)) < 1e-6


def test_region_across_the_antimeridian():
    pts, _ = vl.region_lines(np.radians(179.9), 0.0, np.radians(-179.9), np.radians(0.1), 0, 0)
    lon = np.degrees(np.arctan2(pts[:, 1], pts[:, 0]))
    assert np.all(np.abs(lon) > 179.8)                 # the short way round


def test_sphere_circles():
    c = vl.geodetic_to_ecef(np.radians(12.45), np.radians(41.9), 0.0)
    pts, segs = vl.shape_lines(("sphere", tuple(c), 50.0))
    assert np.allclose(np.linalg.norm(pts - c, axis=1), 50.0)
    assert len(segs) == 3 * vl.SPHERE_STEPS
    up = c / np.linalg.norm(c)
    assert np.ptp((pts[:vl.SPHERE_STEPS] - c) @ up) < 1.0   # the first circle sits level
