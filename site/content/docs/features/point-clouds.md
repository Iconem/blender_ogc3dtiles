---
title: "Point clouds"
description: "How points are drawn and how large they are"
---

Point cloud tiles (`pnts`, or glTF tiles made of points) stream like meshes. Their settings are in
the **Nodes: Geometry** panel: how each point is drawn, and how large.

## Display

| Mode | What you get |
|---|---|
| **Point cloud** | Blender points. The cheapest. Colours show in Material Preview and Rendered; Solid shows the material colour. |
| **Tiny tetrahedra** | Four vertices per point, as a real mesh. Colours also show in Solid, with *Color > Attribute* in the viewport shading popover. |
| **Disc splats** | A small disc on every point, turned along the point's normal when the tile has normals, otherwise toward the view. |

## Radius

| Mode | Point size |
|---|---|
| **Attenuated** (default) | From the spacing of the points in each tile, times *Point scale*, kept between *Min px* and *Max px* on screen. Coarse tiles get large points, fine tiles small ones, so the cloud looks filled at every zoom. |
| **Per tile** | The same, without the pixel limits. |
| **Uniform** | One radius, in metres, for every tile. |
| **Screen pixels** | Every point the same size on screen, wherever it is. The most exact and the heaviest: all point tiles are re-evaluated whenever the view moves. |

If points look too sparse or too fat, change *Point scale* first.

## Colours

Points keep their own colour. To colour them by class or by intensity, see
[Nodes: Metadata](/features/nodes-metadata); to drape a map on them, see
[Raster overlays](/features/raster-overlays). The `OGC3D Points` node group is shown in
[Nodes: Geometry](/features/nodes-geometry).

## How it works

- A point tile is a mesh with vertices only, a `Col` colour attribute, and the shared `OGC3D Points`
  Geometry Nodes modifier.
- *Attenuated* uses 0.6 × the tile's mean point spacing, measured at the distance from the eye to the
  view's orbit centre (from the camera to the tiles when rendering). One distance for the whole scene
  gives every tile of a level the same radius, as CesiumJS' point cloud attenuation does. The sizes
  are recomputed only when that distance changes by more than 15 %, so tiles are re-evaluated while
  zooming, not while orbiting.
- *Screen pixels* reads the eye position from the `OGC3D View` Empty, per point.
- *Disc splats* keeps the glTF normal as the `ogc3d_normal` attribute.
