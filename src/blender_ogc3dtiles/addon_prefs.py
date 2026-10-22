"""
addon_prefs.py — Blender Addon Preferences
------------------------------------------
Edit → Preferences → Add-ons → OGC 3D Tiles → Preferences

Sections
  1. Traversal Backend   — CESIUM / PYTHON / AUTO + status + perf stats
  2. Performance         — live timing comparison between backends
  3. Developer           — dev mode, coord debug, wheel/install path
"""

from __future__ import annotations

import bpy
from bpy.types import AddonPreferences, Operator
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, StringProperty

from .tileset.backend import get_available_backends, probe_cesium


# ── Prefs class ───────────────────────────────────────────────────────────────

def _get_prefs(context):
    """Safe prefs lookup — works for both legacy addon and Extension install."""
    for key in ("blender_ogc3dtiles",
                "bl_ext.user_default.blender_ogc3dtiles",
                "user_default.blender_ogc3dtiles"):
        try:
            return context.preferences.addons[key].preferences
        except (KeyError, AttributeError):
            pass
    return None


class OGC3DTilesPreferences(AddonPreferences):
    bl_idname = __package__

    # ── Backend selection ──────────────────────────────────────────────────────
    def _backend_items(self, _context):
        return [(id_, name, desc) for id_, name, desc in get_available_backends()]

    traversal_backend: EnumProperty(
        name="Traversal Backend",
        description=(
            "Which tile LOD engine to use.\n\n"
            "cesium-native-python: full spec compliance, async, ion, implicit tiling.\n"
            "Pure Python: no deps, good for debugging and perf baselining."
        ),
        items=_backend_items,
        default=0,
    )

    # ── Performance tracking (written by the modal operator each tick) ─────────
    # These are exposed in prefs so the panel can read them without a context ref.
    perf_cesium_ms: FloatProperty(
        name="cesium-native update_view (ms)",
        default=0.0, precision=3,
        options={"HIDDEN"},
    )
    perf_python_ms: FloatProperty(
        name="Python update_view (ms)",
        default=0.0, precision=3,
        options={"HIDDEN"},
    )
    perf_samples: IntProperty(
        name="Perf sample count",
        default=0,
        options={"HIDDEN"},
    )
    show_perf_compare: BoolProperty(
        name="Live Backend Comparison",
        description=(
            "Run both backends every tick and display timing.\n"
            "⚠  Doubles CPU usage — for profiling only."
        ),
        default=False,
    )

    # ── Developer ──────────────────────────────────────────────────────────────
    dev_mode: BoolProperty(
        name="Developer Mode",
        description="Show ECEF coords, SSE values, tile counts in the 3D view panel",
        default=False,
    )
    show_coord_debug: BoolProperty(
        name="Coordinate Debug Panel",
        description="Show ENU ↔ ECEF ↔ Blender mapping in a sidebar panel",
        default=False,
    )
    cesium_wheel_repo: StringProperty(
        name="Wheel release repo",
        description="GitHub repository whose latest Release carries cesium-native-python "
                    "wheels (owner/name); the matching CPython / platform wheel is "
                    "downloaded and pip-installed into Blender's Python",
        default="jo-chemla/cesium-native-python",
    )
    cesium_install_path: StringProperty(
        name="cesium-native-python source dir",
        description=(
            "Path to a locally-cloned cesium-native-python repo. "
            "Used by 'Install / Rebuild' button."
        ),
        subtype="DIR_PATH",
        default="",
    )

    # ── Draw ───────────────────────────────────────────────────────────────────
    def draw(self, context):
        layout = self.layout

        # ── 1. Backend ────────────────────────────────────────────────────────
        box = layout.box()
        row = box.row()
        row.label(text="Traversal Backend", icon="MOD_DYNAMICPAINT")

        box.prop(self, "traversal_backend", text="")

        # Status row
        ok, status = probe_cesium()
        status_row = box.row()
        status_row.label(
            text=f"cesium-native-python:  {status}",
            icon="CHECKMARK" if ok else ("ERROR" if "error" in status.lower() else "INFO"),
        )

        # Install from a release wheel (no compiler needed), or build from source
        row1 = box.row(align=True)
        row1.operator("ogc3dtiles.install_cesium_wheel", icon="IMPORT", text="Install wheel from GitHub Release")
        row1.operator("ogc3dtiles.reload_cesium", icon="FILE_REFRESH", text="")
        box.prop(self, "cesium_wheel_repo", text="Release repo")
        row2 = box.row(align=True)
        row2.operator("ogc3dtiles.install_cesium", icon="TOOL_SETTINGS", text="Build / install from source")
        box.prop(self, "cesium_install_path", text="Source dir")

        # ── 2. Performance comparison ─────────────────────────────────────────
        layout.separator()
        box2 = layout.box()
        box2.label(text="Performance", icon="SORTTIME")
        box2.prop(self, "show_perf_compare")

        if self.perf_samples > 0:
            col = box2.column(align=True)
            col.scale_y = 0.9

            def bar(label: str, ms: float, ref_ms: float):
                pct = (ms / ref_ms * 100) if ref_ms > 0 else 0
                row = col.row(align=True)
                row.label(text=f"{label:<22} {ms:6.3f} ms  ({pct:.0f}%)")

            ref = max(self.perf_cesium_ms, self.perf_python_ms, 0.001)
            bar("cesium-native-python", self.perf_cesium_ms, ref)
            bar("Pure Python",          self.perf_python_ms, ref)
            col.label(text=f"Samples: {self.perf_samples}", icon="DRIVER")

            row3 = box2.row()
            row3.operator("ogc3dtiles.reset_perf_stats", icon="X", text="Reset Stats")
        else:
            box2.label(text="Start streaming to gather samples.", icon="INFO")

        # ── 3. Developer ──────────────────────────────────────────────────────
        layout.separator()
        box3 = layout.box()
        box3.label(text="Developer", icon="SCRIPT")
        box3.prop(self, "dev_mode")
        box3.prop(self, "show_coord_debug")


