"""feature_meta.py — per-feature metadata of a tile → per-vertex arrays  (no bpy).

cesium-native exposes ``EXT_structural_metadata`` property tables, and converts
b3dm / pnts batch tables to them on load.  ``_FEATURE_ID_n`` says which row of a
table each vertex belongs to, so a column becomes a vertex attribute by a lookup:

* numbers: the value itself (a float attribute);
* text: an integer class code, shared by all tiles and tilesets of the session
  (a per-tile code could not drive one shared shader).  Columns that look like
  identifiers (every row different) get no code, they stay in the lookup table.

A tile keeps its feature ids and its table, a per-tile lookup by feature id.
Only the columns in use become attributes: all of them cost 0.8 GB on 440 tiles
of swissBUILDINGS3D (9.5 M vertices, 22 columns), one costs 40 MB.

Point clouds have one value per point instead, as property attributes or as a
table without ids: millions of rows would not fit a Python table, so these numeric
columns are read straight from the buffer and always become attributes.

Textures hold them per pixel: a feature id texture points at table rows, a property
texture holds the values. A tile keeps these grids and only the column in use becomes
an image, sampled in its material (``texel_values``).

Tileset, group, tile and content metadata live in tileset.json: ``note_tileset_json``
collects them as the JSON comes in, by content URL.
"""
from __future__ import annotations

import json
import re
import threading
from urllib.parse import urljoin

import numpy as np

ATTR_PREFIX = "meta_"
FEATURE_ID_ATTR = "ogc3d_feature"
MAX_CLASSES = 255        # code 0 means "no class"; see materials.palette
_MIN_ROWS_FOR_ID_TEST = 8
_NO_DATA_TEXT = {"", "null", "none", "nan"}   # batch tables written by converters
_MAX_POINT_CLASSES = 32


class Column:
    __slots__ = ("name", "kind", "codes", "lo", "hi", "dropped", "filled")

    def __init__(self, name, kind):
        self.name = name
        self.kind = kind        # "number" or "class"
        self.codes = {}         # text -> code (1..MAX_CLASSES)
        self.lo = float("inf")
        self.hi = float("-inf")
        self.dropped = False    # more classes than a palette holds
        self.filled = 0         # rows with a value


def _free_code(taken, text):
    """A class code: from the value for whole numbers ("6", or "6 Building"), so that
    a class keeps its color from one session to the next whatever tile a worker
    finishes first."""
    number = text.split(" ", 1)[0]
    if number.isdecimal() and 0 <= int(number) < MAX_CLASSES and int(number) + 1 not in taken.values():
        return int(number) + 1
    used = set(taken.values())
    return next(c for c in range(1, MAX_CLASSES + 1) if c not in used)


