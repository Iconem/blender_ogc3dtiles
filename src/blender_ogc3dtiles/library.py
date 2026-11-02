"""Tileset library: JSON files listing ready-to-stream tileset entries.

A library lives wherever the team keeps it (a personal file, a NAS share)
and holds the entries' URLs and keys, so share links never sit in the
add-on or its repository. Several files can be listed in the preferences
(``;``-separated). Format::

    {"version": 1,
     "tilesets": [
       {"name": "San Pietro", "kind": "TILESET", "url": "https://...",
        "ion_asset_id": 0, "ion_token": "", "use_own_sse": false, "max_sse": 4.0,
        "use_overlays": false, "group": "Rome", "notes": "", "content": "MESH",
        "overlays": [{"name": "OSM", "kind": "URL", "url": "...", ...}]}
     ]}

``content`` (MESH, POINTS or SPLATS) is optional; without it the type is guessed
from the entry's words. No bpy here: entries convert from / to anything with the TilesetItem /
OverlayItem attribute names.
"""
from __future__ import annotations

import json
import os
import tempfile

VERSION = 1
ITEM_FIELDS = ("name", "kind", "url", "ion_asset_id", "ion_token", "use_own_sse",
               "max_sse", "use_overlays")
OVERLAY_FIELDS = ("name", "kind", "url", "key", "layer", "style", "matrix_set",
                  "image_format", "min_level", "max_level", "detail_px", "enabled", "alpha")


CONTENT_WORDS = (("SPLATS", ("splat", "3dgs", "spz")),
                 ("POINTS", ("point cloud", "pointcloud", "lidar", "copc", "pnts")),
                 ("MESH", ("mesh", "b3dm", "photorealistic")))


def content_type(entry: dict) -> str:
    """MESH, POINTS or SPLATS, "" when the entry doesn't tell."""
    if entry.get("content"):
        return entry["content"]
    text = f"{entry.get('group', '')} {entry.get('name', '')} {entry.get('notes', '')}".lower()
    return next((kind for kind, words in CONTENT_WORDS if any(w in text for w in words)), "")


def matches(entry: dict, query: str, kinds=()) -> bool:
    """Does the entry hold every word of ``query``, and is it of one of ``kinds``
    (none: any type)?"""
    if kinds and content_type(entry) not in kinds:
        return False
    text = f"{entry.get('group', '')} {entry.get('name', '')} {entry.get('notes', '')}".lower()
    return all(w in text for w in query.lower().split())


def split_paths(s: str) -> list:
    return [p.strip().strip('"') for p in (s or "").split(";") if p.strip()]


def read(path: str) -> list:
    """Entries of one library file ([] when missing or empty)."""
    if not os.path.isfile(path):
        return []
    with open(path, "r", encoding="utf-8") as fh:
        txt = fh.read().strip()
    if not txt:
        return []
    data = json.loads(txt)
    entries = data.get("tilesets", []) if isinstance(data, dict) else data
    return [e for e in entries if isinstance(e, dict) and e.get("name")]


def read_all(paths) -> list:
    """[(path, entry)] over every library; unreadable files are reported as
    (path, {"error": ...})."""
    out = []
    for p in paths:
        try:
            out.extend((p, e) for e in read(p))
        except (OSError, ValueError) as exc:
            out.append((p, {"error": str(exc)}))
    return out


def entry_from_item(item) -> dict:
    e = {f: getattr(item, f) for f in ITEM_FIELDS if hasattr(item, f)}
    e["overlays"] = [{f: getattr(o, f) for f in OVERLAY_FIELDS if hasattr(o, f)}
                     for o in getattr(item, "overlays", [])]
    return e


def apply_entry(item, entry: dict, add_overlay=None) -> None:
    """Fill a TilesetItem from an entry. ``add_overlay(item)`` returns a new
    OverlayItem (bpy collections need ``item.overlays.add()``)."""
    for f in ITEM_FIELDS:
        if f in entry:
            setattr(item, f, entry[f])
    if add_overlay is None:
        return
    for oe in entry.get("overlays", []):
        ov = add_overlay(item)
        for f in OVERLAY_FIELDS:
            if f in oe:
                setattr(ov, f, oe[f])


def save_entry(path: str, entry: dict) -> bool:
    """Insert or replace (by name) an entry. Re-reads the file just before
    writing and replaces it atomically, so teammates editing the same NAS
    file lose at most a concurrent edit of the same entry. True = replaced."""
    entries = read(path) if os.path.isfile(path) else []
    replaced = False
    for i, e in enumerate(entries):
        if e.get("name") == entry["name"]:
            keep = {k: e[k] for k in ("group", "notes", "content") if k in e and k not in entry}
            entries[i] = {**entry, **keep}
            replaced = True
            break
    else:
        entries.append(entry)
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".tilesets-", suffix=".json", dir=d)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump({"version": VERSION, "tilesets": entries}, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, path)
    return replaced
