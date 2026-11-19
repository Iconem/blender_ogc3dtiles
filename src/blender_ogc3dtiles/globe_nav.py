"""Globe navigation (beta prototype): navigate a streamed planet the way 3d-tiles-renderer's GlobeControls does.

The view stays near the Blender origin and the world moves under it. Every tileset root Empty is parented to one
"OGC3D Globe" Empty, and the gestures edit that Empty's matrix: one matrix write, whatever the number of tiles.
Tile selection already reads each root's full world matrix, scale included (camera.get_view_state), so the right
tiles follow on the next tick.

  wheel              zoom about the point under the cursor. Near the ground it moves the view; once the eye is
                     more than D_FAR away it scales the Globe instead, so view distances and clip ranges stay small
  middle drag        orbit and tilt around the point under the cursor, about the local vertical there
  Shift+middle drag  grab the globe: it turns about the Earth's centre so the grabbed point stays under the cursor
                     (close to the ground that is a pan)

Everything else passes through to Blender. Objects parented to the Globe Empty move with it.

The point under the cursor comes from the viewport's depth buffer, copied on each redraw while the mode is on;
where nothing is drawn, from a sphere through the scene origin.

Re-anchor: once the gestures stop, the Globe's transform is folded into a new scene origin under the view, and
the loaded tiles are placed again from their ECEF matrices in double precision. Tile coordinates stay small
however far the view has travelled. What you see does not move.
"""
from __future__ import annotations

import math
import time

import bpy
import numpy as np
from bpy.types import Operator, Panel
try:
    from mathutils import Matrix, Quaternion, Vector
except ImportError:                                  # the test suite imports the package without Blender
    Matrix = Quaternion = Vector = None

GLOBE = "OGC3D Globe"
D_FAR = 2000.0              # eye-to-cursor-point distance beyond which the wheel scales the Globe
ZOOM_STEP = 1.2
ORBIT_RAD_PER_PX = 0.0065
TILT_MIN, TILT_MAX = math.radians(0.5), math.radians(89.0)
REANCHOR_IDLE_S = 0.4
REANCHOR_MIN_M = 2000.0     # the view centre must be this far from the scene origin (metres on the ground)
MIN_SCALE = 1e-8

_nav = {"active": False, "draw": None, "depth": {}, "last_t": 0.0, "dirty": False, "drag": None,
        "last_view": None, "cap_ms": 0.0, "anchors": 0}


# ── matrices ───────────────────────────────────────────────────────────────────────────────────────────────────
def _np(m) -> np.ndarray:
    return np.array([list(r) for r in m], dtype=np.float64)


def _mx(a) -> Matrix:
    return Matrix([[float(v) for v in r] for r in a])


def _about(point, m3) -> np.ndarray:
    """4x4 of the 3x3 ``m3`` applied about ``point``."""
    M = np.eye(4)
    M[:3, :3] = m3
    M[:3, 3] = point - m3 @ point
    return M


def _rotation(a, b) -> np.ndarray:
    """3x3 rotation taking direction ``a`` to ``b`` by the shortest arc, in double precision: a metre of pan
    close to the ground is 1.5e-7 rad about the Earth's centre, below what single precision resolves."""
    a = a / np.linalg.norm(a)
    b = b / np.linalg.norm(b)
    v = np.cross(a, b)
    s, c = np.linalg.norm(v), float(a @ b)
    if s < 1e-300:
        return np.eye(3)
    k = v / s
    K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    ang = math.atan2(s, c)
    return np.eye(3) + math.sin(ang) * K + (1.0 - math.cos(ang)) * (K @ K)


def _E(lla) -> np.ndarray:
    from .tileset.native_backend import enu_from_ecef_matrix
    return enu_from_ecef_matrix(*lla)


