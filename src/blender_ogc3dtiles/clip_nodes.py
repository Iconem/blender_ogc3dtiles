"""Clipping volumes in Blender nodes (see clipping.py for the modes).

* Box terms in mesh tile materials: Texture Coordinate (Object = the box)
  gives the shading point in the box's own space, so moving / rotating /
  scaling the box needs no rebuild.
* Point and splat tiles: one Geometry Nodes group per tileset (modifier
  "OGC3D Clip", first in the stack) deletes the cut vertices. Boxes test the
  vertex in the box's space; prisms cast a vertical ray onto a hidden helper
  mesh holding the flattened, filled outlines in the tileset frame (face
  attribute ``clip_poly`` = prism index).
* Mesh tiles with Cut Geometry: the same test in a second group deletes the
  faces whose vertices are all cut; the shader still trims the faces across
  the boundary. Solid view, exports and snapping then see the cut.

The per-tileset settings live on the tileset's root Empty (``ogc_clip``) so
tiles built later pick them up (io._new_tile_hooks → apply_to_tile).
"""
from __future__ import annotations

import bpy

from .overlays import POLY_TAG, clip_attr_names, relink_clip_chain

CFG_PROP = "ogc_clip"
GN_MOD = "OGC3D Clip"
GN_PREFIX = "OGC3D Clip "
GN_FACES_PREFIX = "OGC3D Clip Faces "
HELPER_PREFIX = "OGC3D Clip Prisms "
POLY_ATTR = "clip_poly"
RAY_Z = 1.0e5


# ── config on the root Empty ─────────────────────────────────────────────────
def make_cfg(uid, op, outside, boxes, n_prisms, helper_name, masks=(), geometry=False) -> dict:
    """boxes: [(object name, centre xyz, half size xyz)]; masks: uids of the
    tileset's cesium masks; geometry: Cut Geometry on mesh tiles."""
    return {"uid": uid, "op": op, "outside": bool(outside), "n_prisms": int(n_prisms),
            "helper": helper_name or "", "masks": list(masks), "geometry": bool(geometry),
            "boxes": [{"obj": n, "c": list(c), "h": list(h)} for n, c, h in boxes]}


def _cfg(root):
    cfg = root.get(CFG_PROP) if root is not None else None
    return cfg.to_dict() if hasattr(cfg, "to_dict") else cfg


def _is_point_tile(obj) -> bool:
    return obj.type == "MESH" and (obj.modifiers.get("Points") is not None
                                   or obj.modifiers.get("Splats") is not None
                                   or (len(obj.data.vertices) and not len(obj.data.polygons)))


# ── box terms in materials ───────────────────────────────────────────────────
def _box_names(i):
    b = f"{POLY_TAG} box{i}"
    return {k: f"{b} {k.title()}" for k in ("coord", "map", "abs", "sep", "mxy", "mxyz")} | \
        {"term": f"{b} Term"}


