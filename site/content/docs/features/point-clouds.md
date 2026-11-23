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

If points look too sparse or too fat, change *Point scale* first. *Min px* and *Max px* are 4 and 12 by
default.

## Lighting

Points are shaded by the scene's lights, like mesh tiles: their colour is the surface colour of a
matte material, and the sun, the lamps and the world act on the cloud, which casts and receives
shadows. A point has no surface of its own, so each one is shaded as the small sphere, tetrahedron
or disc it is drawn as. *Disc splats* gives the smoothest result on tiles that carry normals, since
the discs then follow the scanned surface. Files saved with an older version, where points showed
their colours without any light, are shaded the same way when opened.

To see the colours as they are, without any light, pick the **Shadeless** preset in the *Nodes: Material*
panel. It applies to every tile, meshes included.

## X-ray

![Gaussian splats of Kirants monastery: the splats, and the same view with X-ray on, in the splats' own colours and tinted](/img/xray_splats.jpg)

**X-ray**, a look of the *Nodes: Material* panel, shows point clouds and Gaussian splats as a radiograph: every point adds a little light
and hides nothing. Where many points line up along the view (a wall seen edge-on, a vault, the far
side of a building) the light adds up, so the structure reads through itself.

| Setting | What it does |
|---|---|
| **Strength** | Light added by each point. Lower it where a dense cloud burns to white. |
| **Splat radius** | Size of the points Gaussian splats become while X-ray is on, in metres. Point clouds keep the size their display gives them. |
| **Tint amount** and its colour | At 0 the points keep their own colours; at 1 they all take the tint. |

- It needs a dark background: set the World colour to black, or render with a transparent film over
  a dark page. On a light background the added light does not show.
- It works in EEVEE and in Cycles; EEVEE is much faster here.
- It reads best on buildings and interiors. On a wide terrain it shows the tiles: a point cloud
  tile adds its points to its parent's, so where finer tiles are loaded there are more points per
  pixel and the X-ray is brighter, in rectangles. Lower *Strength*, or a lower *Max SSE* so that the
  whole view reaches the same level.
- Mesh tiles are X-rayed too unless **Meshes** is unticked: see [X-ray on meshes](#x-ray-on-meshes).

How it works: X-ray is a material effect. A shared shader group, `OGC3D X-ray`, sits in front of
the Material Output of every point material and mixes the usual shader with a Transparent shader
added to an Emission shader; the material is drawn blended while it is on. Points keep the shape
their display gives them: points, tetrahedra or discs. Gaussian splats are the one exception:
Blender draws them with its own splat renderer, which ignores materials, so while X-ray is on their
Splats modifier is swapped for the `OGC3D X-ray Points` geometry group, which makes plain points of
them with the same shader. Both groups can be edited. Ordinary transparency does not give this
look: semi-transparent points fade everything to an even fog, because each one also hides what is
behind it.

The **X-ray** and **X-ray Mono** [presets](/features/nodes-material#presets) at the top of the panel
turn it on in one click, in the tiles' own colours or in the tint.

### X-ray on meshes

The X-ray looks give mesh tiles the same treatment (the **Meshes** checkbox under the X-ray settings,
ticked by default, leaves them out): every face adds its texture colour as light and hides nothing, front and back faces alike.
A building then shows its rooms, vaults and far walls through its roof, and a site with meshes and
point clouds reads as one radiograph.

| Setting | What it does |
|---|---|
| **Mesh strength** | Light added by a face seen edge-on. Lower it where many walls line up and burn to white. |
| **Mesh edges** | 0: every face adds the same light, like a double exposure of the textures. Higher: faces seen edge-on (walls, outlines) stand out and faces turned to you fade, down to a line drawing around 3. |

- It is the same `OGC3D X-ray` group, on each mesh material with its *Mesh* input at 1, and it works
  with or without the shared shader nodes. Clipping still cuts it.
- While it is on, mesh materials are drawn blended and no face is culled, whatever *Faces* says;
  both come back with any other look.
- Tint amount and its colour apply to meshes too.
- It is a different thing from the [X-ray slider of the shared shader nodes](/features/nodes-material#x-ray),
  which fades the faces turned toward you and needs no dark background.

## Colours

![IGN LiDAR HD around the Eiffel Tower coloured by LAS class, with eye-dome lighting](/img/beauty_edl_ign.jpg)

Points keep their own colour. To colour them by class or by intensity, see
[Nodes: Metadata](/features/nodes-metadata); to drape a map on them, see
[Raster overlays](/features/raster-overlays). The `OGC3D Points` node group is shown in
[Nodes: Geometry](/features/nodes-geometry).

## A cloud that stays sparse from afar

From far away a point cloud shows only the tiles near the top of its tree, which hold a thinned-out
copy of the cloud. How thin is the tiler's choice. A tiler that starts very coarse gives an overview
that looks like a scatter of dots, and a viewer then has to go many levels down, through many small
tiles, before the cloud looks solid.

One case found: a cloud of more than 150 million points made with gocesiumtiler. Its root tile keeps
one point per 20 m cell (33 points), each level halves the cell, and its first five levels hold
fewer than a million points; the geometric errors match those spacings. Its 40,000 tiles of a few
thousand points each are each in a separate `tileset.json`, which adds one download per tile and one
more wait at each level. What helps here: a larger *Max px*, so that coarse points grow to cover
their cell, and in the tiler a finer root cell, more points per tile and fewer `tileset.json` files.

Another scan of the same site, in Potree 1.7 (1.1 billion points), streamed through a Potree to 3D Tiles
middleware with implicit tiling, starts at a 1.3 m spacing: from close by, 2.4 million points in 218
tiles load within 15 s at a 2 px error, where the tileset above was still loading after 3 minutes.
Such a converter sets each tile's geometric error to its point spacing, so a lower *Max screen space
error* (2 to 4) than for meshes gives the detail a Potree viewer shows.

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