# ── Operators ─────────────────────────────────────────────────────────────────

class OGC3D_OT_InstallCesium(Operator):
    """Install or rebuild cesium-native-python using uv"""
    bl_idname = "ogc3dtiles.install_cesium"
    bl_label  = "Install / Rebuild cesium-native-python"

    def execute(self, context):
        import subprocess, sys, os
        prefs = _get_prefs(context)
        if prefs is None:
            self.report({"ERROR"}, "Could not find addon preferences")
            return {"CANCELLED"}
        src   = prefs.cesium_install_path.strip()
        # Always use Blender's own Python (sys.executable) to install
        # into Blender's site-packages. uv would try to find a venv.
        if src and os.path.isdir(src):
            cmd = [sys.executable, "-m", "pip", "install", src,
                   "--no-build-isolation", "-v"]
            msg = f"pip: building cesium from {src}"
        else:
            cmd = [sys.executable, "-m", "pip", "install",
                   "git+https://github.com/calebbuffa/cesium-native-python.git"]
            msg = "pip: installing cesium-native-python from GitHub"

        self.report({"INFO"}, msg)
        try:
            kwargs: dict = {}
            if sys.platform == "win32":
                kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, **kwargs,
            )
            stdout, _ = proc.communicate(timeout=600)
            if proc.returncode == 0:
                self.report({"INFO"}, "cesium-native-python installed. Reload Blender.")
            else:
                self.report({"ERROR"}, f"Build failed (rc={proc.returncode}). Check System Console.")
                print(stdout)
        except subprocess.TimeoutExpired:
            self.report({"WARNING"}, "Build >10 min — check terminal.")
        except Exception as e:
            self.report({"ERROR"}, str(e))

        return {"FINISHED"}


def wheel_tags():
    """(cpython tag, platform substrings) a wheel for this interpreter must carry."""
    import platform
    import sys
    cp = f"cp{sys.version_info.major}{sys.version_info.minor}"
    machine = platform.machine().lower()
    if sys.platform == "win32":
        plat = ("win_amd64",) if machine in ("amd64", "x86_64") else ("win_arm64",)
    elif sys.platform == "darwin":
        plat = ("macosx", "arm64" if machine == "arm64" else "x86_64")
    else:
        plat = ("manylinux", "aarch64" if machine in ("aarch64", "arm64") else "x86_64")
    return cp, plat


def pick_wheel(names, cp, plat):
    """First wheel file name matching the interpreter tag and every platform
    substring (abi3 wheels accepted for any CPython >= their tag)."""
    for n in names:
        if not n.endswith(".whl") or not all(p in n for p in plat):
            continue
        if f"-{cp}-{cp}-" in n or f"-{cp}-abi3-" in n:
            return n
    for n in names:                               # abi3 built on an older CPython
        if n.endswith(".whl") and all(p in n for p in plat) and "-abi3-" in n:
            return n
    return None


