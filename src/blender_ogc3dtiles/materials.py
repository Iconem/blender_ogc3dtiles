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
    ("Shadow Lift", 1.0, 0.5, 3.0, "Gamma on the albedo: >1 lifts baked shadows"),
    ("Saturation", 1.0, 0.0, 2.0, "Albedo saturation"),
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


def _value_node(ng, name, default):
    n = ng.nodes.new("ShaderNodeValue")
    n.name = n.label = name
    n.outputs[0].default_value = default
    return n


def ensure_relight_group():
    ng = bpy.data.node_groups.get(GROUP_NAME)
    if ng is not None:
        return ng
    ng = bpy.data.node_groups.new(GROUP_NAME, "ShaderNodeTree")
    iface = ng.interface
    iface.new_socket("Albedo", in_out="INPUT", socket_type="NodeSocketColor")
    iface.new_socket("Alpha", in_out="INPUT", socket_type="NodeSocketFloat").default_value = 1.0
    iface.new_socket("BSDF", in_out="OUTPUT", socket_type="NodeSocketShader")
    nodes, links = ng.nodes, ng.links
    n_in = nodes.new("NodeGroupInput")
    n_out = nodes.new("NodeGroupOutput")
    n_in.location = (-1400, 0)
    n_out.location = (900, 0)

    vals = {}
    for i, (name, default, *_rest) in enumerate(TUNABLES):
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

    # luminance → roughness ramp
    bw = nodes.new("ShaderNodeRGBToBW")
    bw.location = (-700, -100)
    links.new(hsv.outputs["Color"], bw.inputs["Color"])
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
    mask = nodes.new("ShaderNodeMath")
    mask.operation = "MULTIPLY"
    mask.label = "gold mask"
    mask.location = (0, -400)
    links.new(hue_mask.outputs["Result"], mask.inputs[0])
    links.new(sat_mask.outputs[0], mask.inputs[1])

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
    links.new(hsv.outputs["Color"], color.inputs[6])            # A (color)
    links.new(boost.outputs[0], color.inputs[7])                 # B (color from float)

    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (650, 0)
    links.new(color.outputs[2], bsdf.inputs["Base Color"])
    links.new(rough_mix.outputs[0], bsdf.inputs["Roughness"])
    links.new(metallic.outputs[0], bsdf.inputs["Metallic"])
    if "Specular IOR Level" in bsdf.inputs:
        links.new(vals["Specular"].outputs[0], bsdf.inputs["Specular IOR Level"])
    links.new(n_in.outputs["Alpha"], bsdf.inputs["Alpha"])
    links.new(bsdf.outputs["BSDF"], n_out.inputs["BSDF"])
    return ng


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


def tile_materials():
    seen = set()
    for o in bpy.data.objects:
        if "tile_url" in o and o.type == "MESH" and o.data is not None:
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
    layout.label(text="Materials", icon="MATERIAL")
    row = layout.row(align=True)
    row.operator("ogc3dtiles.relight_apply", icon="SHADING_RENDERED", text="Apply Relight")
    row.operator("ogc3dtiles.relight_remove", icon="X", text="")
    layout.prop(props, "auto_relight", text="Relight new tiles")
    ng = bpy.data.node_groups.get(GROUP_NAME)
    if ng is not None:
        col = layout.column(align=True)
        for name, *_rest in TUNABLES:
            n = ng.nodes.get(name)
            if n is not None:
                col.prop(n.outputs[0], "default_value", text=name)
        layout.label(text="Edit the group itself in the Shader Editor", icon="NODETREE")


_classes = [OGC3D_OT_RelightApply, OGC3D_OT_RelightRemove]


def register():
    for c in _classes:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(_classes):
        bpy.utils.unregister_class(c)