class Registry:
    """Columns seen so far. Written from cesium-native's worker threads."""

    def __init__(self):
        self._lock = threading.Lock()
        self._columns = {}
        self.version = 0

    def clear(self):
        with self._lock:
            self._columns = {}
            self.version += 1

    def _column(self, name, kind):
        """The column, or None when tiles disagree on its type: batch tables
        have a per-tile type, so the first tile decides."""
        col = self._columns.get(name)
        if col is None:
            col = self._columns[name] = Column(name, kind)
            self.version += 1
        return col if col.kind == kind else None

    def codes_for(self, name, values):
        """Integer code per value (0 for None), or None once the column has too
        many classes."""
        with self._lock:
            col = self._column(name, "class")
            if col is None or col.dropped:
                return None
            col.filled += sum(v is not None for v in values)
            out = np.zeros(len(values), np.int32)
            for i, v in enumerate(values):
                if v is None:
                    continue
                code = col.codes.get(v)
                if code is None:
                    if len(col.codes) >= MAX_CLASSES:
                        col.dropped = True
                        self.version += 1
                        return None
                    code = col.codes[v] = _free_code(col.codes, v)
                    self.version += 1
                out[i] = code
            return out

    def note_range(self, name, values, robust=False):
        """``robust``: 1st to 99th percentile, as LiDAR intensity has rare huge values."""
        finite = values[np.isfinite(values)]
        if not len(finite):
            return
        if robust and len(finite) >= 1000:
            lo, hi = (float(v) for v in np.percentile(finite, (1.0, 99.0)))
        else:
            lo, hi = float(finite.min()), float(finite.max())
        with self._lock:
            col = self._column(name, "number")
            if col is None:
                return
            col.filled += len(finite)
            if lo < col.lo or hi > col.hi:
                col.lo, col.hi = min(col.lo, lo), max(col.hi, hi)
                self.version += 1

    def columns(self):
        """[(name, kind, lo, hi, n_classes)] of the usable columns, sorted."""
        with self._lock:
            return sorted((c.name, c.kind, c.lo, c.hi, len(c.codes))
                          for c in self._columns.values() if not c.dropped)

    def best_column(self):
        """The likeliest "building type": the fullest text column with a few
        classes, else the fullest column."""
        with self._lock:
            usable = [c for c in self._columns.values() if not c.dropped]
            typed = [c for c in usable if c.kind == "class" and 1 < len(c.codes) <= 32]
            pool = typed or usable
            return max(pool, key=lambda c: c.filled).name if pool else ""

    def classes(self, name):
        """[(text, code)] of a class column."""
        with self._lock:
            col = self._columns.get(name)
            return sorted(col.codes.items(), key=lambda kv: kv[1]) if col is not None else []

    def get(self, name):
        with self._lock:
            return self._columns.get(name)


REGISTRY = Registry()


def attribute_name(column: str) -> str:
    return ATTR_PREFIX + re.sub(r"[^0-9A-Za-z_]+", "_", column)


def _plain(v):
    """A table cell as JSON-friendly data."""
    if v is None or isinstance(v, (bool, int, float, str)):
        return v
    if isinstance(v, np.generic):
        return v.item()
    try:
        return [_plain(x) for x in v]
    except TypeError:
        return str(v)


def read_table(cs, model, index):
    """{column: [cell, ...]} of a property table. Cells the binding cannot
    convert (vector columns on v0.59) leave the column out."""
    ext = model.ext_structural_metadata
    ext = ext() if callable(ext) else ext
    if ext is None or not 0 <= index < len(ext.property_tables):
        return None
    table = ext.property_tables[index]
    view = cs.gltf.PropertyTableView(model, table)
    out = {}
    for name in table.properties.keys():
        try:
            acc = view[name]
            out[name] = [_plain(acc[i]) for i in range(int(table.count))]
        except Exception:      # noqa: BLE001
            continue
    return out


def _feature_ids(cs, model, prim):
    """(per-vertex feature ids, property table index) of a primitive, or None.
    Only attribute feature ids with a table: texture ids need per-pixel work."""
    ext = prim.ext_mesh_features
    ext = ext() if callable(ext) else ext
    if ext is None:
        return None
    for fid in ext.feature_ids:
        if fid.attribute is None or fid.property_table is None or fid.property_table < 0:
            continue
        try:
            ids = np.asarray(cs.gltf.get_feature_id_accessor_view(model, prim, fid.attribute))
        except Exception:      # noqa: BLE001
            return None
        return ids.astype(np.int64), int(fid.property_table)
    return None


def primitive_features(cs, model, prim, n_verts):
    """(ids, table index) of a primitive when they cover every vertex."""
    got = _feature_ids(cs, model, prim)
    if got is None or len(got[0]) != n_verts:
        return None
    return got


