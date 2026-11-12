"""Exact scene origin.

The three sidebar fields (``origin_lat``, ``origin_lon``, ``origin_height``) are
``FloatProperty``, which Blender keeps in single precision: at longitude 150 the
spacing is 1.5e-5 degrees, up to 0.7 m on the ground, and the local-frame
height (-6 356 752 m) is kept to 0.5 m. So the add-on reads the origin through
``origin_lla()``: the exact doubles sit in an ID property of the scene, written
by ``set_origin()`` whenever the add-on picks an origin and by the fields'
update callback when the user edits them. The ID property only counts while it
rounds to the fields' values, so a .blend from an older version, or a field
changed by a driver, falls back to the fields.
"""
from __future__ import annotations

import re
import struct

ORIGIN_KEY = "ogc3dtiles_origin"


def _f32(x: float) -> float:
    return struct.unpack("<f", struct.pack("<f", x))[0]


def _owner(props):
    return getattr(props, "id_data", None)


def origin_lla(props) -> tuple[float, float, float]:
    """(lat, lon, height) in double precision when the exact store matches the
    fields, else the fields themselves."""
    fields = (float(props.origin_lat), float(props.origin_lon), float(props.origin_height))
    owner = _owner(props)
    try:
        exact = tuple(float(v) for v in owner[ORIGIN_KEY])
    except Exception:
        return fields
    if len(exact) == 3 and all(_f32(e) == f for e, f in zip(exact, fields)):
        return exact
    return fields


def set_origin(props, lat: float, lon: float, height: float) -> None:
    """Set the three fields and the exact store (the fields' update callback
    runs first and is then overwritten with the exact values)."""
    lat, lon, height = float(lat), float(lon), float(height)
    props.origin_lat, props.origin_lon, props.origin_height = lat, lon, height
    owner = _owner(props)
    if owner is not None:
        owner[ORIGIN_KEY] = [lat, lon, height]


def on_origin_edit(props, _context=None) -> None:
    """Update callback of the three fields: an edited field replaces the exact value."""
    owner = _owner(props)
    if owner is not None:
        owner[ORIGIN_KEY] = [float(props.origin_lat), float(props.origin_lon), float(props.origin_height)]


_NUM = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")


def parse_origin_text(text: str):
    """'lat, lon[, height]' with any separators, degrees, full precision.
    Returns (lat, lon, height) or None; a missing height is 0."""
    nums = [float(m) for m in _NUM.findall(text or "")]
    if len(nums) not in (2, 3):
        return None
    lat, lon = nums[0], nums[1]
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return None
    return (lat, lon, nums[2] if len(nums) == 3 else 0.0)
