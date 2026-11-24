"""Dots for the datasets of an aggregate tileset, at a fixed size on screen.

An Empty is drawn no larger than a kilometre (empty_display_size stops at 1000), so the sphere of a dataset is
lost from a few hundred kilometres. With *Markers for every dataset* on, this draws one point per dataset Empty
in every 3D viewport, a few pixels wide at any distance and any Globe scale, depth tested against the tiles.
The viewport's far clip plane is much nearer than the other side of a continent, so a dot beyond it is drawn on
its view ray just inside the plane: same place on screen, and still behind every tile.
Orange: no tile of the dataset is loaded. Blue: some are. Viewport only.
"""
from __future__ import annotations

import time

import bpy
import numpy as np

PROP = "ogc3dtiles_dataset"            # dataset_empties.PROP: that module needs mathutils, the tests have none

REFRESH_S = 1.0
PENDING = (1.0, 0.55, 0.1, 1.0)
LOADED = (0.25, 0.75, 1.0, 1.0)
RIM = (0.0, 0.0, 0.0, 0.85)
_state = {"handle": None, "t": 0.0, "empties": [], "sig": None, "batches": None}


def _empties():
    """The dataset Empties, looked for once a second: tiles are many more objects than datasets."""
    now = time.monotonic()
    if now - _state["t"] >= REFRESH_S:
        _state["t"] = now
        _state["empties"] = [o.name for o in bpy.data.objects if o.type == "EMPTY" and PROP in o]
        _state["sig"] = None                      # an Empty the user moved is picked up here
    out = []
    for n in _state["empties"]:
        o = bpy.data.objects.get(n)
        if o is not None:
            out.append(o)
    return out


def _signature(es) -> tuple:
    """What the dots' places depend on between two refreshes: the roots (the Globe moves and scales them)."""
    roots = {}
    for e in es:
        p = e.parent
        if p is not None and p.name not in roots:
            roots[p.name] = tuple(round(v, 6) for row in p.matrix_world for v in row)
    return (len(es), tuple(sorted(roots.items())))


def _rebuild(es):
    """World positions, by colour."""
    pending = [tuple(e.matrix_world.translation) for e in es if not e.children]
    loaded = [tuple(e.matrix_world.translation) for e in es if e.children]
    _state["batches"] = [(c, np.asarray(pts, dtype=np.float64))
                         for c, pts in ((PENDING, pending), (LOADED, loaded)) if pts]


def within_clip(points, eye, far, keep=0.9):
    """Points further from the eye than ``keep`` x far, moved onto that distance along their view ray. No bpy."""
    p = np.asarray(points, dtype=np.float64)
    d = p - np.asarray(eye, dtype=np.float64)
    dist = np.linalg.norm(d, axis=1)
    k = np.minimum(1.0, keep * far / np.maximum(dist, 1e-9))
    return eye + d * k[:, None]


def _far_and_eye(rv):
    """(far clip distance, eye position) of a perspective view, else (None, None): an orthographic view clips by
    depth along the view axis only, and its dots stay where they are."""
    if not rv.is_perspective:
        return None, None
    P = rv.window_matrix
    far = P[2][3] / (P[2][2] + 1.0) if abs(P[2][2] + 1.0) > 1e-12 else None
    return far, np.array(rv.view_matrix.inverted().translation, dtype=np.float64)


def _draw():
    scene = bpy.context.scene
    props = getattr(scene, "ogc3dtiles", None)
    if props is None or not props.dataset_markers or props.dataset_marker_px <= 0.0:
        return
    try:
        es = _empties()
        if not es:
            return
        sig = _signature(es)
        if sig != _state["sig"] or _state["batches"] is None:
            _state["sig"] = sig
            _rebuild(es)
    except Exception as e:                           # noqa: BLE001
        print(f"[3DTiles] dataset dots: {e}")
        _state["batches"] = None
        return
    import gpu
    from gpu_extras.batch import batch_for_shader
    shader = gpu.shader.from_builtin("POINT_UNIFORM_COLOR")
    far, eye = _far_and_eye(bpy.context.region_data)
    batches = []
    for color, pts in _state["batches"]:
        if far:
            pts = within_clip(pts, eye, far)
        batches.append((color, batch_for_shader(shader, "POINTS", {"pos": pts.astype(np.float32)})))
    d = 2.0 * float(props.dataset_marker_px) * bpy.context.preferences.system.ui_scale
    gpu.state.blend_set("ALPHA")
    gpu.state.depth_test_set("LESS_EQUAL")
    shader.bind()
    for size, tint in ((d + 3.0, 0), (d, 1)):        # a dark rim, then the dot
        gpu.state.point_size_set(size)
        for color, batch in batches:
            shader.uniform_float("color", color if tint else RIM)
            batch.draw(shader)
    gpu.state.point_size_set(1.0)
    gpu.state.depth_test_set("NONE")
    gpu.state.blend_set("NONE")


def invalidate() -> None:
    _state["t"], _state["sig"], _state["batches"] = 0.0, None, None
    wm = getattr(bpy.context, "window_manager", None)
    for w in (wm.windows if wm else ()):
        for a in w.screen.areas:
            if a.type == "VIEW_3D":
                a.tag_redraw()


def on_load(*_args) -> None:
    invalidate()


def register():
    if _state["handle"] is None and not bpy.app.background:
        _state["handle"] = bpy.types.SpaceView3D.draw_handler_add(_draw, (), "WINDOW", "POST_VIEW")
    bpy.app.handlers.persistent(on_load)
    if on_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(on_load)


def unregister():
    if on_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(on_load)
    if _state["handle"] is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_state["handle"], "WINDOW")
        _state["handle"] = None
