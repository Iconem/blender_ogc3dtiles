---
title: "Gaussian splats"
description: "3D Tiles of splats in Blender 5.3"
---

![Gaussian splat tiles: Elevator sample streamed in Blender 5.3 (Solid and Rendered viewport), Cycles render, and a local 3dtiled tileset](/img/splat_tiles.jpg)

Tiles whose glTF carries `KHR_gaussian_splatting` (SPZ-compressed through
`KHR_gaussian_splatting_compression_spz_2`, as
[3dtiled](https://github.com/Iconem/3dtiled-to-3dtiles), the Cesium tilers
and the 3DGS-PLY-3DTiles converter write them) stream through the
cesium-native backend like any other content: cesium-native decodes the
SPZ payload and the direct-mesh path carries position, colour and opacity,
rotation, scale and the spherical-harmonic coefficients into the tile.  On
Blender 5.3 or newer, which adds native 3D Gaussian Splats
([release notes](https://developer.blender.org/docs/release_notes/5.3/rendering/)),
the tile gets the shared 'OGC3D Splats' Geometry Nodes
group (Mesh to Points, Set Point Cloud Type: 3D Gaussian Splat) and is a
native Gaussian splat point cloud, rendered by Workbench, EEVEE and Cycles
with Blender's splat pipeline.  The attribute conventions follow Blender's
SPZ importer: `radiance:base` holds the spherical-harmonic DC term plus
opacity, `scale` is in metres, `rotation` a (w, x, y, z) quaternion,
`radiance:sh_n` the higher-degree coefficients; the glTF Y-up to Z-up change
conjugates the rotation and permutes the scale axes.  Below Blender 5.3 the
same tiles show as coloured points with the usual point display modes.
LOD, scene origin, clipping, the render pipeline and the converged
animation render apply unchanged.  Blender sorts splats per object, so
where a parent and its children overlap during a REPLACE transition the
blend order between tile objects is undefined for a moment.

A tileset that is not georeferenced (its root sits at the ECEF origin, as
3dtiled and other local converters write it) is detected at start and gets an
identity frame: the tileset's own Z-up axes and metres become the Blender
scene, centred vertically.  The Scene Origin panel then reads "Local tileset".
When the origin is already fixed (Custom, Keep, a place, or an earlier
georeferenced tileset), such a tileset still lands at the Blender origin in
its own axes: the stream keeps its own frame for its tiles and camera, and
its root Empty can be moved to place it.

Converter output often keeps its content under many levels of tiles without
content, each with a smaller geometric error than its parent. cesium-native
renders such a tile as a hole once it meets the screen-space error (a
documented choice: "nothing to render at this level of detail"), so nothing
showed from most viewpoints. The asset accessor gives those tiles their
parent's error on the way in (`tileset/asset_fixes.py`), which cesium-native
takes as "refine unconditionally".

Tested with 3dtiled output and with the public sample of the
[3D-Tiles-RendererJS 3DGS plugin](https://github.com/WilliamLiu-1997/3D-Tiles-RendererJS-3DGS-Plugin)
(`data/Elevator-3dtiles/tileset.json` on raw.githubusercontent.com, degree-3
spherical harmonics).
