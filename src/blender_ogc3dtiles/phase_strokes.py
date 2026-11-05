"""phase_strokes.py — beta: phases outlined with Grease Pencil strokes on the surface.

A stroke drawn around a part of the monument (Annotate or a Grease Pencil object,
stroke placement *Surface*) is read as a closed outline. It becomes a prism: the
outline in its best-fit plane, pushed behind the surface and a little in front of
it. The prism is a closed mesh in the "Phases" collection with ``code``, ``year``
and ``color``, so ``phases.build`` voxelizes it like any hand-made volume.

This module is plain numpy, so it is tested outside Blender; the operator is
``phases.OGC3D_OT_PhaseFromStrokes``. Limits: one
plane per stroke, so an outline that wraps around a corner needs one stroke per
face; an outline that crosses itself gives a wrong volume.
"""
from __future__ import annotations

import numpy as np

MAX_POINTS = 200        # per outline: ear clipping is quadratic


def clean_loop(points, min_step=0.0, max_points=MAX_POINTS):
    """Outline without repeated points nor its closing duplicate, thinned to at most
    ``max_points``. (N, 3) float64, possibly with fewer than 3 points."""
    pts = np.asarray(points, np.float64).reshape(-1, 3)
    if len(pts) < 2:
        return pts
    step = max(float(min_step), 1e-9)
    keep = [0]
    for i in range(1, len(pts)):
        if np.linalg.norm(pts[i] - pts[keep[-1]]) > step:
            keep.append(i)
    if len(keep) > 1 and np.linalg.norm(pts[keep[-1]] - pts[keep[0]]) <= step:
        keep.pop()
    pts = pts[keep]
    if len(pts) > max_points:
        pts = pts[np.linspace(0, len(pts), max_points, endpoint=False).astype(int)]
    return pts


def fit_plane(points):
    """(centre, u, v, n) of the plane closest to the points; u, v, n are orthonormal
    and right-handed."""
    pts = np.asarray(points, np.float64)
    centre = pts.mean(0)
    _s, _w, vt = np.linalg.svd(pts - centre, full_matrices=False)
    u, v = vt[0], vt[1]
    return centre, u, v, np.cross(u, v)


def _area2(poly):
    x, y = poly[:, 0], poly[:, 1]
    return float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def _inside(p, a, b, c):
    def side(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    return side(a, b, p) >= 0.0 and side(b, c, p) >= 0.0 and side(c, a, p) >= 0.0


def triangulate(poly):
    """Triangles (index triples, counter-clockwise) of a simple 2D polygon, by ear
    clipping. The polygon may turn either way."""
    poly = np.asarray(poly, np.float64)
    order = list(range(len(poly)))
    if _area2(poly) < 0.0:
        order.reverse()
    tris = []
    while len(order) > 3:
        n = len(order)
        for k in range(n):
            i, j, l = order[k - 1], order[k], order[(k + 1) % n]
            a, b, c = poly[i], poly[j], poly[l]
            if (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]) <= 0.0:
                continue        # reflex corner
            if any(_inside(poly[m], a, b, c) for m in order if m not in (i, j, l)):
                continue
            break
        else:
            k = 0               # crossing outline: clip anyway, the loop must end
            i, j, l = order[-1], order[0], order[1]
        tris.append((i, j, l))
        order.pop(k)
    tris.append(tuple(order))
    return tris


def prism(points, toward_viewer=None, front=0.25, back=1.0, min_step=0.0):
    """Closed mesh (vertices (2N, 3), triangles) from an outline: its best-fit
    plane polygon between ``front`` metres toward the viewer and ``back`` metres
    away. None when the outline has no area."""
    pts = clean_loop(points, min_step)
    if len(pts) < 3:
        return None
    centre, u, v, n = fit_plane(pts)
    if toward_viewer is not None and float(np.dot(n, toward_viewer)) < 0.0:
        v, n = -v, -n
    flat = np.stack([(pts - centre) @ u, (pts - centre) @ v], axis=1)
    if abs(_area2(flat)) < 1e-9:
        return None
    base = centre + np.outer(flat[:, 0], u) + np.outer(flat[:, 1], v)
    count = len(base)
    verts = np.concatenate([base + n * front, base - n * back])
    tris = triangulate(flat)
    faces = list(tris) + [(c + count, b + count, a + count) for a, b, c in tris]
    ccw = _area2(flat) > 0.0
    for i in range(count):
        j = (i + 1) % count
        a, b = (i, j) if ccw else (j, i)
        faces += [(a, a + count, b + count), (a, b + count, b)]
    return verts, faces


# ── Blender side ──────────────────────────────────────────────────────────────

def stroke_loops(context):
    """World-space outlines: the active Grease Pencil object's strokes at the current
    frame, else the scene's annotations."""
    obj = context.active_object
    loops = []
    if obj is not None and obj.type == "GREASEPENCIL":
        for layer in obj.data.layers:
            frame = None if layer.hide else layer.current_frame()
            if frame is None:
                continue
            world = np.array(obj.matrix_world @ layer.matrix_local)
            for stroke in frame.drawing.strokes:
                pts = np.array([p.position for p in stroke.points], np.float64).reshape(-1, 3)
                loops.append(pts @ world[:3, :3].T + world[:3, 3])
        return loops
    annotation = context.scene.annotation or getattr(context, "annotation_data", None)
    now = context.scene.frame_current
    for layer in (annotation.layers if annotation is not None else ()):
        if layer.annotation_hide or layer.is_ruler:
            continue
        # active_frame is only set by drawing: take the frame shown now
        frames = [f for f in layer.frames if f.frame_number <= now] or list(layer.frames)
        frame = max(frames, key=lambda f: f.frame_number) if frames else None
        for stroke in (frame.strokes if frame is not None else ()):
            loops.append(np.array([p.co for p in stroke.points], np.float64).reshape(-1, 3))
    return loops
