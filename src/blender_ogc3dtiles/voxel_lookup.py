"""voxel_lookup.py — color other tilesets from a voxel tileset, per pixel.

The tiles of a voxel tileset are pasted into one grid over its root box, coarse
tiles first, kept as slices of one 2D atlas. A shared shader group reads the voxel
under each pixel from its world position: the class color mixes with the material's
own texture or vertex color, and with **Cut** the pixels outside all voxels turn
transparent, a boolean intersect without touching the geometry.

Rewriting the atlas and palette recompiles no shader, so tiles can stream in.
"""
from __future__ import annotations

import numpy as np

import bpy

from .tileset import feature_meta, voxels

GROUP = "OGC3D Voxel Lookup"
ATLAS = "OGC3D Voxel Atlas"
COLOR_NODE = "OGC3D Voxel Color"
CUT_MIX = "OGC3D Voxel Cut"
CUT_TRANSPARENT = "OGC3D Voxel Cut Transparent"
_REBUILD_DELAY = 1.5        # seconds without a new tile before the atlas is rewritten

_state = {"tiles": {}, "root": None, "shape": None, "scene": None, "scheduled": False}


def clear():
    _state.update(tiles={}, root=None, shape=None)


def add_tile(payload, key, world_from_ecef, scene):
    """Keep a voxel tile for the atlas. Its grid is in the tile box's own axes."""
    grid, box, root = payload["voxel_grid"], payload["voxel_matrix"], payload.get("voxel_root")
    if root is None:
        return False
    signs = voxels.grid_to_box(payload, box)
    flip = signs[1, 1] < 0
    lo, hi = voxels.box_range(root, box)
    columns = {name: (values[:, ::-1] if flip else values) for name, values in grid["grids"].items()}
    _state["tiles"][key] = (lo, hi, columns)
    if _state["root"] is None:
        _state["root"] = np.asarray(world_from_ecef, np.float64) @ root
        _state["shape"] = voxels.lookup_shape(grid["shape"], (hi - lo) / 2.0)
    _state["scene"] = scene.name
    _schedule()
    return True


def _schedule():
    if not _state["scheduled"]:
        _state["scheduled"] = True
        bpy.app.timers.register(_rebuild_timer, first_interval=_REBUILD_DELAY)


def _rebuild_timer():
    _state["scheduled"] = False
    scene = bpy.data.scenes.get(_state["scene"] or "")
    if scene is not None:
        try:
            rebuild(scene)
        except Exception as e:      # noqa: BLE001
            print(f"[3DTiles] voxel lookup: {e}")
    return None


def _active_attribute(props):
    """The grid to show: the panel's column when voxels have it, else their first."""
    if not _state["tiles"]:
        return None, None
    wanted = feature_meta.attribute_name(props.meta_column) if props.meta_column else ""
    names = {n for _lo, _hi, columns in _state["tiles"].values() for n in columns}
    if wanted in names:
        return props.meta_column, wanted
    first = sorted(names)[0] if names else None
    for col in feature_meta.REGISTRY.columns():
        if feature_meta.attribute_name(col[0]) == first:
            return col[0], first
    return None, first


def rebuild(scene):
    """Paste every kept tile into the grid and write the atlas."""
    column, attribute = _active_attribute(scene.ogc3dtiles)
    shape = _state["shape"]
    if attribute is None or shape is None:
        return False
    info = feature_meta.REGISTRY.get(column) if column else None
    number = info is not None and info.kind == "number"
    span = (info.lo, max(info.hi, info.lo + 1e-6)) if number else None
    volume = np.zeros(shape, np.uint8)
    # coarse first, so finer tiles replace them
    tiles = sorted(_state["tiles"].values(), key=lambda t: -float(np.prod(t[1] - t[0])))
    for lo, hi, columns in tiles:
        values = columns.get(attribute)
        if values is not None:
            voxels.paste(volume, voxels.lookup_codes(values, span), lo, hi)
    cols, rows = voxels.atlas_layout(shape)
    pixels = voxels.atlas_pixels(volume, cols, rows)
    height, width = pixels.shape[:2]
    img = bpy.data.images.get(ATLAS)
    if img is None or tuple(img.size) != (width, height):
        if img is not None:
            bpy.data.images.remove(img)
        img = bpy.data.images.new(ATLAS, width, height, alpha=False)
        img.colorspace_settings.name = "Non-Color"
        img.use_fake_user = True
    img.pixels.foreach_set(pixels.ravel())
    img.update()
    img.pack()                  # Cycles reads a generated image's pixels only once packed
    _update_group(scene, cols, rows, number)
    return True


