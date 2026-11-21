---
title: "Point clouds"
description: "How points are drawn and how large they are"
---

Point cloud tiles (`pnts`, or glTF tiles made of points) stream like meshes. Their settings are in
the **Nodes: Geometry** panel: how each point is drawn, and how large.

![Sacré-Cœur, Paris, as a point cloud in EEVEE](/img/points_sacre_colour.jpg)

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

If points look too sparse or too fat, change *Point scale* first. *Min px* and *Max px* are 2 and 6 by
default.

## Lit points

Points show their colours as they are, without any light: a scan already carries the light it was
captured in, and the cloud needs no lamp. That is why they look the same in Material Preview and in
a render, in EEVEE and in Cycles, whatever the lighting.

**Lit points** shades them with the scene's lights instead. A point has no surface of its own, so
each one is shaded as the small sphere, tetrahedron or disc it is drawn as: the sun and the lamps
act on the cloud and it casts shadows, with a grainier look. *Disc splats* gives the best result on
tiles that carry normals, since the discs then follow the scanned surface.

## X-ray

![A Gaussian splat scene of a church in a forest: the splats, and the same view with X-ray on, in the splats' own colours and tinted](/img/xray_splats.jpg)

**X-ray** shows point clouds and Gaussian splats as a radiograph: every point adds a little light
and hides nothing. Where many points line up along the view (a wall seen edge-on, a vault, the far
side of a building) the light adds up, so the structure reads through itself.

| Setting | What it does |
|---|---|
| **Strength** | Light added by each point. Lower it where a dense cloud burns to white. |
| **Point radius** | Size of the X-ray points, in metres. |
| **Tint amount** and its colour | At 0 the points keep their own colours; at 1 they all take the tint. |

- It needs a dark background: set the World colour to black, or render with a transparent film over
  a dark page. On a light background the added light does not show.
- It works in EEVEE and in Cycles; EEVEE is much faster here.
- It is a different thing from the [X-ray slider of meshes](/features/nodes-material#x-ray), which
  fades the faces turned toward you.

How it works: the tile's Points or Splats modifier is given the `OGC3D X-ray` node group, which
turns the vertices into points and gives them the `OGC3D X-ray` material: a Transparent shader
added to an Emission shader, blended. Both can be edited. Ordinary transparency does not give this
look: semi-transparent points fade everything to an even fog, because each one also hides what is
behind it.

## Colours

![IGN LiDAR HD around the Eiffel Tower coloured by LAS class, with eye-dome lighting](/img/beauty_edl_ign.jpg)

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
