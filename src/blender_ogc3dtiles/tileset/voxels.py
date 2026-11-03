"""voxels.py — voxel tiles (EXT_primitive_voxels) → crisp meshes  (no bpy).

A voxel tile has no geometry: a glTF primitive holds one value per cell, and the
grid fills the tile's bounding volume. On a worker thread only the cell faces next
to empty space become quads, in a unit cube; ``place`` puts them in ECEF on the main
thread, where cesium-native gives the bounding volume. Values reach the Metadata
panel as a per-tile table with one row per distinct value, so classes, ramps and
the shared palette work as they do for feature tables.

Axes, as in CesiumJS, by the tile's bounding volume: box grids are Y-up, [glTF z, y, x]
with tile x = glTF x, tile y = -glTF z, tile z = glTF y (checked on the colours of
Cesium's VoxelBox sample, which equal the position). Regions are Z-up, [z, y, x]. The whole map must stay a
rotation, so a mirrored box (GeoTOP's Y points south) already holds the flip: then
tile y = +glTF z, checked against a georeferenced region tileset of the same area,
and across the borders of neighbouring tiles.
"""
from __future__ import annotations

import json
import struct

import numpy as np

from . import feature_meta
from .native_mesh import _raw_accessor, finalize_payload

_MAX_CLASSES_IN_TILE = 32
_MAX_NUMBER_ROWS = 1024
_QUANTIZE_LEVELS = 256
_QUAD_TRIS = np.array([[0, 1, 2], [0, 2, 3]], np.int32)
_WGS84_A = 6378137.0
_WGS84_E2 = 6.69437999014e-3


def _is_voxel_primitive(prim) -> bool:
    """No positions. Not by mode: drafts of the extension use several values, some
    of which don't fit the int32 the reader stores them in."""
    return "POSITION" not in prim.attributes and len(prim.attributes) > 0


def is_voxel_model(model) -> bool:
    return any(_is_voxel_primitive(p) for m in model.meshes for p in m.primitives)


def gltf_document(raw: bytes):
    """The JSON of a .gltf or .glb. The binding has no accessor for
    EXT_primitive_voxels, so its dimensions come from the source."""
    if raw[:4] == b"glTF":
        length = struct.unpack_from("<I", raw, 12)[0]
        raw = raw[20:20 + length]
    return json.loads(raw)


def _voxel_spec(doc):
    """(primitive JSON, its EXT_primitive_voxels) of the first voxel primitive."""
    for mesh in doc.get("meshes") or []:
        for prim in mesh.get("primitives") or []:
            ext = (prim.get("extensions") or {}).get("EXT_primitive_voxels")
            if ext is not None:
                return prim, ext
    return None, None


def _column_names(doc, prim):
    """{glTF attribute: metadata property name}."""
    names = {}
    meta = (doc.get("extensions") or {}).get("EXT_structural_metadata") or {}
    attrs = meta.get("propertyAttributes") or []
    used = ((prim.get("extensions") or {}).get("EXT_structural_metadata") or {}).get("propertyAttributes") or []
    for i in used:
        if 0 <= i < len(attrs):
            for name, spec in (attrs[i].get("properties") or {}).items():
                if spec.get("attribute"):
                    names[spec["attribute"]] = name
    return names


def grid_shape(dims, y_up):
    """Cell counts along the grid's (x, y, z), before the box decides on y's sign."""
    return (dims[0], dims[2], dims[1]) if y_up else tuple(dims)


def to_tile_axes(values, dims, y_up, padding=None):
    """Flat glTF-ordered values → array indexed [x, y, z, ...] with its padding cut
    off. ``dims`` is EXT_primitive_voxels' (x, y, z). The sign of y is up to ``place``."""
    nx, ny, nz = dims
    before = (padding or {}).get("before") or (0, 0, 0)
    after = (padding or {}).get("after") or (0, 0, 0)
    full = (nz + before[2] + after[2], ny + before[1] + after[1], nx + before[0] + after[0])
    grid = np.asarray(values).reshape(full + np.shape(values)[1:])
    grid = grid[before[2]:before[2] + nz, before[1]:before[1] + ny, before[0]:before[0] + nx]
    return np.moveaxis(grid, (2, 0, 1), (0, 1, 2)) if y_up else np.moveaxis(grid, (2, 1, 0), (0, 1, 2))


