"""
tileset/native_mesh.py — worker-side extraction of a cesium-native glTF Model
into plain numpy arrays, so the main thread can build Blender meshes directly
with ``foreach_set`` instead of re-serialising a GLB and running
``bpy.ops.import_scene.gltf`` (which costs 50–150 ms per tile).

No bpy here: this runs on cesium-native's worker threads.  The payload is
consumed by ``io.build_tile_from_payload`` on the main thread.

Payload layout
--------------
{
  "verts":  (N,3) float32  — Blender Z-up, node transforms applied
  "normals": (N,3) float32 or None
  "faces":  (F,3) int32    — triangle vertex indices (empty for point clouds)
  "uvs":    (F*3,2) float32 or None  — per-loop, v flipped for Blender
  "colors": (N,4) float32 or None   — vertex colours (point clouds)
  "face_mat": (F,) int32   — material slot per face
  "points": bool           — True when every primitive is POINTS
  "materials": [ {name, base_color, image: int|None, double_sided, unlit} ]
  "images": [ {name, kind: 'file'|'rgba', data: bytes, width, height} ]
}
"""
from __future__ import annotations

import numpy as np

_MODE_POINTS = 0
_MODE_TRIANGLES = 4
_MODE_TRIANGLE_STRIP = 5
_MODE_TRIANGLE_FAN = 6

# glTF (x, y, z) Y-up  →  Blender (x, -z, y) Z-up — same as Blender's importer
_YUP_TO_ZUP3 = np.array([[1.0, 0.0, 0.0],
                         [0.0, 0.0, -1.0],
                         [0.0, 1.0, 0.0]], dtype=np.float64)


def _val(x):
    return x() if callable(x) else x


def _as_array(view, dtype=None):
    if view is None:
        return None
    try:
        arr = np.asarray(view)
    except Exception:
        return None
    if arr.size == 0:
        return None
    return arr.astype(dtype, copy=False) if dtype is not None else arr


def _strip_to_triangles(idx: np.ndarray) -> np.ndarray:
    if len(idx) < 3:
        return np.zeros((0, 3), np.int64)
    a, b, c = idx[:-2], idx[1:-1], idx[2:]
    tris = np.stack([a, b, c], axis=1)
    odd = np.arange(len(tris)) % 2 == 1
    tris[odd] = tris[odd][:, [1, 0, 2]]     # keep winding consistent
    return tris


def _fan_to_triangles(idx: np.ndarray) -> np.ndarray:
    if len(idx) < 3:
        return np.zeros((0, 3), np.int64)
    return np.stack([np.full(len(idx) - 2, idx[0]), idx[1:-1], idx[2:]], axis=1)


def _node_matrix(node) -> np.ndarray:
    """Row-major 4x4 local transform of a glTF node (matrix or TRS)."""
    m = list(node.matrix) if node.matrix is not None else []
    if len(m) == 16:
        M = np.array(m, dtype=np.float64).reshape(4, 4).T        # glTF matrix is column-major
        if not np.allclose(M, np.eye(4)):
            return M                                              # explicit matrix wins
    T = np.eye(4)
    t = list(node.translation) if node.translation is not None else []
    r = list(node.rotation) if node.rotation is not None else []
    s = list(node.scale) if node.scale is not None else []
    if len(s) == 3:
        T[0, 0], T[1, 1], T[2, 2] = s
    if len(r) == 4:
        x, y, z, w = r
        R = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                      [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                      [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
        T[:3, :3] = R @ T[:3, :3]
    if len(t) == 3:
        T[:3, 3] = t
    return T


def _iter_primitives(model):
    """Yield (primitive, world_transform_row_major) for the default scene.
    Done in Python because the binding's for_each_primitive_in_scene cannot
    hand the glm transform back to a Python callback."""
    nodes = list(model.nodes)
    meshes = list(model.meshes)
    if model.scenes and 0 <= (model.scene if model.scene is not None else 0) < len(model.scenes):
        roots = list(model.scenes[model.scene if model.scene is not None else 0].nodes)
    elif model.scenes:
        roots = list(model.scenes[0].nodes)
    else:
        # no scene: every node that is nobody's child is a root
        children = {c for n in nodes for c in (n.children or [])}
        roots = [i for i in range(len(nodes)) if i not in children]
    stack = [(i, np.eye(4)) for i in roots]
    seen = set()
    while stack:
        ni, parent_T = stack.pop()
        if ni < 0 or ni >= len(nodes) or ni in seen:
            continue
        seen.add(ni)
        node = nodes[ni]
        T = parent_T @ _node_matrix(node)
        mi = node.mesh if node.mesh is not None else -1
        if 0 <= mi < len(meshes):
            for prim in meshes[mi].primitives:
                yield prim, T
        for c in (node.children or []):
            stack.append((c, T))


_CT_DTYPE = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16,
             5125: np.uint32, 5126: np.float32}
_TYPE_N = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}


