"""
tileset/gltf_payload.py — pure numpy GLB → mesh payload for the Python backend.

Same payload layout as ``native_mesh.extract_mesh_payload`` so the main
thread builds the Blender mesh with ``io.build_tile_from_payload`` instead of
running ``bpy.ops.import_scene.gltf`` (≈40 ms per tile vs ≈8 ms).  Runs on
the download worker threads: no bpy here.

Supported: glTF 2.0 GLB with a single BIN buffer (or data: URIs), any
accessor component type (KHR_mesh_quantization), interleaved buffer views,
TRIANGLES / STRIP / FAN / POINTS, TEXCOORD_n, NORMAL, COLOR_0, embedded
JPEG / PNG images, KHR_materials_unlit, doubleSided.

Returns None (caller falls back to Blender's importer) for Draco, meshopt,
KTX2 / basisu textures, sparse accessors and external buffers.
"""
from __future__ import annotations

import base64
import json
import struct

import numpy as np

from .native_mesh import (
    _MODE_POINTS,
    _MODE_TRIANGLE_FAN,
    _MODE_TRIANGLE_STRIP,
    _MODE_TRIANGLES,
    _YUP_TO_ZUP3,
    _fan_to_triangles,
    _strip_to_triangles,
    finalize_payload,
)

_CT = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16,
       5125: np.uint32, 5126: np.float32}
_NC = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT2": 4, "MAT3": 9, "MAT4": 16}
_UNSUPPORTED = ("KHR_draco_mesh_compression", "EXT_meshopt_compression", "KHR_texture_basisu")


def _split_glb(glb: bytes):
    if len(glb) < 20 or glb[:4] != b"glTF":
        return None, None
    total = struct.unpack_from("<I", glb, 8)[0]
    off, doc, bin_ = 12, None, b""
    while off + 8 <= min(total, len(glb)):
        clen, ctype = struct.unpack_from("<I4s", glb, off)
        chunk = glb[off + 8:off + 8 + clen]
        if ctype == b"JSON":
            doc = json.loads(chunk.decode("utf-8"))
        elif ctype == b"BIN\x00" and not bin_:
            bin_ = chunk
        off += 8 + clen
    return doc, bin_


def _buffer_bytes(doc, bin_, index):
    buf = doc.get("buffers", [])[index]
    uri = buf.get("uri")
    if uri is None:
        return bin_ if index == 0 else None
    if uri.startswith("data:"):
        return base64.b64decode(uri.split(",", 1)[1])
    return None                                  # external file: not supported


def _accessor(doc, buffers, idx, as_float=False):
    if idx is None or idx < 0 or idx >= len(doc.get("accessors", [])):
        return None
    acc = doc["accessors"][idx]
    if "sparse" in acc or "bufferView" not in acc:
        return None
    bv = doc["bufferViews"][acc["bufferView"]]
    data = buffers.get(bv.get("buffer", 0))
    if data is None:
        return None
    dt = np.dtype(_CT[acc["componentType"]])
    nc = _NC[acc["type"]]
    count = int(acc["count"])
    off = int(bv.get("byteOffset", 0)) + int(acc.get("byteOffset", 0))
    elem = dt.itemsize * nc
    stride = int(bv.get("byteStride", 0) or 0)
    if count == 0:
        return np.zeros((0, nc), dt)
    if stride and stride != elem:
        need = (count - 1) * stride + elem
        base = np.frombuffer(data, np.uint8, need, off)
        arr = np.lib.stride_tricks.as_strided(base, shape=(count, elem), strides=(stride, 1))
        arr = np.ascontiguousarray(arr).view(dt).reshape(count, nc)
    else:
        arr = np.frombuffer(data, dt, count * nc, off).reshape(count, nc)
    if as_float or acc.get("normalized"):
        if dt.kind in "iu" and (acc.get("normalized") or as_float):
            info = np.iinfo(dt)
            if dt.kind == "u" or acc.get("normalized"):
                arr = arr.astype(np.float64) / float(info.max)
                if dt.kind == "i":
                    arr = np.maximum(arr, -1.0)
            else:
                arr = arr.astype(np.float64)
        else:
            arr = arr.astype(np.float64)
    return arr