# ── the Globe Empty ────────────────────────────────────────────────────────────────────────────────────────────
def globe(create_in=None):
    """The Globe Empty, or None. ``create_in`` = a scene: make it and adopt the tileset roots."""
    g = bpy.data.objects.get(GLOBE)
    if g is not None or create_in is None:
        return g
    g = bpy.data.objects.new(GLOBE, None)
    g.empty_display_type = "SPHERE"
    g.empty_display_size = 1.0
    g["ogc3dtiles_globe"] = True
    create_in.collection.objects.link(g)
    for o in bpy.data.objects:
        if o.get("ogc3dtiles_root") and o.parent is None:
            adopt_root(o, fresh=False)
    return g


def adopt_root(root, fresh: bool) -> None:
    """Parent a tileset root to the Globe. A root just made sits in the scene-origin frame, which the Globe
    carries: it takes the Globe's transform. One that existed keeps its place in the world."""
    g = globe()
    if g is None or root.parent is not None or root is g:
        return
    world = root.matrix_world.copy()
    root.parent = g
    root.matrix_parent_inverse = Matrix.Identity(4)
    if not fresh:
        root.matrix_world = world


def globe_scale(g=None) -> float:
    g = g or globe()
    if g is None:
        return 1.0
    s = g.matrix_world.to_scale()
    return (abs(s.x) + abs(s.y) + abs(s.z)) / 3.0


def _earth_centre(G, props) -> np.ndarray:
    """The Earth's centre in the Blender world."""
    from .tileset.origin import origin_lla
    return (G @ _E(origin_lla(props))[:, 3])[:3]


def _under_globe(obj) -> bool:
    while obj is not None:
        if obj.name == GLOBE:
            return True
        obj = obj.parent
    return False


# ── the point under the cursor ─────────────────────────────────────────────────────────────────────────────────
def _capture():
    """Draw callback: keep this region's depth buffer and the matrices it was drawn with."""
    if not _nav["active"]:
        return
    try:
        import gpu
        ctx = bpy.context
        region, rv3d = ctx.region, ctx.region_data
        g = globe()
        if region is None or rv3d is None or g is None:
            return
        t0 = time.perf_counter()
        w, h = region.width, region.height
        buf = gpu.state.active_framebuffer_get().read_depth(0, 0, w, h)
        depth = np.frombuffer(buf, dtype=np.float32).reshape(h, w).copy()
        _nav["depth"][region.as_pointer()] = {
            "depth": depth, "inv": np.linalg.inv(_np(rv3d.perspective_matrix)), "Ginv": np.linalg.inv(_np(g.matrix_world)),
            "w": w, "h": h}
        _nav["cap_ms"] = (time.perf_counter() - t0) * 1000.0
    except Exception as e:                           # noqa: BLE001 — never break the viewport's drawing
        _nav["cap_err"] = str(e)


def _ray(region, rv3d, x, y):
    from bpy_extras import view3d_utils
    o = view3d_utils.region_2d_to_origin_3d(region, rv3d, (x, y))
    d = view3d_utils.region_2d_to_vector_3d(region, rv3d, (x, y))
    return np.array(o, dtype=np.float64), np.array(d, dtype=np.float64)


def _ray_sphere(o, d, c, r):
    """Nearest hit in front of the ray's origin, or None."""
    d = d / np.linalg.norm(d)
    oc = o - c
    b = float(oc @ d)
    disc = b * b - (float(oc @ oc) - r * r)
    if disc < 0.0:
        return None
    t = -b - math.sqrt(disc)
    if t <= 0.0:
        t = -b + math.sqrt(disc)
    return o + t * d if t > 0.0 else None


def pick(scene, region, rv3d, x, y):
    """World position under region pixel (x, y): the drawn surface, else the sphere through the scene origin."""
    g = globe()
    if g is None:
        return None
    G = _np(g.matrix_world)
    c = _nav["depth"].get(region.as_pointer())
    if c is not None and c["w"] == region.width and c["h"] == region.height and 0 <= x < c["w"] and 0 <= y < c["h"]:
        win = c["depth"][max(y - 2, 0):y + 3, max(x - 2, 0):x + 3]
        d = float(win.min())
        if 0.0 < d < 0.999999:
            ndc = np.array([2.0 * (x + 0.5) / c["w"] - 1.0, 2.0 * (y + 0.5) / c["h"] - 1.0, 2.0 * d - 1.0, 1.0])
            p = c["inv"] @ ndc
            p = np.append(p[:3] / p[3], 1.0)
            return (G @ (c["Ginv"] @ p))[:3]         # the world may have moved since that redraw
    o, d = _ray(region, rv3d, x, y)
    centre = _earth_centre(G, scene.ogc3dtiles)
    return _ray_sphere(o, d, centre, float(np.linalg.norm(G[:3, 3] - centre)))


