---
title: "Beta features"
description: "The phases timeline and other experiments"
---

## Globe navigation

A section of the sidebar's *Scene Origin* panel, *Globe Navigation (beta)*, that is never folded, for moving around a whole planet without the view
running out of precision or of clipping range. Press **Globe Navigation**; a thin blue frame around the 3D
view shows it is on, and the same button stops it.

![Globe navigation over Tokyo on Google Photorealistic 3D Tiles: the thin blue frame around the 3D view and the label at the bottom show it is on](/img/globe_nav_frame.jpg)

| Gesture | What it does |
|---|---|
| Wheel | Zooms about the point under the cursor. |
| Middle drag | Orbits around the point under the cursor. |
| Shift + middle drag | Grabs the globe and turns it. |

Everything else stays Blender's own navigation.

- An Empty, *OGC3D Globe*, carries every tileset. **Parent Selection to Globe** makes your own objects
  move with the planet.
- Far from the ground the wheel scales that Empty instead of moving the view. The panel shows the
  scale both as a multiplier (×0.01) and as 1:N (1:100), the same value typed either way. Typing one
  resizes the Empty about the point the view looks at, under a view that stays where it is, so the world
  grows or shrinks on screen. **To 1:1, keeping the view** brings it back and moves the view to match, with
  nothing moving on screen. Do this before a render or an export, where metres must be metres.
- When the gestures stop, the scene origin moves under the view and the tiles are placed again in
  double precision. **Re-anchor Scene Origin** does it at once; it is greyed while Globe Navigation
  is off.
- Re-anchoring changes nothing on screen, so after a long way on the globe the ground under the view
  is no longer level in Blender: its vertical leans away from +Z by the angle travelled (0.09° per
  10 km). The panel shows that angle, and **Reset** next to it puts the origin under the view with
  +Z up and +Y north, turning the view with it. Do this before adding lights, physics or anything
  else that needs a true vertical.
- A place search, or a new scene origin typed in the Scene Origin panel, puts the Globe back in place
  at 1:1 with the view on the new origin. **Reset Globe** does the same for the current origin, when
  the planet has gone out of sight.

## Preferences

Off by default, under *Preferences > Add-ons > OGC 3D Tiles > Beta features*:

![Phases timeline on Google Photorealistic 3D Tiles over the Colosseum, north at the bottom: the year slider on top, with Clip to phases underneath. The volumes and dates are invented. One class per cell, so the 1990 blob overwrites the wall where they overlap, and the wall has a hole in it at year 250](/img/phases_colosseum.jpg)

- **Phases timeline.** A sidebar tab of its own, *Phases*, for closed meshes in a `Phases` collection, each with
  the custom properties `code` (1 to 255) and `year`, optionally `color`. *Build class grid*
  voxelizes them around the scene origin into a one-tile voxel tileset, later years winning
  where they overlap, and adds it to the list. After a Start, every other tileset is colored
  by it, and the year slider shows the phases built by then. *Clip to phases* hides the
  surface outside them too. `scripts/phase_volumes.py` builds a demo on invented volumes. The
  grid is one tile, with no coarser levels. See [docs/voxels.md](/dev/notes/voxels) for classes
  per cell and how the tileset is made.
- **Phases from strokes.** Needs Phases timeline. Draw on the monument with Annotate
  (stroke placement *Surface*) or a Grease Pencil object, then *Phase from strokes* in the
  Phases panel asks for a code, a year, a color and how to read the strokes.
  *Painted areas* (default): everything within the *Brush radius* of a stroke is in the
  phase, in depth too, so scribbling over an area fills it and it follows curved surfaces.
  The strokes are kept as a wire mesh with a `brush` property in the `Phases` collection.
  *Outlines*: each stroke is the outline of a flat area and becomes a prism, from *In front*
  metres toward the viewer to *Behind* metres away; an outline that wraps around a corner
  needs a stroke per face. *Build class grid* then treats both like any other volume.
  Checked with generated strokes, not yet with hand-drawn ones.
- **Material controls.** The sliders of the shared shader nodes, in the Nodes: Material panel. See
  [Nodes: Material Shader](/features/nodes-material).
