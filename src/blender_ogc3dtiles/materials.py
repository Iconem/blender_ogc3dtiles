"""
materials.py — "Relight" node group for photogrammetry tiles.

Photogrammetry textures carry the capture lighting. This module builds ONE
shared, user-editable node group ("OGC3D Relight") that derives roughness,
a gold/metal mask and a shadow lift from the albedo, and swaps every tile
material's Principled BSDF for it (the Image Texture node stays).

Everything tunable lives in Value nodes inside the group (named, so the
sidebar can show them as sliders); because the group is shared, editing it
once — in the panel or in the Shader Editor — changes every tile.
"""
from __future__ import annotations

import bpy
from bpy.types import Operator

GROUP_NAME = "OGC3D Relight"
TUNABLES = (
    # (node name, default, min, max, description)
    ("Albedo Strength", 1.0, 0.0, 1.0, "1 = photo albedo, 0 = pure clay (the 'Clay Color' RGB node "
                                       "in the group)"),
    ("Shadow Lift", 1.3, 0.5, 3.0, "Gamma on the albedo: >1 lifts baked shadows"),
    ("Saturation", 1.1, 0.0, 2.0, "Albedo saturation"),
    ("Baked Light", 0.5, 0.0, 1.0, "0 = fully lit Principled BSDF, 1 = unlit albedo. Photogrammetry "
                                  "already carries its lighting; higher values also hide "
                                  "shading seams between tiles"),
    ("Roughness Dark", 0.95, 0.0, 1.0, "Roughness for dark albedo"),
    ("Roughness Bright", 0.55, 0.0, 1.0, "Roughness for bright albedo"),
    ("Gold Hue", 0.11, 0.0, 1.0, "Hue centre of the metal mask (0.11 ≈ gold)"),
    ("Gold Range", 0.06, 0.005, 0.5, "Hue half-width of the metal mask"),
    ("Gold Min Saturation", 0.25, 0.0, 1.0, "Below this saturation nothing counts as gold"),
    ("Gold Metallic", 0.9, 0.0, 1.0, "Metallic applied inside the mask"),
    ("Gold Roughness", 0.25, 0.0, 1.0, "Roughness inside the mask"),
    ("Gold Boost", 0.35, 0.0, 2.0, "Extra brightness inside the mask"),
    ("Specular", 0.3, 0.0, 1.0, "Specular IOR level outside the mask"),
)
HIDDEN_TUNABLES = (("Gold Enable", 0.0),)     # driven by scene props, not sliders
GROUP_VERSION_NODE = "Clay Color"             # presence marks an up-to-date group


def _value_node(ng, name, default):
    n = ng.nodes.new("ShaderNodeValue")
    n.name = n.label = name
    n.outputs[0].default_value = default
    return n


def ensure_relight_group():
    ng = bpy.data.node_groups.get(GROUP_NAME)
    if ng is not None:
        if ng.nodes.get(GROUP_VERSION_NODE) is not None:
            return ng
        # older group from a previous version: rebuild the nodes in place.
        # The interface sockets are kept (removing them would drop the links
        # of every material using the group → black tiles).
        for n in list(ng.nodes):
            ng.nodes.remove(n)
    else:
        ng = bpy.data.node_groups.new(GROUP_NAME, "ShaderNodeTree")
    _build_relight_group(ng)
    return ng


