#!/bin/bash
# enc_anim.sh <shot> <clip name> [crf] [first] [last] [hold]: slides_shots/anim_<shot>/f_*.png -> docs/video/<clip>.mp4
# and a poster .jpg. first..last keep part of the frames (a demo that loops past the window, a slow start); hold
# repeats the last frame that many times before the clip loops. Transparent frames go over the page grey (#f7f7f7),
# so the Workbench clips sit on the docs page like the stills.
R=$(cygpath -u "$TEMP")/ogc_tests/r9; W=$(git rev-parse --show-toplevel)/docs/video
mkdir -p "$W"; D=$R/slides_shots/anim_$1; N=$(ls $D/f_*.png | wc -l)
A=${4:-0}; B=${5:-$((N - 1))}; H=${6:-0}
ffmpeg -v error -y -f lavfi -i "color=c=0xf7f7f7:s=1280x720:r=24" -start_number $A -framerate 24 -i "$D/f_%04d.png" \
  -filter_complex "[1]trim=end_frame=$((B - A + 1)),tpad=stop_mode=clone:stop=$H[f];[0][f]overlay=shortest=1,format=yuv420p" \
  -c:v libx264 -preset slow -crf ${3:-24} -profile:v high -movflags +faststart -an "$W/$2.mp4"
ffmpeg -v error -y -f lavfi -i "color=c=0xf7f7f7:s=1280x720" -i "$D/f_$(printf %04d $((A + (B - A) * 2 / 3))).png" \
  -filter_complex "[0][1]overlay" -frames:v 1 -q:v 3 "$W/$2.jpg"
echo "$2: frames $A..$B + $H held, $(stat -c %s "$W/$2.mp4") bytes"
