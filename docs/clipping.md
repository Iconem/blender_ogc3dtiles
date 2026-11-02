# How clipping works

Each tileset entry lists Blender objects, used as **clip-polygons** (2D outlines in the
tileset frame, extruded along its Z) or **boxes** (the object's bounding box with
its full transform).
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
| Clip-polygon test | Shader, edge by edge | Geometry Nodes, vertical raycast on a flat helper mesh |
| Clip-polygon over 64 points | cesium-native mask, sampled in the shader | Same raycast |
| Box test | Shader, in the box's object space | Geometry Nodes, in the box's object space |
| Removing what's cut | Transparent BSDF; faces too with Cut Geometry | Delete Geometry on points |
| Skipping whole tiles, clip-polygons | cesium-native excluder | cesium-native excluder |
| Skipping whole tiles, boxes | Python `ITileExcluder` | Python `ITileExcluder` |

From cesium-native, through the Python binding:

- `RasterizedPolygonsTileExcluder` drops tiles entirely on one side of the
  polygons, so they are never downloaded.
- `ITileExcluder`, subclassed in `native_backend._volume_excluder`, does the same
  for boxes.
- `RasterizedPolygonsOverlay` rasterises polygons into a mask draped on tiles
  like imagery. It's now only the fallback for very dense outlines.

Everything else is Blender nodes.

### What clip-polygons are

A clip-polygon is a 2D polygon in the tileset frame, which is ENU at the scene origin
unless the tileset's root Empty was moved. It's extruded without height limits
along that frame's Z, on every kind of tile. An object's vertex heights are
ignored.

Two things still work in longitude / latitude, so their walls follow the ellipsoid
normal: the tile excluders and the fallback masks. The offset from a Z wall is
about height × distance from the origin / 6400 km, so 1.5 cm for 100 m of height
at 1 km. A tile could only be wrongly skipped within that margin.

### To make one

1. Add a mesh or a curve seen from above: a Circle or Plane mesh edited in Top
   view, a face-less polyline, or a closed Bezier curve. Each closed loop of
   boundary edges is one clip-polygon, so one object can hold several.
2. Select it, then press **+** in the tileset's **Clipping** list. Cube-like meshes
   come in as boxes; the list's dropdown switches between Clip-polygon and Box.

### Why not the mask

