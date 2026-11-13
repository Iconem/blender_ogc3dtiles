"""Panoramic cameras: the cube faces that cover them and their resolution."""
import math
from types import SimpleNamespace

from blender_ogc3dtiles.camera import panorama_faces


def _cam(ptype, **kw):
    base = dict(panorama_type=ptype, longitude_min=-math.pi, longitude_max=math.pi,
                fisheye_fov=math.pi)
    base.update(kw)
    return SimpleNamespace(**base)


def test_equirectangular_quarter_width_per_face():
    px, faces = panorama_faces(_cam("EQUIRECTANGULAR", latitude_min=-math.pi / 2,
                                    latitude_max=math.pi / 2), 4096, 2048)
    assert px == 1024 and len(faces) == 6


def test_square_equirectangular_uses_its_finer_height():
    px, _faces = panorama_faces(_cam("EQUIRECTANGULAR", latitude_min=-math.pi / 2,
                                     latitude_max=math.pi / 2), 1920, 1920)
    assert px == 960


def test_partial_longitude_range_raises_the_resolution():
    px, _faces = panorama_faces(_cam("EQUIRECTANGULAR", longitude_min=-math.pi / 2,
                                     longitude_max=math.pi / 2, latitude_min=-math.pi / 2,
                                     latitude_max=math.pi / 2), 4096, 2048)
    assert px == 2048


def test_fisheye_drops_faces_outside_its_field():
    px, faces = panorama_faces(_cam("FISHEYE_EQUIDISTANT"), 2048, 2048)
    assert px == 1024
    assert len(faces) == 5 and ((0.0, 0.0, 1.0), (0.0, 1.0, 0.0)) not in faces   # no back face
    _px, wide = panorama_faces(_cam("FISHEYE_EQUISOLID", fisheye_fov=2 * math.pi), 2048, 2048)
    assert len(wide) == 6
