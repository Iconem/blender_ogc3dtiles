---
title: "Clipping"
description: "Cut tilesets with polygons, boxes and the viewport region"
---

Clipping cuts a tileset with Blender objects: remove a block to place your own model, keep only one
site out of a city, drop a detailed scan into a coarser tileset without the two overlapping. It works
on meshes, point clouds and Gaussian splats.

## Add a clipping object

1. Draw the shape: a Circle or Plane mesh, a polyline or a closed curve in Top view for an outline,
   or a Cube for a box.
2. Select it, select the tileset in the list, tick **Clipping** and press **+**.

Each object is one of:

- a **Clip-polygon**: its outline seen from above, cutting at every height. One object can hold
  several outlines.
- a **Box**: its bounding box, with its location, rotation and scale. It cuts in 3D: the top floors
  of a building, a slab of a point cloud. Cube-like meshes are added as boxes.

Move, rotate, scale or keyframe the object: the cut follows live, without reloading tiles.

## Mode

| Mode | Removes |
|---|---|
| Cut inside any | what is inside at least one object |
| Cut inside all | what is inside every object |
| Keep inside any | what is outside every object |
| Keep inside all | what is outside at least one object |

Switching mode is close to instant.

## Solid view and exports

On mesh tiles the cut is made in the material, which Solid view, snapping and exports do not see.
**Slower: Also cut in solid view/exports** (on by default) also deletes the faces that are entirely
cut. Faces across the boundary stay whole outside Material Preview and Rendered. Untick it if
dragging a box gets slow on a large scene. Point clouds and splats always lose the cut points for
real.

## Viewport region (Alt+B)

Blender's clipping region (Alt+B) only cuts in Solid and Wireframe shading; EEVEE ignores it.
**Clip to viewport region**, in the main panel, makes Material Preview and Rendered honour it too, for
every tileset. Drag a region with Alt+B to clip, press Alt+B again to clear. It is on by default.

The region comes from the largest 3D viewport, and F12 renders use the region that viewport last had.

## Details

- Tiles entirely cut are not downloaded.
- Clipping objects without a parent are parented to the tileset's root Empty, so they follow it.
- An outline is every closed loop of boundary edges, or every edge of a mesh without faces or of a
  curve. Outlines of more than 64 points are masks made by cesium-native, and moving those does
  reload tiles.
- The viewport-region clip is a Mix Shader to a Transparent BSDF in each tile material, driven by the
  shared `OGC3D Clip` group, into which the add-on copies the viewport's clip planes.
- [The clipping notes](/dev/notes/clipping) explain how it all works, what comes from cesium-native,
  and give measurements.
