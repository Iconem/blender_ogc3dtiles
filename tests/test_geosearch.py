"""geosearch: Photon parsing, PNG / Terrarium decoding, EGM96 sampling (offline)."""
import struct
import zlib

import numpy as np

from blender_ogc3dtiles import geosearch as g


def _png(rgb: np.ndarray, filt: int = 0) -> bytes:
    h, w, _ = rgb.shape
    rows = []
    prev = np.zeros(w * 3, np.int32)
    for y in range(h):
        line = rgb[y].reshape(-1).astype(np.int32)
        if filt == 1:
            enc = line.copy()
            enc[3:] = (line[3:] - line[:-3]) & 0xFF
        elif filt == 2:
            enc = (line - prev) & 0xFF
        else:
            enc = line
        rows.append(bytes([filt]) + bytes(enc.astype(np.uint8)))
        prev = line

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(b"".join(rows))) + chunk(b"IEND", b""))


def test_png_filters_roundtrip():
    rng = np.random.default_rng(0)
    img = rng.integers(0, 256, (5, 7, 3), dtype=np.uint8)
    for f in (0, 1, 2):
        assert np.array_equal(g.decode_png(_png(img, f)), img)


def test_terrarium_decoding():
    # 100.5 m: 32868.5 = 128 * 256 + 100 + 128 / 256
    px = np.array([[[128, 100, 128]]], np.uint8)
    assert abs(g.terrarium_to_metres(px)[0, 0] - 100.5) < 1e-9


def test_tile_pixel_rome():
    x, y, px, py = g.tile_pixel(41.8902, 12.4922, 13)
    assert (x, y) == (4380, 3044) and 0 <= px < 256 and 0 <= py < 256


def test_egm96_sampling_matches_grid_nodes_and_wraps():
    grid = np.zeros((g.EGM96_ROWS, g.EGM96_COLS), ">i2")
    grid[4, 8] = 1234             # lat 89, lon 2 → 12.34 m
    grid[4, 0] = 500
    grid[4, -1] = -500
    egm = g.Egm96(grid.tobytes())
    assert abs(egm.height(89.0, 2.0) - 12.34) < 1e-9
    assert abs(egm.height(89.0, 1.875) - 6.17) < 1e-9          # half way to the node
    assert abs(egm.height(89.0, 359.875) - 0.0) < 1e-9         # wraps past 360 to column 0
    assert abs(egm.height(89.0, -0.25) + 5.0) < 1e-9           # negative longitudes wrap


def test_parse_photon():
    data = {"features": [
        {"geometry": {"type": "Point", "coordinates": [12.4923841, 41.8902572]},
         "properties": {"name": "Colosseo", "city": "Roma", "country": "Italia",
                        "osm_value": "archaeological_site"}},
        {"geometry": {"type": "Point", "coordinates": [2.35, 48.85]},
         "properties": {"name": "Paris", "city": "Paris", "country": "France", "type": "city"}},
    ]}
    r = g.parse_photon(data)
    assert r[0]["label"] == "Colosseo, Roma, Italia" and r[0]["kind"] == "archaeological_site"
    assert abs(r[0]["lat"] - 41.8902572) < 1e-9 and abs(r[0]["lon"] - 12.4923841) < 1e-9
    assert r[1]["label"] == "Paris, France"
