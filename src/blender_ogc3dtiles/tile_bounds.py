"""Show tile bounds: a viewport overlay with one wire outline per visible tile.

Two sources (scene property ``tile_bounds``):
- OBJECT: the tile objects' own bounding boxes (``Object.bound_box``), what each
  tile holds, for meshes, point clouds and splats alike (Blender's own Bounds
  display draws nothing for splat objects);
- VOLUME: the bounding volumes the tileset declares for the tiles cesium-native
  shows (box, region or sphere), recorded by the native backend as tiles load.

Outlines are drawn by a 3D view draw handler: no object is added to the scene
and nothing shows in renders. The tile list is gathered at most every REFRESH_S
seconds; between two scans each redraw only draws the cached batch.
"""
import time
import zlib

import bpy
import numpy as np

REFRESH_S = 0.3
_EDGES = ((0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4),
          (0, 4), (1, 5), (2, 6), (3, 7))
_state = {"handle": None, "batch": None, "sig": None, "t": 0.0}


def _tile_color(name, base, random_colors):
    if not random_colors:
        return tuple(base)
    import colorsys
    h = (zlib.crc32(str(name).encode("utf-8")) % 997) / 997.0
    r, g, b = colorsys.hsv_to_rgb(h, 0.75, 1.0)
    return (r, g, b, base[3])


def _visible_tiles(scene):
    for o in scene.objects:
        if "tile_url" not in o or o.type != "MESH":
            continue
        try:
            if o.visible_get():
                yield o
        except RuntimeError:                         # not in the active view layer
            continue


def object_lines(scene, random_colors=False, base=(1.0, 0.45, 0.05, 1.0)):
    """(points, rgba per point, segments) of the visible tiles' object boxes."""
    pts, cols, segs = [], [], []
    for o in _visible_tiles(scene):
        bb = np.asarray([tuple(c) for c in o.bound_box], np.float64)
        if not bb.any():
            continue                                 # empty tile
        m = np.asarray(o.matrix_world, np.float64)
        b = len(pts) * 8
        pts.append(bb @ m[:3, :3].T + m[:3, 3])
        cols.extend([_tile_color(o.name, base, random_colors)] * 8)
        segs.extend((b + i, b + j) for i, j in _EDGES)
    if not pts:
        return [], [], []
    return np.concatenate(pts), cols, segs


def _streams():
    try:
        from .ui import _state as ui_state
    except Exception:                                # noqa: BLE001
        return []
    return [st for st in ui_state.get("streams", {}).values() if st.get("backend") is not None]


def _ecef_to_world(st):
    """4 x 4 float64: ECEF to Blender world for one stream's tiles."""
    from .ui import _enu_from_ecef
    props = bpy.context.scene.ogc3dtiles
    root = bpy.data.objects.get(st.get("root_obj") or "")
    to_world = np.asarray(root.matrix_world, np.float64) if root is not None else np.eye(4)
    return to_world @ np.asarray(_enu_from_ecef(props, st), np.float64)


def volume_lines(random_colors=False, base=(1.0, 0.45, 0.05, 1.0)):
    """(points, rgba per point, segments) of the 3D Tiles volumes of the tiles
    each stream shows. Done in doubles until the points are in the scene frame."""
    from .tileset.volume_lines import shape_lines
    pts, cols, segs, n = [], [], [], 0
    for st in _streams():
        vols = getattr(st["backend"], "tile_volumes", None)
        if not vols:
            continue
        m = _ecef_to_world(st)
        for key in st.get("render_keys") or ():
            shape = vols.get(key)
            if shape is None:
                continue
            p, s = shape_lines(shape)
            pts.append(p @ m[:3, :3].T + m[:3, 3])
            cols.extend([_tile_color(key, base, random_colors)] * len(p))
            segs.extend((n + int(a), n + int(b)) for a, b in s)
            n += len(p)
    if not pts:
        return [], [], []
    return np.concatenate(pts), cols, segs


def _signature(scene, props):
    mode = props.tile_bounds
    look = (mode, bool(props.tile_bounds_random), tuple(round(v, 3) for v in props.tile_bounds_color))
    if mode == "VOLUME":
        keys = tuple(frozenset(st.get("render_keys") or ()) for st in _streams())
        roots = [bpy.data.objects.get(st.get("root_obj") or "") for st in _streams()]
        mats = tuple(tuple(v for r in o.matrix_world for v in r) for o in roots if o is not None)
        return hash((look, keys, mats))
    tiles = [o for o in scene.objects if "tile_url" in o and not o.hide_viewport]
    parents = {o.parent for o in tiles if o.parent is not None}
    return hash((look, tuple(o.name for o in tiles),
                 tuple(sorted(tuple(v for r in p.matrix_world for v in r) for p in parents))))


def _rebuild(scene, props):
    import gpu
    from gpu_extras.batch import batch_for_shader
    fn = volume_lines if props.tile_bounds == "VOLUME" else (lambda r, b: object_lines(scene, r, b))
    pts, cols, segs = fn(props.tile_bounds_random, tuple(props.tile_bounds_color))
    if not len(pts):
        _state["batch"] = None
        return
    shader = gpu.shader.from_builtin("POLYLINE_FLAT_COLOR")
    coords = [tuple(p) for p in np.asarray(pts, np.float32)]
    _state["batch"] = (shader, batch_for_shader(shader, "LINES", {"pos": coords, "color": cols},
                                                indices=segs))


def _draw():
    ctx = bpy.context
    scene = ctx.scene
    props = getattr(scene, "ogc3dtiles", None)
    if props is None or props.tile_bounds == "OFF":
        return
    now = time.monotonic()
    if _state["sig"] is None or now - _state["t"] >= REFRESH_S:
        _state["t"] = now
        try:
            sig = _signature(scene, props)
            if sig != _state["sig"]:
                _state["sig"] = sig
                _rebuild(scene, props)
        except Exception as e:                       # noqa: BLE001
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
    invalidate()


def invalidate() -> None:
    _state["sig"] = _state["batch"] = None
    _state["t"] = 0.0
    wm = getattr(bpy.context, "window_manager", None)
    for w in (wm.windows if wm else ()):
        for a in w.screen.areas:
            if a.type == "VIEW_3D":
                a.tag_redraw()


def on_load(*_args) -> None:
    """A file was opened: follow its setting."""
    scene = bpy.context.scene
    props = getattr(scene, "ogc3dtiles", None) if scene else None
    enable(bool(props and props.tile_bounds != "OFF"))


def register():
    bpy.app.handlers.persistent(on_load)            # kept when another file opens
    if on_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(on_load)
    bpy.app.timers.register(lambda: on_load() or None, first_interval=0.5)


def unregister():
    if on_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(on_load)
    enable(False)