def exposed_quads(mask):
    """Faces of the ``True`` cells that border empty space.
    (corners (Q, 4, 3) in cell units wound outward, cell of each quad (Q, 3))."""
    corners, cells = [], []
    for axis in range(3):
        u, v = (axis + 1) % 3, (axis + 2) % 3
        for side in (0, 1):
            to, source = [slice(None)] * 3, [slice(None)] * 3
            to[axis], source[axis] = (slice(0, -1), slice(1, None)) if side else (slice(1, None), slice(0, -1))
            neighbour = np.zeros_like(mask)
            neighbour[tuple(to)] = mask[tuple(source)]
            at = np.argwhere(mask & ~neighbour)
            if not len(at):
                continue
            offsets = np.zeros((4, 3), np.float64)
            offsets[:, axis] = side
            offsets[[1, 2], u] = 1.0
            offsets[[2, 3], v] = 1.0
            corners.append(at[:, None, :] + (offsets if side else offsets[::-1]))
            cells.append(at)
    if not corners:
        return np.zeros((0, 4, 3)), np.zeros((0, 3), np.int64)
    return np.concatenate(corners), np.concatenate(cells)


def _cell_texts(values):
    return [str(int(v)) for v in values]


def _column_kind(name, values, is_integral, registry):
    """"class" for a few whole numbers, as in lithology codes, else "number".
    The first tile decides, like batch tables."""
    known = registry.get(name)
    if known is not None:
        return known.kind
    return "class" if is_integral and len(np.unique(values)) <= _MAX_CLASSES_IN_TILE else "number"


def _quantized(values):
    """Few distinct values, or a table as long as the tile's faces."""
    if len(np.unique(values)) <= _MAX_NUMBER_ROWS:
        return values
    lo, hi = float(values.min()), float(values.max())
    if hi <= lo:
        return values
    step = (hi - lo) / _QUANTIZE_LEVELS
    return lo + np.floor((values - lo) / step).clip(0, _QUANTIZE_LEVELS - 1) * step + step / 2


def scalar_table(columns, cells, registry=feature_meta.REGISTRY):
    """Per-tile table of scalar voxel columns at the exposed ``cells``.
    (row of each cell, {"columns", "rows"}, {column: kind})."""
    names = list(columns)
    stacked, kinds = [], {}
    for name in names:
        values = columns[name]["values"][tuple(cells.T)]
        valid = columns[name]["valid"][tuple(cells.T)]
        shown = values[valid]
        integral = bool(len(shown)) and bool(np.all(shown == np.rint(shown)))
        kinds[name] = _column_kind(name, shown, integral, registry)
        if kinds[name] == "number" and len(shown):
            registry.note_range(name, shown.astype(np.float64))
            values = values.copy()
            values[valid] = _quantized(shown)
        stacked.append(np.where(valid, values, np.nan))
    data = np.stack(stacked, axis=1) if stacked else np.zeros((len(cells), 0))
    uniq, inverse = np.unique(data, axis=0, return_inverse=True)
    rows = []
    for row in uniq:
        out = []
        for v, name in zip(row, names):
            if np.isnan(v):
                out.append(None)
            else:
                out.append(str(int(v)) if kinds[name] == "class" else float(v))
        rows.append(out)
    table = {"columns": names, "rows": rows}
    for i, name in enumerate(names):
        feature_meta.column_values(name, [r[i] for r in rows], registry)
    return np.asarray(inverse).ravel().astype(np.int32), table, kinds