def _build_relight_group(ng):
    iface = ng.interface
    have = {it.name for it in iface.items_tree if getattr(it, "item_type", "") == "SOCKET"}
    if "Albedo" not in have:
        iface.new_socket("Albedo", in_out="INPUT", socket_type="NodeSocketColor")
    if "Alpha" not in have:
        iface.new_socket("Alpha", in_out="INPUT", socket_type="NodeSocketFloat").default_value = 1.0
    if "BSDF" not in have:
        iface.new_socket("BSDF", in_out="OUTPUT", socket_type="NodeSocketShader")
    nodes, links = ng.nodes, ng.links
    n_in = nodes.new("NodeGroupInput")
    n_out = nodes.new("NodeGroupOutput")
    n_in.location = (-1400, 0)
    n_out.location = (900, 0)

    vals = {}
    for i, (name, default, *_rest) in enumerate(TUNABLES + HIDDEN_TUNABLES):
        v = _value_node(ng, name, default)
        v.location = (-1400, -250 - 110 * i)
        vals[name] = v

    # albedo → gamma (shadow lift) → saturation
    gamma = nodes.new("ShaderNodeGamma")
    gamma.location = (-1100, 100)
    links.new(n_in.outputs["Albedo"], gamma.inputs["Color"])
    links.new(vals["Shadow Lift"].outputs[0], gamma.inputs["Gamma"])
    hsv = nodes.new("ShaderNodeHueSaturation")
    hsv.location = (-900, 100)
    links.new(gamma.outputs["Color"], hsv.inputs["Color"])
    links.new(vals["Saturation"].outputs[0], hsv.inputs["Saturation"])

    # albedo ↔ clay
    clay = nodes.new("ShaderNodeRGB")
    clay.name = clay.label = "Clay Color"
    clay.location = (-900, 350)
    clay.outputs[0].default_value = (0.55, 0.52, 0.48, 1.0)
    albedo_mix = nodes.new("ShaderNodeMix")
    albedo_mix.data_type = "RGBA"
    albedo_mix.blend_type = "MIX"
    albedo_mix.label = "albedo strength"
    albedo_mix.location = (-750, 200)
    links.new(vals["Albedo Strength"].outputs[0], albedo_mix.inputs["Factor"])
    links.new(clay.outputs[0], albedo_mix.inputs[6])           # A: clay
    links.new(hsv.outputs["Color"], albedo_mix.inputs[7])      # B: processed albedo
    hsv_out = albedo_mix.outputs[2]

    # luminance → roughness ramp
    bw = nodes.new("ShaderNodeRGBToBW")
    bw.location = (-700, -100)
    links.new(hsv_out, bw.inputs["Color"])
    rough = nodes.new("ShaderNodeMapRange")
    rough.location = (-450, -100)
    rough.label = "Roughness from luminance"
    rough.inputs["From Min"].default_value = 0.0
    rough.inputs["From Max"].default_value = 1.0
    links.new(bw.outputs["Val"], rough.inputs["Value"])
    links.new(vals["Roughness Dark"].outputs[0], rough.inputs["To Min"])
    links.new(vals["Roughness Bright"].outputs[0], rough.inputs["To Max"])

    # gold mask from hue / saturation
    sep = nodes.new("ShaderNodeSeparateColor")
    sep.mode = "HSV"
    sep.location = (-700, -350)
    links.new(hsv.outputs["Color"], sep.inputs["Color"])
    hue_d = nodes.new("ShaderNodeMath")
    hue_d.operation = "SUBTRACT"
    hue_d.location = (-500, -350)
    links.new(sep.outputs["Red"], hue_d.inputs[0])
    links.new(vals["Gold Hue"].outputs[0], hue_d.inputs[1])
    hue_abs = nodes.new("ShaderNodeMath")
    hue_abs.operation = "ABSOLUTE"
    hue_abs.location = (-350, -350)
    links.new(hue_d.outputs[0], hue_abs.inputs[0])
    hue_mask = nodes.new("ShaderNodeMapRange")
    hue_mask.location = (-200, -350)
    hue_mask.label = "hue → mask"
    hue_mask.inputs["To Min"].default_value = 1.0
    hue_mask.inputs["To Max"].default_value = 0.0
    hue_mask.inputs["From Min"].default_value = 0.0
    links.new(hue_abs.outputs[0], hue_mask.inputs["Value"])
    links.new(vals["Gold Range"].outputs[0], hue_mask.inputs["From Max"])
    sat_mask = nodes.new("ShaderNodeMath")
    sat_mask.operation = "GREATER_THAN"
    sat_mask.location = (-350, -550)
    links.new(sep.outputs["Green"], sat_mask.inputs[0])
    links.new(vals["Gold Min Saturation"].outputs[0], sat_mask.inputs[1])
    mask0 = nodes.new("ShaderNodeMath")
    mask0.operation = "MULTIPLY"
    mask0.label = "gold mask"
    mask0.location = (0, -400)
    links.new(hue_mask.outputs["Result"], mask0.inputs[0])
    links.new(sat_mask.outputs[0], mask0.inputs[1])
    mask = nodes.new("ShaderNodeMath")          # × Gold Enable (0/1 from the panel toggle)
    mask.operation = "MULTIPLY"
    mask.label = "gold mask (enabled)"
    mask.location = (100, -500)
    links.new(mask0.outputs[0], mask.inputs[0])
    links.new(vals["Gold Enable"].outputs[0], mask.inputs[1])

    # metallic / roughness / specular / colour from the mask
    metallic = nodes.new("ShaderNodeMath")
    metallic.operation = "MULTIPLY"
    metallic.location = (200, -300)
    links.new(mask.outputs[0], metallic.inputs[0])
    links.new(vals["Gold Metallic"].outputs[0], metallic.inputs[1])
    rough_mix = nodes.new("ShaderNodeMix")
    rough_mix.data_type = "FLOAT"
    rough_mix.location = (200, -100)
    links.new(mask.outputs[0], rough_mix.inputs["Factor"])
    links.new(rough.outputs["Result"], rough_mix.inputs[2])      # A (float)
    links.new(vals["Gold Roughness"].outputs[0], rough_mix.inputs[3])  # B (float)
    boost = nodes.new("ShaderNodeMath")
    boost.operation = "MULTIPLY_ADD"
    boost.location = (200, -500)
    links.new(mask.outputs[0], boost.inputs[0])
    links.new(vals["Gold Boost"].outputs[0], boost.inputs[1])
    boost.inputs[2].default_value = 1.0
    color = nodes.new("ShaderNodeMix")
    color.data_type = "RGBA"
    color.blend_type = "MULTIPLY"
    color.location = (400, 100)
    color.inputs["Factor"].default_value = 1.0
    links.new(hsv_out, color.inputs[6])                         # A (color)
    links.new(boost.outputs[0], color.inputs[7])                 # B (color from float)

    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (650, 0)
    links.new(color.outputs[2], bsdf.inputs["Base Color"])
    links.new(rough_mix.outputs[0], bsdf.inputs["Roughness"])
    links.new(metallic.outputs[0], bsdf.inputs["Metallic"])
    if "Specular IOR Level" in bsdf.inputs:
        links.new(vals["Specular"].outputs[0], bsdf.inputs["Specular IOR Level"])
    links.new(n_in.outputs["Alpha"], bsdf.inputs["Alpha"])
    # baked-light mix: unlit albedo (emission) vs the lit BSDF
    emis = nodes.new("ShaderNodeEmission")
    emis.location = (650, -350)
    links.new(color.outputs[2], emis.inputs["Color"])
    emis.inputs["Strength"].default_value = 1.0
    transp = nodes.new("ShaderNodeBsdfTransparent")
    transp.location = (650, -500)
    emis_a = nodes.new("ShaderNodeMixShader")     # alpha for the unlit branch
    emis_a.location = (850, -400)
    links.new(n_in.outputs["Alpha"], emis_a.inputs["Fac"])
    links.new(transp.outputs[0], emis_a.inputs[1])
    links.new(emis.outputs[0], emis_a.inputs[2])
    mixsh = nodes.new("ShaderNodeMixShader")
    mixsh.location = (1050, 0)
    links.new(vals["Baked Light"].outputs[0], mixsh.inputs["Fac"])
    links.new(bsdf.outputs["BSDF"], mixsh.inputs[1])
    links.new(emis_a.outputs[0], mixsh.inputs[2])
    n_out.location = (1250, 0)
    links.new(mixsh.outputs[0], n_out.inputs["BSDF"])
    return ng