def set_box_terms(mat, boxes, tileset_uid) -> None:
    """Make the material's box terms match ``boxes`` (cfg entries). Existing
    nodes are updated in place; the chain is only relinked when a term comes
    or goes."""
    if mat is None or not mat.use_nodes or mat.node_tree is None:
        return
    nt = mat.node_tree
    N, L = nt.nodes.new, nt.links.new
    changed = False
    keep = set()
    for i, b in enumerate(boxes):
        nm = _box_names(i)
        keep.update(nm.values())
        obj = bpy.data.objects.get(b["obj"])
        c, h = b["c"], b["h"]
        coord = nt.nodes.get(nm["coord"])
        if coord is None:
            x0, y0 = -2200.0, -1400.0 - 220.0 * i
            coord = N("ShaderNodeTexCoord")
            mp = N("ShaderNodeMapping")
            mp.vector_type = "POINT"
            ab = N("ShaderNodeVectorMath")
            ab.operation = "ABSOLUTE"
            sep = N("ShaderNodeSeparateXYZ")
            mxy = N("ShaderNodeMath")
            mxy.operation = "MAXIMUM"
            mxyz = N("ShaderNodeMath")
            mxyz.operation = "MAXIMUM"
            term = N("ShaderNodeMath")
            term.operation = "LESS_THAN"
            for k, n in zip(("coord", "map", "abs", "sep", "mxy", "mxyz", "term"),
                            (coord, mp, ab, sep, mxy, mxyz, term)):
                n.name = n.label = nm[k]
            for k, n in enumerate((coord, mp, ab, sep, mxy, mxyz, term)):
                n.location = (x0 + 180 * k, y0)
            L(coord.outputs["Object"], mp.inputs["Vector"])
            L(mp.outputs["Vector"], ab.inputs[0])
            L(ab.outputs["Vector"], sep.inputs[0])
            L(sep.outputs["X"], mxy.inputs[0])
            L(sep.outputs["Y"], mxy.inputs[1])
            L(mxy.outputs[0], mxyz.inputs[0])
            L(sep.outputs["Z"], mxyz.inputs[1])
            L(mxyz.outputs[0], term.inputs[0])
            term.inputs[1].default_value = 1.0
            changed = True
        mp = nt.nodes[nm["map"]]
        if coord.object is not obj:
            coord.object = obj
        mp.inputs["Scale"].default_value = tuple(1.0 / v for v in h)
        mp.inputs["Location"].default_value = tuple(-cv / hv for cv, hv in zip(c, h))
    for n in [n for n in nt.nodes if n.name.startswith(f"{POLY_TAG} box") and n.name not in keep]:
        nt.nodes.remove(n)
        changed = True
    if changed:
        relink_clip_chain(mat, tileset_uid)


def clear_box_terms(mat) -> None:
    if mat is None or mat.node_tree is None:
        return
    nt = mat.node_tree
    boxes = [n for n in nt.nodes if n.name.startswith(f"{POLY_TAG} box")]
    for n in boxes:
        nt.nodes.remove(n)
    if boxes:
        relink_clip_chain(mat)


# ── prism helper mesh ────────────────────────────────────────────────────────
def update_helper(uid, root, loops_local, coll):
    """Hidden mesh with one flat (z = 0) n-gon per prism outline, in the
    tileset frame (object matrix = the root's). None without prisms."""
    name = HELPER_PREFIX + uid
    ob = bpy.data.objects.get(name)
    if not loops_local:
        if ob is not None:
            me = ob.data
            bpy.data.objects.remove(ob)
            if me is not None and me.users == 0:
                bpy.data.meshes.remove(me)
        return None
    verts, faces = [], []
    for loop in loops_local:
        base = len(verts)
        verts.extend((p[0], p[1], 0.0) for p in loop)
        faces.append(list(range(base, base + len(loop))))
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    a = me.attributes.new(POLY_ATTR, "INT", "FACE")
    a.data.foreach_set("value", list(range(len(faces))))
    me.update()
    if ob is None:
        ob = bpy.data.objects.new(name, me)
        coll.objects.link(ob)
        ob.hide_select = True
        ob.display_type = "WIRE"
    else:
        old = ob.data
        ob.data = me
        if old is not None and old.users == 0:
            bpy.data.meshes.remove(old)
    ob.hide_viewport = True
    ob.hide_render = True
    ob.matrix_world = root.matrix_world.copy()
    return ob


# ── Geometry Nodes group for point / splat tiles ─────────────────────────────
def _gn_signature(cfg, faces) -> str:
    return repr((cfg["op"], cfg["outside"], cfg["n_prisms"], cfg["helper"], faces,
                 [(b["obj"], [round(v, 6) for v in b["c"]], [round(v, 6) for v in b["h"]])
                  for b in cfg["boxes"]]))


