"""Pure-numpy GLB reader (Python backend direct-mesh path)."""
import json
import struct

import numpy as np
import pytest

from blender_ogc3dtiles.tileset.gltf_payload import glb_to_payload


def _glb(doc: dict, bin_: bytes) -> bytes:
    js = json.dumps(doc).encode()
    js += b" " * ((4 - len(js) % 4) % 4)
    bin_ += b"\0" * ((4 - len(bin_) % 4) % 4)
    body = struct.pack("<I4s", len(js), b"JSON") + js + struct.pack("<I4s", len(bin_), b"BIN\0") + bin_
    return struct.pack("<4sII", b"glTF", 2, 12 + len(body)) + body


def _quad_glb(mode=4, quantized=False, big_translation=False):
    """Two triangles (or a 4-vertex strip) with UVs, normals, colours, 1 JPEG-ish image."""
    pos = np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]], np.float32)
    if quantized:
        pos_b = (pos * 1000).astype(np.int16).tobytes()      # KHR_mesh_quantization + node scale
        ctype, scale = 5122, [0.001, 0.001, 0.001]
    else:
        pos_b, ctype, scale = pos.tobytes(), 5126, None
    nrm = np.tile(np.array([[0, 0, 1]], np.float32), (4, 1)).tobytes()
    uv = np.array([[0, 0], [1, 0], [1, 1], [0, 1]], np.float32).tobytes()
    col = np.array([[255, 0, 0, 255]] * 4, np.uint8).tobytes()
    idx = (np.array([0, 1, 2, 0, 2, 3], np.uint16) if mode == 4
           else np.array([0, 1, 3, 2], np.uint16)).tobytes()
    img = b"\xff\xd8\xff\xe0JFIFfake"
    chunks = [pos_b, nrm, uv, col, idx, img]
    offs, bin_ = [], b""
    for c in chunks:
        offs.append(len(bin_))
        bin_ += c + b"\0" * ((4 - len(c) % 4) % 4)
    bvs = [{"buffer": 0, "byteOffset": o, "byteLength": len(c)} for o, c in zip(offs, chunks)]
    node = {"mesh": 0}
    if scale:
        node["scale"] = scale
    if big_translation:
        node["translation"] = [1.0e6, 2.0e6, -3.0e6]
    doc = {
        "asset": {"version": "2.0"}, "scene": 0, "scenes": [{"nodes": [0]}], "nodes": [node],
        "buffers": [{"byteLength": len(bin_)}], "bufferViews": bvs,
        "accessors": [
            {"bufferView": 0, "componentType": ctype, "count": 4, "type": "VEC3"},
            {"bufferView": 1, "componentType": 5126, "count": 4, "type": "VEC3"},
            {"bufferView": 2, "componentType": 5126, "count": 4, "type": "VEC2"},
            {"bufferView": 3, "componentType": 5121, "count": 4, "type": "VEC4", "normalized": True},
            {"bufferView": 4, "componentType": 5123, "count": 6 if mode == 4 else 4, "type": "SCALAR"},
        ],
        "images": [{"bufferView": 5, "mimeType": "image/jpeg"}],
        "textures": [{"source": 0}],
        "materials": [{"name": "m", "doubleSided": True,
                       "pbrMetallicRoughness": {"baseColorTexture": {"index": 0}}}],
        "meshes": [{"primitives": [{"mode": mode, "material": 0, "indices": 4,
                                    "attributes": {"POSITION": 0, "NORMAL": 1, "TEXCOORD_0": 2,
                                                   "COLOR_0": 3}}]}],
    }
    return _glb(doc, bin_)


def test_triangles_payload():
    p = glb_to_payload(_quad_glb())
    assert p is not None and not p["points"]
    assert p["faces"].shape == (2, 3)
    assert p["uvs"].shape == (6, 2) and np.isclose(p["uvs"][1][1], 1.0)   # v flipped
    assert p["colors"].shape == (4, 4) and np.isclose(p["colors"][0][0], 1.0)
    assert p["materials"][0]["image"] == 0 and p["images"][0]["data"].startswith(b"\xff\xd8")
    # Y-up → Z-up and recentring: verts + offset reproduce the swizzled quad
    V = p["verts"] + np.asarray(p["offset"])
    assert np.allclose(sorted(V[:, 2].tolist()), [0, 0, 1, 1], atol=1e-6)      # glTF y → Blender z
    assert np.allclose(V[:, 1], 0.0, atol=1e-6)


def test_strip_and_quantized():
    p = glb_to_payload(_quad_glb(mode=5, quantized=True))
    assert p is not None and p["faces"].shape == (2, 3)
    V = p["verts"] + np.asarray(p["offset"])
    assert np.isclose(V[:, 0].max(), 1.0, atol=1e-3)         # int16 × node scale


def test_big_translation_is_moved_to_offset():
    p = glb_to_payload(_quad_glb(big_translation=True))
    assert np.abs(p["verts"]).max() < 2.0                    # float32 verts stay small
    assert abs(p["offset"][0] - 1.0e6) < 1.0                 # float64 offset carries it


def test_unsupported_falls_back():
    glb = _quad_glb()
    assert glb_to_payload(b"not a glb") is None
    doc_end = glb.index(b"BIN\0")
    js = glb[20:doc_end - 4].decode().rstrip()
    doc = json.loads(js)
    doc["extensionsRequired"] = ["KHR_draco_mesh_compression"]
    assert glb_to_payload(_glb(doc, b"\0" * 8)) is None


@pytest.mark.parametrize("stride", [12, 16, 24])
def test_interleaved_positions(stride):
    pos = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], np.float32)
    bin_ = b""
    for row in pos:
        bin_ += row.tobytes() + b"\0" * (stride - 12)
    doc = {"asset": {"version": "2.0"}, "nodes": [{"mesh": 0}],
           "buffers": [{"byteLength": len(bin_)}],
           "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": len(bin_), "byteStride": stride}],
           "accessors": [{"bufferView": 0, "componentType": 5126, "count": 3, "type": "VEC3"}],
           "meshes": [{"primitives": [{"attributes": {"POSITION": 0}}]}]}
    p = glb_to_payload(_glb(doc, bin_))
    assert p is not None and p["faces"].shape == (1, 3)
    V = p["verts"] + np.asarray(p["offset"])
    assert np.allclose(sorted(V[:, 0].tolist()), [0, 0, 1], atol=1e-6)
