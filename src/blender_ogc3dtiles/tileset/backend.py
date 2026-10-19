"""
tileset/backend.py
------------------
Pluggable traversal backend.  Addon preferences expose a dropdown:

  CESIUM   → cesium-native-python  (github.com/calebbuffa/cesium-native-python)
             Real cesium-native: selection, implicit tiling, b3dm/i3dm/pnts/cmpt,
             Draco/meshopt/KTX2 decoding, LRU tile cache, sqlite HTTP cache.
             Implemented in native_backend.py against the binding's real API.

  PYTHON   → Pure-Python traversal (always available): frustum + distance
             culling, dynamic SSE, REPLACE gating, priority ordering.

  AUTO     → Try CESIUM first, silently fall back to PYTHON.

Both backends are driven by ui/__init__.py; the Python one returns Tile
objects from ``select(view, is_ready)``, the native one returns ready GLBs
through ``pop_ready()`` and render keys through ``update_view(...)``.
"""
from __future__ import annotations

import sys
from enum import Enum
from typing import Callable, NamedTuple

from .traversal import Tile, TilesetTraversal, ViewState


# ── Shared result (legacy, URI based) ─────────────────────────────────────────

class TraversalResult(NamedTuple):
    to_load: list    # content URIs to start fetching
    to_render: list  # content URIs that should be visible
    to_unload: list  # content URIs that can be hidden/removed


class BackendChoice(str, Enum):
    AUTO = "AUTO"
    CESIUM = "CESIUM"
    PYTHON = "PYTHON"


# ── Pure Python backend ───────────────────────────────────────────────────────

class PythonBackend:
    """Self-contained Python traversal — zero external dependencies."""

    name = "Pure Python"

    def __init__(self, max_sse: float = 16.0, max_tiles: int = 200,
                 detail_falloff: float = 600.0, max_dist: float = float("inf"), **_ignored):
        self._traversal = TilesetTraversal(max_sse=max_sse, max_tiles=max_tiles,
                                           detail_falloff=detail_falloff, max_dist=max_dist)
        self._root = None

    def load_tileset(self, url: str, ion_token: str, options: dict) -> None:
        pass   # tileset.json is fetched by the operator; see set_root()

    def set_root(self, root: Tile) -> None:
        self._root = root
        self._traversal.root = root

    # full API ----------------------------------------------------------------
    def select(self, view: ViewState, is_ready: Callable[[Tile], bool]):
        """→ (load_tiles_by_priority, render_tiles, unload_tiles)"""
        if self._root is None:
            return [], [], []
        return self._traversal.update_view_state(view, is_ready)

    def last_selection(self):
        return self._traversal.last_selection

    # legacy API ---------------------------------------------------------------
    def update_view(self, cam_ecef, screen_height: int, fov_y_rad: float) -> TraversalResult:
        if self._root is None:
            return TraversalResult([], [], [])
        load, render, unload = self._traversal.update_view(cam_ecef, screen_height, fov_y_rad)
        return TraversalResult([t.content_uri for t in load if t.content_uri],
                               [t.content_uri for t in render if t.content_uri],
                               [t.content_uri for t in unload if t.content_uri])

    def tick(self) -> None:
        pass

    def teardown(self) -> None:
        self._root = None

    def set_max_sse(self, v: float) -> None:
        self._traversal.max_sse = v

    def set_max_tiles(self, v: int) -> None:
        self._traversal.max_tiles = v


# ── cesium-native backend (real binding API) ──────────────────────────────────

try:
    from .native_backend import CesiumNativeBackend  # noqa: F401
except Exception as _exc:   # numpy missing etc. — keep the module importable
    CesiumNativeBackend = None  # type: ignore[assignment,misc]
    _native_import_error = _exc
else:
    _native_import_error = None


# ── Availability probe ────────────────────────────────────────────────────────

def probe_cesium() -> tuple:
    """(available, status_message) — only checks importability."""
    if sys.version_info < (3, 12):
        return False, f"Python {sys.version_info.major}.{sys.version_info.minor} — needs 3.12+"
    try:
        import cesium  # noqa: F401, PLC0415
        import cesium.tiles.selection  # noqa: F401, PLC0415
        ver = getattr(cesium, "__version__", "0.1.0")
        if CesiumNativeBackend is None:
            return False, f"cesium-native-python {ver} found but backend unavailable: {_native_import_error}"
        return True, f"cesium-native-python {ver} ✓"
    except ImportError:
        return False, "Not installed — build from github.com/calebbuffa/cesium-native-python"
    except Exception as exc:    # noqa: BLE001
        return False, f"Import error: {exc}"


# ── Factory ───────────────────────────────────────────────────────────────────

def make_backend(choice, max_sse: float = 16.0, max_tiles: int = 200,
                 detail_falloff: float = 600.0, max_dist: float = float("inf"),
                 cache_dir: str | None = None, **kw):
    """AUTO → cesium-native if importable else Python; CESIUM → raises ImportError
    when unavailable; PYTHON → always Python."""
    choice = BackendChoice(choice)

    if choice == BackendChoice.PYTHON:
        print("[3DTiles] Backend: Pure Python")
        return PythonBackend(max_sse=max_sse, max_tiles=max_tiles,
                             detail_falloff=detail_falloff, max_dist=max_dist)

    ok, msg = probe_cesium()
    if choice == BackendChoice.CESIUM and not ok:
        raise ImportError(f"cesium-native-python is not available: {msg}")
    if ok:
        print("[3DTiles] Backend: cesium-native-python")
        return CesiumNativeBackend(max_sse=max_sse, cache_dir=cache_dir,
                                   max_cached_mb=kw.get("max_cached_mb", 512),
                                   max_dist=max_dist, detail_falloff=detail_falloff)
    print(f"[3DTiles] Backend: Pure Python (cesium-native unavailable: {msg})")
    return PythonBackend(max_sse=max_sse, max_tiles=max_tiles,
                         detail_falloff=detail_falloff, max_dist=max_dist)


def get_available_backends() -> list:
    ok, status = probe_cesium()
    cesium_label = "cesium-native-python  ✓" if ok else f"cesium-native  [{status}]"
    return [
        ("AUTO", "Auto", "Use cesium-native if available, else Pure Python"),
        ("CESIUM", cesium_label, "Full cesium-native: implicit tiling, ion, all content types"),
        ("PYTHON", "Pure Python", "No dependencies — always available"),
    ]
