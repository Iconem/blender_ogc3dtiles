"""Clipping volumes: Blender objects that cut a tileset.

Each tileset entry lists objects (meshes or curves), each used either as a
**prism** (its closed outlines seen from above, extruded vertically along the
scene's up axis, like Cesium's cartographic polygons) or as a **box** (its
bounding box with its full transform, so it can cut in 3D).

Modes, as (combine op, per-volume term) where a point is cut when the
combined term is 1:
  * CUT_ANY  — MAX of "inside":  cut inside the union;
  * CUT_ALL  — MIN of "inside":  cut inside the overlap only;
  * KEEP_ANY — MIN of "outside": cut what is outside every volume;
  * KEEP_ALL — MAX of "outside": cut what is outside any volume.

Mesh tiles: prisms become cesium-native ``RasterizedPolygonsOverlay`` masks
(one per prism, or one for the union when the mode allows), boxes an
object-space test in the shader; both feed one chain in the tile material
(overlays.attach_clip / clip_nodes). ``RasterizedPolygonsTileExcluder`` skips
tiles that are cut whatever the other volumes say. Point and splat tiles: a
Geometry Nodes modifier deletes the cut points (clip_nodes).

An object's outline is every closed loop of its boundary edges (edges used
by one face, or every edge of a face-less mesh or curve), so one object can
hold several polygons. Prisms need the cesium-native backend for meshes.
"""
from __future__ import annotations

import math
from collections import defaultdict

from .tileset.traversal import blender_to_ecef, ecef_to_geodetic

MIN_LOOP = 3


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


def mode_op(mode) -> tuple:
    """(combine op, outside term?) of a clip mode."""
    return MODE_OPS.get(mode, MODE_OPS["CUT_ANY"])


def clip_specs(item, polygons, n_boxes=0, detail_px=2.0) -> list:
    """Backend overlay specs (native_backend._make_overlay kind CLIP) for a
    tileset entry's lon/lat prisms. The mask of a spec is the per-volume
    term (inside, or outside when inverted). One spec covers the union when
    the combine op allows it (MAX of inside = inside the union, MIN of
    outside = outside the union); otherwise one spec per polygon. A spec
    also excludes whole tiles when its mask being 1 means "cut" whatever the
    other volumes (boxes included) say."""
    if not polygons:
        return []
    op, outside = mode_op(item.clip_mode)
    base = f"clip_{item.uid}"
    union = (op == "MAXIMUM") != outside or len(polygons) == 1
    if union:
        exclude = op == "MAXIMUM" or n_boxes == 0
        return [{"uid": f"{base}_u", "kind": "CLIP", "polygons": polygons, "invert": outside,
                 "exclude": exclude, "detail_px": detail_px}]
    return [{"uid": f"{base}_p{i}", "kind": "CLIP", "polygons": [p], "invert": outside,
             "exclude": op == "MAXIMUM", "detail_px": detail_px} for i, p in enumerate(polygons)]


def box_extent(bound_box) -> tuple:
    """Centre and half sizes (clamped away from 0) of an object's local
    bounding box corners."""
    xs, ys, zs = zip(*[tuple(c) for c in bound_box])
    c = tuple((max(v) + min(v)) * 0.5 for v in (xs, ys, zs))
    h = tuple(max((max(v) - min(v)) * 0.5, 1e-6) for v in (xs, ys, zs))
    return c, h


def looks_like_box(n_verts, n_faces) -> bool:
    """Default shape for a newly added object: a cube-like mesh is a box."""
    return n_verts == 8 and n_faces == 6