def _grid_values(columns, kinds, registry):
    """Whole-grid values for a Volume, by the attribute name a shader reads."""
    grids = {}
    for name, col in columns.items():
        values = np.where(col["valid"], col["values"], 0.0).astype(np.float32)
        if kinds.get(name) == "class":
            uniq = np.unique(values[col["valid"]])
            codes = registry.codes_for(name, _cell_texts(uniq))
            if codes is None:
                continue
            lut_at = np.searchsorted(uniq, values).clip(0, max(len(uniq) - 1, 0))
            coded = codes[lut_at].astype(np.float32) if len(uniq) else values
            values = np.where(col["valid"], coded, 0.0).astype(np.float32)
        grids[feature_meta.attribute_name(name)] = values
    return grids


def tile_payload(cs, model, raw, y_up=True, want_grid=False, registry=feature_meta.REGISTRY):
    """Payload of a voxel tile with its corners still in the unit cube [-1, 1]:
    ``place`` finishes it. None when it has no voxels, {} when they can't be shown."""
    doc = gltf_document(raw)
    prim_json, ext = _voxel_spec(doc)
    if ext is None:
        return None
    prim = next(p for m in model.meshes for p in m.primitives if _is_voxel_primitive(p))
    dims = tuple(int(d) for d in ext["dimensions"])
    padding = ext.get("padding")
    names = _column_names(doc, prim_json)
    no_data = ext.get("noData") or {}

    columns, colors = {}, None
    for attribute, index in prim.attributes.items():
        arr = _raw_accessor(model, index, keep_integers=True)
        if arr is None:
            continue
        if arr.shape[1] == 1:
            grid = to_tile_axes(arr[:, 0], dims, y_up, padding)
            valid = np.isfinite(grid)
            for nd in no_data.get(attribute) or ():
                valid &= grid != nd
            label = names.get(attribute) or attribute.lstrip("_").lower()
            columns[label] = {"values": grid, "valid": valid}
        elif colors is None and arr.shape[1] in (3, 4):
            colors = to_tile_axes(arr / 255.0 if arr.max() > 1.0 else arr, dims, y_up, padding)
    if not columns and colors is None:
        return {}

    shape = grid_shape(dims, y_up)
    mask = np.zeros(shape, bool)
    for col in columns.values():
        mask |= col["valid"]
    if colors is not None:
        mask |= colors[..., 3] > 0 if colors.shape[-1] == 4 else True

    corners, cells = exposed_quads(mask)
    unit = corners.reshape(-1, 3) / np.array(shape, np.float64) * 2.0 - 1.0
    n_quads = len(cells)
    faces = (_QUAD_TRIS[None] + 4 * np.arange(n_quads, dtype=np.int32)[:, None, None]).reshape(-1, 3)

    features, kinds = None, {}
    if columns and n_quads:
        row, table, kinds = scalar_table(columns, cells, registry)
        features = {"feature_id": np.repeat(row, 4), "table": table}
    vertex_colors = None
    if colors is not None and n_quads:
        rgba = colors[tuple(cells.T)][:, :4].astype(np.float32)
        if rgba.shape[1] == 3:
            rgba = np.concatenate([rgba, np.ones((n_quads, 1), np.float32)], axis=1)
        vertex_colors = np.repeat(rgba, 4, axis=0)

    grid = None
    if want_grid:
        grid = {"shape": shape, "mask": mask, "grids": _grid_values(columns, kinds, registry),
                "colors": colors[..., :3].astype(np.float32) if colors is not None else None}
    return {
        "voxel": True,
        "voxel_y_up": y_up,
        "unit_verts": unit,
        "voxel_grid": grid,
        "verts": np.zeros((0, 3), np.float32),
        "normals": None,
        "faces": faces,
        "uvs": None,
        "overlay_uvs": None,
        "colors": vertex_colors,
        "face_mat": np.zeros(len(faces), np.int32),
        "points": False,
        "splats": False,
        "materials": [{"name": "voxel", "base_color": (0.6, 0.6, 0.6, 1.0), "image": None,
                       "double_sided": False, "unlit": False}],
        "images": {},
        "features": features,
    }


