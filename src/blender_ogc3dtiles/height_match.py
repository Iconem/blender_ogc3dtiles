"""Match Height to Terrain: move a dataset up or down onto the terrain under it, once.

Height references differ between sources (ellipsoid, sea level, a local datum) and some datasets are just
placed wrong, so a dataset often floats over the terrain or sinks into it. For each dataset, the tiles
shown are binned into ground cells seen from above (blend_raster), as are the terrain tiles under it; the
difference is taken in the cells that are open ground in both (highest and lowest height agree: one
surface), and the dataset moves by its median along the local vertical.

What moves is an Empty: the tileset's root, or, in a tileset of tilesets with *An Empty per dataset*, the
Empty of each dataset that has tiles shown, each by its own amount. Nothing holds it there afterwards.
Terrain blending is not needed: any background entry that streams (a terrain layer, Cesium World Terrain,
Google or Bing 3D Tiles) is the terrain.
"""
from __future__ import annotations

import bpy
import numpy as np

from . import blend_raster as br

MIN_CELLS = 8
FAR_BELOW_M = 100_000.0     # terrain this far under the dataset is the other side of the Earth, not its ground


def _np(m) -> np.ndarray:
    return np.array(m, np.float64)


def local_frame(st, objs):
    """4 x 4, frame to world: east, north, up at the centre of ``objs``, tiles of the stream ``st``."""
    from .tile_bounds import _ecef_to_world
    pts = np.array([_np(o.matrix_world) @ (*c, 1.0) for o in objs for c in (o.bound_box[0], o.bound_box[6])])
    if not len(pts):
        return None
    to_world = _ecef_to_world(st)
    centre = np.linalg.inv(to_world) @ ((pts.min(0) + pts.max(0)) / 2)
    up = centre[:3] / (np.linalg.norm(centre[:3]) or 1.0)
    east = np.cross((0.0, 0.0, 1.0), up)
    east /= np.linalg.norm(east) or 1.0
    m = np.eye(4)
    m[:3, 0], m[:3, 1], m[:3, 2], m[:3, 3] = east, np.cross(up, east), up, centre[:3]
    return to_world @ m


def _groups(st):
    """[(name, the Empty that moves, its tiles shown, is a dataset Empty)] of one stream."""
    from .blend import _tile_objects
    from .dataset_empties import PROP
    root = bpy.data.objects.get(st.get("root_obj") or "")
    by_parent = {}
    for o in _tile_objects(st):
        p = o.parent
        while p is not None and PROP not in p and p != root:
            p = p.parent
        by_parent.setdefault(p.name if p is not None and PROP in p else "", []).append(o)
    out = []
    for name, objs in by_parent.items():
        e = bpy.data.objects.get(name) if name else root
        if e is not None:
            out.append((e.name if name else st["name"], e, objs, bool(name)))
    return out


_FLIP = np.diag([1.0, 1.0, -1.0, 1.0])    # seen from below: the lowest of -z is the highest z
OPEN_SHARE = 0.05           # open ground decides when it is at least this share of the shared cells


def _low_top(cells_of, to_frame):
    """(cells, lowest z, highest z) of some tiles: seen from above and from below."""
    low = br.merge(cells_of(to_frame, False))
    top = br.merge(cells_of(_FLIP @ to_frame, True))
    keys, i_l, i_t = np.intersect1d(low[0], top[0], assume_unique=True, return_indices=True)
    return keys, low[1][i_l].astype(np.float64), -top[1][i_t].astype(np.float64)


def most_common(d, step: float = 0.5) -> float:
    """The offset most cells agree on: the busiest ``step`` metres of the differences (with its two
    neighbours), then the median of the cells within a metre of it. A median over everything is pulled by
    what only one of the two shows: buildings and trees of a scan over a bare terrain."""
    d = np.asarray(d, np.float64)
    if len(d) < 3:
        return float(np.median(d))
    lo = float(np.percentile(d, 1))
    hi = float(np.percentile(d, 99))
    if hi - lo < 2 * step:
        return float(np.median(d))
    hist, edges = np.histogram(d, bins=int(np.ceil((hi - lo) / step)), range=(lo, hi))
    smooth = np.convolve(hist, (1, 1, 1), mode="same")
    k = int(np.argmax(smooth))
    centre = 0.5 * (edges[k] + edges[k + 1])
    near = d[np.abs(d - centre) <= 1.0]
    return float(np.median(near)) if len(near) else float(np.median(d))