# ── the view: a viewport, or the camera of a locked camera view ────────────────────────────────────────────────
class _View:
    def __init__(self, space, rv3d):
        self.space, self.rv3d = space, rv3d
        self.cam = None
        if rv3d.view_perspective == "CAMERA":
            if space.camera is None or not space.lock_camera:
                raise ValueError("camera view without Lock Camera to View")
            self.cam = space.camera
        self.save()

    def save(self):
        if self.cam is not None:
            self.m0 = self.cam.matrix_world.copy()
            self.ortho0 = self.cam.data.ortho_scale
        else:
            self.loc0 = self.rv3d.view_location.copy()
            self.rot0 = self.rv3d.view_rotation.copy()
            self.dist0 = self.rv3d.view_distance

    def restore(self):
        if self.cam is not None:
            self.cam.matrix_world = self.m0
            self.cam.data.ortho_scale = self.ortho0
        else:
            self.rv3d.view_location, self.rv3d.view_rotation = self.loc0, self.rot0
            self.rv3d.view_distance = self.dist0

    def eye(self) -> Vector:
        if self.cam is not None:
            return self.cam.matrix_world.translation.copy()
        return self.rv3d.view_location + self.rv3d.view_rotation @ Vector((0.0, 0.0, self.rv3d.view_distance))

    def rot(self) -> Quaternion:
        return self.cam.matrix_world.to_quaternion() if self.cam is not None else self.rv3d.view_rotation.copy()

    def persp(self) -> bool:
        return self.cam.data.type != "ORTHO" if self.cam is not None else bool(self.rv3d.is_perspective)

    def distance_to(self, p) -> float:
        if not self.persp():
            return self.cam.data.ortho_scale if self.cam is not None else self.rv3d.view_distance
        return (self.eye() - Vector(p)).length

    def follows_globe(self) -> bool:
        return self.cam is not None and _under_globe(self.cam)

    def dolly(self, p, k):
        """Move towards ``p`` so that it looks k times bigger (k < 1: away)."""
        p = Vector(p)
        if self.cam is not None:
            m = self.cam.matrix_world.copy()
            m.translation = p + (m.translation - p) / k
            self.cam.matrix_world = m
            if self.cam.data.type == "ORTHO":
                self.cam.data.ortho_scale /= k
        else:
            self.rv3d.view_location = p + (self.rv3d.view_location - p) / k
            self.rv3d.view_distance /= k
            self.space.clip_end = max(self.space.clip_end, 4.0 * self.rv3d.view_distance)

    def orbit(self, p, up, yaw, pitch):
        """From the saved state: pitch about the view's right axis, then yaw about ``up``, both through ``p``."""
        p, up = Vector(p), Vector(up)
        rot0 = self.m0.to_quaternion() if self.cam is not None else self.rot0
        right = rot0 @ Vector((1.0, 0.0, 0.0))
        q = Quaternion(up, yaw) @ Quaternion(right, pitch)
        if self.cam is not None:
            self.cam.matrix_world = Matrix.Translation(p) @ q.to_matrix().to_4x4() @ Matrix.Translation(-p) @ self.m0
        else:
            eye0 = self.loc0 + rot0 @ Vector((0.0, 0.0, self.dist0))
            rot = q @ rot0
            self.rv3d.view_rotation = rot
            self.rv3d.view_location = p + q @ (eye0 - p) - rot @ Vector((0.0, 0.0, self.dist0))


