"""Voxel tiles: grid order, exposed faces, placement, and the subtree request fixes."""
import base64
import json
import struct

import numpy as np
import pytest

from blender_ogc3dtiles.tileset import asset_fixes, voxels


def _unit_box(mirror=False):
    return voxels.box_matrix((10.0, 20.0, 30.0), np.diag((2.0, -3.0 if mirror else 3.0, 4.0)))


def _payload(unit, y_up=True):
    return {"unit_verts": unit, "voxel_y_up": y_up, "voxel_grid": None,
            "faces": np.array([[0, 1, 2]], np.int32), "points": False}


class TestGridOrder:
    def test_y_up_box_grid(self):
        # glTF dims (x=2, y=3, z=4): value = x + 10 y + 100 z, x fastest
        dims = (2, 3, 4)
        flat = np.array([x + 10 * y + 100 * z for z in range(4) for y in range(3) for x in range(2)], float)
        grid = voxels.to_tile_axes(flat, dims, True)
        assert grid.shape == (2, 4, 3) == voxels.grid_shape(dims, True)
        assert grid[1, 3, 2] == 1 + 10 * 2 + 100 * 3

    def test_z_up_grid(self):
        dims = (2, 3, 4)
        flat = np.array([x + 10 * y + 100 * z for z in range(4) for y in range(3) for x in range(2)], float)
        grid = voxels.to_tile_axes(flat, dims, False)
        assert grid.shape == (2, 3, 4) == voxels.grid_shape(dims, False)
        assert grid[1, 2, 3] == 1 + 10 * 2 + 100 * 3

    def test_padding_is_cut(self):
        padding = {"before": (1, 0, 0), "after": (1, 0, 0)}
        flat = np.array([x for _z in range(1) for _y in range(1) for x in range(4)], float)
        grid = voxels.to_tile_axes(flat, (2, 1, 1), True, padding)
        assert grid.ravel().tolist() == [1.0, 2.0]


class TestExposedFaces:
    def test_single_cell_has_six_outward_faces(self):
        mask = np.ones((1, 1, 1), bool)
        corners, cells = voxels.exposed_quads(mask)
        assert len(corners) == 6 == len(cells)
        centre = np.array((0.5, 0.5, 0.5))
        for quad in corners:
            normal = np.cross(quad[1] - quad[0], quad[2] - quad[0])
            assert normal @ (quad.mean(axis=0) - centre) > 0

    def test_shared_faces_are_gone(self):
        corners, _ = voxels.exposed_quads(np.ones((2, 1, 1), bool))
        assert len(corners) == 10

    def test_hollow_inside_stays_hidden(self):
        corners, _ = voxels.exposed_quads(np.ones((3, 3, 3), bool))
        assert len(corners) == 6 * 9

    def test_empty(self):
        corners, cells = voxels.exposed_quads(np.zeros((2, 2, 2), bool))
        assert len(corners) == 0 == len(cells)


class TestPlacement:
    def test_right_handed_box_flips_y_grid(self):
        # grid y = +1 is glTF z = max, which is tile -Y
        out = voxels.place(_payload(np.array([[0.0, 1.0, 0.0]])), box=_unit_box())
        assert out["offset"] == pytest.approx([10.0, 17.0, 30.0])

    def test_mirrored_box_holds_the_flip(self):
        # GeoTOP: the box's Y already points the other way, the map stays a rotation
        out = voxels.place(_payload(np.array([[0.0, 1.0, 0.0]])), box=_unit_box(mirror=True))
        assert out["offset"] == pytest.approx([10.0, 17.0, 30.0])

    def test_faces_turn_when_the_map_mirrors(self):
        out = voxels.place(_payload(np.zeros((3, 3))), box=_unit_box())
        assert out["faces"].tolist() == [[0, 2, 1]]

    def test_z_up_grid_keeps_y(self):
        out = voxels.place(_payload(np.array([[0.0, 1.0, 0.0]]), y_up=False), box=_unit_box())
        assert out["offset"] == pytest.approx([10.0, 23.0, 30.0])
        assert out["faces"].tolist() == [[0, 1, 2]]

    def test_region_on_the_equator(self):
        out = voxels.place(_payload(np.array([[-1.0, -1.0, -1.0]]), y_up=False), region=(0, 0, 0.1, 0.1, 100.0, 200.0))
        assert out["offset"] == pytest.approx([6378237.0, 0.0, 0.0])

    def test_volume_matrix_centres_the_cells(self):
        payload = _payload(np.zeros((1, 3)))
        payload["voxel_grid"] = {"shape": (2, 2, 2)}
        voxels.place(payload, box=voxels.box_matrix((0, 0, 0), np.eye(3)))
        m = voxels.volume_matrix(payload)
        assert (m @ (0, 0, 0, 1))[:3] == pytest.approx((-0.5, 0.5, -0.5))
        assert (m @ (1, 1, 1, 1))[:3] == pytest.approx((0.5, -0.5, 0.5))

    def test_no_volume_for_a_region(self):
        payload = _payload(np.zeros((1, 3)), y_up=False)
        payload["voxel_grid"] = {"shape": (2, 2, 2)}
        voxels.place(payload, region=(0, 0, 0.1, 0.1, 0.0, 1.0))
        assert voxels.volume_matrix(payload) is None

    def test_exaggeration_keeps_the_center(self):
        center = (0.0, 0.0, 6378137.0)
        m = voxels.exaggeration_matrix(center, 10.0)
        assert (m @ (*center, 1.0))[:3] == pytest.approx(center)
        assert (m @ (5.0, 0.0, 6378138.0, 1.0))[:3] == pytest.approx((5.0, 0.0, 6378147.0))


