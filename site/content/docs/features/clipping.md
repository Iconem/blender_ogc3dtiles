---
title: "Clipping"
description: "Cut tilesets with polygons, boxes and the viewport region"
---

Each tileset entry has a **Clipping** list of Blender objects. **+** adds the
selected meshes or curves; each one is either:

- a **Clip-polygon**: its outlines seen from above, extruded along the tileset frame's Z
  (ENU up at the scene origin). An outline is every closed loop of boundary edges,
  or every edge of a face-less mesh or curve, so one object can hold several
  polygons. To make one, draw a Circle or Plane mesh, a polyline or a closed curve
  in Top view;
- a **Box**: the object's bounding box with its location, rotation and
  scale, so it clips in 3D (cut the top floors of a building, or a slab of a
  point cloud). Cube-like meshes are added as boxes.

The mode combines the volumes:

| Mode | Removes | |
|---|---|---|
| Cut inside any | what is inside at least one volume | union cut |
| Cut inside all | what is inside every volume | overlap cut |
| Keep inside any | what is outside every volume (*outside all*) | union kept |
| Keep inside all | what is outside at least one volume (*outside any*) | overlap kept |

Meshes, point clouds and Gaussian splats are clipped. Moving, rotating or
scaling a box or a clip-polygon updates the cut live, with no tile reloaded
(outlines over 64 points are cesium masks, which do reload them). Objects without
a parent are parented to the tileset's root Empty, so they follow it.
Tiles entirely cut by the
volumes aren't downloaded.

On mesh tiles the cut is done in the material, so Solid view, snapping and
exports still see the full mesh. **Slower: Also cut in solid view/exports** also deletes the faces that
are entirely cut, with Geometry Nodes and without fetching anything again. Faces
across the boundary stay whole outside the Material and Rendered views. It's off
by default because it slows down dragging a box on large scenes. Point clouds
and splats always lose the cut points for real.

Switching mode is close to instant: no material changes. See
[docs/clipping.md](/dev/notes/clipping) for how it all works, what comes from
cesium-native, and measurements.

## Viewport region (Alt+B)

Blender's clipping region (Alt+B) only cuts in Solid and Wireframe shading: EEVEE (Material Preview,
Rendered) ignores it. **Clip to viewport region**
(main panel, under Clipping) works around that: every tile material gets a Mix Shader
to a Transparent BSDF driven by the shared 'OGC3D Clip' group, into which the
add-on copies the viewport's clip planes each tick.  While it is on, Alt+B
alone toggles the clipping (drag a region to clip, Alt+B again to clear);
the planes come from the largest 3D viewport, and F12 renders use whatever
region that viewport last had.  It is on by default; untick to remove the
nodes again.

