"""Developer hot-reload for the extension.

Run Blender with:  blender --python scripts/dev_watch.py
(or use scripts/dev_blender.ps1).  Every second the watcher compares the
mtimes of the extension's .py files; when something changed it stops
streaming, disables the add-on, drops its modules from sys.modules and
enables it again, so the sidebar panel always runs the code on disk.

Manual alternative inside Blender: F3 → "Reload Scripts" (menu Blender ▸
System ▸ Reload Scripts).  There is no default key binding for it.
"""
import os
import sys
import time

import bpy

ADDON_IDS = ("bl_ext.user_default.blender_ogc3dtiles", "blender_ogc3dtiles")
POLL_S = 1.0
QUIET_S = 2.0        # reload only after the tree has been unchanged this long


def _addon_id():
    for aid in ADDON_IDS:
        if aid in bpy.context.preferences.addons:
            return aid
    return _state.get("last_aid")


def _src_dir():
    aid = _addon_id()
    mod = sys.modules.get(aid) if aid else None
    if mod is not None and getattr(mod, "__file__", None):
        return os.path.dirname(os.path.realpath(mod.__file__))
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(os.path.dirname(here), "src", "blender_ogc3dtiles")


def _snapshot(root):
    snap = {}
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d != "__pycache__"]
        for f in fn:
            if f.endswith((".py", ".toml")):
                p = os.path.join(dp, f)
                try:
                    snap[p] = os.stat(p).st_mtime_ns
                except OSError:
                    pass
    return snap


def _reload(aid):
    try:
        if getattr(bpy.context.scene, "ogc3dtiles", None) and bpy.context.scene.ogc3dtiles.is_streaming:
            bpy.ops.ogc3dtiles.stop_stream()
    except Exception:
        pass
    bpy.ops.preferences.addon_disable(module=aid)
    for name in [m for m in sys.modules if m == aid or m.startswith(aid + ".")]:
        del sys.modules[name]
    bpy.ops.preferences.addon_enable(module=aid)
    for w in bpy.context.window_manager.windows:
        for a in w.screen.areas:
            a.tag_redraw()


_state = {"snap": None, "root": None, "dirty_since": None, "pending": []}


def _tick():
    aid = _addon_id()
    if aid is None:
        return POLL_S
    _state["last_aid"] = aid
    root = _state["root"] or _src_dir()
    _state["root"] = root
    snap = _snapshot(root)
    if _state["snap"] is None:
        _state["snap"] = snap
        print(f"[dev_watch] watching {root} ({len(snap)} files)")
        return POLL_S
    if snap != _state["snap"]:
        changed = [os.path.relpath(p, root) for p in snap if _state["snap"].get(p) != snap[p]]
        _state["snap"] = snap
        _state["pending"].extend(changed)
        _state["dirty_since"] = time.monotonic()      # debounce multi-file edits
        return POLL_S
    if _state["dirty_since"] is not None and time.monotonic() - _state["dirty_since"] >= QUIET_S:
        print(f"[dev_watch] changed: {sorted(set(_state['pending']))} → reloading {aid}")
        _state["dirty_since"] = None
        _state["pending"] = []
        try:
            _reload(aid)
            print("[dev_watch] reloaded OK")
        except Exception as e:                        # noqa: BLE001
            import traceback
            traceback.print_exc()
            print(f"[dev_watch] reload FAILED: {e}")
        # a failed register leaves the add-on disabled (and the sidebar tab
        # gone): keep trying every poll until it is back
        if aid not in bpy.context.preferences.addons:
            try:
                bpy.ops.preferences.addon_enable(module=aid)
                print("[dev_watch] re-enabled add-on")
            except Exception as e:                    # noqa: BLE001
                print(f"[dev_watch] re-enable failed: {e}")
    return POLL_S


bpy.app.timers.register(_tick, first_interval=2.0, persistent=True)
