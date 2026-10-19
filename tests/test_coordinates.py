"""
tests/test_coordinates.py — geodetic ↔ ECEF ↔ ENU math
"""
from __future__ import annotations
import math
import pytest

ORIGIN = dict(lat_deg=51.5074, lon_deg=-0.1278, height_m=0.0)


class TestGeodeticToECEF:

    def test_equator_greenwich(self):
        from blender_ogc3dtiles.tileset.traversal import _geodetic_to_ecef
        p = _geodetic_to_ecef(0.0, 0.0, 0.0)
        assert abs(p[0] - 6_378_137.0) < 1.0
        assert abs(p[1]) < 1.0
        assert abs(p[2]) < 1.0

    def test_north_pole(self):
        from blender_ogc3dtiles.tileset.traversal import _geodetic_to_ecef
        p = _geodetic_to_ecef(90.0, 0.0, 0.0)
        assert abs(p[0]) < 1.0
        assert abs(p[2] - 6_356_752.3) < 1.0

    def test_height_offset(self):
        from blender_ogc3dtiles.tileset.traversal import _geodetic_to_ecef
        p0 = _geodetic_to_ecef(0.0, 0.0, 0.0)
        p1 = _geodetic_to_ecef(0.0, 0.0, 1000.0)
        dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(p0, p1)))
        assert abs(dist - 1000.0) < 0.1


class TestECEFToENU:

    def test_origin_maps_to_zero(self):
        from blender_ogc3dtiles.tileset.traversal import _geodetic_to_ecef, ecef_to_enu
        p   = _geodetic_to_ecef(**ORIGIN)
        enu = ecef_to_enu(p, ORIGIN["lat_deg"], ORIGIN["lon_deg"], ORIGIN["height_m"])
        assert all(abs(v) < 0.01 for v in enu)

    def test_east_is_positive_x(self):
        from blender_ogc3dtiles.tileset.traversal import _geodetic_to_ecef, ecef_to_enu
        lat, lon, h = ORIGIN["lat_deg"], ORIGIN["lon_deg"], ORIGIN["height_m"]
        dlon = math.degrees(1000.0 / (6_378_137.0 * math.cos(math.radians(lat))))
        p    = _geodetic_to_ecef(lat, lon + dlon, h)
        enu  = ecef_to_enu(p, lat, lon, h)
        assert enu[0] > 900
        assert abs(enu[1]) < 50

    def test_up_is_positive_z(self):
        from blender_ogc3dtiles.tileset.traversal import _geodetic_to_ecef, ecef_to_enu
        lat, lon, h = ORIGIN["lat_deg"], ORIGIN["lon_deg"], ORIGIN["height_m"]
        p   = _geodetic_to_ecef(lat, lon, h + 1000.0)
        enu = ecef_to_enu(p, lat, lon, h)
        assert enu[2] > 900


@pytest.mark.parametrize("lat,lon,h", [
    (0.0,   0.0,    0.0),
    (51.5,  -0.1,   50.0),
    (-33.9, 151.2,  10.0),
    (35.7,  139.8,  40.0),
    (89.9,  0.0,    0.0),
])
def test_geodetic_roundtrip(lat, lon, h):
    from blender_ogc3dtiles.tileset.traversal import _geodetic_to_ecef, ecef_to_enu
    p   = _geodetic_to_ecef(lat, lon, h)
    enu = ecef_to_enu(p, lat, lon, h)
    assert all(abs(v) < 0.1 for v in enu), f"Round-trip failed ({lat},{lon},{h}): ENU={enu}"