def _node_matrix(node):
    m = node.get("matrix")
    if m and len(m) == 16:
        M = np.asarray(m, dtype=np.float64).reshape(4, 4).T      # glTF is column-major
        if not np.allclose(M, np.eye(4)):
            return M
    T = np.eye(4)
    s = node.get("scale")
    r = node.get("rotation")
    t = node.get("translation")
    if s:
        T = T @ np.diag([s[0], s[1], s[2], 1.0])
    if r:
        x, y, z, w = r
        R = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                      [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                      [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
        R4 = np.eye(4)
        R4[:3, :3] = R
        T = R4 @ T
    if t:
        T[:3, 3] += np.asarray(t, dtype=np.float64)
    return T


def _iter_primitives(doc):
    nodes = doc.get("nodes", [])
    meshes = doc.get("meshes", [])
    scenes = doc.get("scenes", [])
    if scenes:
        si = doc.get("scene", 0)
        roots = list(scenes[si if 0 <= si < len(scenes) else 0].get("nodes", []))
    else:
        children = {c for n in nodes for c in n.get("children", [])}
        roots = [i for i in range(len(nodes)) if i not in children]
    stack = [(i, np.eye(4)) for i in roots]
    seen = set()
    while stack:
        ni, parent_T = stack.pop()
        if ni in seen or not (0 <= ni < len(nodes)):
            continue
        seen.add(ni)
        node = nodes[ni]
        T = parent_T @ _node_matrix(node)
        mi = node.get("mesh")
        if mi is not None and 0 <= mi < len(meshes):
            for prim in meshes[mi].get("primitives", []):
                yield prim, T
        for c in node.get("children", []):
            stack.append((c, T))


def _image_payload(doc, buffers, image_index):
    img = doc.get("images", [])[image_index]
    mime = img.get("mimeType", "")
    try:
        if "bufferView" in img:
            bv = doc["bufferViews"][img["bufferView"]]
            data = buffers.get(bv.get("buffer", 0))
            if data is None:
                return None
            off = int(bv.get("byteOffset", 0))
            raw = bytes(data[off:off + int(bv["byteLength"])])
        elif str(img.get("uri", "")).startswith("data:"):
            raw = base64.b64decode(img["uri"].split(",", 1)[1])
        else:
            return None
    except Exception:
        return None
    if "ktx" in mime.lower() or raw[:12] == b"\xabKTX 20\xbb\r\n\x1a\n":
        return None
    return {"name": img.get("name") or f"image_{image_index}", "kind": "file", "data": raw,
            "width": 0, "height": 0}


def glb_to_payload(glb: bytes):
    """GLB bytes → payload dict (see native_mesh), or None when unsupported."""
    doc, bin_ = _split_glb(glb)
    if doc is None:
        return None
    for ext in doc.get("extensionsRequired", []) + doc.get("extensionsUsed", []):
        if ext in _UNSUPPORTED:
            return None
    buffers = {}
    for i in range(len(doc.get("buffers", []))):
        b = _buffer_bytes(doc, bin_, i)
        if b is None:
            return None
        buffers[i] = b

    verts, normals, faces, uvs, colors, face_mat = [], [], [], [], [], []
    have_normals = have_uvs = have_colors = True
    all_points = True
    mats_used = {}
    base = 0
    for prim, T in _iter_primitives(doc):
        if prim.get("extensions"):
            if any(e in prim["extensions"] for e in _UNSUPPORTED):
                return None
        attrs = prim.get("attributes", {})
        pos = _accessor(doc, buffers, attrs.get("POSITION"), as_float=True)
        if pos is None or len(pos) == 0:
            continue
        n = len(pos)
        p = pos[:, :3] @ T[:3, :3].T + T[:3, 3]
        p = p @ _YUP_TO_ZUP3.T
        verts.append(p)
        mode = int(prim.get("mode", _MODE_TRIANGLES))

        nrm = _accessor(doc, buffers, attrs.get("NORMAL"), as_float=True)
        if nrm is not None and len(nrm) == n:
            R = T[:3, :3]
            try:
                nmat = np.linalg.inv(R).T
            except np.linalg.LinAlgError:
                nmat = R
            nn = nrm[:, :3] @ nmat.T @ _YUP_TO_ZUP3.T
            norms = np.linalg.norm(nn, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            normals.append((nn / norms).astype(np.float32))
        else:
            have_normals = False

        col = _accessor(doc, buffers, attrs.get("COLOR_0"), as_float=True)
        if col is not None and len(col) == n:
            if col.shape[1] == 3:
                col = np.concatenate([col, np.ones((n, 1))], axis=1)
            colors.append(col[:, :4].astype(np.float32))
        else:
            have_colors = False

        if mode == _MODE_POINTS:
            base += n
            continue
        all_points = False

        idx = _accessor(doc, buffers, prim.get("indices"))
        idx = idx.reshape(-1).astype(np.int64) if idx is not None else np.arange(n, dtype=np.int64)
        if mode == _MODE_TRIANGLES:
            tris = idx[: (len(idx) // 3) * 3].reshape(-1, 3)
        elif mode == _MODE_TRIANGLE_STRIP:
            tris = _strip_to_triangles(idx)
        elif mode == _MODE_TRIANGLE_FAN:
            tris = _fan_to_triangles(idx)
        else:
            return None
        if len(tris) == 0:
            base += n
            continue
        ok = (tris[:, 0] != tris[:, 1]) & (tris[:, 1] != tris[:, 2]) & (tris[:, 0] != tris[:, 2])
        ok &= (tris < n).all(axis=1)
        tris = tris[ok]
        faces.append(tris + base)

        mi = int(prim.get("material", -1))
        slot = mats_used.setdefault(mi, len(mats_used))
        face_mat.append(np.full(len(tris), slot, dtype=np.int32))

        tc_set = 0
        if 0 <= mi < len(doc.get("materials", [])):
            bct = doc["materials"][mi].get("pbrMetallicRoughness", {}).get("baseColorTexture")
            if bct:
                tc_set = int(bct.get("texCoord", 0))
        uv = _accessor(doc, buffers, attrs.get(f"TEXCOORD_{tc_set}"), as_float=True)
        if uv is not None and len(uv) == n:
            loop_uv = uv[tris.reshape(-1), :2].astype(np.float32)
            loop_uv[:, 1] = 1.0 - loop_uv[:, 1]
            uvs.append(loop_uv)
        else:
            have_uvs = False
        base += n

    if not verts:
        return None
    V = np.concatenate(verts)
    F = np.concatenate(faces).astype(np.int32) if faces else np.zeros((0, 3), np.int32)

    images = {}
    materials = []
    gmats = doc.get("materials", [])
    textures = doc.get("textures", [])
    for mi, _slot in sorted(mats_used.items(), key=lambda kv: kv[1]):
        m = {"name": f"mat_{mi}", "base_color": (0.8, 0.8, 0.8, 1.0), "image": None,
             "double_sided": True, "unlit": False}
        if 0 <= mi < len(gmats):
            gm = gmats[mi]
            m["name"] = gm.get("name") or m["name"]
            m["double_sided"] = bool(gm.get("doubleSided", False))
            m["unlit"] = "KHR_materials_unlit" in gm.get("extensions", {})
            pbr = gm.get("pbrMetallicRoughness", {})
            bc = pbr.get("baseColorFactor", [1, 1, 1, 1])
            m["base_color"] = tuple(float(v) for v in (list(bc) + [1, 1, 1, 1])[:4])
            bct = pbr.get("baseColorTexture")
            if bct and 0 <= bct.get("index", -1) < len(textures):
                tex = textures[bct["index"]]
                if "KHR_texture_basisu" in tex.get("extensions", {}):
                    return None
                src = tex.get("source")
                if src is not None and 0 <= src < len(doc.get("images", [])):
                    if src not in images:
                        images[src] = _image_payload(doc, buffers, src)
                    m["image"] = src if images[src] is not None else None
        materials.append(m)

    payload = {
        "verts": V,
        "normals": np.concatenate(normals) if (have_normals and normals) else None,
        "faces": F,
        "uvs": np.concatenate(uvs) if (have_uvs and uvs and not all_points) else None,
        "colors": np.concatenate(colors) if (have_colors and colors) else None,
        "face_mat": np.concatenate(face_mat) if face_mat else np.zeros(0, np.int32),
        "points": all_points,
        "materials": materials,
        "images": images,
    }
    return finalize_payload(payload)
