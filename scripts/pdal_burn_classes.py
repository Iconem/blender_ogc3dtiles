"""DRAFT, never run in PDAL: burn a class grid into a point cloud's Classification with PDAL.

Reads the one-tile voxel tileset that *Build class grid* writes (``phases.py``), looks up the
cell under each point, and writes the class where there is one. The LAS then goes to Potree
or any other viewer. Pipeline::

    pdal pipeline burn.json

    [
      "site.copc.laz",
      {"type": "filters.python", "script": "scripts/pdal_burn_classes.py", "function": "burn",
       "module": "anything", "pdalargs": {"tileset": "phases_tileset/tileset.json",
                                          "srs": "EPSG:2154+5720"}},
      {"type": "writers.las", "filename": "site_classes.laz", "minor_version": 4,
       "dataformat_id": 6, "forward": "all"}
    ]

Needs numpy and pyproj in PDAL's Python. Things to check on the first run:

- ``srs`` must include the vertical datum. The grid is in ECEF, so a horizontal CRS alone
  puts French IGN69 heights about 45 m off, and pyproj needs the geoid grid to apply it.
- Classes 0 to 63 mean something in the LAS specification (2 is ground, 6 is building), so
  ``offset``, 64 by default, moves phase codes above them. Point formats below 6 only hold 0
  to 31, hence ``dataformat_id`` 6.
- Points outside the grid, or in an empty cell, keep the class they have.
"""
import json
import os

import numpy as np
from pyproj import Transformer

_grid = {}


def read_grid(path):
    """(codes indexed [x, y, z], box center, box axes as rows): tile axes as in
    ``tileset.voxels.write_class_tileset``, which stores [z, y, x] with y up and z = -tile y."""
    folder = os.path.dirname(path)
    with open(path, encoding="utf-8") as fh:
        box = json.load(fh)["root"]["boundingVolume"]["box"]
    with open(os.path.join(folder, "tiles/0/0/0/0.gltf"), encoding="utf-8") as fh:
        prim = json.load(fh)["meshes"][0]["primitives"][0]
    nx, nz, ny = prim["extensions"]["EXT_primitive_voxels"]["dimensions"]
    values = np.fromfile(os.path.join(folder, "tiles/0/0/0/0.bin"), np.float32).reshape(ny, nz, nx)
    return np.moveaxis(values[::-1], (2, 0, 1), (0, 1, 2)), np.array(box[:3]), np.array(box[3:]).reshape(3, 3)


def lookup(points_ecef, codes, center, axes):
    """The class under each point, 0 outside the grid."""
    unit = (points_ecef - center) @ axes.T / (axes * axes).sum(axis=1)     # -1 to 1 inside the box
    index = np.floor((unit + 1.0) / 2.0 * np.array(codes.shape)).astype(np.int64)
    inside = ((index >= 0) & (index < np.array(codes.shape))).all(axis=1)
    found = np.zeros(len(points_ecef), np.float32)
    found[inside] = codes[tuple(index[inside].T)]
    return found


def burn(ins, outs):
    args = pdalargs      # noqa: F821 (PDAL's filters.python provides it)
    if not _grid:
        _grid["data"] = read_grid(args["tileset"])
        _grid["to_ecef"] = Transformer.from_crs(args["srs"], "EPSG:4978", always_xy=True)
    x, y, z = _grid["to_ecef"].transform(ins["X"], ins["Y"], ins["Z"])
    found = lookup(np.column_stack((x, y, z)), *_grid["data"])
    classes = ins["Classification"].copy()
    hit = found > 0
    classes[hit] = found[hit].astype(classes.dtype) + int(args.get("offset", 64))
    outs["Classification"] = classes
    return True
