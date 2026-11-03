"""feature_meta: table rows to per-vertex attributes, shared class codes."""
import numpy as np

from blender_ogc3dtiles.tileset import feature_meta as fm


class _Acc:
    def __init__(self, vals):
        self.vals = vals

    def __getitem__(self, i):
        if isinstance(self.vals, str):
            raise TypeError(self.vals)
        return self.vals[i]


class _Table:
    def __init__(self, cols):
        self.properties = {k: None for k in cols}
        self.count = max(len(v) for v in cols.values() if not isinstance(v, str))
        self.cols = cols


class _Cs:
    class gltf:
        @staticmethod
        def PropertyTableView(_model, table):
            return {k: _Acc(v) for k, v in table.cols.items()}


class _Model:
    def __init__(self, *tables):
        class Ext:
            property_tables = list(tables)
        self.ext_structural_metadata = Ext()


def _combine(cols, ids, reg):
    ids = np.asarray(ids, np.int64)
    return fm.combine(_Cs, _Model(_Table(cols)), [(len(ids), (ids, 0))], len(ids), reg)


def test_numbers_and_classes_become_vertex_attributes():
    reg = fm.Registry()
    got = _combine({"year": [2024, None], "type": ["house", "shed"]}, [0, 0, 1], reg)
    attrs = fm.vertex_attributes(got["feature_id"], got["table"], ["year", "type"], reg)
    year = attrs["meta_year"]
    assert year.dtype == np.float32 and year.tolist() == [2024.0, 2024.0, 0.0]
    assert attrs["meta_type"].tolist() == [1, 1, 2]
    assert got["feature_id"].tolist() == [0, 0, 1]
    assert got["table"]["columns"] == ["type", "year"]
    assert got["table"]["rows"][1] == ["shed", None]
    assert reg.get("year").lo == 2024.0


def test_class_codes_are_shared_between_tiles():
    reg = fm.Registry()
    a = _combine({"type": ["house", "shed"]}, [0, 1], reg)
    b = _combine({"type": ["shed", "barn"]}, [0, 1], reg)
    per_tile = [fm.vertex_attributes(t["feature_id"], t["table"], ["type"], reg) for t in (a, b)]
    assert per_tile[0]["meta_type"].tolist() == [1, 2]
    assert per_tile[1]["meta_type"].tolist() == [2, 3]
    assert reg.classes("type") == [("house", 1), ("shed", 2), ("barn", 3)]


def test_identifier_columns_stay_lookup_only():
    reg = fm.Registry()
    ids = [f"uuid-{i}" for i in range(8)]
    got = _combine({"uuid": ids}, list(range(8)), reg)
    assert fm.vertex_attributes(got["feature_id"], got["table"], ["uuid"], reg) == {}
    assert got["table"]["rows"][3] == ["uuid-3"]
    assert reg.columns() == []


def test_too_many_classes_drop_the_column():
    reg = fm.Registry()
    assert reg.codes_for("c", [str(i) for i in range(fm.MAX_CLASSES)]) is not None
    assert reg.codes_for("c", ["one more"]) is None
    assert reg.columns() == []


def test_blank_text_and_out_of_range_ids_have_no_class():
    reg = fm.Registry()
    got = _combine({"type": ["\n\t\t", "shed"]}, [0, 1, 7, -1], reg)
    attrs = fm.vertex_attributes(got["feature_id"], got["table"], ["type"], reg)
    assert attrs["meta_type"].tolist() == [0, 1, 0, 0]
    assert got["feature_id"].tolist() == [0, 1, -1, -1]


def test_no_data_text_is_not_a_class():
    reg = fm.Registry()
    _combine({"h": ["null", "NULL", "tall"]}, [0, 1, 2], reg)
    assert reg.classes("h") == [("tall", 1)]


def test_no_data_text_does_not_hide_a_number_column():
    reg = fm.Registry()
    got = _combine({"h": ["null", 4.5]}, [0, 1], reg)
    assert fm.vertex_attributes(got["feature_id"], got["table"], ["h"], reg)["meta_h"].tolist() == [0.0, 4.5]
    assert reg.get("h").kind == "number"


def test_tiles_disagreeing_on_a_type_keep_the_first():
    reg = fm.Registry()
    _combine({"h": ["tall", "low"]}, [0, 1], reg)
    got = _combine({"h": [3.5, 4.5]}, [0, 1], reg)
    assert fm.vertex_attributes(got["feature_id"], got["table"], ["h"], reg) == {}
    assert reg.classes("h") == [("tall", 1), ("low", 2)]


def test_best_column_is_the_fullest_with_a_few_classes():
    reg = fm.Registry()
    _combine({"usage": [None, None, "farm", "barn"], "kind": ["a", "b", "a", "b"], "year": [1, 2, 3, 4]},
             [0, 1, 2, 3], reg)
    assert reg.best_column() == "kind"


def test_columns_the_binding_cannot_read_are_left_out():
    reg = fm.Registry()
    got = _combine({"vec": "cannot convert", "h": [1.5, 2.5]}, [0, 1], reg)
    assert got["table"]["columns"] == ["h"]


def test_no_features_gives_nothing():
    assert fm.combine(_Cs, _Model(), [(3, None)], 3, fm.Registry()) is None


def test_attribute_names_are_sanitised():
    assert fm.attribute_name("Roof Height (m)") == "meta_Roof_Height_m_"