CesiumJS removed the signed distance texture from `ClippingPolygonCollection` in
1.145 (2026-09-02,
[#13654](https://github.com/CesiumGS/cesium/pull/13654)): clipping now uses "an
algorithm, based on the techniques used for vector tiles", which it says vastly
improves quality across distance scales. It also gained holes
([#13660](https://github.com/CesiumGS/cesium/pull/13660)).

cesium-native hasn't changed. As of v0.66.0 (2026-11-02), clipping polygons are
still `RasterizedPolygonsOverlay`, a raster draped on tiles. The CesiumJS change
is in its renderer, so it has nothing to port as it stands.

Masks had two costs here: the edge follows the raster resolution, and cesium-native
reloads a tileset's tiles when an overlay is added or replaced, so moving one
reloaded everything. The shader test has neither.

### Other native paths

cesium-native ships no box volume and no geometry cut.
`GltfModifier` is the hook made for one: since v0.53, so already in the v0.59 the
binding vendors, it edits a tile's glTF in a worker thread, and `trigger()`
re-applies it to loaded tiles without reloading them. A tileset has one, set on
`TilesetExternals` before the tileset is created.

- **From Python it fails today**, with "Tried to call pure virtual function
  GltfModifier.apply", so tiles don't load. The trampoline looks the override up
  through `GltfModifier`, a type pybind11 doesn't know; `PyGltfModifier` is the
  registered one. Changing that one cast fixes it:
  [cesium-native-python#7](https://github.com/calebbuffa/cesium-native-python/pull/7).
- **The real path is C++:** a clipping modifier in cesium-native, which the binding
  then exposes as a plain class, with no Python holding the GIL while it cuts. Draft
  request: `docs/cesium-native-clipping-request.md`.

Upstream:
[cesium-unreal#1644](https://github.com/CesiumGS/cesium-unreal/issues/1644) asks
for real geometry cuts and is open;
[cesium-unreal#1818](https://github.com/CesiumGS/cesium-unreal/issues/1818) tried
Manifold booleans, which need closed meshes;
[cesium-native#1307](https://github.com/CesiumGS/cesium-native/pull/1307) (open)
fixes `GltfModifier` with raster overlays. cesium-native has no issue for geometry
clipping yet; [#878](https://github.com/CesiumGS/cesium-native/issues/878) is about
Cesium ion clip jobs.

## Mesh tiles: one shared group

Each tile has its own material, because each has its own texture. What clips is
shared: every material holds a few nodes pointing at two groups of its tileset.

```
"OGC3D Clip Volumes <uid> v<n>":  Geometry Position (world)
    → clip-polygons: through the tileset frame's inverse, then the winding number
    → boxes: through the box's inverse, then max(|x|, |y|, |z|) < 1
    → Min and Max over the volumes

"OGC3D Clip Mode <uid>":  Min, Max → Mix (attribute "any") → |x - attribute "invert"| → Cut

material:  Volumes group ─(with any mask terms: MIN and MAX chains)→ Mode group
           → Mix Shader (surface, Transparent BSDF)
mask:      UV Map (_CESIUMOVERLAY_n) → Mapping → Image (mask) → Term
```

Everything that moves is an **attribute**, not a node value: custom properties on
the scene (`ogc_clip_<uid>_…`), read by Attribute nodes of type View Layer. That's
each edge's (x, y, dx/dy), the transforms, and the mode. Writing them recompiles
nothing. A value in a node, or an object in a Texture Coordinate node, makes Blender
regenerate the shader of every material using it.

- **So a shader only changes with the shape of the volumes:** an outline or box
  added or removed, or an outline outgrowing its slots. Outlines get 8, 16, 32 or
  64 slots, so adding a point rarely costs anything.
- **A new shape takes over tile by tile.** Regenerating a material costs about 0.4 ms
  per slot, so swapping every material at once blocked Blender for 10 s with 4 slots,
  18 s with 16, 40 s with 32 and 77 s with 64, over 2900 materials. Instead each shape
  is a new version of the group (`… v2`) with its own attributes, assigned to a few
  tiles per tick, visible ones first. Tiles not reached yet keep the old cut, exactly.
- **Over 64 points an outline becomes a mask**, as do outlines past 240 slots in a
  tileset: versions coexist during a takeover, and Blender reads 512 view-layer
  attributes in all.
- **One mask per polygon, in every mode.** Masks always read "inside", so a mode
  switch needs no new raster. Above 8 polygons the "any" modes share one union
  mask, to stay within GPU texture slots. The "all" modes can't use a union and
  stay per polygon.
- **A mask keeps its nodes when a finer raster replaces it.** Only the image
  changes, which needs no shader recompile.

The first volume still adds nodes to each material, 15–18 ms per tile on Google 3D
Tiles (39 ms before the groups). That's done a little per tick, visible tiles first,
so the interface doesn't freeze. Further volumes touch no material.

### Convex-only outlines

Not worth it. A convex test needs about the same nodes per edge, and only saves the
final winding sum, while taking away what people want to draw.

Masks are keyed by overlay uid, not by texture coordinate set: cesium-native
gives every overlay with the same projection the same set. Imagery overlays are
keyed the same way, and mix in list order, so two Web Mercator layers coexist.

## Point clouds and splats

One Geometry Nodes group per tileset (`OGC3D Clip <uid>`, modifier `OGC3D Clip`,
first in the stack) deletes the cut points.

- **Boxes:** the point goes to world space, then through the inverse of the box
  transform, and is tested against the box's half sizes.
- **Clip-polygons:** a hidden helper mesh (`OGC3D Clip Polygons <uid>`) holds the outlines
  as flat n-gons, with a face attribute `clip_poly` for the outline's index. Each
  outline gets a straight-down ray from above the point.

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
faces, one clip-polygon and one box, while tiles were still streaming, so the numbers
are noisy):

| | Cut Geometry off | Cut Geometry on |
|---|---|---|
| Move a box, then redraw | 3–6 s | 7–10 s |

It's off by default for that reason. Turn it on when you need the cut in Solid
view or in an export.

## What updates when

| Change | Cost |
|---|---|
| Switch mode | Writes two attributes. |
| Move, rotate or scale a clip-polygon or a box | Live, through the attributes. 0.35 s after the last change, the excluders, masks and point / splat groups follow, and newly needed tiles load. |
| Edit a clip-polygon's points | The same, unless it outgrows its slots. |
| Add or remove a volume | Tiles take the new version a few per tick (above). |
| Move or edit a clip-polygon over 64 points | The mask is replaced, so cesium-native reloads the tiles. |
| Move the tileset's root Empty | Clipping objects without a parent are parented to it when added, so they follow. No shader changes: 0.05 s for the matrices of 3200 tiles, then a 0.1 s draw. |
| Keyframe a volume | Followed in the viewport and in renders, on mesh tiles through a frame change handler. No tile is skipped while a volume is keyframed, since it may uncover any of them, and a render doesn't stream. |

Measured in Material view on Google 3D Tiles over Rome (3000–3500 materials, 2500–3200
tiles, still streaming), with a 16-point clip-polygon:

| | Nodes in each material | Shared group, swapped at once | Shared group, tile by tile |
|---|---|---|---|
| Add it, then a box | 39 ms per tile, then a 16 s block | 18 ms per tile, then a 25–30 s block | longest freeze 1.7 s, then 3.7 s; about 2 minutes at around 1 frame per second until all tiles have it |
| Move it | 12–15 s draw | 0.27 s draw | same |
| Move a box | 32 s draw with the box in a shared node | 0.13 s draw | same |

Reloading the tiles instead wouldn't be quicker: reaching those 2700 tiles from a
new start took 172 s, and each new material regenerates its shader anyway.

The box excluder averaged 9.7 µs per tile visited on Google 3D Tiles: 14640 calls,
142 ms in total over about 20 s.

## Georeferenced and local tilesets

Both clip in the shader the same way, because it only sees the scene: a georeferenced
tileset sits in ENU at the scene's one origin, a local one in its own coordinates.
What differs is skipping whole tiles, which needs a place on the globe: a local
tileset with a clip-polygon skips none, so tiles under the cut still download.

Checked in Material view, the Cycles viewport and Cycles renders on the interior 473M:
a clip-polygon, a box, 64 and 65 points, a root moved and rotated, Cut Geometry, and a
keyframed box in Cycles and EEVEE animation renders. Checked in Material view on a
local mesh tileset.

## Known limits

- Only masks (outlines over 64 points) follow a raster resolution, so they can be
  a metre or two off on coarse tiles.
- Adding a volume to a tileset of thousands of tiles takes minutes to reach all of
  them, at a low frame rate.
- On points and splats, a keyframed clip-polygon doesn't follow in renders: its
  helper mesh is baked. A keyframed box does.
- The box excluder is conservative: "entirely outside" only tries the box's own
  axes, so a tile near a corner of a rotated box can load, then be hidden.
- On a tileset that isn't georeferenced, a clip-polygon means no tile is skipped,
  and outlines over 64 points don't clip mesh tiles.
