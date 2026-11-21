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

## Lighting

Points are shaded by the scene's lights, like mesh tiles: their colour is the surface colour of a
matte material, and the sun, the lamps and the world act on the cloud, which casts and receives
shadows. A point has no surface of its own, so each one is shaded as the small sphere, tetrahedron
or disc it is drawn as. *Disc splats* gives the smoothest result on tiles that carry normals, since
the discs then follow the scanned surface. Files saved with an older version, where points showed
their colours without any light, are shaded the same way when opened.

## X-ray

![Gaussian splats of Kirants monastery: the splats, and the same view with X-ray on, in the splats' own colours and tinted](/img/xray_splats.jpg)

**X-ray points and splats**, in the *Nodes: Material* panel, shows point clouds and Gaussian splats as a radiograph: every point adds a little light
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

## A cloud that stays sparse from afar

From far away a point cloud shows only the tiles near the top of its tree, so those tiles must hold
a thinned-out copy of the whole cloud: that is what the levels of detail of a point cloud are. Some
tilers leave them nearly empty and put every point in the deepest tiles. The cloud then looks like a
sparse scatter of dots until the camera is close enough to load those, and getting there means
loading tens of thousands of small tiles. No viewer can fix this; the tileset has to be made again.

To check a tileset, count the points in its first levels: with Potree-style tilers, the root tile
alone usually holds thousands to tens of thousands of points. One case found: a
cloud of more than 150 million points held 33 points in its root tile and fewer than a million in
its first five levels. Its 40,000 tiles of a few thousand points each were also each in a separate
`tileset.json`, which adds one download per tile and one more wait at each level.

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
