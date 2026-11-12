#!/bin/bash
# run.sh file.py [timeout_s]: run a script in the test window, print its output
D=/c/Users/jonathan/AppData/Local/Temp/ogc_tests/r9
rm -f $D/cmd.out
{ printf 'import os\nexec(open(os.path.join(os.environ["TEMP"],"ogc_tests","r9","h.py")).read())\n'; cat "$1"; } > $D/cmd.tmp
mv $D/cmd.tmp $D/cmd.py
for i in $(seq 1 $((${2:-100}*2))); do
  [ -f $D/cmd.out ] && { cat $D/cmd.out; exit 0; }
  sleep 0.5
done
echo "TIMEOUT"
