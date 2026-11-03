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
"""
from __future__ import annotations

import re
import threading

import numpy as np

ATTR_PREFIX = "meta_"
FEATURE_ID_ATTR = "ogc3d_feature"
MAX_CLASSES = 255        # code 0 means "no class"; see materials.palette
_MIN_ROWS_FOR_ID_TEST = 8
_NO_DATA_TEXT = {"", "null", "none", "nan"}   # batch tables written by converters


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
                    code = col.codes[v] = len(col.codes) + 1
                    self.version += 1
                out[i] = code
            return out

    def note_range(self, name, values):
        finite = values[np.isfinite(values)]
        if not len(finite):
            return
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
