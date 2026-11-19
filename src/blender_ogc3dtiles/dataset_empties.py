"""One Empty per dataset of an aggregate tileset.

A tileset.json can be nothing but a tree of grouping tiles whose leaves are external tilesets, one per dataset
(several surveys of a city, the datasets of a server). The cesium-native backend tells, for each tile it hands
over, which of those external tilesets it came from; every such dataset gets an Empty under the tileset's root,
and its tiles are parented to that Empty instead of the root.

    world = root · B · U · B⁻¹ · M

M is the tile's matrix in the root's frame, exactly what a tile parented to the root has. B puts the Empty at the
dataset's centre with Z along the local vertical; it lives in the Empty's parent-inverse matrix, and B⁻¹ in the
tiles'. U is the Empty's own location, rotation and scale: zero until the user moves it, and Location Z is then a
height offset along the vertical (a dataset in geoid heights among ellipsoidal ones). U is remembered per dataset
URL on the tileset's entry, so it comes back after a Stop, a reload or a restart of Blender.

Level of detail and culling do not know about U: cesium-native selects the tiles where the dataset says it is.
"""
from __future__ import annotations

import json
from urllib.parse import parse_qs, unquote, urlsplit

import bpy
import numpy as np
from mathutils import Matrix

PROP = "ogc3dtiles_dataset"            # on the Empty: the external tileset's URL
CENTRE = "ogc3dtiles_dataset_centre"   # on the Empty: the dataset's centre, ECEF metres
GENERIC = {"tileset", "cloud", "lod-meta", "metadata", "layer", "ept", "root", "index", "meta", "3dtiles", "tiles"}
SAVE_EVERY_S = 1.0


def short_name(url: str) -> str:
    """A name for the Empty: the last telling part of the URL. A converter URL (…/tileset.json?url=<source>) is
    named after its source; file names every dataset shares (tileset.json, cloud.js) give way to their folder."""
    try:
        parts = urlsplit(url)
        inner = parse_qs(parts.query).get("url")
        if inner:
            return short_name(unquote(inner[0]))
        segs = [unquote(s) for s in parts.path.replace("\\", "/").split("/") if s]
        for s in reversed(segs):
            stem = s.rsplit(".", 1)[0] if "." in s else s
            if stem.lower() not in GENERIC:
                return stem[:60]
        return (parts.netloc or url)[:60]
    except Exception:                                  # noqa: BLE001
        return url[-60:]


def volume_centre(shape):
    """ECEF centre of a native_backend.volume_shape()."""
    if shape[0] == "region":
        from .tileset.traversal import geodetic_to_ecef
        w, s, e, n, lo, hi = shape[1]
        return tuple(float(v) for v in geodetic_to_ecef(np.degrees((s + n) / 2), np.degrees((w + e) / 2), (lo + hi) / 2))
    return tuple(float(v) for v in shape[1])


def base_matrix(frame, centre) -> np.ndarray:
    """B: the dataset's east-north-up frame at its centre, in the root's frame (float64)."""
    from .tileset.native_backend import enu_from_ecef_matrix
    from .tileset.traversal import ecef_to_geodetic
    c = np.asarray(centre, dtype=np.float64)
    if float(np.linalg.norm(c)) < 6.0e6:               # not georeferenced: its own axes, at its centre
        T = np.eye(4)
        T[:3, 3] = c
        return enu_from_ecef_matrix(*frame) @ T
    return enu_from_ecef_matrix(*frame) @ np.linalg.inv(enu_from_ecef_matrix(*ecef_to_geodetic(*c)))


def _mx(a) -> Matrix:
    return Matrix(np.asarray(a, dtype=np.float64).tolist())


def _item(scene, st):
    props = getattr(scene, "ogc3dtiles", None)
    return next((it for it in props.tilesets if it.uid == st.get("key")), None) if props is not None else None


def _stored(item) -> dict:
    try:
        return json.loads(item.dataset_offsets) if item is not None and item.dataset_offsets else {}
    except Exception:                                  # noqa: BLE001
        return {}


def adopt(scene, st, root, coll, obj_name: str, dataset, frame) -> None:
    """Parent the tile object to its dataset's Empty, making the Empty on the dataset's first tile."""
    obj = bpy.data.objects.get(obj_name)
    if obj is None or root is None or obj.parent is not root:
        return
    url, centre = dataset
    names = st.setdefault("datasets", {})
    e = bpy.data.objects.get(names.get(url, ""))
    if e is None or e.get(PROP) != url:
        e = bpy.data.objects.new(short_name(url), None)
        e.empty_display_type = "SINGLE_ARROW"          # points up: Location Z is the height offset
        e.empty_display_size = 20.0
        e[PROP] = url
        e[CENTRE] = [float(v) for v in centre]
        (coll or scene.collection).objects.link(e)
        e.parent = root
        e.matrix_parent_inverse = _mx(base_matrix(frame, centre))
        saved = _stored(_item(scene, st)).get(url)
        if saved and len(saved) == 16:
            e.matrix_basis = Matrix([saved[i:i + 4] for i in range(0, 16, 4)])
        names[url] = e.name
    obj.parent = e
    obj.matrix_parent_inverse = e.matrix_parent_inverse.inverted()


def refresh(st, frame) -> None:
    """The scene origin moved (re-anchor): B again for every Empty, and B⁻¹ for its tiles. Nothing moves."""
    for name in (st.get("datasets") or {}).values():
        e = bpy.data.objects.get(name)
        if e is None or CENTRE not in e:
            continue
        B = _mx(base_matrix(frame, tuple(e[CENTRE])))
        e.matrix_parent_inverse = B
        inv = B.inverted()
        for c in e.children:
            if "tile_url" in c:
                c.matrix_parent_inverse = inv


def save(scene, st, now: float | None = None) -> None:
    """Write the Empties the user moved to the tileset's entry. ``now``: at most once a second (the tick)."""
    names = st.get("datasets")
    if not names:
        return
    if now is not None:
        if now - st.get("datasets_saved_t", 0.0) < SAVE_EVERY_S:
            return
        st["datasets_saved_t"] = now
    item = _item(scene, st)
    if item is None:
        return
    offsets = _stored(item)
    ident = Matrix.Identity(4)
    for url, name in names.items():
        e = bpy.data.objects.get(name)
        if e is None:
            continue
        m = e.matrix_basis
        if all(abs(m[i][j] - ident[i][j]) < 1e-7 for i in range(4) for j in range(4)):
            offsets.pop(url, None)
        else:
            offsets[url] = [round(float(m[i][j]), 7) for i in range(4) for j in range(4)]
    text = json.dumps(offsets, sort_keys=True) if offsets else ""
    if text != item.dataset_offsets:
        item.dataset_offsets = text


def empties(st) -> list:
    return [o for o in (bpy.data.objects.get(n) for n in (st.get("datasets") or {}).values()) if o is not None]
