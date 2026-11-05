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

## Search a place

![Search place: origin on the Basilica di San Pietro (ground 62 m + geoid 48 m), WGS84 globe with OpenStreetMap](/img/place_search.jpg)

Set the mode to *Search place*, type a place, press Enter and pick one of the results. The origin
moves there and a running stream restarts around it. It is the quickest way to look at a spot of a
worldwide tileset: Google Photorealistic 3D Tiles, or the WGS84 globe with imagery.

The origin is put on the ground, so the ground sits near z = 0.

## Details

- Places come from [Photon](https://photon.komoot.io), which searches OpenStreetMap. Only the text you
  type is sent to it.
- The ground height comes from an elevation tile (by default the AWS open-data Terrain Tiles), plus
  the EGM96 geoid height, which turns a height above sea level into the height above the ellipsoid
  that 3D Tiles use. The geoid grid is a 2 MB file, downloaded once into the cache.
- The three addresses are in the add-on preferences; a self-hosted Photon works the same.
