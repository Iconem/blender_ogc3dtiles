---
title: "Scene origin"
description: "Where the Blender origin sits on the globe, and how to move it to a place by name"
---

3D Tiles are positioned on the globe; Blender works best near its own origin. The **Scene Origin**
panel says which point of the globe the Blender origin stands on. Every tileset shares it, with X to
the east, Y to the north, Z up, in metres.

| Mode | The origin is |
|---|---|
| **Auto** | The centre of the first tileset. A later Start keeps it when the new tileset is within *Reuse within* km of it (10 km by default); otherwise the scene is re-centred. |
| **Keep current** | Never moved once set. |
| **Custom** | The latitude, longitude and height you type. |
| **Search place** | A place found by name. |

The origin is saved in the .blend. *Reset Origin* forgets it.

## Precision

Blender keeps the three fields in single precision: at longitude 150 the step between two
representable values is about 1.5 x 10^-5 degrees, up to 0.7 m on the ground. The add-on
therefore keeps the exact origin in a scene property (`ogc3dtiles_origin`, three doubles) and
places tiles and cameras from it. It is written whenever the add-on picks an origin (Auto, Search
place, a local tileset) and whenever you edit a field.

A value typed in a float field is rounded before the add-on sees it. To set an exact origin, use
the **Paste** field under the three: `latitude, longitude[, height]`, any separator, full
precision. The three fields then show the rounded values and the scene property holds the exact
ones. The scene property only counts while it rounds to the fields, so a .blend saved by an older
version, or a field changed by a driver, falls back to the fields.

## Search a place

![Search place: origin on the Basilica di San Pietro (ground 62 m + geoid 48 m), WGS84 globe with OpenStreetMap](/img/place_search.jpg)

Set the mode to *Search place*, type a place, press Enter and pick one of the results. The origin
moves there and a running stream restarts around it. It is the quickest way to look at a spot of a
worldwide tileset: Google Photorealistic 3D Tiles, or the WGS84 globe with imagery.

The origin is put on the ground, so the ground sits near z = 0.

## Terrain tiles and geoid grid

The add-on preferences list a *Terrain tiles* address and a *Geoid grid* address. Both are only used
by *Search place*:

- the **terrain tiles** give the height of the ground at the place found, above sea level;
- the **geoid grid** converts that height above sea level into the height above the ellipsoid, which
  is what 3D Tiles use.

They are not terrain to display. To show terrain, add a *Quantized-mesh terrain* or a Cesium ion
entry: see [Raster overlays](/features/raster-overlays).

## Details

- Places come from [Photon](https://photon.komoot.io), which searches OpenStreetMap. Only the text you
  type is sent to it.
- The ground height comes from an elevation tile (by default the AWS open-data Terrain Tiles), plus
  the EGM96 geoid height, which turns a height above sea level into the height above the ellipsoid
  that 3D Tiles use. The geoid grid is a 2 MB file, downloaded once into the cache.
- The three addresses are in the add-on preferences; a self-hosted Photon works the same.
