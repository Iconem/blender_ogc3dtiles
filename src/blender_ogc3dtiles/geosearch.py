"""Place search for the scene origin: Photon geocoding, terrain height, geoid.

* Photon (https://photon.komoot.io, OpenStreetMap data, self-hostable) turns
  a free-text query into places with WGS84 longitude / latitude.
* The ground height there comes from a Terrarium-encoded elevation tile
  (default: the AWS open-data Terrain Tiles, metres above sea level).
* The scene origin height is an ellipsoid height (3D Tiles are in ECEF), so
  the EGM96 geoid undulation is added: cesium-native's 15' grid
  (WW15MGH.DAC, 2 MB, downloaded once into the add-on cache).

No bpy here: the add-on calls these from operators, the tests call them
with canned bytes.
"""
from __future__ import annotations

import json
import math
import os
import struct
import urllib.parse
import urllib.request
import zlib

import numpy as np

PHOTON_URL = "https://photon.komoot.io/api/"
TERRARIUM_URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
GEOID_URL = "https://raw.githubusercontent.com/CesiumGS/cesium-native/v0.59.0/data/WW15MGH.DAC"
USER_AGENT = "blender_ogc3dtiles (place search; https://github.com/jo-chemla/blender_ogc3dtiles)"

EGM96_ROWS, EGM96_COLS = 721, 1440
EGM96_BYTES = EGM96_ROWS * EGM96_COLS * 2


def _get(url: str, timeout: float = 8.0) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:      # noqa: S310 (user-set https URLs)
        return r.read()


# ── Photon ────────────────────────────────────────────────────────────────────
def parse_photon(data: dict) -> list:
    """Photon GeoJSON → [{label, lat, lon, kind}] (point features only)."""
    out = []
    for f in data.get("features") or []:
        g = f.get("geometry") or {}
        if g.get("type") != "Point":
            continue
        lon, lat = g.get("coordinates")[:2]
        p = f.get("properties") or {}
        name = p.get("name") or p.get("street") or p.get("city") or "?"
        where = [p.get(k) for k in ("city", "county", "state", "country") if p.get(k)]
        where = [w for i, w in enumerate(where) if w != name and w not in where[:i]]
        label = name + (", " + ", ".join(where[:2]) if where else "")
        kind = p.get("osm_value") or p.get("type") or ""
        out.append({"label": label, "lat": float(lat), "lon": float(lon), "kind": kind})
    return out


def photon_search(query: str, endpoint: str = PHOTON_URL, limit: int = 6,
                  lang: str = "", timeout: float = 8.0) -> list:
    q = {"q": query.strip(), "limit": str(int(limit))}
    if lang:
        q["lang"] = lang
    url = endpoint.rstrip("?") + ("&" if "?" in endpoint else "?") + urllib.parse.urlencode(q)
    return parse_photon(json.loads(_get(url, timeout).decode("utf-8")))


# ── Terrarium elevation tiles ─────────────────────────────────────────────────
def decode_png(data: bytes) -> np.ndarray:
    """Minimal PNG decoder for 8-bit RGB / RGBA, non-interlaced (what
    elevation tile servers send). Returns (h, w, channels) uint8."""
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")
    pos, idat, w = 8, [], None
    while pos < len(data):
        length, ctype = struct.unpack(">I4s", data[pos:pos + 8])
        chunk = data[pos + 8:pos + 8 + length]
        pos += 12 + length
        if ctype == b"IHDR":
            w, h, depth, color, _c, _f, interlace = struct.unpack(">IIBBBBB", chunk)
            if depth != 8 or color not in (2, 6) or interlace:
                raise ValueError(f"unsupported PNG (depth {depth}, colour {color}, interlace {interlace})")
            ch = 3 if color == 2 else 4
        elif ctype == b"IDAT":
            idat.append(chunk)
        elif ctype == b"IEND":
            break
    if w is None:
        raise ValueError("PNG without IHDR")
    raw = zlib.decompress(b"".join(idat))
    stride = w * ch
    out = bytearray(h * stride)
    prev = bytearray(stride)
    for y in range(h):
        o = y * (stride + 1)
        ftype, line = raw[o], raw[o + 1:o + 1 + stride]
        cur = bytearray(line)
        if ftype == 1:
            for x in range(ch, stride):
                cur[x] = (cur[x] + cur[x - ch]) & 0xFF
        elif ftype == 2:
            for x in range(stride):
                cur[x] = (cur[x] + prev[x]) & 0xFF
        elif ftype == 3:
            for x in range(stride):
                a = cur[x - ch] if x >= ch else 0
                cur[x] = (cur[x] + ((a + prev[x]) >> 1)) & 0xFF
        elif ftype == 4:
            for x in range(stride):
                a = cur[x - ch] if x >= ch else 0
                b = prev[x]
                c = prev[x - ch] if x >= ch else 0
                pp = a + b - c
                pa, pb, pc = abs(pp - a), abs(pp - b), abs(pp - c)
                pred = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                cur[x] = (cur[x] + pred) & 0xFF
        elif ftype != 0:
            raise ValueError(f"bad PNG filter {ftype}")
        out[y * stride:(y + 1) * stride] = cur
        prev = cur
    out = np.frombuffer(bytes(out), np.uint8)
    return out.reshape(h, w, ch)