def combine(cs, model, parts, n_total, registry=REGISTRY):
    """Payload entry for a tile. ``parts`` is one (vertex count, features or
    None) per primitive, in vertex order. None when no primitive has features."""
    if not any(f is not None for _n, f in parts):
        return None
    tables, rows_base, n_rows = {}, {}, 0
    for _n, f in parts:
        if f is not None and f[1] not in tables:
            t = read_table(cs, model, f[1])
            if t is None:
                continue
            tables[f[1]] = t
            rows_base[f[1]] = n_rows
            n_rows += len(next(iter(t.values()))) if t else 0
    if not n_rows:
        return None

    names = sorted({name for t in tables.values() for name in t})
    cells = {name: [None] * n_rows for name in names}
    for idx, t in tables.items():
        for name, vals in t.items():
            cells[name][rows_base[idx]:rows_base[idx] + len(vals)] = vals

    # per-vertex row, -1 where no feature
    row = np.full(n_total, -1, np.int64)
    at = 0
    for n, f in parts:
        if f is not None and f[1] in tables:
            ids = f[0]
            size = len(next(iter(tables[f[1]].values()))) if tables[f[1]] else 0
            ok = (ids >= 0) & (ids < size)
            row[at:at + n][ok] = ids[ok] + rows_base[f[1]]
        at += n

    for name in names:
        column_values(name, cells[name], registry)
    return {
        "feature_id": row.astype(np.int32),
        "table": {"columns": names, "rows": [[cells[n][i] for n in names] for i in range(n_rows)]},
    }


_COMPONENT_DTYPE = {"INT8": np.int8, "UINT8": np.uint8, "INT16": np.int16, "UINT16": np.uint16,
                    "INT32": np.int32, "UINT32": np.uint32, "FLOAT32": np.float32, "FLOAT64": np.float64}


def _structural(model):
    ext = model.ext_structural_metadata
    return ext() if callable(ext) else ext


def _class_property(ext, class_name, name):
    schema = ext.schema
    cls = schema.classes.get(class_name) if schema is not None else None
    return cls.properties.get(name) if cls is not None else None


def _enum_names(ext, class_property):
    """{integer value: name} of an enum property."""
    enum = ext.schema.enums.get(class_property.enum_type) if class_property.enum_type else None
    return {v.value: v.name for v in enum.values} if enum is not None else {}


def _plain_table_columns(model, ext, table):
    """{name: (values, enum names)} of the numeric scalar columns of a table."""
    out = {}
    for name, prop in table.properties.items():
        spec = _class_property(ext, table.class_property, name)
        if spec is None or str(spec.type).rsplit(".", 1)[-1].upper() != "SCALAR" or spec.array:
            continue
        dtype = _COMPONENT_DTYPE.get(str(spec.component_type or "").rsplit(".", 1)[-1].upper())
        if dtype is None or not 0 <= prop.values < len(model.buffer_views):
            continue
        view = model.buffer_views[prop.values]
        data = np.asarray(model.buffers[view.buffer].cesium.data, np.uint8)
        out[name] = (np.frombuffer(data, dtype, int(table.count), int(view.byte_offset)), _enum_names(ext, spec))
    return out


_NOT_COLUMNS = ("_CESIUMOVERLAY_", "_FEATURE_ID_", "_BATCHID", "_ROTATION", "_SCALE")

# ASPRS LAS 1.4 standard point classes (point formats 6 to 10). 64 and above are
# user-defined, so they keep their number.
LAS_CLASSES = {
    0: "Never classified", 1: "Unclassified", 2: "Ground", 3: "Low vegetation",
    4: "Medium vegetation", 5: "High vegetation", 6: "Building", 7: "Low noise",
    9: "Water", 10: "Rail", 11: "Road surface", 13: "Wire guard", 14: "Wire conductor",
    15: "Transmission tower", 16: "Wire connector", 17: "Bridge deck", 18: "High noise",
    19: "Overhead structure", 20: "Ignored ground", 21: "Snow", 22: "Temporal exclusion",
}
LAS_COLUMN = "classification"
_LAS_NAMES = {code: f"{code} {text}" for code, text in LAS_CLASSES.items()}


