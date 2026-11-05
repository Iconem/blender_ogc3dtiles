---
title: "Scene origin"
description: "Where the Blender origin sits on the globe, and how to move it to a place by name"
---

All streams share one ENU origin (`Scene Origin` sub-panel):

- **Auto** — centre on the first tileset.  On a later Start the current origin
  is kept when the new tileset's centre lies within *Reuse within* km of it
  (default 10 km, CloudCompare-style), otherwise the scene is re-centred.
- **Keep current** — never move it once set.
- **Custom** — use the typed latitude / longitude / height.

The origin is stored in the .blend; *Reset Origin* forgets it.

## Search a place

![Search place: origin on the Basilica di San Pietro (ground 62 m + geoid 48 m), WGS84 globe with OpenStreetMap](/img/place_search.jpg)

Scene Origin > Mode > *Search place*: type a place (Enter) and pick one of
the results; the origin moves there and a running stream restarts around it,
which is the quickest way to look at a spot of a global tileset (Google
Photorealistic 3D Tiles, the WGS84 globe with imagery).  Places come from
[Photon](https://photon.komoot.io) (OpenStreetMap data); the origin height is
the ground (a Terrarium elevation tile, by default the AWS open-data Terrain
Tiles) plus the EGM96 geoid undulation, i.e. an ellipsoid height as 3D Tiles
use, so the ground sits near z = 0.  The geoid grid is cesium-native's
`WW15MGH.DAC` (2 MB, fetched once into the cache).  The three endpoints are
in the add-on preferences (a self-hosted Photon works the same); the query
text is sent to the geocoder, nothing else is.
