"""tileset package: traversal/backends are bpy-free; props needs Blender."""
try:
    import bpy  # noqa: F401
    _HAS_BPY = True
except ImportError:
    _HAS_BPY = False

if _HAS_BPY:
    from . import props


def register():
    if _HAS_BPY:
        props.register()


def unregister():
    if _HAS_BPY:
        props.unregister()