def _set_globe(context, g, G, view=None):
    """Write the Globe's matrix. A locked camera parented to the Globe keeps its place: it is the view."""
    cam_m = view.cam.matrix_world.copy() if view is not None and view.follows_globe() else None
    g.matrix_world = _mx(G)
    if cam_m is not None:
        context.view_layer.update()
        view.cam.matrix_world = cam_m


# ── gestures ───────────────────────────────────────────────────────────────────────────────────────────────────
def zoom(context, view, p, factor):
    """``factor`` > 1 zooms in. Moves the view near the ground, scales the Globe far from it; the image is the
    same either way (scaling the world about a point equals moving the eye towards it)."""
    g = globe()
    s = globe_scale(g)
    scale_k = 1.0
    if not view.follows_globe():
        if factor > 1.0 and s < 1.0:
            scale_k = min(factor, 1.0 / s)                 # back up to 1:1 first
        elif factor < 1.0 and view.distance_to(p) / factor > D_FAR and s * factor >= MIN_SCALE:
            scale_k = factor
    if scale_k != 1.0:
        _set_globe(context, g, _about(np.asarray(p, dtype=np.float64), np.eye(3) * scale_k) @ _np(g.matrix_world), view)
    rest = factor / scale_k
    if abs(rest - 1.0) > 1e-9:
        view.dolly(p, rest)


def _local_up(context, p) -> np.ndarray:
    g = globe()
    up = np.asarray(p, dtype=np.float64) - _earth_centre(_np(g.matrix_world), context.scene.ogc3dtiles)
    return up / np.linalg.norm(up)


def orbit_update(drag, dx, dy):
    view, up = drag["view"], Vector(drag["up"])
    rot0 = view.m0.to_quaternion() if view.cam is not None else view.rot0
    fwd = rot0 @ Vector((0.0, 0.0, -1.0))
    right = rot0 @ Vector((1.0, 0.0, 0.0))
    tilt0 = fwd.angle(-up, 0.0)                            # 0 = straight down
    probe = (Quaternion(right, 0.01) @ fwd).angle(-up, 0.0) - tilt0
    sign = 1.0 if probe >= 0.0 else -1.0
    tilt = min(max(tilt0 + dy * ORBIT_RAD_PER_PX, TILT_MIN), max(TILT_MAX, tilt0))
    view.orbit(drag["p"], up, -dx * ORBIT_RAD_PER_PX, sign * (tilt - tilt0))


def grab_update(context, drag, region, rv3d, x, y):
    o, d = _ray(region, rv3d, x, y)
    c, r = drag["centre"], drag["radius"]
    hit = _ray_sphere(o, d, c, r)
    if hit is None:                                        # the cursor left the globe: the limb point nearest to it
        d = d / np.linalg.norm(d)
        q = o + max(float((c - o) @ d), 0.0) * d - c
        hit = c + r * q / np.linalg.norm(q)
    R = _rotation(drag["p"] - drag["centre"], hit - drag["centre"])
    _set_globe(context, globe(), _about(drag["centre"], R) @ drag["G0"], drag["view"])