def set_gold_enabled(enabled: bool) -> None:
    ng = bpy.data.node_groups.get(GROUP_NAME)
    node = ng.nodes.get("Gold Enable") if ng else None
    if node is not None:
        node.outputs[0].default_value = 1.0 if enabled else 0.0


def _albedo_socket(mat):
    """Find the colour source of a material: Image Texture colour output, or a
    plain RGB from the Principled base colour."""
    nt = mat.node_tree
    for n in nt.nodes:
        if n.type == "TEX_IMAGE" and n.image is not None:
            return n.outputs["Color"], (n.outputs["Alpha"] if n.image.alpha_mode != "NONE" else None)
    bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    rgb = nt.nodes.new("ShaderNodeRGB")
    rgb.location = (-600, 300)
    if bsdf is not None:
        rgb.outputs[0].default_value = bsdf.inputs["Base Color"].default_value
    return rgb.outputs[0], None


def apply_relight(mat) -> bool:
    if mat is None or not mat.use_nodes or mat.node_tree is None:
        return False
    nt = mat.node_tree
    if any(n.type == "GROUP" and n.node_tree and n.node_tree.name == GROUP_NAME for n in nt.nodes):
        return False
    out = next((n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"), None)
    if out is None:
        return False
    albedo, alpha = _albedo_socket(mat)
    for n in [n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"]:
        n.mute = True
        n.hide = True
        n.location.y -= 400
    grp = nt.nodes.new("ShaderNodeGroup")
    grp.node_tree = ensure_relight_group()
    grp.name = grp.label = GROUP_NAME
    grp.location = (out.location.x - 300, out.location.y)
    nt.links.new(albedo, grp.inputs["Albedo"])
    if alpha is not None:
        nt.links.new(alpha, grp.inputs["Alpha"])
    nt.links.new(grp.outputs["BSDF"], out.inputs["Surface"])
    return True


def remove_relight(mat) -> bool:
    if mat is None or not mat.use_nodes or mat.node_tree is None:
        return False
    nt = mat.node_tree
    grp = next((n for n in nt.nodes if n.type == "GROUP" and n.node_tree
                and n.node_tree.name == GROUP_NAME), None)
    if grp is None:
        return False
    out = next((n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"), None)
    bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    nt.nodes.remove(grp)
    if bsdf is not None:
        bsdf.mute = False
        bsdf.hide = False
        bsdf.location.y += 400
        if out is not None:
            nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return True


def _is_tile_object(o) -> bool:
    """Direct-mesh tiles carry ``tile_url`` themselves; glTF-imported tiles are
    meshes parented under an Empty holder that carries it."""
    p = o
    for _ in range(4):
        if p is None:
            return False
        if "tile_url" in p:
            return True
        p = p.parent
    return False


def tile_materials():
    seen = set()
    for o in bpy.data.objects:
        if o.type == "MESH" and o.data is not None and _is_tile_object(o):
            for m in o.data.materials:
                if m is not None and m.name not in seen:
                    seen.add(m.name)
                    yield m


class OGC3D_OT_RelightApply(Operator):
    """Swap every tile material's BSDF for the shared "OGC3D Relight" node group"""
    bl_idname = "ogc3dtiles.relight_apply"
    bl_label = "Apply Relight to Tiles"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        ensure_relight_group()                 # also upgrades a group from an older version
        n = sum(1 for m in tile_materials() if apply_relight(m))
        self.report({"INFO"}, f"Relight applied to {n} materials")
        return {"FINISHED"}


class OGC3D_OT_RelightRemove(Operator):
    """Restore the plain Principled material on every tile"""
    bl_idname = "ogc3dtiles.relight_remove"
    bl_label = "Remove Relight"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        n = sum(1 for m in tile_materials() if remove_relight(m))
        self.report({"INFO"}, f"Relight removed from {n} materials")
        return {"FINISHED"}


def draw_panel(layout, props):
    """Body of the collapsible "Materials" sub-panel."""
    row = layout.row(align=True)
    row.operator("ogc3dtiles.relight_apply", icon="SHADING_RENDERED", text="Apply Relight")
    row.operator("ogc3dtiles.relight_remove", icon="X", text="")
    row.operator("ogc3dtiles.open_nodes", icon="NODETREE", text="").kind = "RELIGHT"
    layout.prop(props, "auto_relight", text="Relight new tiles")
    ng = bpy.data.node_groups.get(GROUP_NAME)
    if ng is not None:
        col = layout.column(align=True)
        for name, *_rest in TUNABLES:
            if name == "Gold Hue":
                col.separator()
                col.prop(props, "relight_gold", text="Gold transfer", toggle=True)
            if name.startswith("Gold") and not props.relight_gold:
                continue
            n = ng.nodes.get(name)
            if n is not None:
                col.prop(n.outputs[0], "default_value", text=name)


_classes = [OGC3D_OT_RelightApply, OGC3D_OT_RelightRemove]


def _persistent(fn):
    """bpy.app.handlers.persistent, tolerant of the test stub without bpy.app."""
    app = getattr(bpy, "app", None)
    return app.handlers.persistent(fn) if app is not None else fn


@_persistent
def _upgrade_group_on_load(_dummy=None):
    """Files saved with an older "OGC3D Relight" group get the current nodes
    (materials keep pointing at the same group datablock)."""
    try:
        if bpy.data.node_groups.get(GROUP_NAME) is not None:
            ensure_relight_group()
    except Exception as e:                        # noqa: BLE001
        print(f"[3DTiles] relight group upgrade failed: {e}")


def register():
    for c in _classes:
        bpy.utils.register_class(c)
    handlers = getattr(getattr(bpy, "app", None), "handlers", None)
    if handlers is not None and _upgrade_group_on_load not in handlers.load_post:
        handlers.load_post.append(_upgrade_group_on_load)


def unregister():
    handlers = getattr(getattr(bpy, "app", None), "handlers", None)
    if handlers is not None and _upgrade_group_on_load in handlers.load_post:
        handlers.load_post.remove(_upgrade_group_on_load)
    for c in reversed(_classes):
        bpy.utils.unregister_class(c)
