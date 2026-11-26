"""native_mesh.rgba_tiff: decoded textures handed to Blender as a TIFF without compression."""
import io
import struct

import numpy as np
import pytest

from blender_ogc3dtiles.tileset import native_mesh as nm


def _pixels(w, h):
    px = np.random.default_rng(0).integers(0, 255, (h, w, 4)).astype(np.uint8)
    px[: h // 2, :, 3] = 255
    return px


def test_layout():
    px = _pixels(7, 5)
    data = nm.rgba_tiff(7, 5, px)
    assert data[:4] == b"II*\x00"
    n = struct.unpack_from("<H", data, 8)[0]
    tags = {struct.unpack_from("<H", data, 10 + 12 * i)[0]: struct.unpack_from("<I", data, 18 + 12 * i)[0] for i in range(n)}
    assert tags[256] == 7 and tags[257] == 5 and tags[279] == 7 * 5 * 4
    assert data[tags[273]:] == px.tobytes()


def test_wrong_size():
    with pytest.raises(ValueError):
        nm.rgba_tiff(4, 4, np.zeros(10, np.uint8))


def test_reads_back():
    Image = pytest.importorskip("PIL.Image")
    px = _pixels(64, 32)
    im = Image.open(io.BytesIO(nm.rgba_tiff(64, 32, px)))
    assert im.mode == "RGBA" and im.size == (64, 32)
    assert np.array_equal(np.asarray(im), px)
