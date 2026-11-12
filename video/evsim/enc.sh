#!/bin/bash
# enc.sh name [fps] [extra vf]: wait for cap_<name>/done.txt, encode ui_<name>.mp4, delete frames
D=/c/Users/jonathan/AppData/Local/Temp/ogc_tests/r9
cd $D
for i in $(seq 1 400); do [ -f cap_$1/done.txt ] && break; sleep 3; done
cat cap_$1/done.txt; echo
VF="scale=1920:-2${3:+,$3}"
ffmpeg -y -loglevel error -framerate ${2:-12} -i cap_$1/f_%04d.png -vf "$VF" -c:v libx264 -pix_fmt yuv420p -crf 21 ui_$1.mp4 && rm -f cap_$1/f_*.png
ls -la ui_$1.mp4
