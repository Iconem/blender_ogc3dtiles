---
title: "extensions.blender.org"
description: "What is ready for a listing on the Blender extensions platform, and what its terms still block"
---

The add-on is not listed on [extensions.blender.org](https://extensions.blender.org) yet. The build and the
upload are ready; two clauses of the platform's
[terms of service](https://extensions.blender.org/terms-of-service/) are not met, and both need a decision
rather than code.

## Two kinds of zip

| Zip | Where | Size | cesium-native backend |
| --- | --- | --- | --- |
| `ogc_3dtiles_streaming-<version>.zip` | GitHub Releases | 0.2 MB | installed from the preferences: the wheel is downloaded from the binding's release |
| `ogc_3dtiles_streaming-<version>-<python>-<platform>.zip` | built for the platform | 8.7 MB Windows x64, 11.4 MB macOS ARM, 15.1 MB Linux x64 | inside the zip, installed by Blender with the extension |

`scripts/build_platform_zips.py --blender <blender> --python cp313` builds the second kind into
`dist/platform/cp313/`. A wheel is built for one Python, and Blender ships one Python per release line, so
there are two sets: `cp311` for Blender 5.0 and `cp313` for 5.1 and later. The platform builds start at
Blender 5.0; the GitHub zip still installs on 4.2 and later. One build serves every feature: what a Blender
version lacks is decided when the add-on runs (Gaussian splats are native from 5.3 and show as points
before), so there is no need for a build per feature. Each manifest carries the
matching `blender_version_min` and `blender_version_max`, so the platform serves the right one. Six zips in
all; macOS Intel and the ARM builds of Windows and Linux have no wheel.

On GitHub: *Actions > release extension > Run workflow* with *platform_zips* ticked builds the six zips as
artifacts, attaches them to a release when *release_tag* is given, and uploads them to the platform when
*publish_extensions* is ticked.

## Uploading

One authenticated request per zip:

```
curl -X POST https://extensions.blender.org/api/v1/extensions/ogc_3dtiles_streaming/versions/upload/ \
  -H "Authorization: Bearer $TOKEN" \
  -F "version_file=@ogc_3dtiles_streaming-0.6.6-cp313-windows_x64.zip" \
  --form-string "release_notes=..."
```

The token is made on the platform (profile, *API tokens*) and stored as the repository secret
`BLENDER_EXTENSIONS_TOKEN` (*Settings > Secrets and variables > Actions*) on the repository that runs the
workflow. The workflow reads it from the secret; it is never written in a file. The first version of an
extension is submitted by hand on the website, where it waits for a review. The API adds versions to an
extension that exists.

## What the terms ask

| Clause | Text | Status |
| --- | --- | --- |
| 5.1 | "Extension must be self-contained and not load remote code for execution." | met by the platform zips |
| 5.2 | no "external functional components" that "need to be downloaded from elsewhere", optional ones included | met by the platform zips |
| 1.1 | "Uploaded add-ons must be wholly compliant with the GNU General Public License, version 3 or later." | **not met**: the add-on is MIT |
| 3.6 | "Source code of the extension must be fully written in Python. Depending on external, pre-compiled packages is not allowed." | **unclear**: the backend is a compiled wheel |

### 5.1 and 5.2: no download of code

The GitHub zip breaks both: its *Install* and *Reinstall* buttons download a wheel and run `pip`. That code is
one module, `wheel_install.py`. The platform build leaves the file out, so those zips hold no downloader at
all, and the preferences then show the binding's version with no button next to it. Blender installs the
bundled wheel itself. A newer binding reaches those users with a new version of the extension.

The add-on still talks to the network: it streams tiles, searches places and reads terrain heights. That is
data, declared under `[permissions] network` in the manifest. One thing is still to do there: the platform's
guidelines want an add-on to stay offline while Blender's *Allow Online Access* preference is off
(`bpy.app.online_access`), and the add-on does not look at it yet.

### 1.1: the licence

The manifest says `SPDX:MIT`. MIT code can be shipped under the GPL, so this is a relicensing of the listing,
not a rewrite: the copyright holders publish the add-on as `GPL-3.0-or-later` (manifest, `LICENSE`, README).
The parts inside the zip allow it: cesium-native and cesium-native-python are Apache 2.0, which GPL 3
accepts. The cost is on the other side: code under GPL 3 can no longer be copied into an MIT or a closed
project. Offering both licences (MIT on GitHub, GPL on the platform) keeps that door open.

### 3.6: a compiled dependency

The pure Python backend meets the clause, the cesium-native one does not read as if it does: it is C++.
Blender's own manual documents wheels bundled in an extension, platform-specific ones included, so the
clause may be aimed at binaries fetched from outside the zip. That reading is ours, not the platform's.
Three ways forward:

- ask the reviewers before submitting, with the wheel's sources and build workflow at hand
  ([cesium-native-python](https://github.com/jo-chemla/cesium-native-python), built by cibuildwheel on GitHub);
- list the platform zips as they are and let the review decide;
- list a Python-only build. It streams mesh tilesets, more slowly, and without what only the cesium-native
  backend does (raster overlays, splats, point clouds, an Empty per dataset...).

Until one of these is settled, the GitHub zip stays the way to install.
