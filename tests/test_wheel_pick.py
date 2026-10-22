"""addon_prefs.pick_wheel: choose the release asset for this interpreter."""
import sys
import types

# addon_prefs imports bpy at module level; stub it for the pure function
sys.modules.setdefault("bpy", types.SimpleNamespace(
    types=types.SimpleNamespace(AddonPreferences=object, Operator=object),
    props=types.SimpleNamespace(**{n: (lambda *a, **k: None) for n in
                                   ("StringProperty", "BoolProperty", "EnumProperty",
                                    "IntProperty", "FloatProperty")})))
from blender_ogc3dtiles.addon_prefs import pick_wheel  # noqa: E402

ASSETS = [
    "cesium_python-0.1.0-cp311-cp311-manylinux_2_28_x86_64.whl",
    "cesium_python-0.1.0-cp312-cp312-manylinux_2_28_x86_64.whl",
    "cesium_python-0.1.0-cp313-cp313-manylinux_2_28_x86_64.whl",
    "cesium_python-0.1.0-cp313-cp313-win_amd64.whl",
    "cesium_python-0.1.0-cp313-cp313-macosx_12_0_arm64.whl",
    "cesium_python-0.1.0.tar.gz",
]


def test_pick_exact():
    assert pick_wheel(ASSETS, "cp313", ("win_amd64",)).endswith("win_amd64.whl")
    assert "cp312-cp312-manylinux" in pick_wheel(ASSETS, "cp312", ("manylinux", "x86_64"))
    assert "arm64" in pick_wheel(ASSETS, "cp313", ("macosx", "arm64"))


def test_pick_missing():
    assert pick_wheel(ASSETS, "cp311", ("win_amd64",)) is None
    assert pick_wheel(ASSETS, "cp313", ("manylinux", "aarch64")) is None


def test_pick_abi3():
    names = ["cesium_python-0.2.0-cp311-abi3-win_amd64.whl"]
    assert pick_wheel(names, "cp313", ("win_amd64",)) == names[0]
