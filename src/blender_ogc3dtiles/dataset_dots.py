"""Dots for the datasets of an aggregate tileset, at a fixed size on screen.

An Empty is drawn no larger than a kilometre (empty_display_size stops at 1000), so the sphere of a dataset is
lost from a few hundred kilometres. With *An Empty per dataset* on, this draws one white disc per dataset Empty
in every 3D viewport, a few pixels wide at any distance and any Globe scale, left out when the Earth is between
it and the eye, and drawn faint where a tile is in front of it (the centre of a dataset is often inside its own
tiles: its dot would vanish as they load). Only the Empties that are visible get a dot: hide a dataset, or its
tileset, and the dot goes. A click on a dot selects its Empty.
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
        _state["empties"] = [o.name for o in bpy.data.objects if o.type == "EMPTY" and PROP in o and _shown(o)]
        _state["sig"] = None                      # an Empty the user moved is picked up here
    out = []
    for n in _state["empties"]:
        o = bpy.data.objects.get(n)
        if o is not None:
            out.append(o)
    return out


def _shown(o) -> bool:
    try:
        return bool(o.visible_get())
    except Exception:                                # noqa: BLE001  (not in this view layer)
        return False


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
    _state["batches"] = np.asarray([tuple(e.matrix_world.translation) for e in es], dtype=np.float64).reshape(-1, 3)
    _state["names"] = [e.name for e in es]
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


HIDDEN_ALPHA = 0.3                      # a dot behind a tile


def _points(props, rv):
    """(world positions of the dots this view shows, the names of their Empties), or (None, None)."""
    if props is None or not props.dataset_empties or props.dataset_marker_px <= 0.0 or rv is None:
        return None, None
    es = _empties()
    if not es:
        return None, None
    sig = _signature(es)
    if sig != _state["sig"] or _state["batches"] is None or len(_state.get("names") or ()) != len(es):
        _state["sig"] = sig
        _rebuild(es)
    pts, names = _state["batches"], _state["names"]
    earth = _state.get("earth")
    if earth is not None and rv.is_perspective:      # datasets behind the globe
        cam = np.array(rv.view_matrix.inverted().translation, dtype=np.float64)
        keep = in_front_of_sphere(pts, cam, *earth)
        pts, names = pts[keep], [n for n, k in zip(names, keep) if k]
    if not len(pts):
        return None, None
    far, eye = _far_and_eye(rv)
    if far:
        pts = within_clip(pts, eye, far)
    return pts, names


def _size_px(props) -> float:
    return 2.0 * float(props.dataset_marker_px) * bpy.context.preferences.system.ui_scale + 3.0


def nearest_on_screen(pts, perspective, width, height, x, y):
    """(index of the point drawn nearest to the pixel (x, y), its distance in pixels). No bpy."""
    h = np.c_[np.asarray(pts, np.float64), np.ones(len(pts))] @ np.asarray(perspective, np.float64).T
    ok = h[:, 3] > 1e-9
    w = np.where(ok, h[:, 3], 1.0)
    d = np.where(ok, np.hypot((h[:, 0] / w * 0.5 + 0.5) * width - x, (h[:, 1] / w * 0.5 + 0.5) * height - y), np.inf)
    i = int(np.argmin(d))
    return i, float(d[i])


def pick(props, region, rv, x: float, y: float):
    """The name of the Empty whose dot is under the pixel (x, y) of the region, or None."""
    pts, names = _points(props, rv)
    if pts is None:
        return None
    i, d = nearest_on_screen(pts, rv.perspective_matrix, region.width, region.height, x, y)
    return names[i] if d <= _size_px(props) / 2.0 + 3.0 else None


def _draw():
    scene = bpy.context.scene
    props = getattr(scene, "ogc3dtiles", None)
    try:
        rv = bpy.context.region_data
        pts, _names = _points(props, rv)
        if pts is None:
            return
        import gpu
        from gpu_extras.batch import batch_for_shader
        shader = _disc_shader()
        batch = batch_for_shader(shader, "POINTS", {"pos": pts.astype(np.float32)})
        size = _size_px(props)
        gpu.state.blend_set("ALPHA")
        gpu.state.program_point_size_set(True)
        shader.bind()
        shader.uniform_float("mvp", rv.perspective_matrix)
        shader.uniform_float("size", size)
        shader.uniform_float("inner", 1.0 - 3.0 / size)
        gpu.state.depth_test_set("NONE")             # faint, wherever it is: behind a tile too
        gpu.state.depth_mask_set(False)
        shader.uniform_float("color", (*COLOR[:3], COLOR[3] * HIDDEN_ALPHA))
        shader.uniform_float("rim", (*RIM[:3], RIM[3] * HIDDEN_ALPHA))
        batch.draw(shader)
        gpu.state.depth_test_set("LESS_EQUAL")       # whole, where nothing is in front
        shader.uniform_float("color", COLOR)
        shader.uniform_float("rim", RIM)
        batch.draw(shader)
        gpu.state.depth_mask_set(True)
        gpu.state.program_point_size_set(False)
        gpu.state.depth_test_set("NONE")
        gpu.state.blend_set("NONE")
    except Exception as e:                           # noqa: BLE001
        if not _state.get("failed"):
            _state["failed"] = True
            print(f"[3DTiles] dataset dots: {e}")


def _pick_invoke(self, context, event):
    name = None
    try:
        if context.region is not None and context.region.type == "WINDOW":
            name = pick(getattr(context.scene, "ogc3dtiles", None), context.region, context.region_data,
                        event.mouse_region_x, event.mouse_region_y)
    except Exception as e:                           # noqa: BLE001
        print(f"[3DTiles] dataset dots: {e}")
    e = bpy.data.objects.get(name or "")
    if e is None or context.mode != "OBJECT":
        return {"PASS_THROUGH"}                      # not on a dot: the click is Blender's
    if not self.extend:
        for o in context.selected_objects:
            o.select_set(False)
    try:
        e.select_set(True)
        context.view_layer.objects.active = e
    except RuntimeError:
        return {"PASS_THROUGH"}
    self.report({"INFO"}, f"Dataset: {e.name}")
    return {"FINISHED"}


_keymaps: list = []
_cls: list = []


def _operator():
    """The click operator, made at register: this module is imported without bpy.props by the tests."""
    if not _cls:
        _cls.append(type("OGC3D_OT_PickDataset", (bpy.types.Operator,), {
            "__doc__": "Select the Empty of the dataset whose dot is under the cursor",
            "bl_idname": "ogc3dtiles.pick_dataset", "bl_label": "Select Dataset", "bl_options": {"REGISTER", "UNDO"},
            "__annotations__": {"extend": bpy.props.BoolProperty(default=False, options={"SKIP_SAVE"})},
            "invoke": _pick_invoke}))
    return _cls[0]


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
    bpy.utils.register_class(_operator())
    if _state["handle"] is None and not bpy.app.background:
        _state["handle"] = bpy.types.SpaceView3D.draw_handler_add(_draw, (), "WINDOW", "POST_VIEW")
    kc = bpy.context.window_manager.keyconfigs.addon if not bpy.app.background else None
    if kc is not None and not _keymaps:              # a click on a dot, before Blender's own selection
        km = kc.keymaps.new(name="3D View", space_type="VIEW_3D")
        _keymaps.append((km, km.keymap_items.new("ogc3dtiles.pick_dataset", "LEFTMOUSE", "PRESS", head=True)))
        kmi = km.keymap_items.new("ogc3dtiles.pick_dataset", "LEFTMOUSE", "PRESS", shift=True, head=True)
        kmi.properties.extend = True
        _keymaps.append((km, kmi))
    bpy.app.handlers.persistent(on_load)
    if on_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(on_load)


def unregister():
    for km, kmi in _keymaps:
        try:
            km.keymap_items.remove(kmi)
        except Exception:                            # noqa: BLE001
            pass
    _keymaps.clear()
    try:
        bpy.utils.unregister_class(_operator())
    except Exception:                                # noqa: BLE001
        pass
    if on_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(on_load)
    if _state["handle"] is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_state["handle"], "WINDOW")
        _state["handle"] = None
