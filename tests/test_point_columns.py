"""feature_meta.point_columns: application attributes of point tiles, without the metadata extension."""
import types

import numpy as np

from blender_ogc3dtiles.tileset import feature_meta


def _read(values):
    return lambda model, index, keep_integers=False: values[index]


def _prim(mode, attributes):
    return types.SimpleNamespace(mode=mode, attributes=attributes)


def test_underscore_attribute_is_a_column(monkeypatch):
    monkeypatch.setattr(feature_meta, "_structural", lambda model: None)
    values = {1: np.arange(4, dtype=np.uint16).reshape(-1, 1), 2: np.zeros((4, 2), np.float32), 3: np.zeros((4, 1))}
    prim = _prim(0, {"POSITION": 0, "_INTENSITY": 1, "_CESIUMOVERLAY_0": 2, "_BATCHID": 3})
    columns = feature_meta.point_columns(object(), prim, 4, _read(values))
    assert list(columns) == ["intensity"]
    assert columns["intensity"][0].tolist() == [0, 1, 2, 3]


def test_mesh_attributes_are_left_alone(monkeypatch):
    monkeypatch.setattr(feature_meta, "_structural", lambda model: None)
    prim = _prim(4, {"_INTENSITY": 1})
    assert feature_meta.point_columns(object(), prim, 4, _read({1: np.zeros((4, 1))})) == {}


def test_robust_range_ignores_rare_huge_values():
    registry = feature_meta.ColumnRegistry() if hasattr(feature_meta, "ColumnRegistry") else type(feature_meta.REGISTRY)()
    values = np.r_[np.linspace(100.0, 200.0, 2000), [65535.0]]
    registry.note_range("intensity", values, robust=True)
    assert registry.get("intensity").hi < 300.0


def test_byte_attribute_with_few_values_is_a_class_column(monkeypatch):
    """A LiDAR classification byte gets palette codes; 16-bit intensity stays a number."""
    monkeypatch.setattr(feature_meta, "_structural", lambda model: None)
    registry = type(feature_meta.REGISTRY)()
    values = {1: np.array([2, 5, 6, 2], np.uint8).reshape(-1, 1),
              2: np.array([10, 20, 30, 40], np.float32).reshape(-1, 1)}
    prim = _prim(0, {"_CLASSIFICATION": 1, "_INTENSITY": 2})
    columns = feature_meta.point_columns(object(), prim, 4, _read(values))
    out = feature_meta.vertex_columns([(4, columns)], 4, registry)
    assert registry.get("classification").kind == "class"
    assert registry.get("intensity").kind == "number"
    assert out[feature_meta.attribute_name("classification")].tolist() == [3, 6, 7, 3]   # code = value + 1
    assert dict(registry.classes("classification")) == {"2 Ground": 3, "5 High vegetation": 6, "6 Building": 7}


def test_user_defined_las_classes_keep_their_number(monkeypatch):
    monkeypatch.setattr(feature_meta, "_structural", lambda model: None)
    registry = type(feature_meta.REGISTRY)()
    prim = _prim(0, {"_CLASSIFICATION": 1})
    columns = feature_meta.point_columns(object(), prim, 2, _read({1: np.array([[64], [9]], np.uint8)}))
    feature_meta.vertex_columns([(2, columns)], 2, registry)
    assert dict(registry.classes("classification")) == {"9 Water": 10, "64": 65}
