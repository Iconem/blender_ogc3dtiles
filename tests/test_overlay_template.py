"""native_backend.xyz_template: XYZ row order to cesium-native placeholders."""
from blender_ogc3dtiles.tileset.native_backend import xyz_template


def test_xyz_y_becomes_reverse_y():
    assert xyz_template("https://tile.osm.org/{z}/{x}/{y}.png") == "https://tile.osm.org/{z}/{x}/{reverseY}.png"


def test_tms_order_is_opt_in():
    assert xyz_template("https://tms.example/{z}/{x}/{-y}.png") == "https://tms.example/{z}/{x}/{y}.png"


def test_other_placeholders_untouched():
    u = "https://a.example/{z}/{y}/{x}?k={westDegrees}"
    assert xyz_template(u) == "https://a.example/{z}/{reverseY}/{x}?k={westDegrees}"


def test_percent_encoded_braces_are_decoded():
    u = "https://mt1.example/vt/lyrs=y&x=%7Bx%7D&y=%7by%7d&z=%7Bz%7D"
    assert xyz_template(u) == "https://mt1.example/vt/lyrs=y&x={x}&y={reverseY}&z={z}"


def test_decode_braces_leaves_other_encodings():
    from blender_ogc3dtiles.tileset.native_backend import decode_braces
    assert decode_braces("https://a/%7Bz%7D?u=b%2Fc") == "https://a/{z}?u=b%2Fc"
