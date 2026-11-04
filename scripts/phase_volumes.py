"""Demo of the add-on's Phases timeline (beta): invented volumes on the Colosseum.

The phases are made up, they only try shapes that a prism or a box can't make. Run it in
Blender's Text Editor with the add-on on and *Beta features > Phases timeline* ticked:

  1. It sets a custom scene origin, adds the volumes to a "Phases" collection and builds
     the class grid, which is added to the tileset list.
  2. Add a mesh tileset of the Colosseum and press Start.
  3. 3D Tiles sidebar > Phases (beta): move the year, or tick Clip to phases.
"""
import math

import bpy

COLLECTION = "Phases"
CENTER = (12.0, 0.0, 0.0)       # the arena from a top view of Google's tiles, around the origin below
ANGLE = math.radians(-18.0)     # its long axis
LAT, LON, HEIGHT = 41.8902, 12.4922, 70.0


def link(name, verts, faces, code, year, color):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    coll = bpy.data.collections.get(COLLECTION) or bpy.data.collections.new(COLLECTION)
    if coll.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(coll)
    coll.objects.link(obj)
    obj["code"], obj["year"], obj["color"] = code, year, color
    obj.display_type = "WIRE"
    obj.hide_render = True
    return obj


def ring(name, profile, code, year, color, top_tilt=0.0, n=128):
    """A closed lathe around an ellipse. ``profile`` is a loop of (s, z), s = 0 at the arena
    edge, 1 at the outer wall; ``top_tilt`` makes the ring lean, so it isn't level either."""
    c, s = math.cos(ANGLE), math.sin(ANGLE)
    verts, faces = [], []
    m = len(profile)
    for i in range(n):
        t = 2 * math.pi * i / n
        for sp, z in profile:
            x, y = (43 + 51 * sp) * math.cos(t), (27 + 51 * sp) * math.sin(t)
            lift = top_tilt * math.sin(t) * max(z, 0.0)
            verts.append((CENTER[0] + c * x - s * y, CENTER[1] + s * x + c * y, CENTER[2] + z + lift))
    for i in range(n):
        j = (i + 1) % n
        for k in range(m):
            q = (k + 1) % m
            faces.append((i * m + k, j * m + k, j * m + q, i * m + q))
    return link(name, verts, faces, code, year, color)


def blob(name, center, size, code, year, color, bumps=0.0):
    """A closed sphere of quads with end fans, scaled by ``size``, bumpy when asked."""
    rows, cols = 32, 64
    verts = [(center[0], center[1], center[2] - size[2])]
    for r in range(1, rows):
        el = -math.pi / 2 + math.pi * r / rows
        for k in range(cols):
            az = 2 * math.pi * k / cols
            b = 1 + bumps * (math.sin(3 * az + 1.0) * math.cos(2 * el + 2.0)
                             + 0.5 * math.sin(7 * az + 4.0) * math.sin(5 * el + 0.5))
            verts.append((center[0] + b * size[0] * math.cos(el) * math.cos(az),
                          center[1] + b * size[1] * math.cos(el) * math.sin(az),
                          center[2] + b * size[2] * math.sin(el)))
    verts.append((center[0], center[1], center[2] + size[2]))
    last = len(verts) - 1
    at = lambda r, k: 1 + (r - 1) * cols + k % cols     # noqa: E731
    faces = []
    for k in range(cols):
        faces.append((0, at(1, k + 1), at(1, k)))
        faces.append((last, at(rows - 1, k), at(rows - 1, k + 1)))
        for r in range(1, rows - 1):
            faces.append((at(r, k), at(r, k + 1), at(r + 1, k + 1), at(r + 1, k)))
    return link(name, verts, faces, code, year, color)


def wedge(name, code, year, color):
    """Against the wall's east end: no vertical side and no level top."""
    ux, uy = math.cos(ANGLE), math.sin(ANGLE)
    ex, ey = CENTER[0] + 94 * ux, CENTER[1] + 94 * uy
    corners = [(-14, -22, -2), (10, -28, -2), (10, 28, -2), (-14, 22, -2),
               (-10, -16, 40), (-2, -10, 46), (-2, 10, 46), (-10, 16, 40)]
    verts = [(ex + ux * p - uy * q, ey + uy * p + ux * q, CENTER[2] + z) for p, q, z in corners]
    faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    return link(name, verts, faces, code, year, color)


def main():
    old = bpy.data.collections.get(COLLECTION)
    if old is not None:
        for obj in list(old.objects):
            bpy.data.objects.remove(obj)
    blob("Arena bowl", (CENTER[0], CENTER[1], CENTER[2] - 2), (47, 31, 9), 1, 80, (0.20, 0.45, 0.95))
    ring("Cavea cone", [(0.0, -2), (0.8, -2), (0.8, 33), (0.45, 18), (0.0, 7)], 2, 90, (0.95, 0.75, 0.15))
    ring("Outer wall, leaning top", [(0.8, -2), (1.06, -2), (1.06, 44), (0.8, 44)], 3, 200, (0.90, 0.22, 0.18),
         top_tilt=0.14)
    wedge("Buttress wedge", 4, 1820, (0.15, 0.80, 0.40))
    blob("Repair blob", (CENTER[0] - 22, CENTER[1] + 62, CENTER[2] + 18), (26, 16, 18), 5, 1990, (0.85, 0.25, 0.85),
         bumps=0.22)
    props = bpy.context.scene.ogc3dtiles
    props.origin_mode = "CUSTOM"
    props.origin_lat, props.origin_lon, props.origin_height = LAT, LON, HEIGHT
    props.origin_valid = True
    print(bpy.ops.ogc3dtiles.phases_build())


main()
