"""
Camera binding: Blender viewport → traversal ViewState (ECEF).

Reads the largest 3D viewport's ``region_3d`` (view matrix + window matrix
+ pixel size), or the scene camera or a chosen camera at the render resolution
(``view_source``), and converts it into:
  - camera position / direction / up in ECEF,
  - the projection entries p00 / p11 (exact FOV, not a guess),
  - the six frustum planes in ECEF for culling,
  - a cheap signature so the traversal only re-runs when the view changed.
"""
from __future__ import annotations

import math

import bpy
from typing import NamedTuple

# while a render waits for a frame's tiles: (evaluated camera, render depsgraph) on the command line, or
# {"src": the tuple of _source()} for an F12 render in the window
RENDER_CAMERA = [None]

from ..tileset.origin import origin_lla
from ..tileset.traversal import (
    ViewState,
    blender_to_ecef,
    build_enu_to_ecef_matrix,
    frustum_planes_from_matrix,
    rotate_enu_to_ecef,
    transform_planes,
)


def find_view3d():
    """(region_3d, region) of the largest VIEW_3D window region, or (None, None)."""
    best = None
    best_area = -1
    wm = bpy.context.window_manager
    if wm is None:
        return None, None
    for window in wm.windows:
        screen = window.screen
        if screen is None:
            continue
        for area in screen.areas:
            if area.type != "VIEW_3D":
                continue
            space = area.spaces.active
            if space is None or space.type != "VIEW_3D":
                continue
            for region in area.regions:
                if region.type == "WINDOW" and region.width * region.height > best_area:
                    best_area = region.width * region.height
                    best = (space.region_3d, region)
    return best if best else (None, None)


def border_view(view, win, w, hpx, is_persp, render):
    """The camera view narrowed to the render border (Ctrl+B in a camera view), so a stream that follows a camera
    loads the tiles of the part that renders. Returns (view, win, w, hpx, border signature); the inputs unchanged
    without a border. Perspective: a symmetric view aimed at the border's centre that covers its four corners, at
    the pixel density the full frame has there (the backends take a symmetric field of view, not an off-centre one).
    Orthographic: the frame moved and shrunk to the border."""
    if not getattr(render, "use_border", False):
        return view, win, w, hpx, ()
    x0, x1 = float(render.border_min_x), float(render.border_max_x)
    y0, y1 = float(render.border_min_y), float(render.border_max_y)
    if x1 - x0 < 1e-4 or y1 - y0 < 1e-4 or (x0 <= 0.0 and y0 <= 0.0 and x1 >= 1.0 and y1 >= 1.0):
        return view, win, w, hpx, ()
    import mathutils
    sig = (round(x0, 4), round(y0, 4), round(x1, 4), round(y1, 4))
    n = [2.0 * v - 1.0 for v in (x0, x1, y0, y1)]             # NDC: left, right, bottom, top
    p00, p11 = float(win[0][0]), float(win[1][1])
    win = win.copy()
    if not is_persp:
        cx = ((n[0] + n[1]) / 2.0 - win[0][3]) / p00
        cy = ((n[2] + n[3]) / 2.0 - win[1][3]) / p11
        win[0][0] = p00 * 2.0 / (n[1] - n[0]); win[0][3] = 0.0
        win[1][1] = p11 * 2.0 / (n[3] - n[2]); win[1][3] = 0.0
        move = mathutils.Matrix.Translation((-cx, -cy, 0.0))
        return move @ view, win, max(int(w * (x1 - x0)), 1), max(int(hpx * (y1 - y0)), 1), sig

    def ray(nx, ny):                                          # camera space, through an NDC point
        return mathutils.Vector(((nx + win[0][2]) / p00, (ny + win[1][2]) / p11, -1.0))
    f = ray((n[0] + n[1]) / 2.0, (n[2] + n[3]) / 2.0).normalized()
    r_ = f.cross(mathutils.Vector((0.0, 1.0, 0.0))).normalized()
    u = r_.cross(f)
    hx = hy = 1e-6
    for nx in n[:2]:
        for ny in n[2:]:
            d = ray(nx, ny)
            hx = max(hx, abs(d.dot(r_) / d.dot(f))); hy = max(hy, abs(d.dot(u) / d.dot(f)))
    turn = mathutils.Matrix((r_, u, -f)).to_4x4()             # old camera space -> the narrowed camera's
    cos2 = max(f.z * f.z, 1e-6)                               # pixels per radian grow off-axis by 1 / cos^2
    win[0][0] = 1.0 / hx; win[0][2] = 0.0
    win[1][1] = 1.0 / hy; win[1][2] = 0.0
    return (turn @ view, win, max(int(hx * w * p00 / cos2), 1), max(int(hy * hpx * p11 / cos2), 1), sig)


