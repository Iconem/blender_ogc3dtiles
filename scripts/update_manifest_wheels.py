#!/usr/bin/env python3
"""
scripts/update_manifest_wheels.py
----------------------------------
After cibuildwheel runs, update blender_manifest.toml with the actual
wheel filenames that ended up in the wheels/ directory.

Usage:
    python scripts/update_manifest_wheels.py \
        --manifest blender_ogc3dtiles/blender_manifest.toml \
        --wheel-dir blender_ogc3dtiles/wheels/
"""

import argparse
import os
import re
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest",  required=True)
    parser.add_argument("--wheel-dir", required=True)
    args = parser.parse_args()

    wheel_dir = args.wheel_dir
    wheels = sorted(
        f for f in os.listdir(wheel_dir) if f.endswith(".whl")
    )

    if not wheels:
        print("ERROR: no .whl files found in", wheel_dir, file=sys.stderr)
        sys.exit(1)

    # Build the TOML files list
    lines = ["files = [\n"]
    for w in wheels:
        lines.append(f'    "./wheels/{w}",\n')
    lines.append("]\n")
    new_block = "".join(lines)

    with open(args.manifest) as f:
        content = f.read()

    # Replace the [wheels] files = [...] block
    content = re.sub(
        r"(\[wheels\]\s*\n)files\s*=\s*\[.*?\]",
        r"\g<1>" + new_block.rstrip(),
        content,
        flags=re.DOTALL,
    )

    with open(args.manifest, "w") as f:
        f.write(content)

    print(f"Updated {args.manifest} with {len(wheels)} wheels:")
    for w in wheels:
        print(f"  {w}")


if __name__ == "__main__":
    main()