def _enum_int(v):
    for attr in ("value", "real"):
        try:
            return int(getattr(v, attr))
        except Exception:
            pass
    try:
        return int(v)
    except Exception:
        return None


def _raw_accessor(model, ai):
    """Accessor data straight from the buffer as float32 (N, ncomp), honouring
    the component type, byte stride and KHR normalisation.  The binding's
    typed AccessorViews are float-only, so ubyte/ushort colours (the usual
    COLOR_0 encoding of point clouds) must be decoded here."""
    acc = model.accessors[ai]
    ct = _enum_int(acc.component_type)
    dtype = _CT_DTYPE.get(ct)
    ncomp = _TYPE_N.get(str(acc.type).rsplit(".", 1)[-1].upper())
    if dtype is None or ncomp is None or acc.buffer_view is None or acc.buffer_view < 0:
        return None
    bv = model.buffer_views[acc.buffer_view]
    buf = np.asarray(model.buffers[bv.buffer].cesium.data, dtype=np.uint8)
    item = np.dtype(dtype).itemsize * ncomp
    stride = bv.byte_stride if bv.byte_stride and bv.byte_stride > 0 else item
    start = int(bv.byte_offset) + int(acc.byte_offset)
    n = int(acc.count)
    if start + (n - 1) * stride + item > len(buf):
        return None
    if stride == item:
        arr = buf[start:start + n * item].view(dtype).reshape(n, ncomp)
    else:
        rows = np.lib.stride_tricks.as_strided(buf[start:], shape=(n, item), strides=(stride, 1))
        arr = np.ascontiguousarray(rows).view(dtype).reshape(n, ncomp)
    out = arr.astype(np.float32)
    if dtype is not np.float32 and (acc.normalized or ct in (5121, 5123)):
        out = out / float(np.iinfo(dtype).max)
    return out


def _color_array(cs, model, prim):
    """COLOR_0 as (N,4) float32 in [0,1], or None."""
    ai = prim.attributes.get("COLOR_0")
    if ai is None:
        return None
    try:
        arr = _raw_accessor(model, ai)
        if arr is None:
            acc = model.accessors[ai]
            t = str(acc.type).rsplit(".", 1)[-1].upper()
            if t == "VEC4":
                arr = _as_array(cs.gltf.AccessorViewVec4(model, ai), np.float32)
            elif t == "VEC3":
                arr = _as_array(cs.gltf.AccessorViewVec3(model, ai), np.float32)
            if arr is None:
                return None
            if arr.max() > 1.0001:
                arr = arr / 255.0
        if arr.shape[1] == 3:
            arr = np.concatenate([arr, np.ones((len(arr), 1), np.float32)], axis=1)
        elif arr.shape[1] != 4:
            return None
        return np.clip(arr, 0.0, 1.0).astype(np.float32)
    except Exception:
        return None


def _image_payload(cs, model, image_index: int):
    img = model.images[image_index]
    mime = (img.mime_type or "").lower()
    name = img.name or f"image_{image_index}"
    # 1. original compressed bytes still in the buffer → pack as a file (fast)
    if img.buffer_view >= 0 and ("jpeg" in mime or "jpg" in mime or "png" in mime):
        try:
            bv = model.buffer_views[img.buffer_view]
            buf = model.buffers[bv.buffer].cesium.data
            data = np.asarray(buf)[bv.byte_offset:bv.byte_offset + bv.byte_length].tobytes()
            if data[:3] == b"\xff\xd8\xff" or data[:8] == b"\x89PNG\r\n\x1a\n":
                return {"name": name, "kind": "file", "data": data,
                        "ext": "jpg" if data[:3] == b"\xff\xd8\xff" else "png"}
        except Exception:
            pass
    # 2. decoded pixels (KTX2 transcoded, or anything else) → PNG bytes
    asset = _val(img.asset)
    if asset is not None and int(asset.compressed_pixel_format) == 0:
        try:
            if asset.channels != 4:
                asset.change_number_of_channels(4, 255)
            png = bytes(cs.gltf.content.ImageManipulation.save_png(asset))
            return {"name": name, "kind": "file", "data": png, "ext": "png"}
        except Exception:
            pass
    return None


