"""
tests/test_traversal.py — SSE + traversal tests
Marks: (none) = pure Python; cesium = needs cesium-python; benchmark = perf
"""
from __future__ import annotations
import math
import pytest

SCREEN_H = 1080
FOV_Y    = math.radians(60)


def make_sphere_tile(cx, cy, cz, radius, error, uri="test.glb", children=None):
    from blender_ogc3dtiles.tileset.traversal import Tile, BoundingVolume
    return Tile(
        bounding_volume=BoundingVolume(sphere=[cx, cy, cz, radius]),
        geometric_error=error,
        content_uri=uri,
        children=children or [],
    )


def ref_sse(geometric_error, dist_to_surface, screen_h, fov_y):
    ssf = screen_h / (2 * math.tan(fov_y / 2))
    return (geometric_error / dist_to_surface) * ssf


# ── SSE ───────────────────────────────────────────────────────────────────────

class TestSSEPython:

    def test_decreases_with_distance(self):
        from blender_ogc3dtiles.tileset.traversal import compute_sse
        tile = make_sphere_tile(6_378_200, 0, 0, 10, 100)
        sse_close = compute_sse(tile, (6_378_200 + 200.0, 0, 0), SCREEN_H, FOV_Y)
        sse_far   = compute_sse(tile, (6_378_200 + 5_000.0, 0, 0), SCREEN_H, FOV_Y)
        assert sse_close > sse_far

    def test_zero_error_returns_zero(self):
        from blender_ogc3dtiles.tileset.traversal import compute_sse
        tile = make_sphere_tile(0, 0, 6_378_137, 100, 0.0)
        assert compute_sse(tile, (0, 0, 6_378_137 + 1000), SCREEN_H, FOV_Y) == 0.0

    def test_formula_accuracy(self):
        from blender_ogc3dtiles.tileset.traversal import compute_sse
        radius = 50.0
        tile   = make_sphere_tile(6_378_137 + 500, 0, 0, radius, 200.0)
        cam    = (6_378_137 + 2_000, 0, 0)
        dist   = max(abs(2_000 - 500) - radius, 1.0)
        expected = ref_sse(200.0, dist, SCREEN_H, FOV_Y)
        got      = compute_sse(tile, cam, SCREEN_H, FOV_Y)
        assert abs(got - expected) / expected < 0.01


# ── Traversal ─────────────────────────────────────────────────────────────────

class TestTraversalPython:

    def test_far_camera_skips_fine_tiles(self, simple_tile_tree, camera_far):
        from blender_ogc3dtiles.tileset.traversal import TilesetTraversal
        t = TilesetTraversal(max_sse=16.0)
        t.root = simple_tile_tree
        _, render, _ = t.update_view(camera_far, SCREEN_H, FOV_Y)
        uris = {tile.content_uri for tile in render if tile.content_uri}
        assert "gc.glb" not in uris

    def test_close_camera_loads_fine_tiles(self, simple_tile_tree, camera_close):
        from blender_ogc3dtiles.tileset.traversal import TilesetTraversal
        t = TilesetTraversal(max_sse=16.0)
        t.root = simple_tile_tree
        _, render, _ = t.update_view(camera_close, SCREEN_H, FOV_Y)
        uris = {tile.content_uri for tile in render if tile.content_uri}
        assert "gc.glb" in uris

    def test_unload_on_camera_move(self, simple_tile_tree):
        from blender_ogc3dtiles.tileset.traversal import TilesetTraversal
        t = TilesetTraversal(max_sse=16.0)
        t.root = simple_tile_tree
        t.update_view((6_378_200.0, 0, 0), SCREEN_H, FOV_Y)
        _, _, unload = t.update_view((6_378_137 + 100_000, 0, 0), SCREEN_H, FOV_Y)
        assert "gc.glb" in {tile.content_uri for tile in unload}


# ── Backend ───────────────────────────────────────────────────────────────────

class TestPythonBackend:

    def test_make_backend_python(self):
        from blender_ogc3dtiles.tileset.backend import make_backend, BackendChoice
        b = make_backend(BackendChoice.PYTHON)
        assert b.name == "Pure Python"

    def test_auto_falls_back_to_python_if_no_cesium(self, monkeypatch):
        import blender_ogc3dtiles.tileset.backend as bmod
        monkeypatch.setattr(bmod, "probe_cesium", lambda: (False, "mocked missing"))
        from blender_ogc3dtiles.tileset.backend import make_backend, BackendChoice, PythonBackend
        b = make_backend(BackendChoice.AUTO)
        assert isinstance(b, PythonBackend)


# ── cesium parity (skipped without cesium-python installed) ───────────────────

def _cesium_ok():
    try:
        import cesium  # noqa: F401
        return True
    except ImportError:
        return False


@pytest.mark.cesium
@pytest.mark.skipif(not _cesium_ok(), reason="cesium-python not installed")
class TestCesiumNativeBackend:

    def test_cartographic_roundtrip(self):
        from blender_ogc3dtiles.tileset.backend import CesiumNativeBackend
        b = CesiumNativeBackend()
        lat, lon, h = 51.5074, -0.1278, 45.0
        ecef = b.cartographic_to_ecef(lat, lon, h)
        lat2, lon2, h2 = b.ecef_to_cartographic(*ecef)
        assert abs(lat - lat2) < 1e-6
        assert abs(lon - lon2) < 1e-6
        assert abs(h   - h2)   < 0.1

    def test_probe_returns_true(self):
        from blender_ogc3dtiles.tileset.backend import probe_cesium
        ok, msg = probe_cesium()
        assert ok, msg


@pytest.mark.benchmark
@pytest.mark.cesium
@pytest.mark.skipif(not _cesium_ok(), reason="cesium-python not installed")
def test_benchmark_python_backend(benchmark, simple_tile_tree):
    from blender_ogc3dtiles.tileset.backend import PythonBackend
    b = PythonBackend(max_sse=16.0)
    b.set_root(simple_tile_tree)
    cam = (6_378_200.0, 0.0, 0.0)
    result = benchmark(lambda: b.update_view(cam, SCREEN_H, FOV_Y))
    assert result is not None
