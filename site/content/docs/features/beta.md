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
| Numpad . | View Selected: frames the selection, and brings the world back to the scale that fits it (real size for a site). A selected dataset Empty is framed with its tiles. |

Everything else stays Blender's own navigation.

- An Empty, *OGC3D Globe*, carries every tileset. **Parent Selection to Globe** makes your own objects
  move with the planet.
- Far from the ground the wheel scales that Empty instead of moving the view. The panel shows the
  scale both as a multiplier (×0.01) and as 1:N (1:100), the same value typed either way. Typing one
  resizes the Empty about the point the view looks at, under a view that stays where it is, so the world
  grows or shrinks on screen. **The scale goes from ×1000 (1:0.001, a millimetre shown as a metre) down to
  ×0.00000001 (1:100,000,000, the Earth 13 cm wide).** The wheel only uses 1:1 and smaller: nearer than 1:1
  it moves the view, and it stops scaling at 1:100,000,000, where it moves the view again. **To 1:1, keeping the view** brings it back and moves the view to match, with
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

## Terrain blending

Off by default: tick *Terrain blending* under *Preferences > Add-ons > OGC 3D Tiles > Beta features*.

A detailed dataset (a photogrammetry mesh, a point cloud) shown over a terrain or a globe fights with it:
the terrain pokes through the dataset wherever it is the higher of the two, and the dataset ends on a hard
edge. Terrain blending makes the terrain transparent under the dataset and lets the dataset's border
fade into the terrain.

![The Giza photogrammetry mesh over Cesium World Terrain. Blending off: the terrain covers part of the mesh. Then the three settings, each with one color per tileset beside it](/img/terrain_blend_giza.jpg)

1. Add the dataset and the background to the list: a *WGS84 globe*, a *Quantized-mesh terrain*, Cesium
   World Terrain, Google Photorealistic 3D Tiles or Bing.
2. Select the background. Under *Color correction*, tick **Terrain blending (beta)**. The box only
   shows on an entry of type *WGS84 globe* or *Quantized-mesh terrain*, and on any tileset whose root
   volume is more than 1000 km in radius once it streams (Google, Bing, Cesium World Terrain). A Cesium
   ion entry shows it before the first Start too, since it may be a terrain. A tileset of tilesets is never
   a background, however far apart its datasets are.
3. Start. Every other tileset that is shown blends into it. A tileset whose eye is closed does not.

![The settings on a cut across a dataset's border. Seen from above: the dataset fades in over Dataset fade, the terrain is whole over Terrain inset and fades out over Terrain fade. Then the two opacities against the distance inside the border, and a cut seen from the side with Keep terrain below](/img/terrain_blend_settings.png)

| Setting | What it does |
|---|---|
| **Distances from the dataset's size** | On by default. The dataset fades over 5% of the width of the smallest dataset shown, the terrain inset and the terrain fade are half of that each, and the three fields are greyed. Untick it to type them. |
| **Dataset fade** | Metres over which a dataset fades in from its border. 0 keeps its hard edge. |
| **Terrain inset** | Metres inside a dataset's border where the terrain is still whole, so that there is terrain behind the faded border. |
| **Terrain fade** | Metres over which the terrain fades out past the inset. 0 is a sharp cut. |
| **Keep terrain below** | On by default. The terrain stays wherever it lies under the dataset, and only the terrain that would poke through it goes. It is the ground seen between the points of a sparse cloud, and under a dataset that floats. The number beside it is the margin: how far under the dataset's lowest point the terrain has to be. Raise it if terrain still shows through the dataset's ground. |
| **Height offset** | The background's own *Location Z*: raises or lowers it. Rarely needed. |
| **Match Dataset Heights to Terrain** | A button. Moves every dataset up or down onto this terrain, once: the dataset's lowest heights are compared with the terrain's where they overlap, and its Empty moves by the median difference. Run it before judging the fades. The same button is on every dataset entry as *Match Height to Terrain*, with or without blending: see [Match Height to Terrain](/features/height-references#match-height-to-terrain). |

The distances are one setting for the scene, and they are live.

![A point cloud of the Geghard monastery over Cesium World Terrain. With Keep terrain below off, third row, the ground between the points is cut away](/img/terrain_blend_geghard.jpg)

- **What stays of each.** *Color tiles by > Tileset* (Nodes: Metadata) gives every tileset one color: it
  shows at once where the dataset ends and the terrain starts.
- **Why not lower the terrain, or cut it with a clipping polygon?** Both were tried. A terrain is not a
  constant height away from a dataset: over the Giza plateau, Cesium World Terrain is between 38 m under
  and 39 m over the photogrammetry. A polygon cut is sharp, and where the two heights differ at the border
  it shows as a gap. It also needs a polygon drawn by hand. Clipping is still the tool to remove
  one block of a city, and it stops the cut tiles from being downloaded, which blending does not.
- **How it works.** The tiles shown of the datasets are drawn from above into a small image, at most
  512 pixels wide: how many metres each ground cell is inside the covered area, and the lowest height of
  the datasets there. Tile materials read
  that image through the shared `OGC3D Blend` node group and mix with a Transparent BSDF. The image is
  saved in the .blend, so a saved scene, a frozen one and a render keep the fades after Stop.
- **Keep terrain below costs nothing more.** It is two more numbers in the same image lookup: the
  material compares the height of the pixel it shades with the dataset's lowest height in that ground
  cell. No polygon is dropped and no geometry is touched.
- **Cost.** A tile is drawn into the image once, when it arrives, in a few milliseconds. The image is
  rebuilt when the tiles shown change, in 30 to 120 ms, and at most every 3 seconds while you navigate
  (at once for a render, so a frame never has an old image). The slower part is Blender's. A tile's
  material is compiled once when the tile loads, with or without blending. Ticking the box changes the
  materials of the tiles already loaded, and those compile again: with a thousand terrain tiles in view
  the first EEVEE frame after ticking took 29 s instead of 3 s, and the next ones 5 s. Moving a slider,
  or tiles coming and going afterwards, compiles nothing more than usual.
- EEVEE and Cycles. The fade is dithered: a still render smooths it, a moving viewport shows grain.

Limits, for now:

- One image for the whole scene. Datasets hundreds of kilometres apart share its 512 pixels, so their
  borders get coarse. It is meant for one site and its surroundings.
- The lowest height comes from every point of the dataset, stray ones under the ground included. Where
  a cloud has such points the terrain is cut although it would sit under the real ground.
- Gaussian splats cut the terrain but do not fade themselves.
- A dataset cannot yet blend into another dataset (a square inside a city model inside Google).
- Datasets moved by hand through their own Empty in a tileset of tilesets need a Stop and Start to redraw
  the image. *Match Height to Terrain* redraws it itself.

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
