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

cesium-native selects tiles where the dataset says it is, so a moved dataset is selected for a camera moved the
other way, which is how Cesium for Unreal and Unity handle a tileset that was moved: view_offsets() gives, for
each distinct U, the matrix that takes the camera there and the datasets it is for. The backend runs one more
selection per matrix, restricted to those datasets, and keeps them out of the main one. Level of detail and
culling then match what is on screen, and nothing is loaded twice.
"""
from __future__ import annotations

import json
from urllib.parse import parse_qs, unquote, urlsplit

import bpy
import numpy as np
from mathutils import Matrix

PROP = "ogc3dtiles_dataset"            # on the Empty: the external tileset's URL
CENTRE = "ogc3dtiles_dataset_centre"   # on the Empty: the dataset's centre, ECEF metres
MARKER = "ogc3dtiles_dataset_marker"   # on the Empty: made from the aggregate's list, no tile of it loaded yet
GENERIC = {"tileset", "cloud", "lod-meta", "metadata", "layer", "ept", "root", "index", "meta", "3dtiles", "tiles"}
SAVE_EVERY_S = 1.0
known: dict = {}                       # Empty name -> (URL, ECEF centre) of the datasets seen this session


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


NAME_KEYS = ("name", "title", "scene", "label")


def display_name(url: str) -> str:
    """A name for the Empty: the property with the `NAME` semantic in the aggregate's tile metadata, else the
    dataset's name there (3D Tiles 1.1: `name`, else
    `title`, `scene`, `label`, with the `project` in front when the name does not hold it), else short_name()."""
    try:
        from .tileset.feature_meta import TILESET_METADATA, content_key
        named = TILESET_METADATA.names.get(url) or TILESET_METADATA.names.get(content_key(url))
        props = (TILESET_METADATA.by_content.get(url) or TILESET_METADATA.by_key.get(content_key(url)) or {})
        name = named or next((str(props[k]).strip() for k in NAME_KEYS
                              if isinstance(props.get(k), (str, int)) and str(props[k]).strip()), "")
        if name:
            project = props.get("project")
            if isinstance(project, str) and project.strip() and project.strip().lower() not in name.lower():
                name = f"{project.strip()} / {name}"
            return name[:60]
    except Exception:                                  # noqa: BLE001
        pass
    return short_name(url)


def volume_centre(shape):
    """ECEF centre of a native_backend.volume_shape()."""
    if shape[0] == "region":
        from .tileset.traversal import geodetic_to_ecef
        w, s, e, n, lo, hi = shape[1]
        return tuple(float(v) for v in geodetic_to_ecef(np.degrees((s + n) / 2), np.degrees((w + e) / 2), (lo + hi) / 2))
    return tuple(float(v) for v in shape[1])


def ground_centre(centre) -> tuple:
    """Where a dataset's Empty goes. The centre of its bounding volume, unless that is far off the ground: the box
    of a country-wide LiDAR in a projected grid can have its centre hundreds of kilometres up, and a very wide
    one many kilometres down. Then the point of the ellipsoid on the same vertical."""
    from .tileset.traversal import ecef_to_geodetic, geodetic_to_ecef
    c = tuple(float(v) for v in centre)
    if float(np.linalg.norm(c)) < 6.0e6:
        return c                                       # not georeferenced
    lat, lon, h = ecef_to_geodetic(*c)
    if -500.0 <= h <= 9000.0:
        return c
    return tuple(float(v) for v in geodetic_to_ecef(lat, lon, 0.0))


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


RADIUS = "ogc3dtiles_dataset_radius"   # on a marker: the dataset's own radius in metres


MAX_RADIUS = 1000.0                    # Blender draws an Empty no larger: empty_display_size stops there


def _markers_on(scene, e) -> bool:
    """"Also the datasets not loaded yet" of the tileset this dataset Empty belongs to."""
    try:
        from .tileset.props import tileset_of
        uid, _root = tileset_of(e)
        return any(it.uid == uid and it.dataset_markers for it in scene.ogc3dtiles.tilesets)
    except Exception:                                  # noqa: BLE001
        return False


def _look(scene, e) -> None:
    """How a dataset's Empty is drawn. With markers on: a sphere of the dataset's size, up to a kilometre, which is
    all an Empty can be; from further away dataset_dots draws a dot of a fixed size on screen. Without: an arrow
    that points up (Location Z is the height offset)."""
    if _markers_on(scene, e):
        e.empty_display_type = "SPHERE"
        e.empty_display_size = min(max(float(e.get(RADIUS, 20.0)), 20.0), MAX_RADIUS)
    else:
        e.empty_display_type, e.empty_display_size = "SINGLE_ARROW", 20.0


def resize(scene) -> None:
    """The markers checkbox, or the dot size, changed in the panel."""
    for e in bpy.data.objects:
        if e.type == "EMPTY" and PROP in e:
            _look(scene, e)
    from . import dataset_dots
    dataset_dots.invalidate()


def adopt(scene, st, root, coll, obj_name: str, dataset, frame) -> None:
    """Parent the tile object to its dataset's Empty, making the Empty on the dataset's first tile."""
    obj = bpy.data.objects.get(obj_name)
    if obj is None or root is None or obj.parent is not root:
        return
    url, centre = dataset
    centre = ground_centre(centre)
    names = st.setdefault("datasets", {})
    e = bpy.data.objects.get(names.get(url, ""))
    if (e is None or MARKER in e) and st.get("dataset_keys"):      # its marker, made before any of its tiles
        from .tileset.feature_meta import content_key
        e = e or bpy.data.objects.get(st["dataset_keys"].get(content_key(url), ""))
        if e is not None and MARKER in e:
            names.pop(e.get(PROP, ""), None)
            del e[MARKER]
            e[PROP] = url
            _look(scene, e)
            saved = _stored(_item(scene, st)).get(url)
            if saved and len(saved) == 16:
                e.matrix_basis = Matrix([saved[i:i + 4] for i in range(0, 16, 4)])
            names[url] = e.name
            known[e.name] = (url, tuple(e[CENTRE]))
        else:
            e = None
    if e is None or e.get(PROP) != url:
        e = bpy.data.objects.new(display_name(url), None)
        e[PROP] = url
        _look(scene, e)
        e[CENTRE] = [float(v) for v in centre]
        (coll or scene.collection).objects.link(e)
        e.parent = root
        e.matrix_parent_inverse = _mx(base_matrix(frame, centre))
        saved = _stored(_item(scene, st)).get(url)
        if saved and len(saved) == 16:
            e.matrix_basis = Matrix([saved[i:i + 4] for i in range(0, 16, 4)])
        names[url] = e.name
        known[e.name] = (url, tuple(float(v) for v in centre))
    obj.parent = e
    obj.matrix_parent_inverse = e.matrix_parent_inverse.inverted()
    own = _collection(coll, e)
    if own is not None:
        from .io import tile_family
        for o in (e, *tile_family(obj)):
            _move(o, own)


COLL = "ogc3dtiles_dataset_coll"       # on the Empty: the name of the dataset's collection


def _collection(coll, e):
    """The dataset's own collection, under the tileset's: its eye hides one dataset among overlapping ones."""
    if coll is None:
        return None
    own = bpy.data.collections.get(e.get(COLL, ""))
    if own is None or coll.children.get(own.name) is None:
        own = bpy.data.collections.new(e.name)
        coll.children.link(own)
        e[COLL] = own.name
    return own


def _move(o, own) -> None:
    if own.objects.get(o.name) is not None:
        return
    for c in list(o.users_collection):
        c.objects.unlink(o)
    own.objects.link(o)


def hidden_urls(st, layer_coll) -> tuple:
    """URLs of the datasets hidden in Blender: the eye or the tick of the dataset's collection, or the eye of
    its Empty. The backend leaves them out of the selection, so they neither load nor stay in memory."""
    off = set()
    for lc in (layer_coll.children if layer_coll is not None else ()):
        if lc.exclude or lc.hide_viewport or lc.collection.hide_viewport:
            off.add(lc.collection.name)
    out = []
    for url, name in (st.get("datasets") or {}).items():
        e = bpy.data.objects.get(name)
        if e is None:
            continue
        if e.get(COLL, "") in off or e.hide_viewport or e.hide_get():
            out.append(url)
    return tuple(sorted(out))


def drop_empty_collections(coll) -> None:
    """After a Clear: the dataset collections nothing is left in."""
    for c in list(coll.children) if coll is not None else ():
        if not c.objects and not c.children:
            bpy.data.collections.remove(c)


def markers(scene, st, root, coll, frame) -> int:
    """Beta. An Empty for every dataset the aggregate's tileset.json lists, before any of its tiles: a sphere of
    the dataset's size at its centre, named as its Empty will be. adopt() takes it over with the first tile."""
    from .tileset.feature_meta import TILESET_METADATA, content_key
    if root is None:
        return 0
    names, keys = st.setdefault("datasets", {}), st.setdefault("dataset_keys", {})
    for u, n in names.items():
        keys.setdefault(content_key(u), n)
    stored = _stored(_item(scene, st))
    left = {o[PROP]: o for o in root.children if MARKER in o}      # of a stream stopped and started again
    made = 0
    for d in TILESET_METADATA.datasets_of(st.get("url") or ""):
        if bpy.data.objects.get(keys.get(d["key"], "")) is not None:
            continue
        url, centre = d["url"], ground_centre(d["centre"])
        if url in left:
            e = left[url]
            e.matrix_parent_inverse = _mx(base_matrix(frame, centre))
            names[url] = keys[d["key"]] = e.name
            known[e.name] = (url, tuple(float(v) for v in centre))
            continue
        e = bpy.data.objects.new(display_name(url), None)
        e[PROP], e[CENTRE], e[MARKER] = url, [float(v) for v in centre], True
        e[RADIUS] = float(min(max(d["radius"], 20.0), 2.0e5))      # its extent, until its tiles say more
        _look(scene, e)
        (coll or scene.collection).objects.link(e)
        e.parent = root
        e.matrix_parent_inverse = _mx(base_matrix(frame, centre))
        saved = stored.get(url)
        if saved and len(saved) == 16:
            e.matrix_basis = Matrix([saved[i:i + 4] for i in range(0, 16, 4)])
        names[url] = keys[d["key"]] = e.name
        known[e.name] = (url, tuple(float(v) for v in centre))
        made += 1
    return made


