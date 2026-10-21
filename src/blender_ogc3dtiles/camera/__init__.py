"""
Camera binding: Blender viewport → traversal ViewState (ECEF).

Reads the largest 3D viewport's ``region_3d`` (view matrix + window matrix
+ pixel size) and converts it into:
  - camera position / direction / up in ECEF,
  - the projection entries p00 / p11 (exact FOV, not a guess),
  - the six frustum planes in ECEF for culling,
  - a cheap signature so the traversal only re-runs when the view changed.
"""
from __future__ import annotations

import math

import bpy
from typing import NamedTuple

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


class CesiumCameraAdapter:
    """Wraps a Blender SpaceView3D and exposes the view in ECEF."""

    def __init__(self, scene: bpy.types.Scene):
        self.scene = scene

    # ── full view state ──────────────────────────────────────────────────────

    def get_view_state(self, root_obj=None) -> ViewState | None:
        """``root_obj`` is the per-tileset root Empty: tiles live in its local
        space (ENU), so the camera is expressed there too. Moving / rotating /
        scaling the Empty is therefore honoured by culling and SSE."""
        r3d, region = find_view3d()
        if r3d is None:
            return None
        props = self.scene.ogc3dtiles
        lat, lon, h = props.origin_lat, props.origin_lon, props.origin_height

        view = r3d.view_matrix            # world → view
        root_sig = ()
        root_scale = 1.0
        if root_obj is not None:
            mw = root_obj.matrix_world
            view = view @ mw              # ENU (root local) → view
            sc = mw.to_scale()
            root_scale = max((abs(sc.x) + abs(sc.y) + abs(sc.z)) / 3.0, 1e-9)
            root_sig = tuple(round(v, 4) for row in mw for v in row)
        win = r3d.window_matrix           # view → clip
        inv = view.inverted()
        pos_enu = inv.translation
        fwd_enu = inv.to_3x3() @ _V((0.0, 0.0, -1.0))
        up_enu = inv.to_3x3() @ _V((0.0, 1.0, 0.0))
        is_persp = r3d.is_perspective
        ortho_offset = 0.0
        if not is_persp:
            # orthographic: Blender's view matrix puts the eye on the pivot;
            # pull it back by the view distance so distances stay meaningful
            pos_enu = pos_enu - fwd_enu * r3d.view_distance
            # cesium-native only knows perspective cameras: a narrow camera
            # far enough back that its frame at the pivot equals the ortho
            # frame (height 2 / win[1][1] world units) gives the same SSE
            p11_w = float(win[1][1]) if abs(win[1][1]) > 1e-9 else 1.0
            far = (1.0 / p11_w) / math.tan(ViewState.ORTHO_FOV / 2.0)
            ortho_offset = max(far - float(r3d.view_distance), 0.0)

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
        w, hpx = max(int(region.width), 1), max(int(region.height), 1)
        p11 = float(win[1][1]) if abs(win[1][1]) > 1e-9 else 1.0
        p00 = float(win[0][0]) if abs(win[0][0]) > 1e-9 else p11 * hpx / w
        if not is_persp:
            # perspective SSE is scale invariant (error and distance both
            # scale); orthographic is not, so fold the root scale in here
            p11 *= root_scale
            p00 *= root_scale
        sig = (tuple(round(v, 1) for v in pos_enu), tuple(round(v, 3) for v in fwd_enu),
               w, hpx, round(p11, 4), is_persp, root_sig)
        return ViewState(position=pos, direction=direction, up=up,
                         viewport_width=w, viewport_height=hpx,
                         p11=p11, p00=p00, is_persp=is_persp,
                         frustum_planes=planes, signature=sig,
                         ortho_eye_offset=ortho_offset)

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
