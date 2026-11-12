"""Exact scene origin (issue 7): doubles behind the single-precision fields."""
import struct

from blender_ogc3dtiles.tileset.origin import (
    ORIGIN_KEY, on_origin_edit, origin_lla, parse_origin_text, set_origin,
)


def f32(x):
    return struct.unpack("<f", struct.pack("<f", x))[0]


class Props:
    """Mimics the PropertyGroup: FloatProperty fields round to float32 and run
    the update callback; id_data is the scene, a dict for ID properties."""
    def __init__(self):
        self.id_data = {}
        self.__dict__.update(origin_lat=0.0, origin_lon=0.0, origin_height=0.0)

    def __setattr__(self, k, v):
        if k.startswith("origin_"):
            v = f32(v)
            object.__setattr__(self, k, v)
            on_origin_edit(self)
        else:
            object.__setattr__(self, k, v)


LAT, LON, H = -30.0235, 150.0123, 42.3456789


def test_fields_alone_lose_decimetres():
    assert abs(f32(LON) - LON) * 111000 * 0.87 > 0.1     # the reported 0.13 m


def test_set_origin_keeps_doubles():
    p = Props()
    set_origin(p, LAT, LON, H)
    assert origin_lla(p) == (LAT, LON, H)
    assert p.origin_lon == f32(LON)                       # the field shows the rounded value
    assert p.id_data[ORIGIN_KEY] == [LAT, LON, H]


def test_edited_field_replaces_exact_value():
    p = Props()
    set_origin(p, LAT, LON, H)
    p.origin_lat = 12.5                                   # typed in the sidebar
    assert origin_lla(p) == (f32(12.5), f32(LON), f32(H))


def test_stale_store_is_ignored():
    p = Props()
    set_origin(p, LAT, LON, H)
    object.__setattr__(p, "origin_lon", f32(10.0))        # changed without the callback (driver, old file)
    assert origin_lla(p) == (f32(LAT), f32(10.0), f32(H))


def test_no_store_falls_back_to_fields():
    p = Props()
    object.__setattr__(p, "origin_lat", f32(LAT))
    assert origin_lla(p) == (f32(LAT), 0.0, 0.0)
    p.id_data = None
    assert origin_lla(p) == (f32(LAT), 0.0, 0.0)


def test_local_frame_height_exact():
    p = Props()
    set_origin(p, 90.0, -90.0, -6356752.314245 + 17.25)
    assert origin_lla(p)[2] == -6356752.314245 + 17.25
    assert abs(p.origin_height - origin_lla(p)[2]) > 0.01  # float32 keeps 0.5 m at that size


def test_parse_origin_text():
    assert parse_origin_text("-30.0235, 150.0123") == (-30.0235, 150.0123, 0.0)
    assert parse_origin_text("48.858370 2.294481 120.5") == (48.858370, 2.294481, 120.5)
    assert parse_origin_text("48.858370; 2.294481; -1e2") == (48.858370, 2.294481, -100.0)
    assert parse_origin_text("") is None
    assert parse_origin_text("1 2 3 4") is None
    assert parse_origin_text("95, 10") is None
