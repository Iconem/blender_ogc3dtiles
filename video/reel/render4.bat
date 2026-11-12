@echo off
cd /d "%OGC_SCRATCH%\reel"
call npx remotion render src/index.ts BlenderDemo out/blender-ogc3dtiles-demo.mp4 --concurrency 3 --timeout 180000 --overwrite > render4.log 2>&1
echo RENDER-DONE >> render4.log
