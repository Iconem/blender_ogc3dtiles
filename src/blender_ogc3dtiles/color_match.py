"""Color match: the numbers that bring one tileset's colors onto another's. No bpy.

Both tilesets are sampled where they overlap, seen from above: one mean color per ground cell each. Per
channel, a gain and a gamma are fitted so that

    reference ≈ gain · color ^ gamma

which is a line in log space: the gamma matches the spread of the two sets of cells, the gain their level
(the color transfer of Reinhard et al., on the logs of linear RGB). Two numbers per channel cannot follow a
different light direction or shadows that moved: it is a global match, good against a color cast, an
exposure or a contrast difference.
"""
from __future__ import annotations

import numpy as np

FLOOR = 0.002                # linear: below this a cell is black, its log says nothing
GAIN_RANGE = (0.2, 5.0)
GAMMA_RANGE = (0.6, 1.6)
MIN_CELLS = 16


def srgb_to_linear(c: np.ndarray) -> np.ndarray:
    c = np.asarray(c, np.float32)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def cell_means(keys: np.ndarray, rgb: np.ndarray):
    """(sorted unique keys, mean color per key) of samples that each fall in the ground cell ``keys``."""
    keys = np.asarray(keys)
    if not len(keys):
        return np.empty(0, np.int64), np.empty((0, 3), np.float32)
    uniq, inv, n = np.unique(keys, return_inverse=True, return_counts=True)
    out = np.zeros((len(uniq), 3), np.float64)
    np.add.at(out, inv, np.asarray(rgb, np.float64))
    return uniq, (out / n[:, None]).astype(np.float32)


def shared(keys_a, rgb_a, keys_b, rgb_b):
    """The colors of the cells both have, in the same order."""
    _k, ia, ib = np.intersect1d(keys_a, keys_b, assume_unique=True, return_indices=True)
    return rgb_a[ia], rgb_b[ib]


def fit(src: np.ndarray, ref: np.ndarray):
    """(gain, gamma), three numbers each, with ``ref ≈ gain * src ** gamma`` over paired colors (N x 3, linear).
    None when too few cells are bright enough in both."""
    src, ref = np.asarray(src, np.float64), np.asarray(ref, np.float64)
    ok = (src > FLOOR).all(1) & (ref > FLOOR).all(1)
    if int(ok.sum()) < MIN_CELLS:
        return None
    ls, lr = np.log(src[ok]), np.log(ref[ok])
    lo, hi = np.percentile(ls, (2, 98), axis=0)      # the extremes (speculars, holes) do not steer the fit
    lo_r, hi_r = np.percentile(lr, (2, 98), axis=0)
    gain, gamma = np.ones(3), np.ones(3)
    for c in range(3):
        keep = (ls[:, c] >= lo[c]) & (ls[:, c] <= hi[c]) & (lr[:, c] >= lo_r[c]) & (lr[:, c] <= hi_r[c])
        s, r = ls[keep, c], lr[keep, c]
        if len(s) < MIN_CELLS:
            s, r = ls[:, c], lr[:, c]
        sd = float(s.std())
        g = float(np.clip(r.std() / sd, *GAMMA_RANGE)) if sd > 1e-4 else 1.0
        gamma[c] = g
        gain[c] = float(np.clip(np.exp(r.mean() - g * s.mean()), *GAIN_RANGE))
    return gain, gamma


def apply(rgb: np.ndarray, gain, gamma) -> np.ndarray:
    return np.asarray(gain) * np.maximum(np.asarray(rgb, np.float64), 0.0) ** np.asarray(gamma)
