"""Wire outlines of 3D Tiles bounding volumes (no bpy, for Show tile bounds).

Each function returns (points N x 3, segments M x 2 of point indices) in the
frame the volume is given in, ECEF for the native backend's volume_shape().
"""
import numpy as np

_A = 6378137.0                       # WGS84
_E2 = 6.69437999014e-3
BOX_EDGES = ((0, 1), (1, 3), (3, 2), (2, 0), (4, 5), (5, 7), (7, 6), (6, 4),
             (0, 4), (1, 5), (2, 6), (3, 7))
REGION_STEPS = 12                    # segments along each curved edge of a region
SPHERE_STEPS = 48


def geodetic_to_ecef(lon, lat, h):
    """Radians and metres (arrays) to ECEF, N x 3."""
    lon, lat, h = (np.asarray(v, np.float64) for v in (lon, lat, h))
    n = _A / np.sqrt(1.0 - _E2 * np.sin(lat) ** 2)
    return np.stack([(n + h) * np.cos(lat) * np.cos(lon),
                     (n + h) * np.cos(lat) * np.sin(lon),
                     (n * (1.0 - _E2) + h) * np.sin(lat)], axis=-1)


def box_lines(center, half_axes):
    c = np.asarray(center, np.float64)
    ax = np.asarray(half_axes, np.float64)           # rows: the three half axes
    signs = np.array([(x, y, z) for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)], np.float64)
    return c + signs @ ax, np.array(BOX_EDGES, np.int64)


def region_lines(west, south, east, north, hmin, hmax, steps=REGION_STEPS):
    """The region's 12 edges, the 8 at constant latitude or longitude sampled
    along the ellipsoid. A region crossing the antimeridian has east < west."""
    if east < west:
        east += 2.0 * np.pi
    t = np.linspace(0.0, 1.0, steps + 1)
    pts, segs = [], []

    def edge(lon, lat, h):
        b = sum(len(p) for p in pts)
        pts.append(geodetic_to_ecef(lon, lat, h))
        segs.extend((b + i, b + i + 1) for i in range(len(lon) - 1))

    for h in (hmin, hmax):
        hh = np.full_like(t, h)
        edge(west + (east - west) * t, np.full_like(t, south), hh)
        edge(west + (east - west) * t, np.full_like(t, north), hh)
        edge(np.full_like(t, west), south + (north - south) * t, hh)
        edge(np.full_like(t, east), south + (north - south) * t, hh)
    for lon in (west, east):
        for lat in (south, north):
            edge(np.array([lon, lon]), np.array([lat, lat]), np.array([hmin, hmax]))
    return np.concatenate(pts), np.array(segs, np.int64)


def sphere_lines(center, radius, axes=None, steps=SPHERE_STEPS):
    """Three great circles; ``axes`` (3 x 3 rows) orients them, the frame's
    axes by default."""
    c = np.asarray(center, np.float64)
    ax = np.eye(3) if axes is None else np.asarray(axes, np.float64)
    a = np.linspace(0.0, 2.0 * np.pi, steps, endpoint=False)
    cos, sin = np.cos(a)[:, None], np.sin(a)[:, None]
    pts, segs = [], []
    for i, j in ((0, 1), (0, 2), (1, 2)):
        b = len(pts) * steps
        pts.append(c + radius * (cos * ax[i] + sin * ax[j]))
        segs.extend((b + k, b + (k + 1) % steps) for k in range(steps))
    return np.concatenate(pts), np.array(segs, np.int64)


def enu_axes(center):
    """East, north, up at an ECEF point (rows), so sphere circles sit level."""
    x, y, z = (float(v) for v in center)
    lon = np.arctan2(y, x)
    lat = np.arctan2(z, np.hypot(x, y))
    e = np.array([-np.sin(lon), np.cos(lon), 0.0])
    u = np.array([np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat)])
    return np.stack([e, np.cross(u, e), u])


def shape_lines(shape):
    """Outline of a native_backend.volume_shape()."""
    kind = shape[0]
    if kind == "region":
        return region_lines(*shape[1])
    if kind == "sphere":
        return sphere_lines(shape[1], shape[2], enu_axes(shape[1]) if np.linalg.norm(shape[1]) > 1e5
                            else None)
    return box_lines(shape[1], shape[2])