def terrarium_to_metres(rgb: np.ndarray) -> np.ndarray:
    r, g, b = (rgb[..., i].astype(np.float64) for i in range(3))
    return r * 256.0 + g + b / 256.0 - 32768.0


def tile_pixel(lat: float, lon: float, z: int, size: int = 256):
    """Web-mercator tile (x, y) and fractional pixel (px, py) of a point."""
    n = 2 ** z
    lat = max(min(lat, 85.0511), -85.0511)
    fx = (lon + 180.0) / 360.0 * n
    s = math.sin(math.radians(lat))
    fy = (0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)) * n
    x, y = int(fx) % n, min(int(fy), n - 1)
    return x, y, (fx - int(fx)) * size, (fy - int(fy)) * size


def terrain_height(lat: float, lon: float, template: str = TERRARIUM_URL,
                   zoom: int = 13, timeout: float = 8.0) -> float:
    """Ground height (m above sea level) from one Terrarium tile, bilinear."""
    x, y, px, py = tile_pixel(lat, lon, zoom)
    url = template.replace("{z}", str(zoom)).replace("{x}", str(x)).replace("{y}", str(y))
    m = terrarium_to_metres(decode_png(_get(url, timeout)))
    h, w = m.shape
    x0, y0 = min(int(px), w - 1), min(int(py), h - 1)
    x1, y1 = min(x0 + 1, w - 1), min(y0 + 1, h - 1)
    tx, ty = px - x0, py - y0
    top = m[y0, x0] * (1 - tx) + m[y0, x1] * tx
    bot = m[y1, x0] * (1 - tx) + m[y1, x1] * tx
    return float(top * (1 - ty) + bot * ty)


# ── EGM96 geoid ───────────────────────────────────────────────────────────────
class Egm96:
    """EGM96 15' grid (WW15MGH.DAC: 721 x 1440 big-endian int16 centimetres,
    rows from 90N to 90S, columns eastward from 0E); same sampling as
    cesium-native's EarthGravitationalModel1996Grid (wraps at 360E)."""

    def __init__(self, data: bytes):
        if len(data) < EGM96_BYTES:
            raise ValueError("EGM96 grid too short")
        self.grid = np.frombuffer(data[:EGM96_BYTES], ">i2").reshape(EGM96_ROWS, EGM96_COLS)

    def height(self, lat: float, lon: float) -> float:
        lon = (lon % 360.0 + 360.0) % 360.0
        lat = max(-90.0, min(90.0, lat))
        hx = EGM96_COLS * lon / 360.0
        vy = (EGM96_ROWS - 1) * (90.0 - lat) / 180.0
        i, j = int(hx), int(vy)
        xn, yn = hx - i, vy - j
        i1, j1 = (i + 1) % EGM96_COLS, min(j + 1, EGM96_ROWS - 1)
        g = self.grid
        v = (g[j, i] * (1 - xn) * (1 - yn) + g[j, i1] * xn * (1 - yn)
             + g[j1, i] * (1 - xn) * yn + g[j1, i1] * xn * yn)
        return float(v) / 100.0


_EGM96: list = []


def egm96(cache_dir: str, url: str = GEOID_URL, timeout: float = 30.0) -> Egm96:
    """The grid, from the cache or downloaded once (2 MB)."""
    if _EGM96:
        return _EGM96[0]
    path = os.path.join(cache_dir, "geoid", "WW15MGH.DAC")
    data = b""
    if os.path.isfile(path) and os.path.getsize(path) >= EGM96_BYTES:
        with open(path, "rb") as fh:
            data = fh.read()
    else:
        data = _get(url, timeout)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(data)
    _EGM96.append(Egm96(data))
    return _EGM96[0]


def ellipsoid_height(lat: float, lon: float, cache_dir: str,
                     terrain_template: str = TERRARIUM_URL, geoid_url: str = GEOID_URL):
    """(ellipsoid height, sea-level height, geoid undulation, notes) at a
    point; parts that fail to download count as 0 and are named in notes."""
    notes = []
    try:
        msl = terrain_height(lat, lon, terrain_template)
    except Exception as e:                           # noqa: BLE001
        msl = 0.0
        notes.append(f"terrain height unavailable ({e})")
    try:
        n = egm96(cache_dir, geoid_url).height(lat, lon)
    except Exception as e:                           # noqa: BLE001
        n = 0.0
        notes.append(f"geoid unavailable ({e})")
    return msl + n, msl, n, notes
