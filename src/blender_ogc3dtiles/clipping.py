"""Clipping volumes: Blender objects that cut a tileset.

Each tileset entry lists objects (meshes or curves), each used either as a
**prism** (its closed outlines in the tileset frame's XY, extruded along that
frame's Z) or as a **box** (its bounding box with its full transform, so it can
cut in 3D).

Modes, as (combine op, per-volume term) where a point is cut when the
combined term is 1:
  * CUT_ANY  — MAX of "inside":  cut inside the union;
  * CUT_ALL  — MIN of "inside":  cut inside the overlap only;
  * KEEP_ANY — MIN of "outside": cut what is outside every volume;
  * KEEP_ALL — MAX of "outside": cut what is outside any volume.

Mesh tiles: prisms are an edge-by-edge test in the shader, boxes an object-space
test, in one group shared by a tileset's materials (clip_nodes, overlays). Their
values and the mode are view-layer attributes, read at render time, so changing
them touches no material and recompiles nothing. Outlines over PRISM_SHADER_EDGES
points fall back on cesium-native ``RasterizedPolygonsOverlay`` masks. Excluders skip
tiles that are cut whatever the other volumes say: native
``RasterizedPolygonsTileExcluder`` for prisms, a Python ``ITileExcluder`` for
boxes. Point and splat tiles: a Geometry Nodes modifier deletes the cut points;
the same on mesh tiles (Cut Geometry) deletes the faces that are entirely cut
(clip_nodes). See docs/clipping.md.

An object's outline is every closed loop of its boundary edges (edges used
by one face, or every edge of a face-less mesh or curve), so one object can
hold several polygons.
"""
from __future__ import annotations

import math
from collections import defaultdict

import numpy as np

from .tileset.traversal import blender_to_ecef, ecef_to_geodetic

MIN_LOOP = 3
PRISM_SHADER_EDGES = 64     # above this an outline is a cesium mask, not shader math
EDGE_SLOT_SIZES = (8, 16, 32, PRISM_SHADER_EDGES)
SHADER_SLOTS = 384          # per tileset: Blender reads 512 view-layer attributes in all


def edge_loops(edges) -> list:
    """Chain undirected edges (pairs of vertex indices) into closed loops of
    vertex indices. Open chains and branching vertices end a loop; open
    chains with at least MIN_LOOP vertices are closed implicitly (a polyline
    drawn without its last edge)."""
    adj = defaultdict(list)
    for a, b in edges:
        if a != b:
            adj[a].append(b)
            adj[b].append(a)
    seen_edges = set()
    loops = []
    # start on chain ends first so open polylines are walked end to end
    starts = sorted(adj, key=lambda v: (len(adj[v]) != 1, v))
    for s in starts:
        for n0 in adj[s]:
            if (min(s, n0), max(s, n0)) in seen_edges:
                continue
            loop = [s]
            prev, cur = s, n0
            seen_edges.add((min(s, n0), max(s, n0)))
            while cur != s:
                loop.append(cur)
                nxt = [n for n in adj[cur] if n != prev and (min(cur, n), max(cur, n)) not in seen_edges]
                if not nxt:
                    break
                prev, cur = cur, nxt[0]
                seen_edges.add((min(prev, cur), max(prev, cur)))
            if len(loop) >= MIN_LOOP:
                loops.append(loop)
    return loops


def boundary_edges(edges, faces) -> list:
    """Edges used by exactly one face; every edge when there are no faces."""
    if not faces:
        return list(edges)
    count = defaultdict(int)
    for f in faces:
        n = len(f)
        for i in range(n):
            a, b = f[i], f[(i + 1) % n]
            count[(min(a, b), max(a, b))] += 1
    return [e for e, c in count.items() if c == 1]


def loops_to_lonlat(loops_xyz, origin) -> list:
    """Blender-frame loops [(x, y, z), ...] → [[lon_rad, lat_rad], ...] per
    loop, through the scene ENU origin (lat, lon, h)."""
    lat0, lon0, h0 = origin
    out = []
    for loop in loops_xyz:
        pts = []
        for p in loop:
            x, y, z = blender_to_ecef(p, lat0, lon0, h0)
            lat, lon, _h = ecef_to_geodetic(x, y, z)
            pts.append([math.radians(lon), math.radians(lat)])
        if len(pts) >= MIN_LOOP:
            out.append(pts)
    return out


