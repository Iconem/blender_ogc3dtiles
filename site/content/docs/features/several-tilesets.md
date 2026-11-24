---
title: "Several tilesets"
description: "The tileset list: entry types, pausing, hiding, a level of detail per tileset"
---

The main panel holds a list of tilesets. They stream together, around the same scene origin and the
same camera: a drone scan inside the city model around it, a point cloud over a globe with imagery.

## Entry types

| Type | Source |
|---|---|
| **3D Tiles** | A `tileset.json` URL, or a local path. |
| **Cesium ion** | An asset id and your access token. The token is only sent to Cesium ion. |
| **WGS84 globe** | A bare globe to drape imagery on. Its *Raster overlays* box is ticked for you. |
| **Quantized-mesh terrain** | The `layer.json` URL of a terrain server. For Cesium World Terrain, use a Cesium ion entry. |

Ion, globe and terrain entries need the cesium-native backend.

![Entry types: WGS84 globe with an OpenStreetMap overlay, 3D Tiles URL with overlays off, Cesium ion asset](/img/tileset_types.png)

## Working with the list

- **+** adds an entry, **-** removes the selected one. Entries added, ticked or removed while
  streaming are picked up at once.
- The **checkbox** of a row pauses that tileset: nothing more is loaded or unloaded, and what is
  loaded stays.
- The **eye** hides it, as in the outliner.
- Editing the URL of a running entry restarts it with the new URL.
- Each tileset has a root Empty, `3D Tiles · <name>`, and a collection, `Tiles · <name>`. Move, rotate
  or scale the Empty to place the tileset; streaming follows.

## A tileset of tilesets

A `tileset.json` can be nothing but a tree of grouping tiles whose leaves are other tilesets, one per
dataset: every survey of a city, every dataset of a server. With the cesium-native backend each of
those datasets gets its own Empty under the tileset's root, named after the dataset, and its tiles are
parented to it. The name is the dataset's `name` in the aggregate's 3D Tiles 1.1 tile metadata (else `title`,
`scene` or `label`, with its `project` in front), and only without one the last telling part of its URL.

**Markers for all N datasets (beta)**, under *An Empty per dataset*, makes those Empties at Start for every
dataset the aggregate's `tileset.json` lists, before any tile of it is loaded: a sphere at its centre. The
sphere has the dataset's size, up to a kilometre: Blender draws an Empty no larger. So each dataset also gets a
**dot** in the 3D viewport, of the **px** radius beside the checkbox (5 pixels by default, 0 for none), the same
at any distance and any Globe scale: a site of a few metres shows from space. Datasets with tiles loaded have a
blue dot, the others an orange one. The dots hide behind tiles, are not in renders and cannot be clicked: pick
a dataset in *Scene Origin > Dataset*, or its Empty in the Outliner. With markers on, a dataset keeps its sphere once its tiles
are in. *Scene Origin > Dataset* then lists them all, so the origin can go to a dataset on the other side
of the world, and its tiles load there. A marker becomes the dataset's ordinary Empty with its first tile.
Unticking removes the markers no tile took over. It reads the root `tileset.json` only: datasets listed in
a sub-tileset of a very large aggregate get no marker yet. The grouping tiles get none.

- The Empty appears with the dataset's first tile, at the dataset's centre, with its Z along the local
  vertical. Its location, rotation and scale start at zero: what you type there is an offset.
  **Location Z** is a height offset, for a dataset whose heights are above the geoid among others
  above the ellipsoid.
- The offset is kept on the tileset's entry, per dataset URL, and saved with the .blend. It comes back
  after a Stop, a reload, or with a dataset that loads later.
- Level of detail and culling follow the offset. cesium-native only knows where the dataset says it
  is, so a moved dataset is selected for a camera moved the other way. Cesium for Unreal and Cesium
  for Unity do the same for a tileset that was moved: the camera goes into the tileset's frame, the
  tiles stay where they are. Here each moved dataset gets a selection pass of its own, limited to
  that dataset, and the main pass leaves it out: nothing is loaded for the place the dataset is no
  longer at. Measured on two splat datasets side by side, one moved 100 m up or down under a camera
  looking towards the horizon: the moved one shows exactly the tiles a camera moved the other way
  would get, and the other one does not change. Without this, 45% of the splats that should be on
  screen were missing in the same test.
- Datasets sharing the same offset share one pass, and up to 32 different offsets are followed per
  tileset, those of the datasets with most tiles first. A scaled dataset keeps the level of detail
  of its original size.
- The names of the Empties also serve the scene origin: its *Dataset* mode puts the origin at the
  dataset picked by name. See [Scene origin](/features/scene-origin#dataset).
- *An Empty per dataset*, under the tileset's boxes in the main panel, turns this off for the tiles
  loaded from then on.
- A tileset that pages its own hierarchy through external files, as Google Photorealistic 3D Tiles
  does, has no datasets and gets no extra Empty.

## Level of detail

**Max SSE** (LOD / Streaming panel) applies to every tileset, live. Lower is finer and heavier. Tick
the checkbox next to **Tileset Max SSE** on an entry to give that tileset its own value.

The value is the error a tile declares, in screen pixels, so what a number looks like depends on the
data and on the tool that tiled it:

- on Google Photorealistic 3D Tiles at 8 px, the median triangle edge measured 3.3 px;
- a COPC point cloud that declared more error than its point spacing (1.2 px between points at 3.2 px
  of error) looked fine at 16 to 32 px.

The view that selects the tiles can be another camera than the one you navigate with: see
[Rendering](/features/rendering).

## Details

- Two entries with the same name get separate collections (`... - 2`), and the entry is renamed to
  match.
- Share links (`/s/<token>/<asset>.json`) are labelled by the asset, never by the token.
- *Start* discards the tiles a previous *Stop* left on screen.
- Load order: missing ancestors first, then shallow tiles, then by screen-space error weighted toward
  the centre of the view, as CesiumJS does. With the pure Python backend, *Foveation cone* and *Edge
  SSE relax* (Advanced) tune that weighting.