class CesiumCameraAdapter:
    """Wraps a Blender SpaceView3D and exposes the view in ECEF."""

    def __init__(self, scene: bpy.types.Scene):
        self.scene = scene

    # ── full view state ──────────────────────────────────────────────────────

    def get_view_state(self, root_obj=None, frame=None) -> ViewState | None:
        """``root_obj`` is the per-tileset root Empty: tiles live in its local
        space (ENU), so the camera is expressed there too. Moving / rotating /
        scaling the Empty is therefore honoured by culling and SSE. ``frame``
        is the stream's own (lat, lon, h) anchor when it differs from the
        scene origin (a tileset that isn't georeferenced)."""
        props = self.scene.ogc3dtiles
        src = self._source(props)
        if src is None:
            return None
        view, win, w, hpx, is_persp, src_sig, pano = src
        lat, lon, h = frame or origin_lla(props)
        root_sig = ()
        root_scale = 1.0
        if root_obj is not None:
            mw = root_obj.matrix_world
            view = view @ mw              # ENU (root local) → view
            sc = mw.to_scale()
            root_scale = max((abs(sc.x) + abs(sc.y) + abs(sc.z)) / 3.0, 1e-9)
            root_sig = tuple(round(v, 4) for row in mw for v in row)
        inv = view.inverted()
        pos_enu = inv.translation
        fwd_enu = inv.to_3x3() @ _V((0.0, 0.0, -1.0))
        up_enu = inv.to_3x3() @ _V((0.0, 1.0, 0.0))
        # orthographic: the eye stays on the pivot (Blender's view matrix puts
        # it there); the backend gets the frame's half extents instead of a fov,
        # so tiles behind the pivot are selected too, as Blender draws them

        # frustum planes: clip = win @ view (ENU) → ECEF
        clip = win @ view
        planes_enu = frustum_planes_from_matrix([list(clip[i]) for i in range(4)])
        enu2ecef = build_enu_to_ecef_matrix(lat, lon, h)
        rot = [row[:3] for row in enu2ecef[:3]]
        origin = (enu2ecef[0][3], enu2ecef[1][3], enu2ecef[2][3])
        planes = transform_planes(planes_enu, rot, origin)

        pos = blender_to_ecef(tuple(pos_enu), lat, lon, h)
        direction = rotate_enu_to_ecef(tuple(fwd_enu.normalized()), lat, lon)
        up = rotate_enu_to_ecef(tuple(up_enu.normalized()), lat, lon)
        p11 = float(win[1][1]) if abs(win[1][1]) > 1e-9 else 1.0
        p00 = float(win[0][0]) if abs(win[0][0]) > 1e-9 else p11 * hpx / w
        if not is_persp:
            # perspective SSE is scale invariant (error and distance both
            # scale); orthographic is not, so fold the root scale in here
            p11 *= root_scale
            p00 *= root_scale
        sig = (tuple(round(v, 1) for v in pos_enu), tuple(round(v, 3) for v in fwd_enu),
               w, hpx, round(p11, 4), is_persp, root_sig, src_sig)
        if pano is not None:
            face_px, face_dirs = pano
            rot3 = inv.to_3x3()
            faces = [(rotate_enu_to_ecef(tuple((rot3 @ _V(d)).normalized()), lat, lon),
                      rotate_enu_to_ecef(tuple((rot3 @ _V(u)).normalized()), lat, lon))
                     for d, u in face_dirs]
            return ViewState(position=pos, direction=direction, up=up,
                             viewport_width=face_px, viewport_height=face_px,
                             p11=1.0, p00=1.0, is_persp=True,
                             frustum_planes=None, signature=sig, faces=faces)
        return ViewState(position=pos, direction=direction, up=up,
                         viewport_width=w, viewport_height=hpx,
                         p11=p11, p00=p00, is_persp=is_persp,
                         frustum_planes=planes, signature=sig)

    def _source(self, props, force_camera=False):
        """(view_matrix, window_matrix, width_px, height_px, is_persp,
        signature) from the 3D viewport, or at the render
        resolution from the scene camera (``view_source`` CAMERA) or from the
        camera the user chose (OBJECT)."""
        scene = self.scene
        source = getattr(props, "view_source", "VIEWPORT")
        cam = (scene.camera if source == "CAMERA"
               else getattr(props, "view_camera", None) if source == "OBJECT" else None)
        if isinstance(RENDER_CAMERA[0], dict):
            # an F12 render in the window: the frame's view, read on the render thread
            return RENDER_CAMERA[0]["src"] if source == "CAMERA" else None
        if RENDER_CAMERA[0] is not None and (source == "CAMERA" or force_camera):
            # a command-line render: the camera as the render depsgraph evaluated it for this frame
            # (the original object keeps the frame the file was saved at)
            cam, dg = RENDER_CAMERA[0]
            r = scene.render
            w = max(int(r.resolution_x * r.resolution_percentage / 100), 1)
            hpx = max(int(r.resolution_y * r.resolution_percentage / 100), 1)
            win = cam.calc_matrix_camera(dg, x=w, y=hpx, scale_x=r.pixel_aspect_x, scale_y=r.pixel_aspect_y)
            pano = panorama_faces(cam.data, w, hpx) if cam.data.type == "PANO" else None
            view, bsig = cam.matrix_world.inverted(), ()
            if pano is None:
                view, win, w, hpx, bsig = border_view(view, win, w, hpx, cam.data.type != "ORTHO", r)
            return (view, win, w, hpx, cam.data.type != "ORTHO",
                    ("CAM", cam.name, scene.frame_current, pano[0] if pano else 0, bsig), pano)
        if cam is not None:
            r = scene.render
            w = max(int(r.resolution_x * r.resolution_percentage / 100), 1)
            hpx = max(int(r.resolution_y * r.resolution_percentage / 100), 1)
            try:
                dg = bpy.context.evaluated_depsgraph_get()
                win = cam.calc_matrix_camera(dg, x=w, y=hpx,
                                             scale_x=r.pixel_aspect_x, scale_y=r.pixel_aspect_y)
            except Exception:                 # noqa: BLE001 — no context in some handlers
                return None
            view = cam.matrix_world.inverted()
            pano = panorama_faces(cam.data, w, hpx) if cam.data.type == "PANO" else None
            bsig = ()
            if pano is None:
                view, win, w, hpx, bsig = border_view(view, win, w, hpx, cam.data.type != "ORTHO", r)
            return (view, win, w, hpx, cam.data.type != "ORTHO",
                    ("CAM", cam.name, scene.frame_current, pano[0] if pano else 0, bsig), pano)
        r3d, region = find_view3d()
        if r3d is None:
            return None
        return (r3d.view_matrix, r3d.window_matrix, max(int(region.width), 1),
                max(int(region.height), 1), bool(r3d.is_perspective), ("VIEW",), None)

    # ── legacy helpers (kept for callers/tests) ──────────────────────────────

    def get_camera_ecef(self) -> tuple:
        vs = self.get_view_state()
        return vs.position if vs else (0.0, 0.0, 0.0)

    def get_fov_y(self) -> float:
        vs = self.get_view_state()
        return vs.fov_y if vs else math.radians(50.0)

    def get_screen_height(self) -> int:
        vs = self.get_view_state()
        return vs.viewport_height if vs else 1080

    def get_view_direction_ecef(self) -> tuple:
        vs = self.get_view_state()
        return vs.direction if vs else (0.0, 0.0, -1.0)


