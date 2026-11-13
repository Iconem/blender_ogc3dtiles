"""Local and network tileset paths → the URLs cesium-native's curl accepts.

Measured with the binding (curl's file:// on Windows):
  ``C:\\x\\tileset.json``, ``C:/x/...``, ``\\\\nas\\share\\...``  → "bad URL"
  ``file://nas/share/...``                                     → "could not read"
  ``file:///C:/x/tileset.json``                               → works
  ``file:////nas/share/x/tileset.json`` (four slashes, UNC)   → works
Relative content URIs resolve against both working forms. curl's ``file:``
responses carry no Cache-Control or ETag, so they never entered the sqlite HTTP
cache; reads from network shares now go through
``asset_fixes.make_network_file_accessor``, which adds an ETag so the cache keeps
them. Files on a local disk still bypass it.
"""
from __future__ import annotations

import os
import re
import sys
from urllib.parse import quote

_DRIVE = re.compile(r"^[A-Za-z]:[\\/]")
_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://")


def is_url(s: str) -> bool:
    return bool(_SCHEME.match(s)) or s.startswith(("ion://", "file:"))


def is_local_path(s: str) -> bool:
    s = s.strip()
    return bool(_DRIVE.match(s)) or s.startswith(("\\\\", "//", "/")) and not is_url(s)


def mapped_drive_unc(path: str) -> str | None:
    """``Z:\\x`` on a mapped network drive → ``\\\\server\\share\\x`` (Windows)."""
    if sys.platform != "win32" or not _DRIVE.match(path):
        return None
    try:
        import ctypes  # noqa: PLC0415
        from ctypes import wintypes  # noqa: PLC0415
        buf = ctypes.create_unicode_buffer(1024)
        n = wintypes.DWORD(len(buf))
        rc = ctypes.windll.mpr.WNetGetConnectionW(path[:2], buf, ctypes.byref(n))
        if rc != 0 or not buf.value:
            return None
        return buf.value.rstrip("\\") + "\\" + path[3:].replace("/", "\\")
    except Exception:          # noqa: BLE001
        return None


def path_to_url(path: str, unc_for_mapped: bool = False) -> str:
    """An absolute local / UNC path → ``file:`` URL; URLs pass through."""
    p = path.strip()
    if not p or is_url(p):
        return p
    if unc_for_mapped:
        p = mapped_drive_unc(p) or p
    p = p.replace("\\", "/")
    if p.startswith("//"):                               # UNC: file:////server/share/...
        return "file:////" + quote(p[2:], safe="/$:@!&'()*+,;=-._~")
    if _DRIVE.match(p):
        return "file:///" + p[:2] + quote(p[2:], safe="/$:@!&'()*+,;=-._~")
    return "file://" + quote(p, safe="/$:@!&'()*+,;=-._~")


def url_to_path(url: str) -> str:
    """Inverse of path_to_url for display and for opening files directly."""
    from urllib.parse import unquote
    u = url.strip()
    if not u.startswith("file:"):
        return u
    rest = unquote(u[5:])
    if rest.startswith("////"):
        return "\\\\" + rest[4:].replace("/", "\\") if os.name == "nt" else "//" + rest[4:]
    if rest.startswith("///"):
        rest = rest[3:] if _DRIVE.match(rest[3:]) else rest[2:]
    elif rest.startswith("//"):
        host, _, tail = rest[2:].partition("/")
        if host and host != "localhost":
            return "\\\\" + host + "\\" + tail.replace("/", "\\") if os.name == "nt" else "//" + rest[2:]
        rest = tail if _DRIVE.match(tail) else "/" + tail
    return rest.replace("/", "\\") if os.name == "nt" and _DRIVE.match(rest) else rest