def region_to_ecef(lon, lat, height):
    """WGS84 geodetic (radians, metres) → ECEF."""
    sin_lat = np.sin(lat)
    n = _WGS84_A / np.sqrt(1.0 - _WGS84_E2 * sin_lat * sin_lat)
    xy = (n + height) * np.cos(lat)
    return np.stack([xy * np.cos(lon), xy * np.sin(lon), (n * (1.0 - _WGS84_E2) + height) * sin_lat], axis=-1)


def box_matrix(center, half_axes):
    """4x4 from the unit cube to ECEF. ``half_axes`` has one axis per row."""
    m = np.eye(4)
    m[:3, :3] = np.asarray(half_axes, np.float64).T
    m[:3, 3] = center
    return m


def exaggeration_matrix(center, factor):
    """Stretch along the local vertical through ``center``, for thin datasets."""
    if factor == 1.0:
        return np.eye(4)
    center = np.asarray(center, np.float64)
    # the geodetic normal: the geocentric direction leans 0.2 degrees at mid
    # latitudes, which a stretch of 80 turns into kilometres of slant
    up = center * (1.0, 1.0, 1.0 / (1.0 - _WGS84_E2))
    length = np.linalg.norm(up)
    up = up / length if length > 1.0 else np.array([0.0, 0.0, 1.0])
    linear = np.eye(3) + (factor - 1.0) * np.outer(up, up)
    m = np.eye(4)
    m[:3, :3] = linear
    m[:3, 3] = center - linear @ center
    return m


def _grid_to_box(payload, box):
    """Diagonal sign matrix from the grid's axes to the box: flips y on a Y-up grid
    unless the box is mirrored, see the module docstring."""
    flip = payload.get("voxel_y_up") and np.linalg.det(box[:3, :3]) > 0
    return np.diag((1.0, -1.0 if flip else 1.0, 1.0))


def place(payload, box=None, region=None, stretch=None):
    """Finish a ``tile_payload`` in ECEF. ``box``: unit cube → ECEF matrix,
    ``region``: (west, south, east, north, min height, max height) in radians and
    metres. ``stretch``: matrix applied last. Returns the payload."""
    unit = payload.pop("unit_verts")
    if box is not None:
        linear = box[:3, :3] @ _grid_to_box(payload, box)
        points = unit @ linear.T + box[:3, 3]
        if np.linalg.det(linear) < 0:          # faces stay wound outward
            payload["faces"] = payload["faces"][:, [0, 2, 1]]
        payload["voxel_matrix"] = box
    else:
        west, south, east, north, low, high = region
        t = (unit + 1.0) / 2.0
        points = region_to_ecef(west + t[:, 0] * (east - west), south + t[:, 1] * (north - south),
                                low + t[:, 2] * (high - low))
        payload["voxel_grid"] = None           # a curved grid is no VDB transform
    if stretch is not None:
        points = points @ stretch[:3, :3].T + stretch[:3, 3]
    payload["voxel_stretch"] = stretch
    payload["verts"] = points
    return finalize_payload(payload)


def volume_matrix(payload):
    """Unit-index VDB cells → ECEF, or None when the tile can't be a Volume.
    Blender puts a VDB cell's centre on its integer index."""
    grid, box = payload.get("voxel_grid"), payload.get("voxel_matrix")
    if not grid or box is None:
        return None
    cell = 2.0 / np.array(grid["shape"], np.float64)
    index = np.eye(4)
    index[:3, :3] = np.diag(cell)
    index[:3, 3] = cell / 2.0 - 1.0
    signs = np.eye(4)
    signs[:3, :3] = _grid_to_box(payload, box)
    stretch = payload.get("voxel_stretch")
    return (stretch if stretch is not None else np.eye(4)) @ box @ signs @ index