def _V(t):
    import mathutils
    return mathutils.Vector(t)


# cube faces in camera space (Blender cameras look down -Z, Y up): direction, up
CUBE_FACES = (
    ((0.0, 0.0, -1.0), (0.0, 1.0, 0.0)),    # front
    ((0.0, 0.0, 1.0), (0.0, 1.0, 0.0)),     # back
    ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),     # right
    ((-1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),    # left
    ((0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),     # up
    ((0.0, -1.0, 0.0), (0.0, 0.0, -1.0)),   # down
)
_FACE_HALF_DIAGONAL = math.atan(math.sqrt(2.0))   # 54.7 deg: face centre to corner


def panorama_faces(cam_data, width_px, height_px):
    """(face_px, [(direction, up)]) of the 90 degree cube faces that cover a
    panoramic camera, in camera space. Each face gets the panorama's angular
    resolution at its centre (an equirectangular image W px wide over 360
    degrees: W / 4 px per face, or more when its height is finer per degree), so tiles are as detailed as the render needs
    there. Fisheye cameras drop the faces entirely outside their field of view."""
    ptype = getattr(cam_data, "panorama_type", "EQUIRECTANGULAR")
    w, h = max(int(width_px), 1), max(int(height_px), 1)
    span = None                                  # field of view, radians
    if ptype == "EQUIRECTANGULAR":
        # the finer of the two axes: a 1:1 image over 360 x 180 degrees has
        # twice the pixels per degree vertically
        lon = float(cam_data.longitude_max) - float(cam_data.longitude_min)
        lat = float(cam_data.latitude_max) - float(cam_data.latitude_min)
        px_per_rad = max(w / max(lon, 1e-3), h / max(lat, 1e-3))
    elif ptype == "CENTRAL_CYLINDRICAL":
        lon = float(cam_data.longitude_max) - float(cam_data.longitude_min)
        px_per_rad = w / max(lon, 1e-3)
    elif ptype in ("FISHEYE_EQUIDISTANT", "FISHEYE_EQUISOLID"):
        span = float(cam_data.fisheye_fov)
        px_per_rad = min(w, h) / max(span, 1e-3)
    elif ptype == "EQUIANGULAR_CUBEMAP_FACE":
        px_per_rad = w / (math.pi / 2.0)
    else:                                        # mirror ball, polynomial fisheye
        px_per_rad = w / (2.0 * math.pi)
    face_px = max(int(round(px_per_rad * math.pi / 2.0)), 1)
    faces = list(CUBE_FACES)
    if span is not None and span < 2.0 * math.pi:
        half = span / 2.0
        faces = [f for f in faces
                 if math.acos(max(-1.0, min(1.0, -f[0][2]))) - _FACE_HALF_DIAGONAL < half]
    return face_px, faces


def register():
    pass


def unregister():
    pass


class ViewFocus(NamedTuple):
    eye: tuple        # world
    dir: tuple        # unit vector from the scene towards the eye (world)
    dist: float       # eye → view pivot (orbit centre)
    p11: float        # window_matrix[1][1]
    height: int       # region height px
    persp: bool


def viewport_focus():
    """Eye, towards-eye direction, pivot distance and projection of the first
    3D viewport (point sizing / disc orientation).  None without a window."""
    r3d, region = find_view3d()
    if r3d is None:
        return None
    inv = r3d.view_matrix.inverted()
    win = r3d.window_matrix
    p11 = float(win[1][1]) if abs(win[1][1]) > 1e-9 else 1.0
    eye = inv.translation
    dist = float((eye - r3d.view_location).length) if r3d.is_perspective else 1.0
    return ViewFocus(tuple(eye), tuple(inv.col[2].xyz), max(dist, 1e-3), p11,
                     max(int(region.height), 1), bool(r3d.is_perspective))


def viewport_eye():
    """(eye_world, p11, viewport_height_px, is_persp) of the first 3D viewport,
    for screen-space point sizing. None without a window (``-b``)."""
    r3d, region = find_view3d()
    if r3d is None:
        return None
    inv = r3d.view_matrix.inverted()
    win = r3d.window_matrix
    p11 = float(win[1][1]) if abs(win[1][1]) > 1e-9 else 1.0
    return (tuple(inv.translation), p11, max(int(region.height), 1), bool(r3d.is_perspective))