# ── re-anchor ──────────────────────────────────────────────────────────────────────────────────────────────────
def reanchor(context, anchor_world) -> bool:
    """Make the point ``anchor_world`` the scene origin, without moving anything on screen. The Globe ends up as
    that point's east-north-up frame (times its scale); tiles are placed again from their ECEF matrices."""
    from . import ui
    from .tileset.origin import origin_lla, set_origin
    from .tileset.traversal import ecef_to_geodetic
    scene = context.scene
    props = scene.ogc3dtiles
    g = globe()
    if g is None or ui.is_local_origin(props) or not props.origin_valid:
        return False
    G0 = _np(g.matrix_world)
    E0 = _E(origin_lla(props))
    W = G0 @ E0                                            # ECEF -> world; stays the same
    a = np.linalg.solve(W, np.append(np.asarray(anchor_world, dtype=np.float64), 1.0))
    lat, lon, h = ecef_to_geodetic(float(a[0]), float(a[1]), float(a[2]))
    E1 = _E((lat, lon, h))
    G1 = W @ np.linalg.inv(E1)
    D = E1 @ np.linalg.inv(E0)                             # old frame -> new frame

    streams = [st for st in ui._state["streams"].values()]
    geo_roots, holders = set(), {}
    for st in streams:
        if st.get("frame") is None and st.get("root_obj"):
            geo_roots.add(st["root_obj"])
            for rec in st["tiles"].values():
                holders[rec.holder] = getattr(rec, "ecef", None)
    keep = []                                              # everything else keeps its place in the world
    for o in bpy.data.objects:
        par = o.parent
        if par is None or o.name in holders:
            continue
        if (par.name == GLOBE and o.name not in geo_roots) or par.name in geo_roots:
            keep.append((o, o.matrix_world.copy()))

    set_origin(props, lat, lon, h)
    g.matrix_world = _mx(G1)
    for name, ecef in holders.items():
        o = bpy.data.objects.get(name)
        if o is None:
            continue
        o.matrix_basis = _mx(E1 @ ecef if ecef is not None else D @ _np(o.matrix_basis))
    context.view_layer.update()
    for o, world in keep:
        o.matrix_world = world
    for st in streams:
        st["last_sig"] = None
    _nav["anchors"] += 1
    return True


