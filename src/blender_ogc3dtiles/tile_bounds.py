"""Show tile bounds: a viewport overlay with one wire box per visible tile.

The boxes are the tile objects' own bounding boxes (``Object.bound_box``), so they
show what each tile holds, for meshes, point clouds and splats alike (Blender's
own Bounds display draws nothing for splat objects). They are drawn by a 3D view
draw handler: no object is added to the scene and nothing shows in renders.

The tile list is gathered at most every REFRESH_S seconds; between two scans
each redraw only draws the cached batch.
"""
import time
import zlib

import bpy

REFRESH_S = 0.3
_EDGES = ((0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4),
          (0, 4), (1, 5), (2, 6), (3, 7))
_state = {"handle": None, "batch": None, "sig": None, "t": 0.0}


def _tile_color(name, base, random_colors):
    if not random_colors:
        return base
    import colorsys
    h = (zlib.crc32(name.encode("utf-8")) % 997) / 997.0
    r, g, b = colorsys.hsv_to_rgb(h, 0.75, 1.0)
    return (r, g, b, base[3])


def tile_boxes(scene, random_colors=False, base=(1.0, 0.45, 0.05, 1.0)):
    """([world corner], [rgba per corner]) of the visible tiles, 8 corners per tile."""
    coords, colors = [], []
    for o in scene.objects:
        if "tile_url" not in o or o.type != "MESH":
            continue
        try:
            if not o.visible_get():
                continue
        except RuntimeError:                         # not in the active view layer
            continue
        bb = o.bound_box
        if all(abs(v) < 1e-12 for c in (bb[0], bb[6]) for v in c):
            continue                                 # empty tile
        m = o.matrix_world
        coords.extend(tuple(m @ _vec(c)) for c in bb)
        colors.extend([_tile_color(o.name, base, random_colors)] * 8)
    return coords, colors


def _vec(c):
    from mathutils import Vector
    return Vector(c)


def _signature(scene, props):
    tiles = [o for o in scene.objects if "tile_url" in o and not o.hide_viewport]
    parents = {o.parent for o in tiles if o.parent is not None}
    return hash((tuple(o.name for o in tiles),
                 tuple(sorted(tuple(v for r in p.matrix_world for v in r) for p in parents)),
                 bool(props.tile_bounds_random), tuple(round(v, 3) for v in props.tile_bounds_color)))


def _rebuild(scene, props):
    import gpu
    from gpu_extras.batch import batch_for_shader
    coords, colors = tile_boxes(scene, props.tile_bounds_random, tuple(props.tile_bounds_color))
    if not coords:
        _state["batch"] = None
        return
    idx = [(b + i, b + j) for b in range(0, len(coords), 8) for i, j in _EDGES]
    shader = gpu.shader.from_builtin("POLYLINE_FLAT_COLOR")
    _state["batch"] = (shader, batch_for_shader(shader, "LINES", {"pos": coords, "color": colors},
                                                indices=idx))


def _draw():
    ctx = bpy.context
    scene = ctx.scene
    props = getattr(scene, "ogc3dtiles", None)
    if props is None or not props.show_tile_bounds:
        return
    now = time.monotonic()
    if _state["sig"] is None or now - _state["t"] >= REFRESH_S:
        _state["t"] = now
        sig = _signature(scene, props)
        if sig != _state["sig"]:
            _state["sig"] = sig
            try:
                _rebuild(scene, props)
            except Exception as e:                   # noqa: BLE001
                print(f"[3DTiles] tile bounds: {e}")
                _state["batch"] = None
    if _state["batch"] is None:
        return
    import gpu
    shader, batch = _state["batch"]
    region = ctx.region
    gpu.state.blend_set("ALPHA")
    gpu.state.depth_test_set("LESS_EQUAL" if props.tile_bounds_depth else "NONE")
    shader.uniform_float("viewportSize", (region.width, region.height))
    shader.uniform_float("lineWidth", float(props.tile_bounds_width))
    batch.draw(shader)
    gpu.state.depth_test_set("NONE")
    gpu.state.blend_set("NONE")


def enable(on: bool) -> None:
    """Add or remove the draw handler; redraws every 3D view."""
    if on and _state["handle"] is None and not bpy.app.background:
        _state["handle"] = bpy.types.SpaceView3D.draw_handler_add(_draw, (), "WINDOW", "POST_VIEW")
    elif not on and _state["handle"] is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_state["handle"], "WINDOW")
        _state["handle"] = None
    _state["sig"] = _state["batch"] = None
    _redraw()


def invalidate() -> None:
    _state["sig"] = None
    _state["t"] = 0.0
    _redraw()


def _redraw():
    wm = getattr(bpy.context, "window_manager", None)
    for w in (wm.windows if wm else ()):
        for a in w.screen.areas:
            if a.type == "VIEW_3D":
                a.tag_redraw()


def on_load(*_args) -> None:
    """A file was opened: follow its toggle."""
    scene = bpy.context.scene
    props = getattr(scene, "ogc3dtiles", None) if scene else None
    enable(bool(props and props.show_tile_bounds))


def register():
    if on_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(on_load)
    bpy.app.timers.register(lambda: on_load() or None, first_interval=0.5)


def unregister():
    if on_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(on_load)
    enable(False)
