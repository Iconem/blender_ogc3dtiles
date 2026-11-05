---
title: "Raster overlays"
description: "Imagery draped on tiles: OSM, Esri, IGN, WMTS, WMS, Google, Bing"
---

![Raster overlays: OpenStreetMap draped on Google Photorealistic 3D Tiles over the Colosseum at opacity 1 and 0.5, and a top view](/img/raster_overlays.jpg)

With the cesium-native backend any streamed tileset can be draped with
raster imagery, the way Cesium for Unreal / Unity do it: add entries under
*Raster overlays* in the tileset box (URL template `{z}/{x}/{y}`, TMS, WMTS,
WMS, Cesium ion imagery, Bing Maps, Google Map Tiles 2D, or cesium-native's
debug colouriser) and press Start.  The bookmark button under + / - adds a
ready-made one: OpenStreetMap, Esri World Imagery and IGN orthophotos (WMTS and
WMS) need no key and come with the add-on; overlays that need a key (Google Map
Tiles, Bing Maps) are read from the `overlays` list of the library files.  cesium-native projects each tile onto
the overlay's tiling scheme, adds a `_CESIUMOVERLAY_<n>` texture-coordinate
set to the tile and streams the raster tiles that cover it at a resolution
matching the tile's screen size; the add-on turns each raster into a packed
Blender image and inserts, per tile material, a *UV Map → Mapping → Image
Texture → Mix* chain over the material's colour (also under the Relight
group).  *Opacity* is live.  Ticking / unticking an overlay while streaming
is live too: cesium-native reloads the loaded tiles with the new texture
coordinates (to apply an edited URL, untick then tick).
Several overlays stack in list order.  Point clouds take them too: cesium-native
computes the coordinates per point in the overlay's own projection, so the point
cloud's CRS doesn't matter, and they cost one more attribute of 8 bytes per point.
Each point shows the raster at its position, seen from above, on walls as well as
on roofs.  Gaussian splat tiles don't take overlays.  A template pasted from a
browser, with `%7Bz%7D` for `{z}`, is shown and used with its braces.  The raster images are packed into the .blend, so a saved scene
keeps its drape.

![WGS84 globe entry with the OpenStreetMap overlay ticked live, over Rome](/img/globe_osm.jpg)

**WGS84 globe.** A tileset entry of type *WGS84 globe* streams
cesium-native's procedural ellipsoid instead of a tileset.json: a bare
globe, subdivided as the camera approaches, to drape imagery on when there
is no 3D Tiles content (the scene origin is yours to set: use *Custom*).

**Quantized-mesh terrain.** A tileset entry of type *Quantized-mesh terrain* takes the
`layer.json` URL of a server, such as
[swisstopo's](https://3d.geo.admin.ch/ch.swisstopo.terrain.3d/v1/layer.json), and streams it like a
tileset, draped the same way. Its root covers the world, so set a *Custom* scene origin.
Cesium World Terrain is an ion asset: use a *Cesium ion* entry. Terrarium / Terrain-RGB raster
DEMs are not terrain providers in cesium-native and are out of scope here.

See [cesium-native: versions and upgrade notes](#cesium-native-versions-and-upgrade-notes)
for what newer cesium-native releases would add (vector overlays,
orthographic view states) once the Python binding bumps its submodule.