class TestExaggeration:
    def test_follows_the_geodetic_normal(self):
        lat, lon = np.radians(52.0), np.radians(5.0)
        center = voxels.region_to_ecef(np.array(lon), np.array(lat), np.array(0.0))
        east = np.array((-np.sin(lon), np.cos(lon), 0.0))
        m = voxels.exaggeration_matrix(center, 80.0)
        moved = (m @ (*(center + 16000.0 * east), 1.0))[:3] - center
        assert moved == pytest.approx(16000.0 * east, abs=1e-6)


class TestDocument:
    def test_glb_json_chunk(self):
        js = json.dumps({"asset": {"version": "2.0"}}).encode()
        glb = b"glTF" + struct.pack("<II", 2, 20 + len(js)) + struct.pack("<I", len(js)) + b"JSON" + js
        assert voxels.gltf_document(glb)["asset"]["version"] == "2.0"

    def test_column_names_from_the_property_attribute(self):
        doc = {"extensions": {"EXT_structural_metadata": {"propertyAttributes": [
            {"properties": {"lithok": {"attribute": "_LITHOK"}}}]}}}
        prim = {"extensions": {"EXT_structural_metadata": {"propertyAttributes": [0]}}}
        assert voxels._column_names(doc, prim) == {"_LITHOK": "lithok"}


class TestScalarTable:
    def _columns(self, values, valid=None):
        values = np.asarray(values, np.float32)
        return {"lithok": {"values": values, "valid": np.ones_like(values, bool) if valid is None else valid}}

    def test_whole_numbers_are_classes(self, fresh_registry):
        columns = self._columns(np.array([[[1.0, 2.0, 2.0]]]))
        row, table, kinds = voxels.scalar_table(columns, np.array([[0, 0, 0], [0, 0, 1], [0, 0, 2]]), fresh_registry)
        assert kinds == {"lithok": "class"}
        assert [table["rows"][i][0] for i in row] == ["1", "2", "2"]
        assert [t for t, _c in fresh_registry.classes("lithok")] == ["1", "2"]

    def test_fractions_are_numbers(self, fresh_registry):
        columns = self._columns(np.array([[[0.5, 2.25]]]))
        _row, table, kinds = voxels.scalar_table(columns, np.array([[0, 0, 0], [0, 0, 1]]), fresh_registry)
        assert kinds == {"lithok": "number"}
        assert sorted(r[0] for r in table["rows"]) == [0.5, 2.25]
        assert fresh_registry.get("lithok").hi == 2.25

    def test_a_long_field_keeps_a_short_table(self, fresh_registry):
        values = np.linspace(0.0, 1.0, 5000, dtype=np.float32).reshape(1, 1, -1)
        cells = np.stack([np.zeros(5000, int), np.zeros(5000, int), np.arange(5000)], axis=1)
        _row, table, _kinds = voxels.scalar_table(self._columns(values), cells, fresh_registry)
        assert len(table["rows"]) <= 256


@pytest.fixture
def fresh_registry():
    from blender_ogc3dtiles.tileset.feature_meta import Registry
    return Registry()


