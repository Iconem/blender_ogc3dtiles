"""Disk cache size cap (no bpy).

cesium-native's SqliteCache bounds itself by item count only (4096 items in
the Python binding, pruned every 10000 requests) and keeps responses until
they expire. Before the first stream of a session opens the database, the
add-on trims it to a byte budget, least recently used first, and does the
same for the pure-Python backend's GLB files. Private databases left behind
by other Blender processes (``http-cache-<pid>.sqlite``) are deleted after a
day.
"""
from __future__ import annotations

import glob
import os
import sqlite3
import time

STALE_PRIVATE_DB_S = 24 * 3600


def http_cache_bytes(db_path: str) -> int:
    if not os.path.isfile(db_path):
        return 0
    con = sqlite3.connect(db_path, timeout=2.0)
    try:
        row = con.execute("SELECT COALESCE(SUM(LENGTH(responseData)), 0) FROM CacheItemTable").fetchone()
        return int(row[0])
    except sqlite3.Error:
        return 0
    finally:
        con.close()


def trim_http_cache(db_path: str, max_bytes: int) -> int:
    """Delete least recently used responses until the payload fits in
    ``max_bytes``; returns the bytes removed. The file shrinks (VACUUM) only
    when at least a quarter of it was freed."""
    if max_bytes <= 0 or not os.path.isfile(db_path):
        return 0
    con = sqlite3.connect(db_path, timeout=2.0)
    try:
        rows = con.execute("SELECT rowid, LENGTH(responseData) FROM CacheItemTable "
                           "ORDER BY lastAccessedTime DESC").fetchall()
    except sqlite3.Error:
        con.close()
        return 0
    total = sum(n or 0 for _, n in rows)
    if total <= max_bytes:
        con.close()
        return 0
    keep, drop, removed = 0, [], 0
    for rowid, n in rows:
        keep += n or 0
        if keep > max_bytes:
            drop.append(rowid)
            removed += n or 0
    try:
        con.executemany("DELETE FROM CacheItemTable WHERE rowid = ?", [(r,) for r in drop])
        con.commit()
        if removed * 4 >= total:
            con.execute("VACUUM")
    except sqlite3.Error as e:
        print(f"[3DTiles] cache trim failed: {e}")
        removed = 0
    finally:
        con.close()
    return removed


def trim_files(root: str, max_bytes: int, pattern: str = "*.glb") -> int:
    """Oldest-first deletion of the pure-Python backend's cached GLBs (and
    their .meta.json) until they fit in ``max_bytes``."""
    if max_bytes <= 0 or not os.path.isdir(root):
        return 0
    files = []
    for p in glob.glob(os.path.join(root, pattern)):
        try:
            st = os.stat(p)
            files.append((st.st_atime, st.st_size, p))
        except OSError:
            pass
    total = sum(s for _, s, _ in files)
    removed = 0
    for _, size, p in sorted(files):
        if total - removed <= max_bytes:
            break
        try:
            os.unlink(p)
            removed += size
            # <sha1>.glb / <sha1>_N.glb share <sha1>.meta.json: drop it so a
            # lookup never points at a missing part
            meta = os.path.join(root, os.path.basename(p)[:40] + ".meta.json")
            if os.path.isfile(meta):
                os.unlink(meta)
        except OSError:
            pass
    return removed


def drop_stale_private_dbs(root: str, now: float | None = None) -> int:
    now = time.time() if now is None else now
    n = 0
    for p in glob.glob(os.path.join(root, "http-cache-*.sqlite*")):
        try:
            if now - os.path.getmtime(p) > STALE_PRIVATE_DB_S:
                os.unlink(p)
                n += 1
        except OSError:
            pass
    return n


def enforce(root: str, max_bytes: int, db_path: str | None = None) -> dict:
    """Session-start trim of the whole cache folder to ``max_bytes``: the
    sqlite HTTP cache gets what the GLB files leave."""
    out = {"stale_dbs": drop_stale_private_dbs(root), "http": 0, "glb": 0}
    if max_bytes <= 0:
        return out
    glb = sum(os.path.getsize(p) for p in glob.glob(os.path.join(root, "*.glb")) if os.path.isfile(p))
    db_path = db_path or os.path.join(root, "http-cache.sqlite")
    http = http_cache_bytes(db_path)
    if glb + http <= max_bytes:
        return out
    # split the budget in proportion to current use
    share = http / float(glb + http) if glb + http else 1.0
    out["http"] = trim_http_cache(db_path, int(max_bytes * share))
    out["glb"] = trim_files(root, int(max_bytes * (1.0 - share)))
    return out