# KHR_gaussian_splatting (spec names; cesium-native decodes the SPZ-compressed
# form into these attributes as well; older converters used the underscored
# names, both are accepted)
_SPLAT_ROTATION = ("KHR_gaussian_splatting:ROTATION", "_ROTATION")
_SPLAT_SCALE = ("KHR_gaussian_splatting:SCALE", "_SCALE")
_SPLAT_SH = "SH_DEGREE_"


def _first_attr(prim, names):
    for n in names:
        ai = prim.attributes.get(n)
        if ai is not None:
            return ai
    return None


def _quat_from_matrix(R):
    """Unit quaternion (x, y, z, w) of a 3x3 rotation matrix (Shepperd)."""
    t = np.trace(R)
    if t > 0:
        s = np.sqrt(t + 1.0) * 2.0
        return np.array([(R[2, 1] - R[1, 2]) / s, (R[0, 2] - R[2, 0]) / s,
                         (R[1, 0] - R[0, 1]) / s, 0.25 * s])
    i = int(np.argmax(np.diag(R)))
    j, k = (i + 1) % 3, (i + 2) % 3
    s = np.sqrt(1.0 + R[i, i] - R[j, j] - R[k, k]) * 2.0
    q = np.zeros(4)
    q[i] = 0.25 * s
    q[j] = (R[j, i] + R[i, j]) / s
    q[k] = (R[k, i] + R[i, k]) / s
    q[3] = (R[k, j] - R[j, k]) / s
    return q


def _quat_mul(a, b):
    """Hamilton product of (N,4) or (4,) quaternions in (x, y, z, w) order."""
    ax, ay, az, aw = a[..., 0], a[..., 1], a[..., 2], a[..., 3]
    bx, by, bz, bw = b[..., 0], b[..., 1], b[..., 2], b[..., 3]
    return np.stack([aw * bx + ax * bw + ay * bz - az * by,
                     aw * by - ax * bz + ay * bw + az * bx,
                     aw * bz + ax * by - ay * bx + az * bw,
                     aw * bw - ax * bx - ay * by - az * bz], axis=-1)


def _splat_arrays(cs, model, prim, T, n):
    """Rotation (N,4 as Blender w,x,y,z), scale (N,3 metres) and spherical
    harmonics [(N,3) per coefficient, spec order] of a splat primitive,
    expressed in Blender's Z-up tile frame, or None when the primitive is
    not a splat cloud."""
    ri, si = _first_attr(prim, _SPLAT_ROTATION), _first_attr(prim, _SPLAT_SCALE)
    if ri is None or si is None:
        return None
    rot = _as_array(cs.gltf.AccessorViewVec4(model, ri), np.float64)
    scl = _as_array(cs.gltf.AccessorViewVec3(model, si), np.float64)
    if rot is None or scl is None or len(rot) != n or len(scl) != n:
        return None
    # node transform: rotation composes, a uniform scale scales the splats
    R = T[:3, :3]
    sT = np.linalg.norm(R, axis=0)
    sT[sT == 0] = 1.0
    Rn = R / sT
    if not np.allclose(Rn, np.eye(3), atol=1e-6):
        rot = _quat_mul(_quat_from_matrix(Rn)[None, :], rot)
    scl = scl * float(np.cbrt(abs(np.linalg.det(R))) or 1.0)
    # glTF Y-up -> Blender Z-up is the rotation (x, y, z) -> (x, -z, y); the
    # ellipsoid is unchanged when the rotation is conjugated and the local
    # scale axes permuted the same way (the unit sphere is rotation invariant)
    rot = rot[:, [0, 2, 1, 3]] * np.array([1.0, -1.0, 1.0, 1.0])
    scl = scl[:, [0, 2, 1]]
    norm = np.linalg.norm(rot, axis=1, keepdims=True)
    norm[norm == 0] = 1.0
    rot = rot / norm
    rot_wxyz = rot[:, [3, 0, 1, 2]].astype(np.float32)
    sh = []
    keys = []
    for name, ai in prim.attributes.items():
        if _SPLAT_SH in name:
            try:
                parts = name.split(_SPLAT_SH)[1].split("_COEF_")
                keys.append((int(parts[0]), int(parts[1]), ai))
            except (IndexError, ValueError):
                continue
    for _deg, _coef, ai in sorted(keys):
        arr = _as_array(cs.gltf.AccessorViewVec3(model, ai), np.float32)
        if arr is None or len(arr) != n:
            sh = []
            break
        sh.append(arr)
    return rot_wxyz, scl.astype(np.float32), sh