def build_group(cfg, faces=False):
    """(Re)build the tileset's clip group, deleting points, or with ``faces``
    the faces whose points are all cut; returns it (None: nothing to clip)."""
    name = (GN_FACES_PREFIX if faces else GN_PREFIX) + cfg["uid"]
    ng = bpy.data.node_groups.get(name)
    if not cfg["boxes"] and not cfg["n_prisms"]:
        return None
    sig = _gn_signature(cfg, faces)
    if ng is not None and ng.get("sig") == sig:
        return ng
    if ng is None:
        ng = bpy.data.node_groups.new(name, "GeometryNodeTree")
        ng.is_modifier = True
        ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
        ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    for n in list(ng.nodes):
        ng.nodes.remove(n)
    N, L = ng.nodes.new, ng.links.new
    gi, go = N("NodeGroupInput"), N("NodeGroupOutput")
    gi.location, go.location = (-1400, 300), (1200, 300)

    def obj_info(obj):
        oi = N("GeometryNodeObjectInfo")
        oi.transform_space = "ORIGINAL"
        oi.inputs["Object"].default_value = obj
        return oi

    def inv(m):
        n = N("FunctionNodeInvertMatrix")
        L(m, n.inputs[0])
        return n.outputs[0]

    def xform(m, v):
        n = N("FunctionNodeTransformPoint")
        L(v, n.inputs["Vector"])
        L(m, n.inputs["Transform"])
        return n.outputs[0]

    def math(op, a, b=None, bval=None):
        n = N("ShaderNodeMath")
        n.operation = op
        L(a, n.inputs[0])
        if b is not None:
            L(b, n.inputs[1])
        elif bval is not None:
            n.inputs[1].default_value = bval
        return n.outputs[0]

    selfo = N("GeometryNodeSelfObject")
    self_info = N("GeometryNodeObjectInfo")
    self_info.transform_space = "ORIGINAL"
    L(selfo.outputs[0], self_info.inputs["Object"])
    pos = N("GeometryNodeInputPosition")
    world = xform(self_info.outputs["Transform"], pos.outputs[0])
    terms = []
    for b in cfg["boxes"]:
        ob = bpy.data.objects.get(b["obj"])
        if ob is None:
            continue
        local = xform(inv(obj_info(ob).outputs["Transform"]), world)
        sub = N("ShaderNodeVectorMath")
        sub.operation = "SUBTRACT"
        L(local, sub.inputs[0])
        sub.inputs[1].default_value = b["c"]
        div = N("ShaderNodeVectorMath")
        div.operation = "DIVIDE"
        L(sub.outputs[0], div.inputs[0])
        div.inputs[1].default_value = b["h"]
        ab = N("ShaderNodeVectorMath")
        ab.operation = "ABSOLUTE"
        L(div.outputs[0], ab.inputs[0])
        sep = N("ShaderNodeSeparateXYZ")
        L(ab.outputs[0], sep.inputs[0])
        m = math("MAXIMUM", math("MAXIMUM", sep.outputs[0], sep.outputs[1]), sep.outputs[2])
        terms.append(math("GREATER_THAN" if cfg["outside"] else "LESS_THAN", m, bval=1.0))
    helper = bpy.data.objects.get(cfg["helper"]) if cfg["n_prisms"] else None
    if helper is not None:
        hi = obj_info(helper)
        hl = xform(inv(hi.outputs["Transform"]), world)
        sep = N("ShaderNodeSeparateXYZ")
        L(hl, sep.inputs[0])
        src = N("ShaderNodeCombineXYZ")
        L(sep.outputs[0], src.inputs[0])
        L(sep.outputs[1], src.inputs[1])
        src.inputs[2].default_value = RAY_Z
        attr = N("GeometryNodeInputNamedAttribute")
        attr.data_type = "INT"
        attr.inputs["Name"].default_value = POLY_ATTR
        for i in range(cfg["n_prisms"]):
            cmp = N("FunctionNodeCompare")
            cmp.data_type = "INT"
            cmp.operation = "EQUAL"
            a_in, b_in = (cmp.inputs[2], cmp.inputs[3]) if len(cmp.inputs) > 2 else                 (cmp.inputs[0], cmp.inputs[1])          # Blender < 4.x kept every type's sockets
            L(attr.outputs[0], a_in)
            b_in.default_value = i
            sg = N("GeometryNodeSeparateGeometry")
            sg.domain = "FACE"
            L(hi.outputs["Geometry"], sg.inputs["Geometry"])
            L(cmp.outputs[0], sg.inputs["Selection"])
            rc = N("GeometryNodeRaycast")
            L(sg.outputs[0], rc.inputs["Target Geometry"])
            L(src.outputs[0], rc.inputs["Source Position"])
            rc.inputs["Ray Direction"].default_value = (0.0, 0.0, -1.0)
            rc.inputs["Ray Length"].default_value = 2.0 * RAY_Z
            hit = rc.outputs["Is Hit"]
            terms.append(math("LESS_THAN", hit, bval=0.5) if cfg["outside"]
                         else math("ADD", hit, bval=0.0))
    if not terms:
        L(gi.outputs[0], go.inputs[0])
    else:
        acc = terms[0]
        for t in terms[1:]:
            acc = math(cfg["op"], acc, t)
        cut = math("GREATER_THAN", acc, bval=0.5)
        dg = N("GeometryNodeDeleteGeometry")
        dg.domain = "FACE" if faces else "POINT"
        L(gi.outputs[0], dg.inputs["Geometry"])
        if faces:
            # a boolean point field read on faces is true when all points are
            on_pts = N("GeometryNodeFieldOnDomain")
            on_pts.data_type = "BOOLEAN"
            on_pts.domain = "POINT"
            L(cut, on_pts.inputs[0])
            cut = on_pts.outputs[0]
        L(cut, dg.inputs["Selection"])
        L(dg.outputs[0], go.inputs[0])
    ng["sig"] = sig
    return ng