def _math(ng, op, a, b=None):
    node = ng.nodes.new("ShaderNodeMath")
    node.operation = op
    for i, value in enumerate((a, b)):
        if value is None:
            continue
        if isinstance(value, (int, float)):
            node.inputs[i].default_value = float(value)
        else:
            ng.links.new(value, node.inputs[i])
    return node.outputs[0]


def _value(ng, name, default=0.0):
    node = ng.nodes.new("ShaderNodeValue")
    node.name = node.label = name
    node.outputs[0].default_value = default
    return node.outputs[0]


def ensure_group():
    ng = bpy.data.node_groups.get(GROUP)
    if ng is not None:
        return ng
    from .materials import _palette_image
    ng = bpy.data.node_groups.new(GROUP, "ShaderNodeTree")
    ng.interface.new_socket("Color", in_out="INPUT", socket_type="NodeSocketColor")
    ng.interface.new_socket("Color", in_out="OUTPUT", socket_type="NodeSocketColor")
    ng.interface.new_socket("Keep", in_out="OUTPUT", socket_type="NodeSocketFloat")
    nodes, links = ng.nodes, ng.links
    gin, gout = nodes.new("NodeGroupInput"), nodes.new("NodeGroupOutput")
    position = nodes.new("ShaderNodeNewGeometry").outputs["Position"]

    # world position -> 0..1 along the root box axes
    axes = []
    for i in range(3):
        dot = nodes.new("ShaderNodeVectorMath")
        dot.operation = "DOT_PRODUCT"
        dot.name = f"Axis {i}"
        links.new(position, dot.inputs[0])
        axes.append(_math(ng, "MULTIPLY", _math(ng, "ADD", _math(ng, "ADD", dot.outputs["Value"], _value(ng, f"Offset {i}")), 1.0), 0.5))
    u, v, w = axes
    inside = _math(ng, "MULTIPLY", _math(ng, "MULTIPLY", *[_math(ng, "MULTIPLY", _math(ng, "GREATER_THAN", a, 0.0), _math(ng, "LESS_THAN", a, 1.0)) for a in (u, v)]),
                   _math(ng, "MULTIPLY", _math(ng, "GREATER_THAN", w, 0.0), _math(ng, "LESS_THAN", w, 1.0)))

    # slice number -> its place in the atlas
    n_slices, n_cols, n_rows = _value(ng, "Slices", 1.0), _value(ng, "Cols", 1.0), _value(ng, "Rows", 1.0)
    slice_at = _math(ng, "FLOOR", _math(ng, "MULTIPLY", w, n_slices))
    row = _math(ng, "FLOOR", _math(ng, "DIVIDE", slice_at, n_cols))
    col = _math(ng, "SUBTRACT", slice_at, _math(ng, "MULTIPLY", row, n_cols))
    uv = nodes.new("ShaderNodeCombineXYZ")
    links.new(_math(ng, "DIVIDE", _math(ng, "ADD", col, u), n_cols), uv.inputs[0])
    links.new(_math(ng, "DIVIDE", _math(ng, "ADD", row, v), n_rows), uv.inputs[1])
    atlas = nodes.new("ShaderNodeTexImage")
    atlas.name = "Atlas"
    atlas.interpolation = "Closest"
    atlas.extension = "EXTEND"
    links.new(uv.outputs[0], atlas.inputs["Vector"])
    byte = _math(ng, "MULTIPLY", nodes["Atlas"].outputs["Color"], 255.0)
    has = _math(ng, "MULTIPLY", _math(ng, "GREATER_THAN", byte, 0.5), inside)

    # classes through the shared palette, numbers through a ramp
    palette_uv = nodes.new("ShaderNodeCombineXYZ")
    palette_uv.inputs[1].default_value = 0.5
    links.new(_math(ng, "DIVIDE", _math(ng, "ADD", _math(ng, "FLOOR", _math(ng, "ADD", byte, 0.5)), 0.5), 256.0), palette_uv.inputs[0])
    palette = nodes.new("ShaderNodeTexImage")
    palette.image = _palette_image()
    palette.interpolation = "Closest"
    palette.extension = "EXTEND"
    links.new(palette_uv.outputs[0], palette.inputs["Vector"])
    ramp = nodes.new("ShaderNodeValToRGB")
    els = ramp.color_ramp.elements
    els[0].color = (0.05, 0.03, 0.4, 1.0)
    els[1].color = (0.98, 0.9, 0.15, 1.0)
    els.new(0.5).color = (0.1, 0.6, 0.5, 1.0)
    links.new(_math(ng, "DIVIDE", _math(ng, "SUBTRACT", byte, 1.0), 254.0), ramp.inputs["Fac"])
    pick = nodes.new("ShaderNodeMix")
    pick.data_type = "RGBA"
    links.new(_value(ng, "Is Number"), pick.inputs[0])
    links.new(palette.outputs["Color"], pick.inputs[6])
    links.new(ramp.outputs["Color"], pick.inputs[7])

    out = nodes.new("ShaderNodeMix")
    out.data_type = "RGBA"
    links.new(_math(ng, "MULTIPLY", _value(ng, "Strength", 1.0), has), out.inputs[0])
    links.new(gin.outputs[0], out.inputs[6])
    links.new(pick.outputs[2], out.inputs[7])
    links.new(out.outputs[2], gout.inputs[0])
    links.new(_math(ng, "SUBTRACT", 1.0, _math(ng, "MULTIPLY", _value(ng, "Cut"), _math(ng, "SUBTRACT", 1.0, has))), gout.inputs[1])
    return ng


