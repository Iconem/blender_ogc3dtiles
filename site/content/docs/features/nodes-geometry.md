---
title: "Nodes: Geometry"
description: "One Geometry Nodes graph on every tile, and the point display"
---

**Shared geometry nodes** (Nodes: Geometry section) puts one Geometry Nodes
modifier, 'OGC3D Tile Geometry', first in the modifier stack of every tile
mesh, loaded or streamed later, so a single graph edits the vertices, edges
or attributes of all tiles (the point display modifier runs after it).  The
group starts as a pass-through; the node-tree button opens it pinned in a
node editor.  Untick to remove the modifier from every tile; the group stays
in the file for the next time.

## Point display

Point tiles are drawn by a geometry nodes group of their own, `OGC3D Points`, which runs after the
shared one. [Point clouds](/features/point-clouds) describes its settings.

![OGC3D Points](/img/nodes_points.jpg)

## Relation lines

*Hide relation lines* turns off the dashed object-to-parent lines in every 3D viewport. Each tile is
parented to its tileset's root, so those lines would otherwise fill the view.