def _view_anchor(context, region, rv3d):
    """Where the view looks: the surface at the middle of the region."""
    return pick(context.scene, region, rv3d, region.width // 2, region.height // 2)


def _maybe_reanchor(context):
    lv = _nav.get("last_view")
    if not _nav["dirty"] or _nav["drag"] is not None or lv is None or time.monotonic() - _nav["last_t"] < REANCHOR_IDLE_S:
        return
    _nav["dirty"] = False
    try:
        region, rv3d = lv
        a = _view_anchor(context, region, rv3d)
        g = globe()
        if a is None or g is None:
            return
        local = np.linalg.solve(_np(g.matrix_world), np.append(a, 1.0))[:3]     # metres from the scene origin
        if float(np.linalg.norm(local)) >= REANCHOR_MIN_M:
            reanchor(context, a)
    except ReferenceError:
        _nav["last_view"] = None


# ── operators ──────────────────────────────────────────────────────────────────────────────────────────────────
def _view3d_at(context, event):
    """(area, region, space) of the 3D viewport under the mouse, None over its header, toolbar or sidebar."""
    x, y = event.mouse_x, event.mouse_y
    for area in context.window.screen.areas:
        if area.type != "VIEW_3D" or not (area.x <= x < area.x + area.width and area.y <= y < area.y + area.height):
            continue
        hit = None
        for r in area.regions:
            if r.width <= 1 or r.height <= 1 or not (r.x <= x < r.x + r.width and r.y <= y < r.y + r.height):
                continue
            if r.type != "WINDOW":
                return None
            hit = r
        if hit is not None and hit.data is not None:
            return area, hit, area.spaces.active
    return None


class OGC3D_OT_GlobeNav(Operator):
    """Navigate like a globe: the wheel zooms about the cursor, middle drag orbits around the point under it, Shift+middle drag grabs the globe. Click again to stop"""
    bl_idname = "ogc3dtiles.globe_nav"
    bl_label = "Globe Navigation"

    def invoke(self, context, event):
        if _nav["active"]:
            _nav["active"] = False                         # the running instance ends on its next event
            return {"FINISHED"}
        if context.scene.ogc3dtiles is None:
            return {"CANCELLED"}
        globe(create_in=context.scene)
        _nav.update(active=True, drag=None, dirty=False, depth={})
        if _nav["draw"] is None:
            _nav["draw"] = bpy.types.SpaceView3D.draw_handler_add(_capture, (), "WINDOW", "POST_VIEW")
        self._timer = context.window_manager.event_timer_add(0.2, window=context.window)
        context.window_manager.modal_handler_add(self)
        for a in context.window.screen.areas:
            a.tag_redraw()
        return {"RUNNING_MODAL"}

    def _end(self, context):
        context.window_manager.event_timer_remove(self._timer)
        if _nav["draw"] is not None:
            bpy.types.SpaceView3D.draw_handler_remove(_nav["draw"], "WINDOW")
            _nav["draw"] = None
        _nav.update(active=False, drag=None, depth={})
        for a in context.window.screen.areas:
            a.tag_redraw()
        return {"FINISHED"}

    def modal(self, context, event):
        if not _nav["active"]:
            return self._end(context)
        if event.type == "TIMER":
            _maybe_reanchor(context)
            return {"PASS_THROUGH"}
        drag = _nav["drag"]
        if drag is not None:
            return self._drag(context, event, drag)
        if event.ctrl or event.alt or event.oskey:
            return {"PASS_THROUGH"}
        wheel = event.type in {"WHEELUPMOUSE", "WHEELDOWNMOUSE"} and not event.shift
        press = event.type == "MIDDLEMOUSE" and event.value == "PRESS"
        if not (wheel or press):
            return {"PASS_THROUGH"}
        at = _view3d_at(context, event)
        if at is None:
            return {"PASS_THROUGH"}
        area, region, space = at
        rv3d = region.data
        try:
            view = _View(space, rv3d)
        except ValueError:
            return {"PASS_THROUGH"}
        x, y = event.mouse_x - region.x, event.mouse_y - region.y
        p = pick(context.scene, region, rv3d, x, y)
        if p is None:
            return {"PASS_THROUGH"}
        _nav["last_view"] = (region, rv3d)
        if wheel:
            zoom(context, view, p, ZOOM_STEP if event.type == "WHEELUPMOUSE" else 1.0 / ZOOM_STEP)
            self._changed(area)
            return {"RUNNING_MODAL"}
        g = globe()
        G0 = _np(g.matrix_world)
        centre = _earth_centre(G0, context.scene.ogc3dtiles)
        _nav["drag"] = {"kind": "GRAB" if event.shift else "ORBIT", "view": view, "p": p, "x": event.mouse_x,
                        "y": event.mouse_y, "area": area, "region": region, "rv3d": rv3d, "G0": G0,
                        "centre": centre, "radius": float(np.linalg.norm(p - centre)), "up": _local_up(context, p)}
        return {"RUNNING_MODAL"}

    def _drag(self, context, event, drag):
        if event.type == "MOUSEMOVE":
            if drag["kind"] == "ORBIT":
                orbit_update(drag, event.mouse_x - drag["x"], event.mouse_y - drag["y"])
            else:
                grab_update(context, drag, drag["region"], drag["rv3d"],
                            event.mouse_x - drag["region"].x, event.mouse_y - drag["region"].y)
            self._changed(drag["area"])
        elif event.type == "MIDDLEMOUSE" and event.value == "RELEASE":
            _nav["drag"] = None
        elif event.type in {"ESC", "RIGHTMOUSE"} and event.value == "PRESS":
            drag["view"].restore()
            _set_globe(context, globe(), drag["G0"], drag["view"])
            _nav["drag"] = None
            self._changed(drag["area"])
        return {"RUNNING_MODAL"}

    @staticmethod
    def _changed(area):
        _nav["last_t"] = time.monotonic()
        _nav["dirty"] = True
        area.tag_redraw()


def _context_view(context):
    space = context.space_data
    if space is None or space.type != "VIEW_3D":
        return None
    region = next((r for r in context.area.regions if r.type == "WINDOW"), None)
    return (region, space.region_3d, space) if region is not None else None


class OGC3D_OT_GlobeScaleReset(Operator):
    """Scale the Globe back to 1:1 about the point the view looks at, and move the view away to match: nothing changes on screen. Do this before rendering or exporting, where metres must be metres"""
    bl_idname = "ogc3dtiles.globe_scale_reset"
    bl_label = "Globe Scale to 1:1"

    def execute(self, context):
        g, cv = globe(), _context_view(context)
        if g is None or cv is None:
            return {"CANCELLED"}
        region, rv3d, space = cv
        s = globe_scale(g)
        if abs(s - 1.0) < 1e-9:
            return {"FINISHED"}
        try:
            view = _View(space, rv3d)
        except ValueError:
            self.report({"WARNING"}, "Leave the camera view, or turn Lock Camera to View on")
            return {"CANCELLED"}
        p = _view_anchor(context, region, rv3d)
        if p is None:
            p = np.array(rv3d.view_location, dtype=np.float64)
        _set_globe(context, g, _about(p, np.eye(3) / s) @ _np(g.matrix_world), view)
        if not view.follows_globe():
            view.dolly(p, s)
        _nav["dirty"] = True
        _nav["last_t"] = time.monotonic()
        context.area.tag_redraw()
        return {"FINISHED"}


class OGC3D_OT_GlobeReanchor(Operator):
    """Move the scene origin under the view and place the loaded tiles again in double precision. Nothing moves on screen. Globe navigation does this by itself when the gestures stop"""
    bl_idname = "ogc3dtiles.globe_reanchor"
    bl_label = "Re-anchor Scene Origin"

    def execute(self, context):
        cv = _context_view(context)
        if cv is None or globe(create_in=context.scene) is None:
            return {"CANCELLED"}
        region, rv3d, _space = cv
        a = _view_anchor(context, region, rv3d)
        if a is None:
            a = np.array(rv3d.view_location, dtype=np.float64)
        if not reanchor(context, a):
            self.report({"WARNING"}, "No georeferenced scene origin to move")
            return {"CANCELLED"}
        context.area.tag_redraw()
        return {"FINISHED"}


class OGC3D_OT_GlobeParent(Operator):
    """Parent the selected objects to the Globe, in place, so they move with the planet"""
    bl_idname = "ogc3dtiles.globe_parent"
    bl_label = "Parent Selection to Globe"

    def execute(self, context):
        g = globe(create_in=context.scene)
        n = 0
        for o in context.selected_objects:
            if o is g or o.parent is not None or o.get("ogc3dtiles_root"):
                continue
            world = o.matrix_world.copy()
            o.parent = g
            o.matrix_parent_inverse = g.matrix_world.inverted()
            o.matrix_world = world
            n += 1
        self.report({"INFO"}, f"{n} object(s) parented to {GLOBE}")
        return {"FINISHED"}


class OGC3D_PT_GlobeNav(Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "3D Tiles"
    bl_label = "Globe Navigation (beta)"
    bl_idname = "OGC3D_PT_globe_nav"
    bl_order = 8
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return hasattr(context.scene, "ogc3dtiles")

    def draw(self, context):
        layout = self.layout
        on = _nav["active"]
        layout.operator("ogc3dtiles.globe_nav", text="Stop Globe Navigation" if on else "Globe Navigation",
                        icon="PAUSE" if on else "WORLD", depress=on)
        g = globe()
        if g is None:
            layout.label(text="Makes an Empty that carries every tileset", icon="INFO")
            return
        col = layout.column(align=True)
        col.label(text="Wheel: zoom about the cursor")
        col.label(text="Middle drag: orbit around the point")
        col.label(text="Shift + middle drag: grab the globe")
        s = globe_scale(g)
        row = layout.row(align=True)
        row.label(text="World scale 1:1" if abs(s - 1.0) < 1e-6 else f"World scale 1:{1.0 / s:,.0f}")
        sub = row.row(align=True)
        sub.enabled = abs(s - 1.0) > 1e-6
        sub.operator("ogc3dtiles.globe_scale_reset", text="To 1:1")
        layout.operator("ogc3dtiles.globe_reanchor", icon="PIVOT_CURSOR")
        layout.operator("ogc3dtiles.globe_parent", icon="CON_CHILDOF")


_classes = (OGC3D_OT_GlobeNav, OGC3D_OT_GlobeScaleReset, OGC3D_OT_GlobeReanchor, OGC3D_OT_GlobeParent,
            OGC3D_PT_GlobeNav)


def register():
    for c in _classes:
        bpy.utils.register_class(c)


def unregister():
    _nav["active"] = False
    if _nav["draw"] is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_nav["draw"], "WINDOW")
        _nav["draw"] = None
    for c in reversed(_classes):
        bpy.utils.unregister_class(c)