def remove_markers(st) -> int:
    """The markers no tile took over."""
    names, keys, n = st.get("datasets") or {}, st.get("dataset_keys") or {}, 0
    for url, name in list(names.items()):
        e = bpy.data.objects.get(name)
        if e is not None and MARKER in e and not e.children:
            names.pop(url, None)
            for k in [k for k, v in keys.items() if v == name]:
                keys.pop(k, None)
            known.pop(name, None)
            bpy.data.objects.remove(e)
            n += 1
    return n


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


MAX_OFFSET_VIEWS = 32


def view_offsets(st):
    """([(4x4 ECEF matrix, URLs)], signature). One entry per distinct offset among the moved Empties (at most
    MAX_OFFSET_VIEWS, those with the most tiles first), with the datasets that share it. The matrix applied to
    the camera gives the camera that sees the dataset's own position as the real camera sees the moved one."""
    names = st.get("datasets")
    if not names:
        return [], ()
    from .tileset.native_backend import enu_from_ecef_matrix
    from .tileset.traversal import ecef_to_geodetic
    ident = Matrix.Identity(4)
    moved = []
    for url, name in names.items():
        e = bpy.data.objects.get(name)
        if e is None or CENTRE not in e:
            continue
        m = e.matrix_basis
        if all(abs(m[i][j] - ident[i][j]) < 1e-6 for i in range(3) for j in range(4)):
            continue
        moved.append((len(e.children), url, e))
    if not moved:
        return [], ()
    moved.sort(key=lambda x: -x[0])
    out = {}                                               # rounded matrix -> [matrix, URLs]
    for _n, url, e in moved:
        c = np.asarray(tuple(e[CENTRE]), dtype=np.float64)
        if float(np.linalg.norm(c)) < 6.0e6:
            Bd = np.eye(4)
            Bd[:3, 3] = c
        else:
            Bd = np.linalg.inv(enu_from_ecef_matrix(*ecef_to_geodetic(*c)))
        U = np.array(e.matrix_basis, dtype=np.float64)
        try:
            inv = Bd @ np.linalg.inv(U) @ np.linalg.inv(Bd)
        except np.linalg.LinAlgError:
            continue
        key = tuple(np.round(inv[:3, :], 3).ravel())
        if key in out:
            out[key][1].append(url)
        elif len(out) < MAX_OFFSET_VIEWS:
            out[key] = [inv, [url]]
    return ([(m, tuple(sorted(urls))) for m, urls in out.values()],
            tuple((k, tuple(sorted(v[1]))) for k, v in out.items()))


def find(name: str):
    """(latitude, longitude, height) of a dataset by the name of its Empty, or None. The height includes the
    Empty's Location Z. Datasets seen earlier in the session are found after a Stop too."""
    from .tileset.traversal import ecef_to_geodetic
    e = bpy.data.objects.get(name)
    if e is not None and CENTRE in e:
        centre, dz = tuple(e[CENTRE]), float(e.location.z)
    elif name in known:
        centre, dz = known[name][1], 0.0
    else:
        return None
    if float(np.linalg.norm(centre)) < 6.0e6:
        return None                                    # not georeferenced
    lat, lon, h = ecef_to_geodetic(*centre)
    return float(lat), float(lon), float(h) + dz


def names_matching(text: str) -> list:
    live = {o.name for o in bpy.data.objects if CENTRE in o}
    t = (text or "").lower()
    return sorted(n for n in live | set(known) if t in n.lower())


def empties(st) -> list:
    return [o for o in (bpy.data.objects.get(n) for n in (st.get("datasets") or {}).values()) if o is not None]
