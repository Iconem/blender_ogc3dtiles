---
title: "Nodes: Material Shader"
description: "The shared shader group, a tile's own material, back faces"
---

Every tile keeps its own material, with its own texture: there is no single material for all tiles.
What they share are node groups placed inside each material, in this order:

tile texture (or vertex colour) → `OGC3D Metadata` (*Color tiles by*) → `OGC3D Relight`
(*Shared shader nodes*) → Material Output

Editing a shared group changes every tile at once. *Open a tile's material*, at the bottom of the
panel, shows the material of the active tile, or of the first one found. Here a point tile with a
raster overlay, clipping, metadata colours and the shared shader nodes:

![A tile's own material](/img/nodes_tile_material.jpg)

Raster overlays have no group of their own: their nodes are in each tile's material.

## Shared shader nodes

Tick **Shared shader nodes** to put the `OGC3D Relight` group on every tile. Photogrammetry carries
its own lighting in its textures; the group lets you mix that baked light with Blender's lamps, lift
shadows, change saturation, or replace the photo with a clay colour.

![OGC3D Relight](/img/nodes_relight.jpg)

The node button opens the group to edit it by hand. Its Value nodes are also available as sliders:

**Material controls.** The Relight sliders, gold transfer and X-ray (faces turned to the
  viewer fade out) included, in the Materials panel. Albedo strength and saturation run
  from -1 to 2. Off, the buttons remain and the shared `OGC3D Relight` node group is where to edit
  these values.

In Rendered shading without lamps the tiles are not black: *Baked Light* (0.5 by default) makes half
of the material emit its own colour, and the add-on brightens Blender's default dark world once when
the scene has no sun.

## Faces

**Faces** sets back-face handling for every tile
material (EEVEE and Cycles): *Force double-sided* (default: clipped or open
meshes show their inside), *Force single-sided*, or *Material setting*,
which restores what the tile declared (glTF `doubleSided`; most
photogrammetry exports are single-sided, which is why tiles used to vanish
from behind).

## Viewport-region clip

`OGC3D Clip` is the group behind *Clip to viewport region (Alt+B)*, described in
[Clipping](/features/clipping):

![OGC3D Clip](/img/nodes_clip.jpg)
