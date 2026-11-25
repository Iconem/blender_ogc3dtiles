"""Dots for the datasets of an aggregate tileset, at a fixed size on screen.

An Empty is drawn no larger than a kilometre (empty_display_size stops at 1000), so the sphere of a dataset is
lost from a few hundred kilometres. With *An Empty per dataset* on, this draws one white disc per dataset Empty
in every 3D viewport, a few pixels wide at any distance and any Globe scale, depth tested against the tiles
and left out when the Earth is between it and the eye.
The viewport's far clip plane is much nearer than the other side of a continent, so a dot beyond it is drawn on
its view ray just inside the plane: same place on screen, and still behind every tile.
Viewport only.
"""
from __future__ import annotations

import time

import bpy
import numpy as np

PROP = "ogc3dtiles_dataset"            # dataset_empties.PROP: that module needs mathutils, the tests have none

REFRESH_S = 1.0
COLOR = (1.0, 1.0, 1.0, 1.0)
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
    """World positions, and the Earth they sit on."""
    _state["batches"] = np.asarray([tuple(e.matrix_world.translation) for e in es], dtype=np.float64)
    _state["earth"] = _earth(es)


EARTH_RADIUS_M = 6.34e6                 # under the lowest ground: a site on the limb is kept


def _earth(es):
    """(centre, radius) of the Earth in world space, or None when the datasets are not on it."""
    try:
        from .tile_bounds import _ecef_to_world, _streams
        roots = {e.parent.name for e in es if e.parent is not None}
        st = next((s for s in _streams() if s.get("root_obj") in roots), None)
        if st is None or not any(float(np.linalg.norm(e["ogc3dtiles_dataset_centre"][:])) > 6.0e6
                                 for e in es if "ogc3dtiles_dataset_centre" in e):
            return None
        M = _ecef_to_world(st)
        return M[:3, 3].copy(), EARTH_RADIUS_M * float(np.linalg.norm(M[:3, 0]))
    except Exception:                                # noqa: BLE001
        return None


def in_front_of_sphere(points, eye, centre, radius):
    """Mask of the points the sphere does not hide from the eye. No bpy."""
    p = np.asarray(points, dtype=np.float64)
    eye, centre = np.asarray(eye, dtype=np.float64), np.asarray(centre, dtype=np.float64)
    d = p - eye
    L = np.maximum(np.linalg.norm(d, axis=1), 1e-9)
    u = d / L[:, None]
    t = np.clip((centre - eye) @ u.T, 0.0, L)           # nearest point of each segment to the centre
    nearest = eye + u * t[:, None]
    return np.linalg.norm(nearest - centre, axis=1) >= radius


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


VERT = "void main() { gl_Position = mvp * vec4(pos, 1.0); gl_PointSize = size; }"
FRAG = """
void main() {
  float r = length(gl_PointCoord - vec2(0.5)) * 2.0;          // 0 at the centre, 1 on the edge
  float px = 2.0 / size;                                      // one pixel, in those units
  if (r > 1.0) discard;
  vec4 c = mix(color, rim, smoothstep(inner - px, inner, r));
  c.a *= 1.0 - smoothstep(1.0 - px, 1.0, r);
  fragColor = c;
}
"""


def _disc_shader():
    """A round point with a dark rim. Blender's own point shaders draw squares."""
    if _state.get("shader") is None:
        import gpu
        info = gpu.types.GPUShaderCreateInfo()
        info.push_constant("MAT4", "mvp")
        info.push_constant("VEC4", "color")
        info.push_constant("VEC4", "rim")
        info.push_constant("FLOAT", "size")
        info.push_constant("FLOAT", "inner")
        info.vertex_in(0, "VEC3", "pos")
        info.fragment_out(0, "VEC4", "fragColor")
        info.vertex_source(VERT)
        info.fragment_source(FRAG)
        _state["shader"] = gpu.shader.create_from_info(info)
    return _state["shader"]


def _draw():
    scene = bpy.context.scene
    props = getattr(scene, "ogc3dtiles", None)
    if props is None or not props.dataset_empties or props.dataset_marker_px <= 0.0:
        return
    try:
        es = _empties()
        if not es:
            return
        sig = _signature(es)
        if sig != _state["sig"] or _state["batches"] is None:
            _state["sig"] = sig
            _rebuild(es)
        import gpu
        from gpu_extras.batch import batch_for_shader
        shader = _disc_shader()
        rv = bpy.context.region_data
        far, eye = _far_and_eye(rv)
        pts = _state["batches"]
        earth = _state.get("earth")
        if earth is not None:                        # datasets behind the globe
            cam = np.array(rv.view_matrix.inverted().translation, dtype=np.float64)
            if rv.is_perspective:
                pts = pts[in_front_of_sphere(pts, cam, *earth)]
            if not len(pts):
                return
        if far:
            pts = within_clip(pts, eye, far)
        batch = batch_for_shader(shader, "POINTS", {"pos": pts.astype(np.float32)})
        size = 2.0 * float(props.dataset_marker_px) * bpy.context.preferences.system.ui_scale + 3.0
        gpu.state.blend_set("ALPHA")
        gpu.state.depth_test_set("LESS_EQUAL")
        gpu.state.program_point_size_set(True)
        shader.bind()
        shader.uniform_float("mvp", rv.perspective_matrix)
        shader.uniform_float("color", COLOR)
        shader.uniform_float("rim", RIM)
        shader.uniform_float("size", size)
        shader.uniform_float("inner", 1.0 - 3.0 / size)
        batch.draw(shader)
        gpu.state.program_point_size_set(False)
        gpu.state.depth_test_set("NONE")
        gpu.state.blend_set("NONE")
    except Exception as e:                           # noqa: BLE001
        if not _state.get("failed"):
            _state["failed"] = True
            print(f"[3DTiles] dataset dots: {e}")


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