def object_loops(obj, depsgraph, to_tileset=None) -> list:
    """World-space (or tileset-frame, with ``to_tileset`` = inverse root
    matrix) outline loops of a mesh / curve object, as lists of xyz."""
    ev = obj.evaluated_get(depsgraph)
    try:
        me = ev.to_mesh()
    except RuntimeError:
        return []
    if me is None:
        return []
    try:
        m = obj.matrix_world if to_tileset is None else to_tileset @ obj.matrix_world
        co = [m @ v.co for v in me.vertices]
        edges = [tuple(e.vertices) for e in me.edges]
        faces = [tuple(p.vertices) for p in me.polygons]
        return [[tuple(co[i]) for i in loop] for loop in edge_loops(boundary_edges(edges, faces))]
    finally:
        ev.to_mesh_clear()


MODE_OPS = {"CUT_ANY": ("MAXIMUM", False), "CUT_ALL": ("MINIMUM", False),
            "KEEP_ANY": ("MINIMUM", True), "KEEP_ALL": ("MAXIMUM", True)}


MAX_MASKS = 8


def mode_op(mode) -> tuple:
    """(combine op, outside term?) of a clip mode."""
    return MODE_OPS.get(mode, MODE_OPS["CUT_ANY"])


def clip_specs(item, polygons, detail_px=2.0) -> list:
    """Backend overlay specs (native_backend._make_overlay kind CLIP) for a
    tileset entry's lon/lat prisms: masks reading 1 inside. One mask per
    polygon, so a mode switch needs no new raster. Beyond MAX_MASKS (GPU
    texture slots) the "any" modes share one mask of the union."""
    if not polygons:
        return []
    base = f"clip_{item.uid}"
    if len(polygons) > MAX_MASKS and item.clip_mode in ("CUT_ANY", "KEEP_ANY"):
        return [{"uid": f"{base}_u", "kind": "CLIP", "polygons": polygons, "invert": False,
                 "detail_px": detail_px}]
    return [{"uid": f"{base}_p{i}", "kind": "CLIP", "polygons": [p], "invert": False,
             "detail_px": detail_px} for i, p in enumerate(polygons)]


def clip_excluders(item, polygons, n_boxes=0) -> list:
    """Native excluders: [{"uid", "kind", "polygons", "invert"}] whose tiles
    are cut whatever the other volumes say, so they are never loaded. With
    "and", a tile is only cut when every volume agrees: these join the boxes in
    one combined excluder (native_backend.set_excluders)."""
    if not polygons:
        return []
    base = f"clipx_{item.uid}"
    mode = item.clip_mode

    def spec(i, polys, invert):
        return {"uid": f"{base}_{i}", "kind": "CLIP", "polygons": polys, "invert": invert}

    if mode == "CUT_ANY":                 # inside one polygon is enough
        return [spec(0, polygons, False)]
    if mode == "KEEP_ALL":                # outside one polygon is enough
        return [spec(i, [p], True) for i, p in enumerate(polygons)]
    if mode == "KEEP_ANY":                # outside the union of the prisms
        return [{**spec(0, polygons, True), "and": bool(n_boxes)}]
    if len(polygons) == 1 and not n_boxes:
        return [spec(0, polygons, False)]
    return [{**spec(i, [p], False), "and": True} for i, p in enumerate(polygons)]


def mode_attrs(mode) -> tuple:
    """(any, invert) read by the material chain: combine the "inside" terms
    with MAX (1) or MIN (0), then invert the result or not. KEEP_ANY =
    MIN of outside = 1 - MAX of inside (and KEEP_ALL likewise)."""
    return (1.0 if mode in ("CUT_ANY", "KEEP_ANY") else 0.0,
            1.0 if mode in ("KEEP_ANY", "KEEP_ALL") else 0.0)


