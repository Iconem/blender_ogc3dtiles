---
title: "Setup, tests, releasing"
description: "Run the add-on from a checkout, its tests, and cut a release"
---

```
uv venv && uv pip install -e . --group dev
PYTHONPATH=src pytest        # traversal + coordinate tests (bpy is stubbed)
```

For development, symlink `src/blender_ogc3dtiles` into
`<config>/extensions/user_default/` and use `scripts/dev_blender.ps1`.

Headless smoke test: see `ui.stream_tick()`; in `blender -b` the operator
does not start a timer, call `stream_tick(bpy.context)` yourself with a
monkeypatched `CesiumCameraAdapter.get_view_state`.

## Releasing

Bump `version` in `blender_manifest.toml`, then `git tag vX.Y.Z` and
`git push origin HEAD:main vX.Y.Z`. `origin` pushes to both `jo-chemla` and `Iconem`, and the
tag runs `release.yml`, which builds, validates and attaches the zip. `Iconem` is a fork and
may not run it on a push: then use
`gh workflow run release.yml -R Iconem/blender_ogc3dtiles --ref vX.Y.Z -f release_tag=vX.Y.Z`.
