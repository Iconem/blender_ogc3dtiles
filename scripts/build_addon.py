"""
scripts/build_addon.py
----------------------
Builds the installable Blender addon zip from the addon/ source directory.

Usage:
    uv run python scripts/build_addon.py

Output:
    dist/ogc_3dtiles_blender_addon.zip

The zip contains a single top-level folder `blender_ogc3dtiles/` with all
addon files — ready to install via Blender's Add-ons → Install, or to
point a junction at for live dev editing.

Structure inside the zip:
    blender_ogc3dtiles/
        __init__.py
        blender_manifest.toml
        addon_prefs.py
        tileset/
        camera/
        io/
        ui/
"""

import os
import sys
import zipfile
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
ADDON_SRC    = PROJECT_ROOT / "src" / "blender_ogc3dtiles"
DIST_DIR     = PROJECT_ROOT / "dist"
ZIP_NAME     = "ogc_3dtiles_blender_addon.zip"

EXCLUDE = {
    "__pycache__", ".pyc", ".pyo",
    ".DS_Store", "Thumbs.db",
}

def should_include(path: Path) -> bool:
    return not any(ex in str(path) for ex in EXCLUDE)

def build():
    DIST_DIR.mkdir(exist_ok=True)
    zip_path = DIST_DIR / ZIP_NAME

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in sorted(ADDON_SRC.rglob("*")):
            if not file.is_file():
                continue
            if not should_include(file):
                continue
            # Archive as blender_ogc3dtiles/<relative path>
            arcname = Path("blender_ogc3dtiles") / file.relative_to(ADDON_SRC)
            zf.write(file, arcname)
            print(f"  + {arcname}")

    print(f"\nBuilt: {zip_path}  ({zip_path.stat().st_size // 1024} KB)")
    print(f"\nInstall in Blender:")
    print(f"  Edit → Preferences → Add-ons → Install → select {zip_path.name}")
    print(f"\nOr junction for live dev editing:")
    print(f"  Windows: mklink /J <blender_ext_dir>\\blender_ogc3dtiles {ADDON_SRC}")
    print(f"  macOS/Linux: ln -s {ADDON_SRC} <blender_ext_dir>/blender_ogc3dtiles")

if __name__ == "__main__":
    build()