def box_extent(bound_box) -> tuple:
    """Centre and half sizes (clamped away from 0) of an object's local
    bounding box corners."""
    xs, ys, zs = zip(*[tuple(c) for c in bound_box])
    c = tuple((max(v) + min(v)) * 0.5 for v in (xs, ys, zs))
    h = tuple(max((max(v) - min(v)) * 0.5, 1e-6) for v in (xs, ys, zs))
    return c, h


def prism_edges(loop) -> list:
    """(x, y, dx/dy) per edge of an outline, for the shader's crossing test
    (clip_nodes): a horizontal edge never crosses, so its slope doesn't matter."""
    out = []
    for i, a in enumerate(loop):
        b = loop[(i + 1) % len(loop)]
        dy = b[1] - a[1]
        out.append((a[0], a[1], (b[0] - a[0]) / dy if dy else 0.0))
    return out


def edge_slots(n) -> int:
    """Edges an outline's shader test has room for. A bit more than it needs, so
    that adding a point to an outline rarely changes the shader."""
    return next(s for s in EDGE_SLOT_SIZES if s >= n)


def padded_edges(loop) -> list:
    """prism_edges filled up to edge_slots. The extra edges stay on the first
    vertex, so the winding number doesn't see them."""
    edges = prism_edges(loop)
    x, y = loop[0][0], loop[0][1]
    return edges + [(x, y, 0.0)] * (edge_slots(len(loop)) - len(edges))


def split_prisms(loops) -> tuple:
    """Indices of the outlines tested in the shader, and of those which become
    cesium masks: too dense, or past what the attributes can hold."""
    small, dense, used = [], [], 0
    for i, lp in enumerate(loops):
        slots = edge_slots(len(lp)) if len(lp) <= PRISM_SHADER_EDGES else None
        if slots is None or used + slots > SHADER_SLOTS:
            dense.append(i)
        else:
            small.append(i)
            used += slots
    return small, dense


def ecef_to_unit_box(enu_to_ecef, obj_to_enu, c, h) -> list:
    """Rows (3 x 4) taking ECEF to the box's [-1, 1] cube. In doubles: ECEF
    doesn't fit in mathutils' floats."""
    unit = np.array([[h[0], 0, 0, c[0]], [0, h[1], 0, c[1]], [0, 0, h[2], c[2]], [0, 0, 0, 1]],
                    np.float64)
    m = np.asarray(enu_to_ecef, np.float64) @ np.asarray(obj_to_enu, np.float64) @ unit
    return np.linalg.inv(m)[:3].tolist()


def obb_vs_box(center, half_axes, box) -> int:
    """1: the oriented box (half_axes as columns) is entirely inside ``box``
    (ecef_to_unit_box); -1: entirely outside; 0: can't tell. Outside only tries
    the box's own axes, so a tile near a corner may read 0, which keeps it."""
    (hxx, hxy, hxz), (hyx, hyy, hyz), (hzx, hzy, hzz) = half_axes
    cx, cy, cz = center
    inside = True
    for a, b, d, t in box:
        v = abs(a * cx + b * cy + d * cz + t)
        e = (abs(a * hxx + b * hyx + d * hzx) + abs(a * hxy + b * hyy + d * hzy)
             + abs(a * hxz + b * hyz + d * hzz))
        if v - e >= 1.0:
            return -1
        inside = inside and v + e <= 1.0
    return 1 if inside else 0


BOX_RULES = {"CUT_ANY": (1, False), "CUT_ALL": (1, True), "KEEP_ANY": (-1, True),
             "KEEP_ALL": (-1, False)}


def box_rule(mode) -> tuple:
    """(obb_vs_box value that cuts, must every volume agree?) of a clip mode."""
    return BOX_RULES.get(mode, BOX_RULES["CUT_ANY"])


def boxes_cut(center, half_axes, boxes, mode) -> bool:
    """Do the boxes alone cut this oriented box under ``mode``?"""
    want, every = box_rule(mode)
    hits = (obb_vs_box(center, half_axes, b) == want for b in boxes)
    return all(hits) if every else any(hits)


def looks_like_box(n_verts, n_faces) -> bool:
    """Default shape for a newly added object: a cube-like mesh is a box."""
    return n_verts == 8 and n_faces == 6
