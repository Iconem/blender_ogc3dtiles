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

## Level of detail

**Max SSE** (LOD / Streaming panel) applies to every tileset, live. Lower is finer and heavier. Tick
**Own SSE** on an entry to give that tileset its own value.

The value is the error a tile declares, in screen pixels, so what a number looks like depends on the
data and on the tool that tiled it:

- on Google Photorealistic 3D Tiles at 8 px, the median triangle edge measured 3.3 px;
- a COPC point cloud that declared more error than its point spacing (1.2 px between points at 3.2 px
  of error) looked fine at 16 to 32 px.

## Details

- Two entries with the same name get separate collections (`... - 2`), and the entry is renamed to
  match.
- Share links (`/s/<token>/<asset>.json`) are labelled by the asset, never by the token.
- *Start* discards the tiles a previous *Stop* left on screen.
- Load order: missing ancestors first, then shallow tiles, then by screen-space error weighted toward
  the centre of the view, as CesiumJS does. With the pure Python backend, *Foveation cone* and *Edge
  SSE relax* (Advanced) tune that weighting.
