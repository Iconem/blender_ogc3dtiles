---
title: "Releasing"
description: "Cut a release on both repositories"
---

Bump `version` in `blender_manifest.toml`, then `git tag vX.Y.Z` and
`git push origin HEAD:main vX.Y.Z`. `origin` pushes to both `jo-chemla` and `Iconem`, and the
tag runs `release.yml`, which builds, validates and attaches the zip. `Iconem` is a fork and
may not run it on a push: then use
`gh workflow run release.yml -R Iconem/blender_ogc3dtiles --ref vX.Y.Z -f release_tag=vX.Y.Z`.
