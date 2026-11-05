---
title: "Point clouds"
description: "Point display, sizes and colours"
---

Point clouds (`pnts`, glTF POINTS) become vertex-only meshes with
a `Col` colour attribute (COLOR_0 decoded straight from the buffer, ubyte /
ushort / float) and a shared Geometry Nodes modifier.  Four radius modes:
**Attenuated** (default): 0.6 × the tile's mean point spacing (5th–95th
percentile extent / point count, ignored below 64 points) × *Point scale*,
clamped to a *Min / Max pixels* range measured at the **view pivot
distance** (eye → orbit centre in the viewport, camera → point tiles when
rendering).  One distance for the whole scene means every tile of one LOD
level gets the same radius, and the two metre bounds are plain Value nodes
rewritten only when the distance moves by more than 15 %, so the point
tiles re-evaluate while zooming, never while orbiting (one size per tile, as
CesiumJS' point cloud attenuation; Potree's adaptive size goes per point and
isn't done here); **Per tile** is the same without the pixel clamp; **Uniform** is one
radius for every tile; **Screen pixels** is the exact per-point version,
radius = pixels × distance to the eye, clamped to a metre range (constant
on-screen size like 3DTilesRendererJS' point size with attenuation) — this
one reads the eye from the 'OGC3D View' Empty, so every point tile
re-evaluates whenever the eye moves.  The streaming tick (or, when nothing
streams, a 0.15 s timer) feeds the viewport, a `render_pre` handler the
scene camera.  Three display modes
(`Nodes: Geometry` sub-panel): **Point cloud** (Mesh → Points; cheapest; unlit
vertex colours in Material Preview / Rendered, material colour in Solid),
**Tiny tetrahedra** (4 vertices per point, realised as a mesh whose active
colour attribute is `Col`, so Solid mode with Color → Attribute shows the
colours as well) and **Disc splats** (an 8-gon disc instanced on every
point, not realised; oriented along the point's glTF normal when the tile
has one — kept as the `ogc3d_normal` attribute — otherwise facing the view
through a shared "View Dir" vector refreshed per tick / render; the point
material reads `Col` through both a Geometry and an Instancer Attribute
node, since instance attributes only reach EEVEE through the latter).
