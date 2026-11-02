# How clipping works

Each tileset entry lists Blender objects, used as **prisms** (outlines extruded
along ENU up) or **boxes** (the object's bounding box with its full transform).
This page explains how each kind of tile gets cut, and what comes from
cesium-native. The README's "Clipping" section covers how to use it.

## Modes

Each volume gives a term that reads 1 inside it. A point is cut when the
combined value is 1.

| Mode | Definition | Computed as | Cuts |
|---|---|---|---|
| Cut inside any | MAX of inside | `max(t)` | the union |
| Cut inside all | MIN of inside | `min(t)` | the overlap |
| Keep inside any | MIN of outside | `1 - max(t)` | outside every volume |
| Keep inside all | MAX of outside | `1 - min(t)` | outside at least one volume |

The keep modes are the cut modes inverted, so two values describe any mode:
which chain to read (`any`), and whether to invert the result (`invert`).

## Who does what

| | Mesh tiles | Point clouds, splats |
|---|---|---|
| Prism test | cesium-native mask, sampled in the shader | Geometry Nodes, vertical raycast on a flat helper mesh |
| Box test | Shader, in the box's object space | Geometry Nodes, in the box's object space |
| Removing what's cut | Transparent BSDF; faces too with Cut Geometry | Delete Geometry on points |
| Skipping whole tiles (prisms only) | cesium-native excluder | cesium-native excluder |

From cesium-native, through the Python binding:

- `RasterizedPolygonsOverlay` rasterises polygons into a mask that is draped
  on tiles like imagery.
- `RasterizedPolygonsTileExcluder` drops tiles entirely on one side of the
  polygons, so they are never downloaded.

Everything else is Blender nodes. cesium-native has no box volume and no way to
cut geometry by a polygon. It also doesn't combine overlays: each mask is a
separate raster, so the intersection logic has to run downstream of it, in the
shader or in Geometry Nodes. Cesium's game-engine plugins work the same way,
with the mask discarding pixels in a material.

## Mesh tiles: the material chain

Each tile has its own material, and each volume is one term node in it:

```
prism:  UV Map (_CESIUMOVERLAY_n) → Mapping → Image (mask) → Term
box:    Texture Coordinate (Object = box) → Mapping → Absolute → max(x, y, z) → Less Than 1 → Term

Terms → MAX chain ─┐
Terms → MIN chain ─┴ Mix (factor: attribute "any") → |x - attribute "invert"|
                     → Greater Than 0.5 → Mix Shader (surface, Transparent BSDF)
```

Nodes are named `OGC3D PolyClip …`. Three choices keep it fast:

- **The mode is two view-layer attributes.** `any` and `invert` are custom
  properties on the scene, `ogc_clip_<uid>_any` and `ogc_clip_<uid>_invert`,
  read by Attribute nodes of type View Layer. A mode switch writes two numbers
  and touches no material.
- **One mask per polygon, in every mode.** Masks always read "inside", so a mode
  switch needs no new raster. cesium-native reloads a tileset's tiles when an
  overlay is added, so swapping masks on a mode switch would be expensive. Above
  8 polygons the "any" modes share one union mask, to stay within GPU texture
  slots. The "all" modes can't use a union and stay per polygon.
- **A mask keeps its nodes when a finer raster replaces it.** Only the image
  changes, which needs no shader recompile.

A shader recompile only happens when a volume is added or removed, or when a
tile first gets a term.

Masks are keyed by overlay uid, not by texture coordinate set: cesium-native
gives every overlay with the same projection the same set. Imagery overlays are
keyed the same way, and mix in list order, so two Web Mercator layers coexist.

## Point clouds and splats

One Geometry Nodes group per tileset (`OGC3D Clip <uid>`, modifier `OGC3D Clip`,
first in the stack) deletes the cut points.

- **Boxes:** the point goes to world space, then through the inverse of the box
  transform, and is tested against the box's half sizes.
- **Prisms:** a hidden helper mesh (`OGC3D Clip Prisms <uid>`) holds the outlines
  as flat n-gons, with a face attribute `clip_poly` for the prism index. Each
  prism gets a straight-down ray from above the point.

Terms combine the same way as in materials. The cesium mask can't serve here:
these tiles carry no overlay texture coordinates.

## Cut Geometry (mesh tiles, optional)

The shader only hides pixels. Solid and Wireframe views, snapping and exports
still see the full mesh. **Cut Geometry** adds the same test to mesh tiles as a
second group (`OGC3D Clip Faces <uid>`), which deletes the faces whose points
are **all** cut. No tile is fetched again.

Faces crossing the boundary stay whole, so the edge in Solid view and in exports
follows the mesh's triangles. Material and Rendered views stay exact, because
the shader still trims those faces. An exact mesh edge would need a boolean per
tile, which is much slower and fails on the non-manifold meshes tiles usually
are.

Measured on Google 3D Tiles over the Vatican (about 1400 visible tiles, 3.2 M
faces, one prism and one box, while tiles were still streaming, so the numbers
are noisy):

| | Cut Geometry off | Cut Geometry on |
|---|---|---|
| Move a box, then redraw | 3–6 s | 7–10 s |

It's off by default for that reason. Turn it on when you need the cut in Solid
view or in an export.

## What updates when

| Change | Cost |
|---|---|
| Switch mode | Under 1.5 s on a globe of about 1300 tiles (it was 30–40 s of shader compiling). Excluders change, so newly needed tiles load. |
| Move, rotate or scale a box | Live, nodes follow the object. Seconds per update on a very large scene. |
| Move or edit a prism | Re-cut 0.35 s after the last change. The masks are replaced, so cesium-native reloads the tiles. |
| Add the first prism, or change the prism count | Same reload as above. |

## Known limits

- The prism edge follows the mask resolution, so it can be a metre or two off on
  coarse tiles.
- Prisms are computed in longitude / latitude, so an edge isn't perfectly
  straight in ENU over long distances.
- Boxes never exclude tiles: a tile inside a box is still downloaded, then hidden.
