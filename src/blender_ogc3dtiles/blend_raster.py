"""Footprint of tiles seen from above, as a raster: which ground cells they cover, how far inside
the covered area each cell is, and how low the tiles go there. No bpy: numpy only (blend.py feeds it and
uses the result).

Cells sit on a fixed lattice (cell size ``cell``, origin 0, 0), so the cells of one tile are computed
once and kept: the footprint of a tileset is the union of its tiles' cells. The cells of a tile are a pair
(packed cell indices, sorted and unique; lowest z in each, float32).
"""
from __future__ import annotations

import math

import numpy as np

GRID = 512                  # cells per side of the coverage, at most
MAX_STEPS = 48              # erosion steps of the distance: a longer fade uses a coarser raster
MAX_VERTS = 400_000         # vertices binned per tile; denser tiles are thinned (they cover every cell anyway)
MAX_SUB = 256               # samples along the edge of a large triangle, at most
_OFF = 1 << 20              # cell indices are packed as (ix + _OFF) << 21 | (iy + _OFF)
EMPTY = (np.empty(0, np.int64), np.empty(0, np.float32))


def cell_size(extent_m: float) -> float:
    """Cell size for a footprint this wide: a power of two (in metres), so it changes rarely while tiles load."""
    c = max(extent_m, 1.0) / (GRID - 32)
    return float(2.0 ** math.ceil(math.log2(c)))


def pack(ix, iy):
    return ((ix.astype(np.int64) + _OFF) << 21) | (iy.astype(np.int64) + _OFF)


def unpack(keys):
    return (keys >> 21) - _OFF, (keys & ((1 << 21) - 1)) - _OFF


def merge(sets):
    """Union of cell sets, keeping the lowest z of a cell."""
    sets = [s for s in sets if len(s[0])]
    if not sets:
        return EMPTY
    keys = np.concatenate([s[0] for s in sets])
    z = np.concatenate([s[1] for s in sets])
    order = np.lexsort((z, keys))                    # by cell, lowest first
    keys, z = keys[order], z[order]
    first = np.ones(len(keys), bool)
    first[1:] = keys[1:] != keys[:-1]
    return keys[first], z[first]


def _cells(xyz, cell):
    """(packed cells holding these points, each once and sorted; the lowest z in each)."""
    if not len(xyz):
        return EMPTY
    ij = np.floor(xyz[:, :2] / cell).astype(np.int64)
    return merge([(pack(ij[:, 0], ij[:, 1]), xyz[:, 2].astype(np.float32))])


