#!/bin/bash
# rebuild, reinstall, restart only the test window (command line holds gui_repl)
cd /c/Users/jonathan/.t3/worktrees/blender_ogc3dtiles/t3-after-handoff
B="C:/tools/BlenderLauncherWinget/custom/blender-5.3.0-beta+v53.3db45062d058-windows.amd64-release/blender.exe"
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='blender.exe'\" | Where-Object { \$_.CommandLine -like '*gui_repl*' } | ForEach-Object { Stop-Process -Id \$_.ProcessId -Force }"


cd "$TEMP/ogc_tests/r9" && rm -f cmd.py cmd.out
("$B" --enable-event-simulate --python "$TEMP/ogc_tests/r9/gui_repl.py" > gui.out 2> gui.err &)
echo relaunched
