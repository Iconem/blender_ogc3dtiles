# Launch Blender with the extension hot-reload watcher (scripts/dev_watch.py).
# Usage: .\scripts\dev_blender.ps1 [-Blender <path\to\blender.exe>] [-Tileset <url>]
param(
    [string]$Blender = "C:\tools\BlenderLauncherWinget\stable\blender-5.1.1-stable.b70da489d7f4\blender.exe",
    [string]$Tileset = ""
)
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$watch = Join-Path $here "dev_watch.py"
$args = @("--python", $watch)
if ($Tileset) {
    $expr = "import bpy; bpy.app.timers.register(lambda: (setattr(bpy.context.scene.ogc3dtiles, 'tileset_url', '$Tileset'), None)[1], first_interval=1.0)"
    $args += @("--python-expr", $expr)
}
Start-Process -FilePath $Blender -ArgumentList $args
Write-Host "Blender started with hot reload; edit files under src/blender_ogc3dtiles and the add-on reloads within ~1 s."
