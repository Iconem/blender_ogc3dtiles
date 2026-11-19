"""Installing the cesium-native-python wheel from inside Blender: download from a GitHub Release, or build
from a source checkout, then pip install into Blender's Python.

This module is left out of the zips built for extensions.blender.org (scripts/build_platform_zips.py): they
carry the wheel, and an extension there may not download code. Without it the preferences show no install
or Reinstall button.
"""
from __future__ import annotations

from bpy.types import Operator


def _get_prefs(context):
    from .addon_prefs import _get_prefs as get
    return get(context)


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


classes = [OGC3D_OT_InstallCesiumWheel, OGC3D_OT_InstallCesium]