def _update_group(scene, cols, rows, number):
    ng = ensure_group()
    img = bpy.data.images.get(ATLAS)
    nodes = ng.nodes
    if img is not None and nodes["Atlas"].image != img:
        nodes["Atlas"].image = img
    nodes["Slices"].outputs[0].default_value = float(_state["shape"][2])
    nodes["Cols"].outputs[0].default_value = float(cols)
    nodes["Rows"].outputs[0].default_value = float(rows)
    nodes["Is Number"].outputs[0].default_value = 1.0 if number else 0.0
    inverse = np.linalg.inv(_state["root"])
    for i in range(3):
        nodes[f"Axis {i}"].inputs[1].default_value = [float(c) for c in inverse[i, :3]]
        nodes[f"Offset {i}"].outputs[0].default_value = float(inverse[i, 3])
    update_settings(scene)


def update_settings(scene):
    ng = bpy.data.node_groups.get(GROUP)
    if ng is not None:
        props = scene.ogc3dtiles
        ng.nodes["Strength"].outputs[0].default_value = props.voxel_mix
        ng.nodes["Cut"].outputs[0].default_value = 1.0 if props.voxel_cut else 0.0


def apply_material(mat) -> bool:
    if mat is None or not mat.use_nodes or mat.node_tree is None:
        return False
    nt = mat.node_tree
    if nt.nodes.get(COLOR_NODE) is not None:
        return False
    from .materials import _color_target, _emission_target
    target = _color_target(mat)
    out = next((n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"), None)
    if target is None or out is None or not out.inputs["Surface"].links:
        return False
    node = nt.nodes.new("ShaderNodeGroup")
    node.node_tree = ensure_group()
    node.name = node.label = COLOR_NODE
    node.location = (target.node.location.x - 220, target.node.location.y - 260)
    if target.links:
        nt.links.new(target.links[0].from_socket, node.inputs[0])
    else:
        node.inputs[0].default_value = target.default_value
    nt.links.new(node.outputs[0], target)
    emission = _emission_target(mat)
    if emission is not None:             # unlit points: their own color would show under it
        nt.links.new(node.outputs[0], emission)

    source = out.inputs["Surface"].links[0].from_socket
    clear = nt.nodes.new("ShaderNodeBsdfTransparent")
    clear.name = clear.label = CUT_TRANSPARENT
    mix = nt.nodes.new("ShaderNodeMixShader")
    mix.name = mix.label = CUT_MIX
    mix.location = (out.location.x - 180, out.location.y + 200)
    nt.links.new(node.outputs["Keep"], mix.inputs["Fac"])
    nt.links.new(clear.outputs[0], mix.inputs[1])
    nt.links.new(source, mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    return True


def remove_material(mat) -> bool:
    if mat is None or not mat.use_nodes or mat.node_tree is None:
        return False
    nt = mat.node_tree
    node = nt.nodes.get(COLOR_NODE)
    if node is None:
        return False
    source = node.inputs[0].links[0].from_socket if node.inputs[0].links else None
    targets = [l.to_socket for l in node.outputs[0].links]
    mix = nt.nodes.get(CUT_MIX)
    if mix is not None:
        shader = mix.inputs[2].links[0].from_socket if mix.inputs[2].links else None
        outs = [l.to_socket for l in mix.outputs[0].links]
        if shader is not None:
            for t in outs:
                nt.links.new(shader, t)
        nt.nodes.remove(mix)
    clear = nt.nodes.get(CUT_TRANSPARENT)
    if clear is not None:
        nt.nodes.remove(clear)
    nt.nodes.remove(node)
    if source is not None:
        for t in targets:
            nt.links.new(source, t)
    return True


def sync_materials(scene) -> int:
    """Follow the Voxels setting on the tiles already loaded."""
    from .materials import tile_materials
    on = scene.ogc3dtiles.voxel_display == "PROJECT"
    return sum(bool(apply_material(m) if on else remove_material(m)) for m in tile_materials())
