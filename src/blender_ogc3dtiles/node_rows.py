"""node_rows.py — the one header row every shared node group gets in the sidebar.

Checkbox: the group exists and is on every tile, loaded or streamed later; off
takes it off the tiles and keeps the group, so hand edits survive. Then the
node editor button, and a menu to reset or delete the group.
"""
from __future__ import annotations


def draw(layout, props, prop, text, kind):
    row = layout.row(align=True)
    row.prop(props, prop, text=text)
    row.operator("ogc3dtiles.open_nodes", text="", icon="NODETREE").kind = kind
    row.operator_menu_enum("ogc3dtiles.nodes_reset", "action", text="",
                           icon="DOWNARROW_HLT").kind = kind
    return getattr(props, prop)