class OGC3D_OT_InstallCesiumWheel(Operator):
    """Download the cesium-native-python wheel for this Blender's Python from
    the latest GitHub Release of the configured repo and pip-install it"""
    bl_idname = "ogc3dtiles.install_cesium_wheel"
    bl_label = "Install cesium-native-python wheel"

    def execute(self, context):
        import json
        import os
        import subprocess
        import sys
        import tempfile
        import urllib.request
        prefs = _get_prefs(context)
        repo = (getattr(prefs, "cesium_wheel_repo", "") or "jo-chemla/cesium-native-python").strip()
        cp, plat = wheel_tags()
        try:
            req = urllib.request.Request(f"https://api.github.com/repos/{repo}/releases/latest",
                                         headers={"Accept": "application/vnd.github+json",
                                                  "User-Agent": "blender_ogc3dtiles"})
            with urllib.request.urlopen(req, timeout=30) as r:
                rel = json.loads(r.read().decode("utf-8"))
        except Exception as e:                        # noqa: BLE001
            self.report({"ERROR"}, f"No release found at {repo}: {e}")
            return {"CANCELLED"}
        assets = {a["name"]: a["browser_download_url"] for a in rel.get("assets", [])}
        name = pick_wheel(sorted(assets), cp, plat)
        if name is None:
            self.report({"ERROR"}, f"Release {rel.get('tag_name')} has no wheel for {cp} "
                                   f"{'/'.join(plat)} (assets: {', '.join(sorted(assets)) or 'none'})")
            return {"CANCELLED"}
        tmp = tempfile.mkdtemp(prefix="ogc3dtiles_wheel_")
        path = os.path.join(tmp, name)
        try:
            req = urllib.request.Request(assets[name], headers={"User-Agent": "blender_ogc3dtiles"})
            with urllib.request.urlopen(req, timeout=600) as r, open(path, "wb") as f:
                f.write(r.read())
        except Exception as e:                        # noqa: BLE001
            self.report({"ERROR"}, f"Download failed: {e}")
            return {"CANCELLED"}
        cmd = [sys.executable, "-m", "pip", "install", "--no-deps", "--force-reinstall", path]
        kwargs: dict = {}
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        try:
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  text=True, timeout=600, **kwargs)
        except Exception as e:                        # noqa: BLE001
            self.report({"ERROR"}, f"pip failed: {e}")
            return {"CANCELLED"}
        if proc.returncode != 0:
            print(proc.stdout)
            self.report({"ERROR"}, f"pip install failed (rc={proc.returncode}), see System Console")
            return {"CANCELLED"}
        try:
            import numpy  # noqa: F401 — the wheel's only runtime dependency
        except ImportError:
            subprocess.run([sys.executable, "-m", "pip", "install", "numpy"], **kwargs)
        self.report({"INFO"}, f"Installed {name} from {repo} {rel.get('tag_name')}. "
                              "Restart Blender (or Reload Module) to use the native backend.")
        return {"FINISHED"}


class OGC3D_OT_ReloadCesium(Operator):
    """Reload cesium modules without restarting Blender (Python parts only)"""
    bl_idname = "ogc3dtiles.reload_cesium"
    bl_label  = "Reload cesium Module"

    def execute(self, context):
        import sys
        removed = [k for k in sys.modules if k.startswith("cesium")]
        for k in removed:
            del sys.modules[k]
        ok, msg = probe_cesium()
        self.report({"INFO"} if ok else {"WARNING"}, f"cesium: {msg}")
        return {"FINISHED"}


class OGC3D_OT_ResetPerfStats(Operator):
    """Clear accumulated backend performance samples"""
    bl_idname = "ogc3dtiles.reset_perf_stats"
    bl_label  = "Reset Perf Stats"

    def execute(self, context):
        prefs = _get_prefs(context)
        if prefs is None:
            self.report({"ERROR"}, "Could not find addon preferences")
            return {"CANCELLED"}
        prefs.perf_cesium_ms = 0.0
        prefs.perf_python_ms = 0.0
        prefs.perf_samples   = 0
        return {"FINISHED"}


# ── Registration ──────────────────────────────────────────────────────────────

_classes = [
    OGC3D_OT_InstallCesiumWheel,
    OGC3DTilesPreferences,
    OGC3D_OT_InstallCesium,
    OGC3D_OT_ReloadCesium,
    OGC3D_OT_ResetPerfStats,
]


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