def _plain_attributes(model, prim, n_verts, read_accessor):
    """Scalar application attributes (glTF's leading underscore), metadata extension or not:
    ``_INTENSITY`` as written by point cloud tilers is the column ``intensity``. Mesh tiles
    are left out: their extra attributes are mostly feature ids."""
    if prim.mode != 0:
        return {}
    out = {}
    for name, index in prim.attributes.items():
        if not name.startswith("_") or name.startswith(_NOT_COLUMNS):
            continue
        arr = read_accessor(model, index, keep_integers=True)
        if arr is not None and len(arr) == n_verts and arr.shape[1] == 1:
            column = name[1:].lower()
            out[column] = (arr[:, 0], _LAS_NAMES if column == LAS_COLUMN else {})
    return out


def point_columns(model, prim, n_verts, read_accessor):
    """{column: (per-vertex values, enum names)} of a primitive, from its property
    attributes and from tables with one implicit row per vertex."""
    out = _plain_attributes(model, prim, n_verts, read_accessor)
    ext = _structural(model)
    if ext is None:
        return out
    prim_ext = prim.ext_structural_metadata
    prim_ext = prim_ext() if callable(prim_ext) else prim_ext
    for i in (prim_ext.property_attributes if prim_ext is not None else ()):
        if not 0 <= i < len(ext.property_attributes):
            continue
        spec = ext.property_attributes[i]
        for name, prop in spec.properties.items():
            index = prim.attributes.get(prop.attribute)
            arr = read_accessor(model, index, keep_integers=True) if index is not None else None
            if arr is None or len(arr) != n_verts or arr.shape[1] != 1:
                continue
            cls = _class_property(ext, spec.class_property, name)
            out[name] = (arr[:, 0], _enum_names(ext, cls) if cls is not None else {})
    features = prim.ext_mesh_features
    features = features() if callable(features) else features
    for fid in (features.feature_ids if features is not None else ()):
        if fid.attribute is not None or fid.texture is not None or fid.property_table is None:
            continue
        if not 0 <= fid.property_table < len(ext.property_tables):
            continue
        table = ext.property_tables[fid.property_table]
        if int(table.count) == n_verts:
            out.update(_plain_table_columns(model, ext, table))
    return out


def vertex_columns(parts, n_total, registry=REGISTRY):
    """{attribute name: per-vertex array} from ``parts``, one (vertex count, columns)
    per primitive. Whole numbers with few values, or an enum, are classes, as in
    point classification; the first tile decides."""
    names = {name for _n, cols in parts for name in cols}
    out = {}
    for name in sorted(names):
        known = registry.get(name)
        values = np.zeros(n_total, np.float64)
        has = np.zeros(n_total, bool)
        enum, at, integers = {}, 0, True
        for n, cols in parts:
            if name in cols:
                arr, names_of = cols[name]
                values[at:at + n] = arr
                has[at:at + n] = True
                enum = enum or names_of
                integers = integers and arr.dtype.kind in "iu"
            at += n
        uniq = np.unique(values[has])
        as_class = known.kind == "class" if known is not None else bool(enum) or (integers and len(uniq) <= _MAX_POINT_CLASSES)
        if not as_class:
            registry.note_range(name, values[has], robust=True)
            known = registry.get(name)
            if known is not None and known.kind == "number":
                out[attribute_name(name)] = values.astype(np.float32)
            continue
        codes = registry.codes_for(name, [enum.get(int(v), str(int(v))) for v in uniq])
        if codes is None:
            continue
        coded = np.zeros(n_total, np.int32)
        coded[has] = codes[np.searchsorted(uniq, values[has])]
        out[attribute_name(name)] = coded
    return out


def _pixels(model, texture_index):
    """(height, width, channels) bytes of a glTF texture, top row first, or None."""
    if not 0 <= texture_index < len(model.textures):
        return None
    source = model.textures[texture_index].source
    if source is None or not 0 <= source < len(model.images):
        return None
    asset = model.images[source].asset
    asset = asset() if callable(asset) else asset
    if asset is None or asset.bytes_per_channel != 1 or int(asset.compressed_pixel_format) != 0:
        return None
    data = np.asarray(asset.pixel_data, np.uint8)
    size = asset.height * asset.width * asset.channels
    return data[:size].reshape(asset.height, asset.width, asset.channels) if data.size >= size else None


