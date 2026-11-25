---
title: "Heights and colors between tilesets"
description: "Why a dataset floats over a terrain or sinks into it, Match Height to Terrain, color correction and Match Colors"
---

Two tilesets of the same place rarely agree out of the box: one sits tens of metres over the other, and
their colors differ. This page says where the height difference comes from, and gives the two one-click
fixes: **Match Height to Terrain** and **Match Colors**.

![The Giza photogrammetry mesh over Google Photorealistic 3D Tiles, six steps. As loaded it lies 23 m under Google's ground and only the pyramid tips show. After Match Height to Terrain the two surfaces fight. With terrain blending Google goes under the mesh, Keep terrain below on, then off. After Match Colors the mesh has Google's tone. Last: one color per tileset](/img/match_height_colors_giza.jpg)

Frames of 960 x 540, EEVEE at 32 samples, Max SSE 8, on the laptop described on the [Videos](/guide/videos)
page: 40 s to load both tilesets, 2 to 5 s a frame.

## Height references

A height is counted from a surface, and sources do not use the same one.

![A cut through the ground with the WGS84 ellipsoid, the geoid and a national sea-level datum under it, apart from each other under the scene origin too: h_WGS84 is the height above the ellipsoid, H_MSL the height above sea level, dz_geoid the geoid's height, h_WGS84 = H_MSL + dz_geoid. Then which sources count from which surface](/img/height_references.png)

- **The ellipsoid** is the smooth mathematical shape GPS works on. 3D Tiles place everything in
  Earth-centred coordinates, so a tileset's heights are heights above the ellipsoid, `h_WGS84`. The add-on reads
  every height that way: Blender's Z is `h_WGS84` of the point minus that of the [scene origin](/features/scene-origin).
- **The geoid** is mean sea level carried under the land (the models EGM96 and EGM2008). Maps and most
  elevation rasters give `H_MSL`, the height above it.
- **A national datum** is one country's own sea level, within a metre or two of the geoid.

`h_WGS84 = H_MSL + dz_geoid`. The geoid is `dz_geoid` metres over the ellipsoid: +45 m in Paris, +15 m in Giza, +36 m in Tokyo, -100 m south of
India. A source that gives heights above sea level, shown by a program that expects heights above the
ellipsoid, lands `dz_geoid` too low.

### What each background gives

Measured with the add-on, cesium-native backend: the surface each background shows at four flat, open
places, minus the ground there (Terrarium tiles for the height above sea level, plus EGM96). Near 0: the
source is in ellipsoid heights. Near `-dz_geoid`: it is in sea-level heights and shows that much too low.

| Background | Giza (dz_geoid +15) | Paris (+45) | Zurich (+47) | Tokyo (+36) | Counts from |
|---|---|---|---|---|---|
| Cesium World Terrain (ion asset 1) | -40.7 m | -0.4 m | 0.0 m | +0.1 m | ellipsoid |
| Google Photorealistic 3D Tiles | +1.8 m | -1.9 m | +4.2 m | -0.4 m | ellipsoid |
| Bing Maps 3D (through 3dtiled) | no tile | no tile | +3.4 m | +0.2 m | ellipsoid |
| swisstopo terrain (quantized-mesh) | | | -43.0 m | | sea level: 43 m too low |
| Terrain viewer companion: Mapterhorn | no data | -45.8 m | | | sea level: *N* too low |
| Terrain viewer companion: Esri World Elevation | -12.9 m | -45.5 m | | | sea level: *N* too low |
| Terrain viewer companion: Mapbox Terrain-RGB | -14.7 m | -45.7 m | | | sea level: *N* too low |

Cesium World Terrain at the Giza point is 41 m under the ground and 25 m under sea level: neither
reference, so its data there is off, not its reference. The other three places agree within half a metre.

From their documentation, not measured here: MapTiler Terrain is in EGM96 heights; Mapbox Terrain-RGB and
Mapterhorn keep each source survey's own datum; Re:Earth Terrain serves both, an `ellipsoid` endpoint and an
`elevation` one; PLATEAU terrain is in ellipsoid heights.

The add-on moves nothing by itself: a dataset is shown where its tileset says it is. The one place it uses
the geoid is *Search place*, to turn the ground's height above sea level into the `h_WGS84` of the scene origin.

## Match Height to Terrain

A button under the entry's fields, for any tileset that is streaming and is not itself a background.

1. Add the dataset and a background (a terrain entry, Cesium World Terrain, Google or Bing 3D Tiles) and
   Start. Any background that streams counts; terrain blending does not have to be on.
2. Look at the dataset, so that tiles of both are shown under each other.
3. Select the dataset in the list and press **Match Height to Terrain**.

The tiles shown of the dataset are binned into ground cells seen from above, as are the terrain tiles under
them. In every cell both have, the lowest height of the terrain minus the lowest height of the dataset is
taken, and the dataset moves by the median, along the local vertical. The report says by how much.

- **What moves** is the tileset's root Empty. In a [tileset of tilesets](/features/several-tilesets#a-tileset-of-tilesets)
  with *Markers - datasets locations* on, each dataset that has tiles shown moves by its own amount, through its own
  Empty (its *Location Z*), and the others are left alone: zoom on the datasets you care about first. The
  offsets are remembered on the entry, like any move of those Empties.
- **Once.** Nothing holds the dataset there afterwards. Undo, or the Empty's location, brings it back.
- On a background entry the same button is **Match Dataset Heights to Terrain**: every other tileset moves
  onto that one.
- The lowest heights are compared, so a dataset with a building on flat ground matches on the ground, not
  on the roof. A dataset with stray points under the ground is pulled up by them where they are.
- Over Google or Bing the terrain is itself a photogrammetry mesh, with its buildings and trees: the match
  is as good as the two agree on what is there.
- Each dataset moved differently is selected with its own view, so many different offsets in one aggregate
  cost streaming time.

On Giza the mesh moved +23.3 to +23.8 m onto Google depending on the level of detail shown, and a second
press measured 0.0 m. The computation took 2.8 s with 5 dataset tiles and 135 Google tiles shown. In the open-data aggregate, the Strasbourg mesh moved +0.08 m
onto Google through its own Empty (0.9 s, 38 and 88 tiles).

## Color correction

A box under *Clipping*, per tileset: tick **Color correction**.

![The Color correction box of a tileset, after Match Colors: gain and gamma per channel, the tileset matched to. Raster overlays and Clipping are ticked and folded by the arrow at their right](/img/color_correction_panel.png)

| Setting | What it does |
|---|---|
| **Exposure** | Stops: +1 doubles the light. One number: per channel it would be the gain again. |
| **Gamma** | Red, green, blue, one under the other: each channel is raised to this power before the gain. Over 1 darkens the mid tones. Drag down the column to set the three together. |
| **Gain** | Red, green, blue, in the column beside it: each channel is multiplied by its number. |
| **Saturation** | 0 is grey, 1 leaves the colors alone. |
| **Contrast** | 0 leaves it alone. |
| **Match to**, **Match Colors** | Fills Gain and Gamma from another tileset (below). |
| The arrow button | Back to no correction. |

It is live, for meshes and point clouds, and it is part of the tile materials: Material Preview, Rendered
view, EEVEE and Cycles renders, not Solid view. Each tileset has its own node group, *OGC3D Color*, between
the tile's texture or point colors and the rest of its material; the node button beside *Gain and Gamma*
opens it. *Color tiles by* colors are not corrected. Moving a slider compiles nothing; ticking the box
compiles the materials of the tiles loaded once. A tile that loads later gets the group as it is built, so
it never shows uncorrected.

### Match Colors

Pick the reference in **Match to**, a list of the other tilesets (Google Photorealistic 3D Tiles under a photogrammetry mesh, for one),
have both streaming with the overlap in view, and press **Match Colors**.

Both tilesets are sampled over the area they share, seen from above, and nowhere else: 3000 points per
tile shown there, each looked up in the tile's texture (or the point's own color), averaged per ground
cell. So it works both ways: a small mesh onto Google, or Google onto the small mesh. Over the cells both
have, a gain and a gamma are fitted per channel so that *reference = gain x color ^ gamma*: the gamma
brings the spread of the colors together, the gain their level. On Giza over Google it compared 8,084
cells in 0.5 s and gave gain 1.24, 1.50, 1.28 and gamma 0.73, 0.87, 0.79; Google onto the mesh, 8,089
cells.

If the reference has a color correction of its own, the match is to what it looks like with it (its
gamma, gain, exposure and saturation; not its contrast): raise Google's exposure, then match the mesh to
that. The tileset being matched is always read uncorrected, and its exposure, saturation and contrast go
back to neutral.

What it is and is not:

- It is a global match: a color cast, an exposure or a contrast difference. Shadows that fall elsewhere,
  a different season or wet ground stay different.
- It samples the level of detail shown. Run it again closer if the result looks off.
- The texture colors are compared, not the lit result, so the lights of the scene do not enter.
- Gain is kept between 0.2 and 5, gamma between 0.6 and 1.6. It needs 16 ground cells with colors in both.
- With raster overlays on a tileset, the first texture of each tile material is the one sampled.