def _set_gn(obj, ng) -> None:
    mod = obj.modifiers.get(GN_MOD)
    if ng is None:
        if mod is not None:
            obj.modifiers.remove(mod)
        return
    if mod is None:
        mod = obj.modifiers.new(GN_MOD, "NODES")
        idx = obj.modifiers.find(GN_MOD)
        if idx > 0:
            obj.modifiers.move(idx, 0)
    if mod.node_group is not ng:
        mod.node_group = ng


# ── applying ─────────────────────────────────────────────────────────────────
def set_mode(scene, uid, any_, invert) -> None:
    """The two attributes the tile materials read; no material is touched."""
    any_name, inv_name = clip_attr_names(uid)
    scene[any_name], scene[inv_name] = float(any_), float(invert)
    scene.update_tag()


def _tile_group(prefix, cfg, faces):
    return bpy.data.node_groups.get(prefix + cfg["uid"]) or build_group(cfg, faces)


def apply_to_tile(obj, cfg=None) -> None:
    """Bring one tile in line with its tileset's clip config."""
    if obj is None or obj.type != "MESH":
        return
    cfg = _cfg(obj.parent) if cfg is None else cfg
    if _is_point_tile(obj):
        _set_gn(obj, _tile_group(GN_PREFIX, cfg, False) if cfg else None)
        return
    _set_gn(obj, _tile_group(GN_FACES_PREFIX, cfg, True) if cfg and cfg.get("geometry") else None)
    for m in obj.data.materials:
        if cfg and cfg["boxes"]:
            set_box_terms(m, cfg["boxes"], cfg["uid"])
        else:
            clear_box_terms(m)


def apply_to_tileset(root, cfg) -> None:
    """Store ``cfg`` (None = no clipping) on the root and update its tiles."""
    if root is None:
        return
    if cfg is None:
        if CFG_PROP in root:
            del root[CFG_PROP]
    else:
        root[CFG_PROP] = cfg
        try:
            build_group(cfg)
            if cfg.get("geometry"):
                build_group(cfg, True)
        except Exception as e:                       # noqa: BLE001
            print(f"[3DTiles] clip group: {e}")
    for o in root.children:
        if "tile_url" in o:
            try:
                apply_to_tile(o, cfg)
            except Exception as e:                   # noqa: BLE001
                print(f"[3DTiles] clip {o.name}: {e}")
    if cfg is None:
        uid = root.get("ogc_clip_uid")
        for prefix in (GN_PREFIX, GN_FACES_PREFIX):
            ng = bpy.data.node_groups.get(prefix + uid) if uid else None
            if ng is not None and ng.users == 0:
                bpy.data.node_groups.remove(ng)
    else:
        root["ogc_clip_uid"] = cfg["uid"]
