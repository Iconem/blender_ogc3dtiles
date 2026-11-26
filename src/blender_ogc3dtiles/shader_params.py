"""Numbers of the shared shader groups, kept as custom properties of the scene.

A number held in a node of a shared group (a Value node, a socket's value) costs a re-evaluation of every
material that uses the group each time it is written: measured on Blender 5.3 with 1,000 tile materials, the
viewport freezes 3 to 6 s for one slider step, as long as for adding the nodes. An Attribute node of type
*View Layer* reads a custom property of the scene instead: writing the property touches no node tree, and
the same 1,000 materials follow in under 0.1 s.

A property that is missing reads 0, so every number is stored as its offset from the value that changes
nothing: a scene without the properties (a new scene, a file appended) shows the tiles untouched.
"""
from __future__ import annotations

import bpy

PREFIX = "ogc3d_"


def key(name: str) -> str:
    return PREFIX + name.lower().replace(" ", "_")


def is_param(node) -> bool:
    return node is not None and node.type == "ATTRIBUTE" and node.attribute_type == "VIEW_LAYER"


def socket(ng, name: str, prop: str | None = None, vector: bool = False):
    """The output of the Attribute node ``name`` of a group, made when missing: the scene property
    ``prop`` (``name`` by default) as a number, or as a vector."""
    n = ng.nodes.get(name)
    if n is not None and n.type != "ATTRIBUTE":
        ng.nodes.remove(n)
        n = None
    if n is None:
        n = ng.nodes.new("ShaderNodeAttribute")
        n.name = n.label = name
    n.attribute_type = "VIEW_LAYER"
    n.attribute_name = key(prop or name)
    return n.outputs["Vector" if vector else "Fac"]


def _same(old, new) -> bool:
    if old is None:
        return False
    try:
        if isinstance(new, (list, tuple)):
            return len(old) == len(new) and all(abs(float(a) - float(b)) < 1e-9 for a, b in zip(old, new))
        return abs(float(old) - float(new)) < 1e-9
    except Exception:                                # noqa: BLE001
        return False


def write(values: dict, only_missing: bool = False) -> bool:
    """{name: number or 3 numbers} into every scene. True when something changed."""
    changed = False
    for sc in bpy.data.scenes:
        touched = False
        for name, v in values.items():
            k = key(name)
            old = sc.get(k)
            if only_missing and old is not None:
                continue
            v = [float(x) for x in v] if isinstance(v, (list, tuple)) else float(v)
            if not _same(old, v):
                sc[k] = v
                touched = True
        if touched:
            sc.update_tag()                          # the viewport and Cycles read the properties again
            changed = True
    return changed


def forget(prefix: str) -> None:
    """Drop the properties whose name starts with ``prefix`` (a tileset that is removed)."""
    k0 = key(prefix)
    for sc in bpy.data.scenes:
        for k in [k for k in sc.keys() if k.startswith(k0)]:
            del sc[k]