def _channel_value(pixels, channels):
    """An integer per pixel from one or more channels, low byte first."""
    value = np.zeros(pixels.shape[:2], np.int64)
    for shift, channel in enumerate(channels):
        if not 0 <= channel < pixels.shape[2]:
            return None
        value |= pixels[..., channel].astype(np.int64) << (8 * shift)
    return value


def _number_or_codes(name, values, is_integer, enum, registry):
    """Per-pixel values as a float32 grid: class codes or numbers. 0 means no class."""
    known = registry.get(name)
    uniq = np.unique(values)
    as_class = known.kind == "class" if known is not None else bool(enum) or (is_integer and len(uniq) <= _MAX_POINT_CLASSES)
    if as_class:
        codes = registry.codes_for(name, [enum.get(int(v), str(int(v))) for v in uniq])
        return None if codes is None else codes[np.searchsorted(uniq, values)].astype(np.float32)
    registry.note_range(name, values.astype(np.float64).ravel())
    known = registry.get(name)
    return values.astype(np.float32) if known is not None and known.kind == "number" else None


def texel_features(cs, model, prim, registry=REGISTRY):
    """What a primitive's textures hold, or None: {"columns": {name: grid},
    "ids": feature id grid or None, "table": its table or None}. Texture coordinate 0
    only, the one a tile's mesh keeps."""
    ext = _structural(model)
    columns, ids, table = {}, None, None
    prim_ext = prim.ext_structural_metadata
    prim_ext = prim_ext() if callable(prim_ext) else prim_ext
    for i in (prim_ext.property_textures if prim_ext is not None and ext is not None else ()):
        if not 0 <= i < len(ext.property_textures):
            continue
        spec = ext.property_textures[i]
        for name, prop in spec.properties.items():
            cls = _class_property(ext, spec.class_property, name)
            pixels = _pixels(model, prop.index) if prop.tex_coord == 0 else None
            if pixels is None or cls is None or str(cls.type).rsplit(".", 1)[-1].upper() != "SCALAR":
                continue
            value = _channel_value(pixels, list(prop.channels))
            if value is None:
                continue
            numeric = value.astype(np.float64)
            if cls.normalized:
                numeric = numeric / float((1 << (8 * len(prop.channels))) - 1)
            grid = _number_or_codes(name, numeric, not cls.normalized, _enum_names(ext, cls), registry)
            if grid is not None:
                columns[name] = grid
    features = prim.ext_mesh_features
    features = features() if callable(features) else features
    for fid in (features.feature_ids if features is not None else ()):
        texture = fid.texture
        if texture is None or ids is not None or texture.tex_coord != 0:
            continue
        pixels = _pixels(model, texture.index)
        value = _channel_value(pixels, list(texture.channels)) if pixels is not None else None
        if value is None:
            continue
        if fid.null_feature_id is not None:
            value = np.where(value == fid.null_feature_id, -1, value)
        if fid.property_table is None or fid.property_table < 0:
            name = fid.label or "feature id"
            valid = value[value >= 0]
            uniq = np.unique(valid)
            codes = registry.codes_for(name, [str(int(v)) for v in uniq])
            if codes is not None and len(uniq):
                grid = np.zeros(value.shape, np.float32)
                grid[value >= 0] = codes[np.searchsorted(uniq, valid)]
                columns[name] = grid
            continue
        cells = read_table(cs, model, fid.property_table)
        if cells:
            names = sorted(cells)
            rows = [[cells[n][i] for n in names] for i in range(len(cells[names[0]]))]
            for n in names:
                column_values(n, cells[n], registry)
            ids, table = value.astype(np.int32), {"columns": names, "rows": rows}
    return {"columns": columns, "ids": ids, "table": table} if columns or ids is not None else None


