# scripts/dev_setup.ps1
# ---------------------
# Bootstrap the OGC 3D Tiles dev environment on Windows using uv.
#
# Usage:
#   .\scripts\dev_setup.ps1 [-BlenderPath "C:\Program Files\Blender Foundation\Blender 4.3"]
#                            [-SkipCesium]   # skip cesium-native-python build (fast, no C++)
#
# Requirements:
#   - CMake 3.15+  (winget install Kitware.CMake)
#   - Visual Studio 2019/2022 with "Desktop development with C++" workload
#     (only needed when -SkipCesium is NOT set)
#   uv installs Python 3.12 automatically.

[CmdletBinding()]
param(
    [string] $BlenderPath = "",
    [switch] $SkipCesium
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectDir = Resolve-Path "$PSScriptRoot\.."

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  OGC 3D Tiles — Dev Setup (uv)  •  Windows" -ForegroundColor Cyan
Write-Host "  Project: $ProjectDir" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# ── Install uv if missing ─────────────────────────────────────────────────────
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "Installing uv..." -ForegroundColor Yellow
    # Official uv Windows installer
    Invoke-RestMethod "https://astral.sh/uv/install.ps1" | Invoke-Expression
    # Reload PATH for this session
    $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "User") + ";" + $env:PATH
}
$uvVer = uv --version
Write-Host "uv: $uvVer" -ForegroundColor Green

# ── Check MSVC (skip if not building cesium) ──────────────────────────────────
if (-not $SkipCesium) {
    $vsWhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
    if (Test-Path $vsWhere) {
        $vsPath = & $vsWhere -latest -property installationPath 2>$null
        Write-Host "MSVC: $vsPath" -ForegroundColor Green
    } else {
        Write-Warning @"
Visual Studio Build Tools not found.
Install from: https://aka.ms/vs/17/release/vs_BuildTools.exe
Select: 'Desktop development with C++'
Or run with -SkipCesium to skip the C++ build.
"@
    }

    # Ninja (faster than MSBuild for incremental cesium builds)
    if (-not (Get-Command ninja -ErrorAction SilentlyContinue)) {
        Write-Host "Installing Ninja..." -ForegroundColor Yellow
        winget install Ninja-build.Ninja --silent 2>$null `
            || choco install ninja --yes --no-progress 2>$null `
            || Write-Warning "Could not install Ninja automatically — install manually."
    }
}

# ── Create venv + sync deps ───────────────────────────────────────────────────
Push-Location $ProjectDir
try {
    Write-Host "`nCreating .venv with Python 3.12..." -ForegroundColor Yellow
    uv venv --python 3.12

    if ($SkipCesium) {
        Write-Host "`nInstalling dev deps (skipping cesium-native-python)..." -ForegroundColor Yellow
        uv sync --group dev --no-install-package cesium-native-python
    } else {
        # Activate MSVC environment so CMake (invoked by uv during cesium build) finds cl.exe
        # We do this by running the VS developer shell setup script
        $vsWhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
        if (Test-Path $vsWhere) {
            $vsPath = & $vsWhere -latest -property installationPath 2>$null
            $vcvars = "$vsPath\VC\Auxiliary\Build\vcvars64.bat"
            if (Test-Path $vcvars) {
                Write-Host "Activating MSVC x64 environment..." -ForegroundColor Yellow
                # Export MSVC env vars into current PowerShell session
                $envDump = cmd /c "`"$vcvars`" >nul 2>&1 && set"
                foreach ($line in $envDump) {
                    if ($line -match "^([^=]+)=(.*)$") {
                        [System.Environment]::SetEnvironmentVariable($Matches[1], $Matches[2], "Process")
                    }
                }
            }
        }
        $env:CMAKE_GENERATOR                = "Ninja"
        $env:CMAKE_BUILD_PARALLEL_LEVEL     = [Environment]::ProcessorCount

        Write-Host "`nInstalling all deps including cesium-native-python..." -ForegroundColor Yellow
        Write-Host "(First build: ~20-40 min; uv caches in %LOCALAPPDATA%\uv\cache)" -ForegroundColor DarkYellow
        uv sync --group dev
    }
} finally {
    Pop-Location
}

# ── Verify cesium ─────────────────────────────────────────────────────────────
Write-Host "`nChecking cesium-native-python..." -ForegroundColor Yellow
$check = uv run python -c @"
try:
    import cesium
    print(f'  OK  cesium {getattr(cesium, "__version__", "(no version)")}')
except ImportError as e:
    print(f'  MISSING  {e}')
"@
Write-Host $check

# ── Run tests ─────────────────────────────────────────────────────────────────
Write-Host "`nRunning tests..." -ForegroundColor Yellow
Push-Location $ProjectDir
try {
    if ($SkipCesium) {
        uv run pytest tests\ -m "not cesium" -v
    } else {
        uv run pytest tests\ -v
    }
} finally {
    Pop-Location
}

# ── Blender addon junction ────────────────────────────────────────────────────
if ($BlenderPath -and (Test-Path $BlenderPath)) {
    $ExtDir = "$env:APPDATA\Blender Foundation\Blender\4.3\extensions\user_default"
    New-Item -ItemType Directory -Force $ExtDir | Out-Null
    $LinkPath   = Join-Path $ExtDir "blender_ogc3dtiles"
    $TargetPath = Join-Path $ProjectDir "blender_ogc3dtiles"
    if (Test-Path $LinkPath) { Remove-Item $LinkPath -Recurse -Force }
    # Junction — no admin rights needed (unlike symlinks on Windows)
    cmd /c "mklink /J `"$LinkPath`" `"$TargetPath`"" | Out-Null
    Write-Host "`nAddon junction: $LinkPath" -ForegroundColor Green
    Write-Host "Restart Blender and enable 'OGC 3D Tiles Streaming'."
}

# ── Summary ───────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  Ready!" -ForegroundColor Green
Write-Host ""
Write-Host "  Run anything:     uv run python / uv run pytest"
Write-Host "  Test (fast):      uv run pytest -m 'not cesium'"
Write-Host "  Test (full):      uv run pytest"
Write-Host "  Lint:             uv run ruff check . ; uv run mypy blender_ogc3dtiles\"
Write-Host "  Re-sync:          uv sync --group dev"
Write-Host "  Update cesium:    uv sync --group dev --upgrade-package cesium-native-python"
Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor Cyan