def cells_of_points(xyz, cell: float, spacing: float = 0.0):
    """Cells holding these points (x, y, z rows). ``spacing`` (m between neighbours, 0: unknown) fills the
    gaps of a sparse cloud: points further apart than a cell cover blocks of cells."""
    xyz = np.asarray(xyz, np.float64)
    if not len(xyz):
        return EMPTY
    if len(xyz) > MAX_VERTS:
        xyz = xyz[:: len(xyz) // MAX_VERTS + 1]
    m = int(min(max(math.ceil(1.5 * spacing / cell), 1), 16))
    if m == 1:
        return _cells(xyz, cell)
    keys, z = _cells(xyz, cell * m)                  # coarse cells, then every fine cell of each
    ix, iy = unpack(keys)
    d = np.arange(m)
    fx = (ix[:, None, None] * m + d[None, :, None]) + 0 * d[None, None, :]
    fy = (iy[:, None, None] * m + d[None, None, :]) + 0 * d[None, :, None]
    return merge([(pack(fx.ravel(), fy.ravel()), np.repeat(z, m * m))])


def cells_of_triangles(xyz, tris, cell: float):
    """Cells a triangle mesh covers: its vertices, plus points inside the triangles wider than a cell."""
    xyz = np.asarray(xyz, np.float64)
    out = [cells_of_points(xyz, cell)]
    tris = np.asarray(tris, np.int64).reshape(-1, 3)
    if len(tris):
        a, b, c = xyz[tris[:, 0]], xyz[tris[:, 1]], xyz[tris[:, 2]]
        size = np.maximum(np.abs(b - a)[:, :2].max(1),
                          np.maximum(np.abs(c - a)[:, :2].max(1), np.abs(c - b)[:, :2].max(1)))
        k = np.ceil(size / cell).astype(np.int64)        # the closing in coverage() fills what is left
        lo = 1
        while True:                                   # triangles grouped by how many samples they need
            hi = lo * 2
            sel = (k > lo) & (k <= hi) if hi < MAX_SUB else (k > lo)
            if sel.any():
                n = min(hi, MAX_SUB)
                i, j = np.meshgrid(np.arange(n + 1), np.arange(n + 1), indexing="ij")
                ok = i + j <= n
                wb, wc = i[ok] / n, j[ok] / n
                idx = np.nonzero(sel)[0]
                step = max(1_000_000 // len(wb), 1)          # a bounded number of samples at a time
                for s0 in range(0, len(idx), step):
                    t = idx[s0:s0 + step]
                    p = (a[t][:, None, :] * (1 - wb - wc)[None, :, None] + b[t][:, None, :] * wb[None, :, None]
                         + c[t][:, None, :] * wc[None, :, None])
                    out.append(_cells(p.reshape(-1, 3), cell))
            if hi >= MAX_SUB:
                break
            lo = hi
    return merge(out)


def _erode(m, diagonal):
    p = np.pad(m, 1)
    r = m & p[:-2, 1:-1] & p[2:, 1:-1] & p[1:-1, :-2] & p[1:-1, 2:]
    if diagonal:
        r &= p[:-2, :-2] & p[:-2, 2:] & p[2:, :-2] & p[2:, 2:]
    return r


def _dilate(m):
    p = np.pad(m, 1)
    return (m | p[:-2, 1:-1] | p[2:, 1:-1] | p[1:-1, :-2] | p[1:-1, 2:]
            | p[:-2, :-2] | p[:-2, 2:] | p[2:, :-2] | p[2:, 2:])


def inside_distance(mask, cell: float, max_m: float):
    """Metres from each covered cell to the nearest uncovered one, up to ``max_m`` (deeper cells read
    ``max_m`` or a little more). Erosions that alternate 4 and 8 neighbours: an octagon, within 8% of a circle."""
    steps = int(min(max(math.ceil(max_m / cell) + 1, 1), 4 * MAX_STEPS))
    dist = np.zeros(mask.shape, np.float32)
    e = mask.copy()
    for k in range(steps):
        if not e.any():
            break
        dist += e
        e = _erode(e, diagonal=k % 2 == 1)
    return np.maximum(dist - 0.5, 0.0) * (mask * cell)


def _fill(low, rounds=3):
    """Cells without a height (inf) take the lowest of their neighbours."""
    for _ in range(rounds):
        p = np.pad(low, 1, constant_values=np.inf)
        nb = np.minimum.reduce([p[:-2, 1:-1], p[2:, 1:-1], p[1:-1, :-2], p[1:-1, 2:],
                                p[:-2, :-2], p[:-2, 2:], p[2:, :-2], p[2:, 2:]])
        low = np.where(np.isinf(low), nb, low)
    return low


def coverage(cell_sets, cell: float, max_m: float, close: int = 1):
    """(distance raster as float32 [y, x] in metres, lowest z per cell, x0, y0, cell of the raster) of the
    union of ``cell_sets``; None when empty. The raster keeps a border of uncovered cells. A fade longer
    than MAX_STEPS cells, or a footprint wider than GRID cells, makes the raster coarser than ``cell``."""
    keys, z = merge(cell_sets)
    if not len(keys):
        return None
    ix, iy = unpack(keys)
    x0, y0 = int(ix.min()), int(iy.min())
    w, h = int(ix.max()) - x0 + 1, int(iy.max()) - y0 + 1
    f = max(int(math.ceil(max(w, h) / (GRID - 8))), int(math.ceil(max_m / cell / MAX_STEPS)), 1)
    ix, iy = (ix - x0) // f, (iy - y0) // f
    w, h = int(ix.max()) + 1, int(iy.max()) + 1
    pad = 3
    mask = np.zeros((h + 2 * pad, w + 2 * pad), bool)
    mask[iy + pad, ix + pad] = True
    low = np.full(mask.shape, np.inf, np.float32)
    order = np.argsort(-z, kind="stable")            # highest first: the last one written is the lowest
    low[iy[order] + pad, ix[order] + pad] = z[order]
    for _ in range(close):                           # pinholes between sparse samples
        mask = _dilate(mask)
    for _ in range(close):
        mask = _erode(mask, True)
    low = _fill(low)
    low[np.isinf(low)] = z.max()
    c = cell * f
    return inside_distance(mask, c, max_m), low, (x0 * cell) - pad * c, (y0 * cell) - pad * c, c
