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


class TestVertexColumns:
    def _reg(self):
        return fm.Registry()

    def test_classification_is_a_class(self):
        reg = self._reg()
        arr = np.array([2, 2, 5], np.uint8)
        out = fm.vertex_columns([(3, {"Classification": (arr, {})})], 3, reg)
        codes = out["meta_Classification"]
        assert codes.dtype.kind == "i" and codes[0] == codes[1] != codes[2]
        assert [t for t, _c in reg.classes("Classification")] == ["2", "5"]

    def test_enum_names_win(self):
        reg = self._reg()
        arr = np.array([0.0, 1.0], np.float32)
        fm.vertex_columns([(2, {"kind": (arr, {0: "Buildings", 1: "Trees"})})], 2, reg)
        assert [t for t, _c in reg.classes("kind")] == ["Buildings", "Trees"]

    def test_intensity_is_a_number(self):
        reg = self._reg()
        arr = np.array([0.25, 0.75], np.float32)
        out = fm.vertex_columns([(2, {"intensity": (arr, {})})], 2, reg)
        assert out["meta_intensity"].tolist() == [0.25, 0.75]
        assert (reg.get("intensity").lo, reg.get("intensity").hi) == (0.25, 0.75)

    def test_many_whole_numbers_are_numbers(self):
        reg = self._reg()
        arr = np.arange(100, dtype=np.uint16)
        fm.vertex_columns([(100, {"intensity": (arr, {})})], 100, reg)
        assert reg.get("intensity").kind == "number"

    def test_primitive_without_the_column_gets_zero(self):
        reg = self._reg()
        arr = np.array([3.5], np.float32)
        out = fm.vertex_columns([(2, {}), (1, {"h": (arr, {})})], 3, reg)
        assert out["meta_h"].tolist() == [0.0, 0.0, 3.5]

    def test_first_tile_decides(self):
        reg = self._reg()
        fm.vertex_columns([(2, {"c": (np.array([1, 2], np.uint8), {})})], 2, reg)
        out = fm.vertex_columns([(1, {"c": (np.array([7], np.uint8), {})})], 1, reg)
        assert out["meta_c"].dtype.kind == "i"


class TestTilesetMetadata:
    DOC = {
        "metadata": {"class": "t", "properties": {"author": "Cesium", "tileCount": 3}},
        "groups": [{"class": "g", "properties": {"layer": "buildings"}}],
        "root": {
            "metadata": {"class": "x", "properties": {"district": "A"}},
            "content": {"uri": "a.glb", "group": 0},
            "children": [
                {"metadata": {"properties": {"population": 9}},
                 "content": {"uri": "sub/b.glb", "metadata": {"properties": {"triangles": 12}}}},
                {"contents": [{"uri": "c.glb"}, {"uri": "d.glb", "group": 0}]},
            ],
        },
    }

    def _noted(self):
        meta = fm.TilesetMetadata()
        meta.note("https://x/y/tileset.json", self.DOC)
        return meta

    def test_tileset_level(self):
        assert self._noted().tileset == {"author": "Cesium", "tileCount": 3}

    def test_group_and_tile(self):
        assert self._noted().by_content["https://x/y/a.glb"] == {"district": "A", "layer": "buildings"}

    def test_child_inherits_and_content_adds(self):
        assert self._noted().by_content["https://x/y/sub/b.glb"] == {
            "district": "A", "population": 9, "triangles": 12}

    def test_multiple_contents(self):
        got = self._noted().by_content
        assert got["https://x/y/c.glb"] == {"district": "A"}
        assert got["https://x/y/d.glb"] == {"district": "A", "layer": "buildings"}

    def test_note_ignores_other_json(self):
        fm.TILESET_METADATA.clear()
        fm.note_tileset_json("https://x/s.json", b'{"tileAvailability": {}}')
        fm.note_tileset_json("https://x/t.json", b'{"metadata": 1, "root": broken')
        assert fm.TILESET_METADATA.tileset == {}


class TestStableCodes:
    def test_whole_numbers_keep_their_code_in_any_order(self):
        a, b = fm.Registry(), fm.Registry()
        a.codes_for("c", ["7", "0"])
        b.codes_for("c", ["0", "3", "7"])
        assert dict(a.classes("c"))["7"] == dict(b.classes("c"))["7"] == 8

    def test_text_never_takes_a_used_code(self):
        reg = fm.Registry()
        reg.codes_for("c", ["0", "roof", "1", "wall"])
        codes = [c for _t, c in reg.classes("c")]
        assert len(set(codes)) == 4 and min(codes) == 1