class TestSubtreeRequests:
    def test_decode_base64(self):
        body = base64.b64encode(b"\xff\x01").decode()
        assert asset_fixes.decode_data_uri(f"data:application/octet-stream;base64,{body}") == (
            "application/octet-stream", b"\xff\x01")

    def test_decode_behind_a_base_url(self):
        assert asset_fixes.decode_data_uri("https://x/y/data:text/plain,a%20b") == ("text/plain", b"a b")

    def test_plain_urls_are_left_alone(self):
        assert asset_fixes.decode_data_uri("https://x/tileset.json") is None

    def test_broken_base64_is_left_alone(self):
        assert asset_fixes.decode_data_uri("data:;base64,a") is None

    def test_missing_byte_length_comes_from_the_views(self):
        doc = {"buffers": [{"uri": "data:,x"}], "tileAvailability": {"bufferView": 0},
               "bufferViews": [{"buffer": 0, "byteOffset": 2, "byteLength": 10}]}
        out = json.loads(asset_fixes.complete_subtree_json(json.dumps(doc).encode()))
        assert out["buffers"][0]["byteLength"] == 12

    def test_class_tileset_places_cells_along_the_tile_axes(self, tmp_path):
        grid = np.zeros((4, 3, 2), np.uint8)
        grid[3, 0, 1] = 7                       # far east, south, top
        frame = np.eye(4)
        frame[:3, 3] = (100.0, 200.0, 300.0)
        path = voxels.write_class_tileset(str(tmp_path), grid, frame, (1.0, 2.0, 3.0), 2.0)
        doc = json.load(open(path))
        assert doc["root"]["boundingVolume"]["box"] == [101.0, 202.0, 303.0, 4.0, 0, 0, 0, 3.0, 0, 0, 0, 2.0]
        gltf = json.load(open(tmp_path / "tiles/0/0/0/0.gltf"))
        assert gltf["meshes"][0]["primitives"][0]["extensions"]["EXT_primitive_voxels"]["dimensions"] == [4, 2, 3]
        values = np.fromfile(tmp_path / "tiles/0/0/0/0.bin", np.float32).reshape(3, 2, 4)
        assert values[2, 1, 3] == 7.0 and np.count_nonzero(values) == 1   # [tile -y, tile z, tile x]

    def test_content_availability_becomes_an_array(self):
        doc = {"tileAvailability": {"constant": 1}, "contentAvailability": {"constant": 1}}
        out = json.loads(asset_fixes.complete_subtree_json(json.dumps(doc).encode()))
        assert out["contentAvailability"] == [{"constant": 1}]

    def test_complete_subtrees_and_other_json_stay_the_same_object(self):
        whole = json.dumps({"buffers": [{"byteLength": 3}], "tileAvailability": {}}).encode()
        assert asset_fixes.complete_subtree_json(whole) is whole
        other = b'{"root": {}}'
        assert asset_fixes.complete_subtree_json(other) is other


class TestLookup:
    def test_range_of_a_child_box(self):
        root = voxels.box_matrix((0.0, 0.0, 0.0), np.diag((4.0, 4.0, 2.0)))
        child = voxels.box_matrix((2.0, -2.0, 1.0), np.diag((2.0, 2.0, 1.0)))
        lo, hi = voxels.box_range(root, child)
        assert lo.tolist() == pytest.approx([0.0, -1.0, 0.0])
        assert hi.tolist() == pytest.approx([1.0, 0.0, 1.0])

    def test_range_of_a_mirrored_box(self):
        axes = np.array([[4.0, 0, 0], [0, -4.0, 0], [0, 0, 2.0]])
        root = voxels.box_matrix((0.0, 0.0, 0.0), axes)
        child = voxels.box_matrix((0.0, -2.0, 0.0), axes / 2.0)
        lo, hi = voxels.box_range(root, child)
        assert lo[1] == pytest.approx(0.0) and hi[1] == pytest.approx(1.0)

    def test_shape_keeps_proportions_within_budget(self):
        nx, ny, nz = voxels.lookup_shape((82, 68, 31), (0.25, 0.25, 0.25))
        assert nx * ny * nz <= 12_500_000
        assert nx / ny == pytest.approx(82 / 68, abs=0.02)
        assert voxels.atlas_layout((nx, ny, nz)) is not None

    def test_a_long_grid_still_fits(self):
        shape = voxels.lookup_shape((4000, 10, 10), (1.0, 1.0, 1.0))
        cols, rows = voxels.atlas_layout(shape)
        assert cols * shape[0] <= voxels.MAX_ATLAS and rows * shape[1] <= voxels.MAX_ATLAS

    def test_paste_upsamples_and_replaces(self):
        volume = np.ones((4, 4, 2), np.uint8)
        voxels.paste(volume, np.array([[[7]], [[9]]], np.uint8), np.array((0.0, -1.0, -1.0)), np.array((1.0, 1.0, 1.0)))
        assert volume[0, 0, 0] == 1 and volume[2, 0, 0] == 7 and volume[3, 3, 1] == 9

    def test_atlas_places_slices(self):
        volume = np.zeros((2, 3, 3), np.uint8)
        volume[1, 2, 2] = 255
        pixels = voxels.atlas_pixels(volume, 2, 2)
        assert pixels.shape == (6, 4, 4)
        # slice 2 is row 1, col 0; x=1, y=2 -> row 3 + 2, column 1
        assert pixels[5, 1, 0] == 1.0 and pixels[..., 0].sum() == 1.0

    def test_codes(self):
        assert voxels.lookup_codes(np.array([0.0, 3.0, 8.0])).tolist() == [0, 3, 8]
        out = voxels.lookup_codes(np.array([0.0, 1.0, 2.0]), (1.0, 2.0))
        assert out[0] == 0 and out[1] == 1 and out[2] == 255
