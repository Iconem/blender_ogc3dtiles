#!/usr/bin/env bash
# scripts/dev_setup.sh
# --------------------
# Bootstrap the OGC 3D Tiles dev environment on macOS / Linux using uv.
#
# Usage:
#   ./scripts/dev_setup.sh [--blender /path/to/blender] [--no-cesium]
#
# What it does:
#   1. Installs uv (if not present)
#   2. Creates .venv with Python 3.12 via uv
#   3. uv sync --group dev  (installs all dev deps + cesium-native-python from git)
#   4. Runs the test suite
#   5. Optionally symlinks the addon into Blender's extensions directory

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "${SCRIPT_DIR}")"
BLENDER_PATH=""
SKIP_CESIUM=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --blender)     BLENDER_PATH="$2"; shift 2 ;;
        --no-cesium)   SKIP_CESIUM=true;  shift   ;;
        *) echo "Unknown arg: $1"; exit 1 ;;
    esac
done

echo ""
echo "══════════════════════════════════════════════════════"
echo "  OGC 3D Tiles — Dev Setup (uv)"
echo "  Project: ${PROJECT_DIR}"
echo "══════════════════════════════════════════════════════"
echo ""

# ── Install uv if missing ─────────────────────────────────────────────────────
if ! command -v uv &>/dev/null; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # Reload PATH so uv is available in this shell
    export PATH="${HOME}/.local/bin:${HOME}/.cargo/bin:${PATH}"
fi
echo "uv: $(uv --version)"

# ── Create venv with Python 3.12 ─────────────────────────────────────────────
cd "${PROJECT_DIR}"
echo ""
echo "Creating .venv with Python 3.12..."
uv venv --python 3.12

echo ""
if [[ "${SKIP_CESIUM}" == true ]]; then
    # Skip cesium-native-python (no C++ toolchain needed)
    # Installs everything except the cesium-native-python git source dep
    echo "Installing dev deps (skipping cesium-native-python)..."
    uv sync --group dev --no-install-package cesium-native-python
else
    # Full sync — clones + builds cesium-native-python from git source
    # First build is slow (~20-40 min); uv caches the build artefacts in ~/.cache/uv
    echo "Installing all deps including cesium-native-python (first build: slow)..."
    echo "Tip: re-run with --no-cesium for a fast iteration cycle without C++."
    echo ""
    uv sync --group dev
fi

# ── Verify cesium import ──────────────────────────────────────────────────────
echo ""
echo "Checking cesium-native-python..."
uv run python -c "
try:
    import cesium
    print(f'  ✓  cesium {getattr(cesium, \"__version__\", \"(no version)\")}')
except ImportError as e:
    print(f'  ✗  {e}')
"

# ── Run tests ─────────────────────────────────────────────────────────────────
echo ""
echo "Running tests..."
if [[ "${SKIP_CESIUM}" == true ]]; then
    uv run pytest tests/ -m "not cesium" -v
else
    uv run pytest tests/ -v
fi

# ── Blender addon symlink ─────────────────────────────────────────────────────
if [[ -n "${BLENDER_PATH}" && -e "${BLENDER_PATH}" ]]; then
    if [[ "$OSTYPE" == "darwin"* ]]; then
        EXT_DIR="${HOME}/Library/Application Support/Blender/4.3/extensions/user_default"
    else
        EXT_DIR="${HOME}/.config/blender/4.3/extensions/user_default"
    fi
    mkdir -p "${EXT_DIR}"
    LINK="${EXT_DIR}/blender_ogc3dtiles"
    TARGET="${PROJECT_DIR}/blender_ogc3dtiles"
    ln -sfn "${TARGET}" "${LINK}"
    echo ""
    echo "Addon symlinked: ${LINK}"
    echo "Restart Blender and enable 'OGC 3D Tiles Streaming'."
fi

echo ""
echo "══════════════════════════════════════════════════════"
echo "  Ready!"
echo ""
echo "  Activate:        source .venv/bin/activate"
echo "  Or prefix:       uv run pytest / uv run python ..."
echo ""
echo "  Test (fast):     uv run pytest -m 'not cesium'"
echo "  Test (full):     uv run pytest"
echo "  Lint:            uv run ruff check . && uv run mypy blender_ogc3dtiles/"
echo "  Re-sync deps:    uv sync --group dev"
echo "  Update cesium:   uv sync --group dev --upgrade-package cesium-native-python"
echo "══════════════════════════════════════════════════════"
