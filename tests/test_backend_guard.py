"""backend.pyd_imports: detect a dynamic MSVC runtime dependency in a module file."""
import pathlib
import sys
import types

sys.modules.setdefault("bpy", types.SimpleNamespace(app=types.SimpleNamespace(version=(4, 5, 2))))
from blender_ogc3dtiles.tileset import backend  # noqa: E402


def test_pyd_imports(tmp_path: pathlib.Path):
    f = tmp_path / "dyn.pyd"
    f.write_bytes(b"MZ... KERNEL32.dll MSVCP140.dll VCRUNTIME140.dll python311.dll")
    assert backend.pyd_imports(f) == ["MSVCP140.dll", "VCRUNTIME140.dll"]
    g = tmp_path / "static.pyd"
    g.write_bytes(b"MZ... KERNEL32.dll python311.dll")
    assert backend.pyd_imports(g) == []
    assert backend.pyd_imports(tmp_path / "missing.pyd") == []


def test_host_crt_rule():
    assert backend.OLD_CRT_BLENDER_MAX == (5, 0, 0)
    bpy = sys.modules["bpy"]
    if getattr(getattr(bpy, "app", None), "version", None) == (4, 5, 2):
        assert backend.host_crt_too_old() is (sys.platform == "win32")