def extract_mesh_payload(cs, model):
    """Flatten every primitive of ``model``'s default scene into one mesh.
    Returns None when something is unsupported (caller falls back to GLB)."""
    prims = []
    for prim, T in _iter_primitives(model):
        prims.append((prim, T))
    if not prims:
        return None

    verts, normals, faces, uvs, colors, face_mat = [], [], [], [], [], []
    have_normals = True
    have_uvs = True
    have_colors = True
    all_points = True
    splat_rot, splat_scale, splat_sh = [], [], []
    all_splats = True
    mats_used = {}
    base = 0
    for prim, T in prims:
        mode = prim.mode if prim.mode is not None else _MODE_TRIANGLES
        pos = _as_array(cs.gltf.get_position_accessor_view(model, prim), np.float64)
        if pos is None:
            continue
        n = len(pos)
        # node transform (glTF space) then Y-up → Z-up
        p = pos @ T[:3, :3].T + T[:3, 3]
        p = p @ _YUP_TO_ZUP3.T
        verts.append(p.astype(np.float32))

        nrm = _as_array(cs.gltf.get_normal_accessor_view(model, prim), np.float64)
        if nrm is not None and len(nrm) == n:
            R = T[:3, :3]
            try:
                nmat = np.linalg.inv(R).T
            except np.linalg.LinAlgError:
                nmat = R
            nn = nrm @ nmat.T @ _YUP_TO_ZUP3.T
            norms = np.linalg.norm(nn, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            normals.append((nn / norms).astype(np.float32))
        else:
            have_normals = False

        col = _color_array(cs, model, prim)
        if col is not None and len(col) == n:
            colors.append(col)
        else:
            have_colors = False

        if mode == _MODE_POINTS:
            sp = _splat_arrays(cs, model, prim, T, n)
            if sp is not None:
                splat_rot.append(sp[0])
                splat_scale.append(sp[1])
                splat_sh.append(sp[2])
            else:
                all_splats = False
            base += n
            continue
        all_points = False
        all_splats = False

        idx_view = cs.gltf.get_index_accessor_view(model, prim)
        idx = _as_array(idx_view, np.int64) if idx_view is not None else np.arange(n, dtype=np.int64)
        if idx is None:
            idx = np.arange(n, dtype=np.int64)
        if mode == _MODE_TRIANGLES:
            tris = idx[: (len(idx) // 3) * 3].reshape(-1, 3)
        elif mode == _MODE_TRIANGLE_STRIP:
            tris = _strip_to_triangles(idx)
        elif mode == _MODE_TRIANGLE_FAN:
            tris = _fan_to_triangles(idx)
        else:
            return None                       # lines etc.: let the GLB path handle it
        if len(tris) == 0:
            continue
        # drop degenerate / out-of-range triangles
        ok = (tris[:, 0] != tris[:, 1]) & (tris[:, 1] != tris[:, 2]) & (tris[:, 0] != tris[:, 2])
        ok &= (tris < n).all(axis=1)
        tris = tris[ok]
        faces.append(tris + base)

        uv = _as_array(cs.gltf.get_tex_coord_accessor_view(model, prim, 0), np.float32)
        if uv is not None and len(uv) == n:
            loop_uv = uv[tris.reshape(-1)]
            loop_uv[:, 1] = 1.0 - loop_uv[:, 1]
            uvs.append(loop_uv)
        else:
            have_uvs = False

        mi = prim.material if prim.material is not None and prim.material >= 0 else -1
        slot = mats_used.setdefault(mi, len(mats_used))
        face_mat.append(np.full(len(tris), slot, np.int32))
        base += n

    if not verts:
        return None
    V = np.concatenate(verts)
    F = np.concatenate(faces).astype(np.int32) if faces else np.zeros((0, 3), np.int32)

    images = {}
    materials = []
    for mi, slot in sorted(mats_used.items(), key=lambda kv: kv[1]):
        m = {"name": f"mat_{mi}", "base_color": (0.8, 0.8, 0.8, 1.0), "image": None,
             "double_sided": True, "unlit": False}
        if mi >= 0 and mi < len(model.materials):
            gm = model.materials[mi]
            m["name"] = gm.name or m["name"]
            m["double_sided"] = bool(gm.double_sided)
            try:
                m["unlit"] = gm.ext_materials_unlit() is not None
            except Exception:
                pass
            pbr = gm.pbr_metallic_roughness
            if pbr is not None:
                bc = list(pbr.base_color_factor) if pbr.base_color_factor else [1, 1, 1, 1]
                m["base_color"] = tuple(float(v) for v in (bc + [1, 1, 1, 1])[:4])
                ti = pbr.base_color_texture
                if ti is not None and 0 <= ti.index < len(model.textures):
                    src = model.textures[ti.index].source
                    if src is not None and 0 <= src < len(model.images):
                        if src not in images:
                            images[src] = _image_payload(cs, model, src)
                        m["image"] = src if images[src] is not None else None
        materials.append(m)

    splats = all_points and all_splats and bool(splat_rot)
    sh_out = None
    if splats:
        counts = {len(s) for s in splat_sh}
        if len(counts) == 1 and splat_sh[0]:
            sh_out = [np.concatenate([s[i] for s in splat_sh]) for i in range(len(splat_sh[0]))]
    return finalize_payload({
        "verts": V,
        "splats": splats,
        "splat_rotation": np.concatenate(splat_rot) if splats else None,
        "splat_scale": np.concatenate(splat_scale) if splats else None,
        "splat_sh": sh_out,
        "normals": np.concatenate(normals) if (have_normals and normals) else None,
        "faces": F,
        "uvs": np.concatenate(uvs) if (have_uvs and uvs and not all_points) else None,
        "colors": np.concatenate(colors) if (have_colors and colors) else None,
        "face_mat": np.concatenate(face_mat) if face_mat else np.zeros(0, np.int32),
        "points": all_points,
        "materials": materials,
        "images": images,          # image index → payload (or None)
    })


def finalize_payload(payload):
    """Shared tail for both payload producers.

    * ``offset``: the float64 centroid of the vertices. It is subtracted here
      and re-applied on the tile's object matrix (in float64, see
      ``io.apply_payload_offset``) so vertex coordinates stay small. Blender
      meshes and GPU buffers are float32: content whose node transforms or
      positions carry ECEF / projected-CRS magnitudes (1e6 m) would otherwise
      be quantised to ~0.1 m and wobble as the view matrix changes.
    * ``point_spacing``: mean spacing of a surface-like cloud,
      sqrt(area / N) over the two largest extents (display radius of points).
    """
    V = np.asarray(payload["verts"], dtype=np.float64)
    offset = V.mean(axis=0) if len(V) else np.zeros(3)
    V = V - offset
    payload["verts"] = V.astype(np.float32)
    payload["offset"] = [float(v) for v in offset]
    spacing = 0.0
    # fewer than 64 points: the area / N estimate is meaningless (a 1-point
    # root tile would get a 5 m blob) → 0 = "unknown", default radius
    if payload.get("points") and len(V) >= 64:
        # 5th..95th percentile extents: a few stray points must not inflate
        # the tile's footprint (and every point's radius) tenfold
        lo, hi = np.percentile(V, [5.0, 95.0], axis=0)
        ext = np.sort(hi - lo)[::-1]
        spacing = float(np.sqrt(max(ext[0] * ext[1], 1e-9) / (0.9 * len(V))))
    payload["point_spacing"] = spacing
    return payload