def texel_values(texel, name, registry=REGISTRY):
    """Float32 grid of a column in a primitive's textures, None when it has none."""
    if name in texel["columns"]:
        return texel["columns"][name]
    table = texel.get("table")
    if table is None or name not in table["columns"]:
        return None
    i = table["columns"].index(name)
    per_row = column_values(name, [r[i] for r in table["rows"]], registry)
    if per_row is None:
        return None
    ids = texel["ids"]
    has = (ids >= 0) & (ids < len(per_row))
    out = np.zeros(ids.shape, np.float32)
    out[has] = per_row[ids[has]]
    return out


class TilesetMetadata:
    """Metadata of tileset.json files seen so far. Written from a Python thread."""

    def __init__(self):
        self._lock = threading.Lock()
        self.tileset = {}        # {"name": value}
        self.by_content = {}     # content URL -> {"name": value}

    def clear(self):
        with self._lock:
            self.tileset, self.by_content = {}, {}

    def note(self, url, doc):
        groups = doc.get("groups") or []
        found = {}

        def walk(tile, inherited):
            own = {**inherited, **_entity_properties(tile.get("metadata"))}
            for content in ([tile["content"]] if tile.get("content") else []) + list(tile.get("contents") or []):
                props = dict(own)
                group = content.get("group")
                if isinstance(group, int) and 0 <= group < len(groups):
                    props.update(_entity_properties(groups[group]))
                props.update(_entity_properties(content.get("metadata")))
                if props and content.get("uri"):
                    found[urljoin(url, content["uri"])] = props
            for child in tile.get("children") or []:
                walk(child, own)

        if isinstance(doc.get("root"), dict):
            walk(doc["root"], {})
        top = _entity_properties(doc.get("metadata"))
        with self._lock:
            self.tileset.update(top)
            self.by_content.update(found)


def _entity_properties(entity):
    return dict(entity.get("properties") or {}) if isinstance(entity, dict) else {}


TILESET_METADATA = TilesetMetadata()


def note_tileset_json(url, data):
    """Collect the metadata of a tileset.json. Anything else is left alone."""
    if b'"metadata"' not in data or b'"root"' not in data:
        return
    try:
        doc = json.loads(data)
    except ValueError:
        return
    if isinstance(doc, dict):
        TILESET_METADATA.note(url.split("?", 1)[0], doc)


def _clean_text(v):
    if not isinstance(v, str):
        return None
    t = v.strip()
    return None if t.lower() in _NO_DATA_TEXT else t


def column_values(name, cells, registry=REGISTRY):
    """Per-row values of a column as an array (float32 numbers, int32 class
    codes), registering what it finds. None when it can't be an attribute."""
    cells = [None if isinstance(v, str) and _clean_text(v) is None else v for v in cells]
    present = [v for v in cells if v is not None]
    if not present:
        return None
    if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in present):
        col = np.array([np.nan if v is None else float(v) for v in cells], np.float64)
        registry.note_range(name, col)
        known = registry.get(name)
        if known is None or known.kind != "number":
            return None
        return np.nan_to_num(col, nan=0.0).astype(np.float32)
    if all(isinstance(v, str) for v in present):
        texts = [_clean_text(v) for v in cells]
        kept = [t for t in texts if t is not None]
        if not kept:
            return None
        known = registry.get(name)
        if known is None and len(kept) >= _MIN_ROWS_FOR_ID_TEST and len(set(kept)) == len(kept):
            return None        # UUIDs and such: lookup only
        return registry.codes_for(name, texts)
    return None


def vertex_attributes(feature_ids, table, wanted, registry=REGISTRY):
    """{attribute name: per-vertex array} of the ``wanted`` columns of a tile.
    Vertices without a feature get 0: no class, below any number range."""
    ids = np.asarray(feature_ids, np.int64)
    has = ids >= 0
    out = {}
    for name in wanted:
        if name not in table["columns"]:
            continue
        i = table["columns"].index(name)
        per_row = column_values(name, [r[i] for r in table["rows"]], registry)
        if per_row is None:
            continue
        per_vert = np.zeros(len(ids), per_row.dtype)
        per_vert[has] = per_row[ids[has]]
        out[attribute_name(name)] = per_vert
    return out
