---
title: "Nodes: Geometry"
description: "One Geometry Nodes graph on every tile, and the point display"
---

## Shared geometry nodes

Tick **Shared geometry nodes** to put one Geometry Nodes modifier on every tile, those loaded and
those that stream in later. A single graph then edits the vertices, edges or attributes of all tiles:
displace them, scatter objects on them, turn a mesh into points.

- The group, `OGC3D Tile Geometry`, starts empty: it passes the geometry through unchanged.
- The node button opens it in a node editor.
- Untick to take the modifier off every tile. The group stays in the file for the next time.

It is first in each tile's modifier stack, so the point display below runs after it.

A modifier is evaluated per tile, and tiles come and go as you move. Light graphs are fine; heavy
ones (subdivision, remeshing, booleans) on hundreds of tiles will slow streaming down.

## Point display

Point tiles are drawn by a geometry nodes group of their own, `OGC3D Points`, which runs after the
shared one. [Point clouds](/features/point-clouds) describes its settings.

![OGC3D Points](/img/nodes_points.jpg)

## Relation lines

*Hide relation lines* turns off the dashed object-to-parent lines in every 3D viewport. Each tile is
parented to its tileset's root, so those lines would otherwise fill the view.
