---
title: "Raster overlays"
description: "Imagery draped on tiles: OpenStreetMap, Esri, IGN, your own WMTS or WMS, Google, Bing"
---

![Raster overlays: OpenStreetMap draped on Google Photorealistic 3D Tiles over the Colosseum at opacity 1 and 0.5, and a top view](/img/raster_overlays.jpg)

A raster overlay drapes a map or an aerial image on a tileset, the way Cesium for Unreal and Unity
do. It needs the cesium-native backend.

## Add one

1. Select a tileset and tick **Raster overlays** in its box.
2. Press the **bookmark button** under + / - and pick a preset (type a few letters to narrow the list down),
   or press **+** and fill in a source.

   ![The overlay library with "bing" typed in its search box: two presets left](/img/overlay_library_search.png)

3. Press Start. If the tileset is already streaming, the overlay appears at once.

| Preset | Key |
|---|---|
| OpenStreetMap | none |
| Esri World Imagery | none |
| IGN orthophotos, France (WMTS or WMS) | none |
| Google Map Tiles, Bing Maps | yours, kept in a [library file](/features/libraries-and-local-files) |

Your own sources: a URL template with `{z}/{x}/{y}`, TMS, WMTS, WMS, a Cesium ion imagery asset, Bing
Maps, Google Map Tiles. A template pasted from a browser, with `%7Bz%7D` for `{z}`, works as it is. A
template can also hold `{q}` (or `{quadkey}`), the Bing quadkey of the tile, and a range of subdomains such as
`{0-3}` or `{a-c}`: `https://ecn.t{0-3}.tiles.virtualearth.net/tiles/a{q}.jpeg?g=15000`.

## Adjust it

- **Opacity** is live.
- Ticking or unticking an overlay is live. To apply an edited URL, untick it, then tick it again.
- Several overlays stack in the order of the list.
- **Raster detail px** (4 by default) sets how sharp the imagery is: higher is coarser, with far fewer
  downloads. See below.
- The images are saved in the .blend, so a saved scene keeps its drape.

## How the imagery level is chosen

For each geometry tile, cesium-native estimates how many pixels the tile covers on screen at the moment
it is replaced by its children: its size on the ground x the tileset's *Max SSE* / its geometric error.
It divides that by *Raster detail px* and picks the imagery level whose texels come closest to that
count, within the overlay's *Min level* and *Max level*.

So one imagery texel covers about *Raster detail px* screen pixels on the tile being shown, wherever you
look from:

- **Raster detail px** is what sets the sharpness on screen: 1 for a texel per pixel, 4 for a texel per
  4 pixels (the default), higher for blurrier imagery and fewer downloads.
- **Max SSE** changes which geometry tiles are shown. A higher value shows coarser tiles, and each gets
  imagery as many times finer, so the sharpness on screen stays about the same; what changes is the number of
  tiles and the imagery requests that go with them.
- **Max level** caps it: past the finest level the server has, the imagery stops getting sharper.

(cesium-native v0.59: `RasterOverlayUtilities::computeDesiredScreenPixels`,
`QuadtreeRasterOverlayTileProvider::computeLevelFromTargetScreenPixels`.)

## On point clouds and splats

Point clouds take overlays too: each point shows the map under it, seen from above, on walls as on
roofs. It costs 8 bytes more per point. Gaussian splat tiles do not take overlays.

## A globe or a terrain to drape on

![WGS84 globe entry with the OpenStreetMap overlay ticked live, over Rome](/img/globe_osm.jpg)

When there is no 3D Tiles content where you look, add a tileset entry of another type:

- **WGS84 globe**: a bare globe, subdivided as the camera gets closer.
- **Quantized-mesh terrain**: the `layer.json` URL of a terrain server, such as
  [swisstopo's](https://3d.geo.admin.ch/ch.swisstopo.terrain.3d/v1/layer.json). For Cesium World
  Terrain, use a Cesium ion entry.

Both cover the whole world, so give the scene an origin first: *Custom*, or *Search place*, in
[Scene origin](/features/scene-origin).

### A terrain server on your own machine

Any server that answers with a `layer.json` works, one on your own machine included. Here the Terrain
service of the [3D Tiled](https://github.com/Iconem/3dtiled-to-3dtiles/releases) local middleware serves the Mapterhorn elevation data as quantized-mesh on
`http://127.0.0.1:3400`. The entry is a *Quantized-mesh terrain*, and two *URL template* overlays from the
same service are draped on it: a sky-view factor shading at 62% opacity over a hypsometric tint. The scene
origin was put on the Matterhorn with *Search place*.

![Blender with the Matterhorn streamed as terrain from a local quantized-mesh service, shaded by two raster overlays; the window of the local service is beside it, its Terrain tab showing the source and its address](/img/terrain_local_service.jpg)

## How it works

cesium-native projects each tile onto the overlay's tiling scheme, adds a set of texture coordinates
to the tile (`_CESIUMOVERLAY_<n>`), and streams the raster tiles that cover it at a resolution
matching the tile's size on screen. The add-on makes each raster a Blender image and adds, in the
tile's material, a *UV Map, Mapping, Image Texture, Mix* chain over the tile's own colour. For point
clouds the coordinates are computed per point, in the overlay's own projection, so the cloud's
coordinate system does not matter.

Terrarium and Terrain-RGB elevation rasters are not terrain sources in cesium-native.
