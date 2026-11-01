"""Clipping polygons: Blender objects that cut holes in a tileset.

Each tileset entry lists objects (meshes or curves). Their outlines, seen
from above (the polygon is extruded vertically, like Cesium's cartographic
polygons), become cesium-native ``RasterizedPolygonsOverlay`` masks; the
tile material turns the mask into transparency (overlays.attach_clip) and a
``RasterizedPolygonsTileExcluder`` skips tiles entirely on the cut side.

Modes:
  * INSIDE_ANY — cut where a point is inside at least one polygon;
  * INSIDE_ALL — cut only where it is inside every polygon (one mask per
    polygon, combined with MIN in the shader; no tile exclusion);
  * OUTSIDE    — keep only what is inside the polygons.

An object's outline is every closed loop of its boundary edges (edges used
by one face, or every edge of a face-less mesh or curve), so one object can
hold several polygons. Cesium-native backend only.
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


def clip_specs(item, polygons, detail_px=2.0) -> list:
    """Backend overlay specs (native_backend._make_overlay kind CLIP) for a
    tileset entry and its lon/lat polygons."""
    if not polygons:
        return []
    base = f"clip_{item.uid}"
    if item.clip_mode == "INSIDE_ALL" and len(polygons) > 1:
        return [{"uid": f"{base}_all_{i}", "kind": "CLIP", "polygons": [p], "invert": False,
                 "exclude": False, "detail_px": detail_px} for i, p in enumerate(polygons)]
    return [{"uid": f"{base}_any", "kind": "CLIP", "polygons": polygons,
             "invert": item.clip_mode == "OUTSIDE", "exclude": True, "detail_px": detail_px}]
