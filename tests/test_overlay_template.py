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


def test_quadkey():
    from blender_ogc3dtiles.tileset.asset_fixes import quadkey
    assert quadkey(0, 0, 0) == ""
    assert quadkey(1, 1, 0) == "1"
    assert quadkey(3, 3, 5) == "213"          # Bing's documented example
    assert quadkey(2, 3, 3) == "33"


def test_quadkey_and_subdomain_round_trip():
    from blender_ogc3dtiles.tileset.asset_fixes import expand_tile_tokens
    t = xyz_template("https://ecn.t{0-3}.tiles.virtualearth.net/tiles/a{q}.jpeg?g=1")
    assert t == "https://ecn.t~sd03~.tiles.virtualearth.net/tiles/a~qk{z}.{x}.{reverseY}~.jpeg?g=1"
    # what cesium-native requests for XYZ tile z=3 x=3 y=5 (reverseY = XYZ y)
    url = expand_tile_tokens(t.replace("{z}", "3").replace("{x}", "3").replace("{reverseY}", "5"))
    assert url.startswith("https://ecn.t") and url.endswith(".tiles.virtualearth.net/tiles/a213.jpeg?g=1")
    assert url[len("https://ecn.t")] in "0123"
    assert expand_tile_tokens(url) == url


def test_subdomain_is_stable_per_tile():
    from blender_ogc3dtiles.tileset.asset_fixes import expand_tile_tokens
    u = "https://mt~sd03~.google.com/vt/lyrs=y&x=1&y=2&z=3"
    assert expand_tile_tokens(u) == expand_tile_tokens(u)
    assert expand_tile_tokens("https://a/{q}~x") == "https://a/{q}~x"


def test_quadkey_alias_and_no_token_untouched():
    assert "~qk{z}.{x}.{reverseY}~" in xyz_template("https://a/{quadkey}.png")
    assert xyz_template("https://a/{z}/{x}/{y}.png") == "https://a/{z}/{x}/{reverseY}.png"
