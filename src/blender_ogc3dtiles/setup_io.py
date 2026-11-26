"""The tileset list of a scene as JSON text: every entry with its raster overlays, clips, color correction and
blend settings, and the scene origin. Copied to the clipboard in one scene, pasted in another, on any machine.

The text holds the URLs as they are, keys and tokens included: it is as private as the library file."""
from __future__ import annotations

import json

FORMAT = "blender_ogc3dtiles setup"
VERSION = 1
# scene settings that belong to the list: where the scene is, and what the boxes of the entries share
SCENE_PREFIXES = ("origin_", "blend_", "dataset_")
SCENE_NAMES = ("clip_materials", "max_sse")
SKIP = {"rna_type", "uid", "dataset_offsets", "origin_text", "origin_text_status", "origin_dataset"}
MESH_MAX_VERTS = 100         # a clip object comes along with its mesh, up to this size


def _object(o) -> dict:
    """A clip polygon or box by name; a small mesh also as geometry, for a scene that does not have it."""
    out = {"__object__": o.name}
    if o.type == "MESH" and len(o.data.vertices) <= MESH_MAX_VERTS:
        out["matrix"] = [list(r) for r in o.matrix_world]
        out["verts"] = [[round(c, 5) for c in v.co] for v in o.data.vertices]
        out["faces"] = [list(p.vertices) for p in o.data.polygons]
        out["edges"] = [list(e.vertices) for e in o.data.edges] if not o.data.polygons else []
        out["display"] = o.display_type
    return out


def dump(pg, only=None) -> dict:
    """A property group as plain data. ``only``: a test on the property name."""
    out = {}
    for p in pg.bl_rna.properties:
        k = p.identifier
        if k in SKIP or (only is not None and not only(k)):
            continue
        if "SKIP_SAVE" in getattr(p, "options", ()) and p.type not in ("COLLECTION", "POINTER"):
            continue
        v = getattr(pg, k)
        if p.type == "COLLECTION":
            out[k] = [dump(x) for x in v]
        elif p.type == "POINTER":
            if v is None:
                continue
            if hasattr(v, "bl_rna") and v.bl_rna.identifier == "Object":
                out[k] = _object(v)
            elif not hasattr(v, "users"):                # a nested property group, not another datablock
                out[k] = dump(v)
        elif p.type == "ENUM":
            out[k] = sorted(v) if p.is_enum_flag else v
        elif p.type in ("BOOLEAN", "INT", "FLOAT") and getattr(p, "is_array", False):
            out[k] = list(v)
        elif p.type in ("BOOLEAN", "INT", "FLOAT", "STRING"):
            out[k] = v
    return out


def _ensure_object(d: dict, scene):
    import bpy
    o = bpy.data.objects.get(d.get("__object__", ""))
    if o is not None or "verts" not in d:
        return o
    from mathutils import Matrix
    me = bpy.data.meshes.new(d["__object__"])
    me.from_pydata(d["verts"], d.get("edges") or [], d.get("faces") or [])
    me.update()
    o = bpy.data.objects.new(d["__object__"], me)
    o.matrix_world = Matrix(d["matrix"])
    o.display_type = d.get("display", "WIRE")
    scene.collection.objects.link(o)
    return o


def load(pg, data: dict, scene, skipped: list) -> None:
    """Write ``data`` into a property group. Names this version does not know are listed in ``skipped``."""
    props = {p.identifier: p for p in pg.bl_rna.properties}
    late = []
    for k, v in data.items():
        p = props.get(k)
        if p is None or k in SKIP:
            skipped.append(k)
            continue
        try:
            if p.type == "COLLECTION":
                coll = getattr(pg, k)
                for row in v:
                    load(coll.add(), row, scene, skipped)
            elif p.type == "POINTER":
                if isinstance(v, dict) and "__object__" in v:
                    late.append((k, v))                  # after the plain values: an update may read them
                elif isinstance(v, dict):
                    load(getattr(pg, k), v, scene, skipped)
            elif p.type == "ENUM" and p.is_enum_flag:
                setattr(pg, k, set(v))
            elif not p.is_readonly:
                setattr(pg, k, v)
        except Exception as e:                           # noqa: BLE001  one bad value must not lose the rest
            skipped.append(f"{k} ({e})")
    for k, v in late:
        try:
            setattr(pg, k, _ensure_object(v, scene))
        except Exception as e:                           # noqa: BLE001
            skipped.append(f"{k} ({e})")


def _scene_setting(name: str) -> bool:
    return name.startswith(SCENE_PREFIXES) or name in SCENE_NAMES


def to_text(props) -> str:
    data = {"format": FORMAT, "version": VERSION,
            "scene": dump(props, only=_scene_setting),
            "tilesets": [dump(it) for it in props.tilesets]}
    return json.dumps(data, indent=1)


def from_text(text: str, props, scene, with_scene: bool) -> tuple:
    """Add the entries of a copied setup to the list. (entries added, names skipped)."""
    try:
        data = json.loads(text)
    except Exception as e:                               # noqa: BLE001
        raise ValueError(f"not JSON: {e}") from None
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        raise ValueError("no tileset setup in this text")
    skipped: list = []
    if with_scene:
        load(props, {k: v for k, v in (data.get("scene") or {}).items() if _scene_setting(k)}, scene, skipped)
    n = 0
    for row in data.get("tilesets") or []:
        it = props.tilesets.add()
        load(it, row, scene, skipped)
        n += 1
    if n:
        props.active_tileset = len(props.tilesets) - 1
    return n, skipped
