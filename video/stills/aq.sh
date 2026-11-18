#!/bin/bash
cd $TEMP/ogc_tests/r9
B="C:/tools/BlenderLauncherWinget/custom/blender-5.3.0-beta+v53.3db45062d058-windows.amd64-release/blender.exe"
for s in "$@"; do
  rm -f slides_shots/$s.done; rm -rf slides_shots/anim_$s
  echo "$(date +%T) start $s" >> aq.log
  sed '/^reset(); res()$/,$d' hshot.py > hanim.py; cat hanim_shots.py >> hanim.py
  timeout 5400 "$B" -b --python hanim.py -- $s > a_$s.out 2>&1
  echo "$(date +%T) end $s $(ls slides_shots/anim_$s 2>/dev/null | grep -c png) frames $( [ -f slides_shots/$s.done ] && echo ok || echo FAILED)" >> aq.log
done
echo "$(date +%T) queue finished" >> aq.log
