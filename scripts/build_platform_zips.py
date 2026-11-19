"""Extension zips with the cesium-native-python wheel inside, one per platform, for extensions.blender.org.

    python scripts/build_platform_zips.py --blender /path/to/blender [--python cp313] [--repo owner/name]

The zip on the GitHub Releases page is pure Python: the wheel is installed from the add-on preferences, so a
binding fix reaches users without a new add-on release. The extensions platform does not allow that download
(an extension has to carry what it runs), so this builds the other kind: the manifest lists the wheels and
`blender --command extension build --split-platforms` writes one zip per platform, each with its own wheel.

One Blender line ships one Python, and a wheel is built for one Python: `--python` picks the wheels (cp313 is
Blender 5.1 and later, cp311 is Blender 4.2 to 5.0) and sets `blender_version_min` and `blender_version_max`
to match, so the two sets can sit side by side on the platform. Platforms without a wheel on the release
(macOS Intel, Windows and Linux on ARM) are left out. `wheel_install.py`, the module that downloads a wheel
from the preferences, is left out too: an extension there may not fetch code.
Output: dist/platform/<python>/, the zips named <id>-<version>-<python>-<platform>.zip.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import shutil
import subprocess
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "blender_ogc3dtiles"
# wheel platform tag (substring) -> Blender platform
PLATFORMS = (("win_amd64", "windows-x64"), ("manylinux", "linux-x64"), ("macosx", "macos-arm64"),
             ("win_arm64", "windows-arm64"))
# first Blender release on each Python
BLENDER_MIN = {"cp311": "4.2.0", "cp313": "5.1.0"}
# first Blender release that no longer runs it (blender_version_max is exclusive)
BLENDER_MAX = {"cp311": "5.1.0"}


def blender_platform(name: str) -> str | None:
    if "macosx" in name and "arm64" not in name:
        return None                                  # macOS Intel: Blender 5 no longer ships it
    if "manylinux" in name and "x86_64" not in name:
        return None
    return next((b for tag, b in PLATFORMS if tag in name), None)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--blender", required=True, help="Blender executable (runs the extension build)")
    ap.add_argument("--python", default="cp313", help="wheel Python tag (default cp313: Blender 5.1+)")
    ap.add_argument("--repo", default="jo-chemla/cesium-native-python", help="GitHub repo with the wheel release")
    a = ap.parse_args()

    req = urllib.request.Request(f"https://api.github.com/repos/{a.repo}/releases/latest",
                                 headers={"Accept": "application/vnd.github+json", "User-Agent": "build-script"})
    rel = json.load(urllib.request.urlopen(req, timeout=30))
    wheels = {x["name"]: x["browser_download_url"] for x in rel["assets"]
              if x["name"].endswith(".whl") and f"-{a.python}-" in x["name"] and blender_platform(x["name"])}
    if not wheels:
        raise SystemExit(f"{a.repo} {rel['tag_name']}: no {a.python} wheels")

    work = ROOT / "dist" / "platform" / a.python
    shutil.rmtree(work, ignore_errors=True)
    stage = work / "stage"
    shutil.copytree(SRC, stage, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "wheel_install.py"))   # no downloader in these zips
    (stage / "wheels").mkdir()
    for name, url in sorted(wheels.items()):
        print("wheel", name)
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "build-script"}),
                                    timeout=600) as r:
            (stage / "wheels" / name).write_bytes(r.read())

    manifest = (stage / "blender_manifest.toml").read_text(encoding="utf-8")
    manifest = re.sub(r'^blender_version_min\s*=.*$', f'blender_version_min = "{BLENDER_MIN.get(a.python, "5.1.0")}"',
                      manifest, flags=re.M)
    if a.python in BLENDER_MAX:
        manifest = manifest.replace("\nlicense", f'\nblender_version_max = "{BLENDER_MAX[a.python]}"\n\nlicense', 1)
    plats = sorted({blender_platform(n) for n in wheels})
    extra = ("platforms = [" + ", ".join(f'"{p}"' for p in plats) + "]\n"
             "wheels = [\n" + "".join(f'  "./wheels/{n}",\n' for n in sorted(wheels)) + "]\n\n")
    manifest = manifest.replace("[permissions]", extra + "[permissions]", 1)
    (stage / "blender_manifest.toml").write_text(manifest, encoding="utf-8", newline="\n")

    subprocess.run([a.blender, "-b", "--command", "extension", "build", "--split-platforms",
                    "--source-dir", str(stage), "--output-dir", str(work)], check=True)
    shutil.rmtree(stage)
    for z in sorted(work.glob("*.zip")):
        z = z.rename(z.with_name(re.sub(r"-([a-z]+_[a-z0-9]+)\.zip$", rf"-{a.python}-\1.zip", z.name)))
        subprocess.run([a.blender, "-b", "--command", "extension", "validate", str(z)], check=True)
        print(f"{z.name}  {z.stat().st_size / 1e6:.1f} MB")
    print(f"binding: {a.repo} {rel['tag_name']}")


if __name__ == "__main__":
    main()
