"""
tests/conftest.py
Stub bpy so addon submodules can be imported without Blender.
The package (blender_ogc3dtiles) is installed from addon/ via hatch sources.
"""
import sys, os, types, pytest

def _make_bpy_stub():
    bpy = types.ModuleType("bpy")
    props = types.ModuleType("bpy.props")
    for name in ("StringProperty", "FloatProperty", "IntProperty", "BoolProperty",
                 "EnumProperty", "PointerProperty", "FloatVectorProperty", "CollectionProperty"):
        setattr(props, name, lambda **kw: None)
    bpy.props = props
    sys.modules["bpy.props"] = props

    btypes = types.ModuleType("bpy.types")
    class _Base:
        def __init_subclass__(cls, **kw): pass
    for name in ("PropertyGroup", "AddonPreferences", "Operator", "Panel", "UIList",
                 "Scene", "Object", "Context"):
        setattr(btypes, name, _Base)
    bpy.types = btypes
    sys.modules["bpy.types"] = btypes

    utils = types.ModuleType("bpy.utils")
    utils.register_class   = lambda cls: None
    utils.unregister_class = lambda cls: None
    bpy.utils = utils
    sys.modules["bpy.utils"] = utils

    bpy.data    = types.SimpleNamespace(objects=[], meshes=[])
    bpy.context = types.SimpleNamespace()
    bpy.ops     = types.SimpleNamespace()
    return bpy

sys.modules.setdefault("bpy", _make_bpy_stub())

@pytest.fixture
def simple_tile_tree():
    from blender_ogc3dtiles.tileset.traversal import Tile, BoundingVolume
    def t(cx, cy, cz, r, err, uri=None, children=None):
        return Tile(bounding_volume=BoundingVolume(sphere=[cx,cy,cz,r]),
                    geometric_error=err, content_uri=uri, children=children or [])
    gc      = t(6_378_200, 0, 0, 10,    10,  "gc.glb")
    child_a = t(6_378_200, 0, 0, 500,   100, "ca.glb")
    child_b = t(6_378_200, 0, 0, 500,   100, "cb.glb", [gc])
    root    = t(6_378_137, 0, 0, 10000, 500, None,     [child_a, child_b])
    return root

@pytest.fixture
def camera_close():
    return (6_378_200.0, 0.0, 0.0)

@pytest.fixture
def camera_far():
    return (6_378_137.0 + 100_000.0, 0.0, 0.0)
