#!/bin/bash
cd $TEMP/ogc_tests/r9
B="C:/tools/BlenderLauncherWinget/custom/blender-5.3.0-beta+v53.3db45062d058-windows.amd64-release/blender.exe"
for s in "$@"; do
  rm -f slides_shots/$s.done
  for k in 1 2; do
    echo "$(date +%T) start $s ($k)" >> sq.log
    timeout 1500 "$B" -b --python hshot.py -- $s > s_$s.out 2>&1
    [ -f slides_shots/$s.done ] && break
  done
  echo "$(date +%T) end $s $(ls slides_shots | grep -c "^${s}_")" >> sq.log
done
echo "$(date +%T) queue finished" >> sq.log