def measure_detail(objs, terrain, st) -> dict | None:
    """How far these tiles are from the terrain, with what it was read from; None without enough shared ground.

    Both are read twice per ground cell: their highest and their lowest height. Where the two agree in both
    tilesets the cell is open ground, a single surface: a square, a street, a field. There the difference is
    the offset, and its median is returned. Under a roof, a tree or a bridge the two tilesets do not show the
    same thing from below (a scan with its interior or the underside of its meshes against a model that is a
    shell; the lowest heights alone put St Peter's 24 m too high over Google), so those cells are left out.
    Without enough open ground the highest heights decide: what both show from above. There the
    offset is the one most cells agree on (most_common), not the median."""
    from .blend import _tile_cells
    frame = local_frame(st, objs)
    if frame is None:
        return None
    to_frame = np.linalg.inv(frame)
    boxes = np.concatenate([np.array([(*c, 1.0) for c in o.bound_box]) @ (to_frame @ _np(o.matrix_world))[:2].T
                            for o in objs])
    lo, hi = boxes.min(0), boxes.max(0)
    cell = br.cell_size(float((hi - lo).max()))
    k_d, low_d, top_d = _low_top(lambda m, _flip: [_tile_cells(o, m, cell) for o in objs], to_frame)
    z_floor = (float(low_d.min()) if len(low_d) else 0.0) - FAR_BELOW_M
    near = []
    for o in terrain:                                # the terrain tiles over the dataset
        p = np.array([(*c, 1.0) for c in o.bound_box]) @ (to_frame @ _np(o.matrix_world))[:2].T
        if (p.max(0) >= lo).all() and (p.min(0) <= hi).all():
            near.append(o)
    # only what is under the dataset, and not the far side of a globe (seen from below it never comes first)
    k_t, low_t, top_t = _low_top(lambda m, flip: [_tile_cells(o, m, cell, box=(lo, hi), z_min=-np.inf if flip else z_floor)
                                                  for o in near], to_frame)
    _k, i_d, i_t = np.intersect1d(k_d, k_t, assume_unique=True, return_indices=True)
    if len(i_d) < MIN_CELLS:
        return None
    d_low = low_t[i_t] - low_d[i_d]
    d_top = top_t[i_t] - top_d[i_d]
    thin = 1.5 + cell                                # a single surface: this thick at most, slope included
    open_ = ((top_d[i_d] - low_d[i_d]) <= thin) & ((top_t[i_t] - low_t[i_t]) <= thin)
    n_open = int(open_.sum())
    by_open = n_open >= max(MIN_CELLS, OPEN_SHARE * len(i_d))
    used = d_top[open_] if by_open else d_top
    dz = float(np.median(used)) if by_open else most_common(used)
    return {"dz": dz, "cells": int(len(i_d)), "open": n_open, "cell": cell, "by": "open ground" if by_open else "tops",
            "low": float(np.median(d_low)), "top": float(np.median(d_top)),
            "spread": float(np.subtract(*np.percentile(used, [75, 25])))}


def measure(objs, terrain, st) -> float | None:
    """Metres to add to these tiles' height to sit on the terrain; None without enough shared ground."""
    d = measure_detail(objs, terrain, st)
    return None if d is None else d["dz"]


def terrain_streams(props, streams, only=None) -> list:
    """The streams that are a terrain: ``only`` (an entry) when given, else every background that streams."""
    from .blend import is_background
    from .ui import _stream_hidden
    out = []
    for it in props.tilesets:
        st = streams.get(it.uid) if it.uid else None
        if st is None or st.get("backend") is None or _stream_hidden(st):
            continue
        if (only is not None and it.uid == only.uid) or (only is None and is_background(it, st)):
            out.append(st)
    return out


def match(props, streams, datasets=None, terrain=None) -> list:
    """Move datasets onto the terrain: [(name, metres moved or None)].

    ``datasets``: the entries to move (None: every entry that is not a terrain). ``terrain``: the entry to
    sit on (None: every background that streams)."""
    from .blend import _tile_objects, is_background
    from .ui import _stream_hidden
    ground_sts = terrain_streams(props, streams, terrain)
    if not ground_sts:
        raise RuntimeError("No terrain is streaming: add a terrain, a globe with terrain, Google or Bing 3D Tiles")
    ground = [o for st in ground_sts for o in _tile_objects(st) if o.type == "MESH"]
    bpy.context.view_layer.update()
    wanted = {it.uid for it in datasets} if datasets is not None else None
    plan = []
    for it in props.tilesets:
        st = streams.get(it.uid) if it.uid else None
        if st is None or st.get("backend") is None or st in ground_sts or _stream_hidden(st):
            continue
        if (wanted is not None and it.uid not in wanted) or (wanted is None and is_background(it, st)):
            continue
        for name, empty, objs, is_dataset in _groups(st):
            plan.append((name, empty, is_dataset, measure(objs, ground, st), local_frame(st, objs)))
    from mathutils import Vector
    out = []
    for name, empty, is_dataset, dz, frame in plan:  # moved last: a root that moves takes its datasets along
        if dz is not None and is_dataset:
            empty.location.z += dz                   # a dataset Empty's own Z is the local vertical
        elif dz is not None:
            m = empty.matrix_world.copy()
            m.translation = m.translation + Vector(frame[:3, 2].tolist()) * dz
            empty.matrix_world = m
        out.append((name, dz))
    from . import blend
    blend._state["cells"].clear()
    blend._state["boxes"].clear()
    blend.mark_dirty()
    return out
