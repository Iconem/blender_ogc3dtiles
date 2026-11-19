---
title: "Changelog"
description: "What changed, newest first"
---

Dates are those of the commits. Versions are the tags on the Releases page; *Unreleased* is on the
main branch and not in a release zip yet.

## Unreleased

- **Tile bounds** (LOD / Streaming panel): a wire outline around every visible tile, drawn in the 3D
  view only, in one colour or a random colour per tile. *Tile objects* outlines what each tile
  holds, splats included, which Blender's own Bounds display skips; *3D Tiles volumes* outlines the
  boxes, spheres and regions the tileset declares. See [Tile bounds](/features/lod-streaming#tile-bounds).
- **A clipping object deleted and recreated under the same name cuts again** on point and splat
  tiles. Their clip node group only compared names, so it kept pointing at the deleted object and
  nothing was cut.
- **Slide decks**: the deck now covers tile bounds, colour by tile level, panoramic cameras, the
  Atmosphere preset, X-ray, voxels, files and export, and the datasets tested; a second deck,
  *Under the hood*, shows how the add-on works inside. Both on the
  [Slide decks](/guide/slide-decks) page, which replaces the Slides page.
- **Docs: new screenshots and a [Videos](/guide/videos) page.** The feature pages show the deck's new screenshots
  (Venice, Giza, Geghard, IGN LiDAR classes, the Bayon, Tokyo, the Grand Canyon). The Videos page has short clips,
  most of them rendered frame by frame with the tiles converged. The screenshots and clips are no longer in git:
  they live on the *Media: screenshots* and *Media: videos* releases, and `scripts/docs-media.mjs` pulls them
  before the site and the decks build.

- **An Empty per dataset in a tileset of tilesets** (cesium-native backend). When a `tileset.json` only gathers
  other tilesets, each of them gets an Empty under the tileset's root, at its centre with Z up, and its tiles
  are parented to it. Typing a Location Z on it shifts that one dataset in height (geoid against ellipsoid);
  the offset is kept per dataset URL with the scene. Level of detail and culling follow the offset: a moved
  dataset is also selected for a camera moved the other way (without it, a 100 m offset under a low camera
  lost 45% of the splats on screen). See [A tileset of tilesets](/features/several-tilesets#a-tileset-of-tilesets).
- **Scene origin: a *Dataset* mode.** The origin goes to a dataset of such a tileset, picked by the name of
  its Empty.
- A tileset path on a mapped network drive is stored as its share path when typed or pasted too, not only
  when browsed to.
- **Globe navigation: a place search now shows the place.** With the Globe scaled or turned, a search or a new
  scene origin left the view looking at nothing; the Globe now returns to 1:1 at the new origin, and objects
  parented to it keep their place on the Earth. *Re-anchor Scene Origin* is greyed while Globe Navigation is
  off, where it used the view's pivot instead of the ground. A thin frame around the 3D view shows the mode is
  on. See [Globe navigation](/features/beta#globe-navigation).
- **Tiles no longer shade like pillows.** Tiles without normals (Google Photorealistic 3D Tiles, most
  photogrammetry) showed every tile's outline under a light, most of all on flat water: the skirt around
  each tile bent the normals along its edges. Edges sharper than 50 degrees now split the normals.
- **Globe navigation (beta prototype)**, a folded section of the *Scene Origin* panel. The wheel zooms about the point under
  the cursor, middle drag orbits around it, Shift+middle drag grabs the globe; everything else stays Blender's.
  An *OGC3D Globe* Empty carries every tileset, and objects parented to it move with the planet. Far from the
  ground the wheel scales that Empty instead of moving the view (*To 1:1* undoes it before a render). When the
  gestures stop, the scene origin moves under the view and the tiles are placed again in double precision.
- **Blender's own renders wait for their tiles: F12, Ctrl+F12 and the command line.** Before each frame
  renders, the add-on streams for the scene camera and waits until its tiles have loaded, with the Render
  panel's Settle and Max wait. A frame that reaches Max wait says how many tiles were still loading. In
  the window a stream must be running; `blender -b scene.blend -a` (or `-f`) starts one, with the Warm-up.
  See [Rendering](/features/rendering#f12-ctrlf12-and-the-command-line).
- **The render border (Ctrl+B in a camera view) narrows what a camera stream loads**: only the tiles of
  the part that renders, for *Stream for* Scene camera or Chosen camera, and in renders.
- **The Atmosphere preset no longer deletes your World's nodes.** The sky is an `OGC3D Sky` group
  plugged into the World's output, next to the nodes already there, or in a new *3D Tiles Sky* World
  (the world-icon button). The beauty compositor keeps a compositor tree of yours and puts it back when
  turned off.
- **Concurrent Requests** (was *Parallel DL*) now applies to cesium-native too, live: it was only read
  by the Python backend, and cesium-native stayed at 20 loads. The default is 20.
- *Own SSE* is now the checkbox next to **Tileset Max SSE**. *Imports / tick* and *Build ms while
  navigating* are in a folded **Viewport Performance** section of LOD / Streaming.
- **Preferences**: the cesium-native status and install button at the top; labels and fields share a
  row; *Material controls* is the first beta feature; the backend choice, Direct mesh, the wheel source
  and the timing comparison are in a folded *Developer* section. The maintainer and the website come
  from the extension manifest. *Open the 3D Tiles sidebar* is gone: the add-on no longer opens the
  sidebar when Blender starts or a file loads.
- `scripts/build_platform_zips.py` builds extension zips with the cesium-native-python wheel inside, one per
  platform (Windows x64, Linux x64, macOS ARM) and per Python (Blender 4.2 to 5.0, Blender 5.1 and later), the
  form extensions.blender.org needs. They hold no wheel downloader, so their preferences show no Install or
  Reinstall button. The *release extension* workflow can build them and upload them to the platform. The zip
  on the Releases page stays pure Python, with the wheel installed from the preferences. What still blocks a
  listing is in [extensions.blender.org](/dev/extensions-platform).
- Tiles imported through the glTF importer find their shader nodes by type, so they work with
  Blender's *Translate New Data* on.

## 0.6.4 (2026-11-14)

- **Panoramic cameras.** A panoramic camera as *Scene camera* or *Chosen camera* selects tiles all
  around it, at the panorama's resolution: six 90° views of a cube (five for a 180° fisheye), which
  cesium-native selects for together. See [Panoramic cameras](/features/lod-streaming#panoramic-cameras).
- **Tilesets on a network share can be cached**: *Cache files on network shares* in the add-on
  preferences, off by default. Files read from a NAS (`\\server\share` paths and mapped drives) then
  go through the disk cache: each file is read from the share again only when its date or size
  changed, so coming back to a tileset on a slow NAS no longer reads it all over the network. Files
  on a local disk are read directly, as before.
- **Metadata colours survive reopening a .blend.** The columns, class codes and number ranges the
  workers collect lived in memory only: after reopening a saved file the Metadata panel hid its
  legend and ramp, and the next edit coloured a number column with the class palette. They are
  now rebuilt from the file on load, and number ranges are saved with it. Opening another file
  no longer carries the previous file's columns over.
- **No more errors when stopping a stream.** Stopping while tiles were still loading logged a
  burst of "Tried to call pure virtual function IPrepareRendererResources..." messages: the
  add-on dropped its tile preparer before cesium-native had finished with it.

## 0.6.3 (2026-11-13)

- **`EXT_splat_opacity` honoured.** Tilesets from the 3DGS-PLY-3DTiles converter (William Liu)
  looked like soft blobs at coarse levels: the converter grows the splats it merged ("coverage
  boost") before writing SPZ and keeps the source opacity and pre-boost shape in this extension.
  The add-on now undoes the growth and draws the source opacity, see
  [Gaussian splats](/features/gaussian-splats#gltf-extensions-honoured-and-ignored).

## 0.6.2 (2026-11-12)

- **Scene origin in double precision** (issue 7). The latitude, longitude and height fields are
  single precision in Blender, which moved tiles by up to 0.7 m at longitude 150 and kept the
  local-frame height to 0.5 m. The add-on now keeps the exact values in a scene property, set
  whenever it picks an origin or a field is edited, and places tiles and cameras from it. A new
  *Paste* field under the three takes `latitude, longitude[, height]` with full precision, since a
  value typed in a float field is rounded before the add-on sees it.

## 0.6.1 (2026-11-12)

- **Orthographic views** select tiles through cesium-native's orthographic view state: the frame
  extents are passed as they are, the eye stays on the pivot, and tiles behind the pivot are
  selected. The 1 degree camera emulation and its pull-back are gone.
- **Linux**: HTTPS works on every distribution. The curl backend reads certifi's CA bundle instead
  of the Red Hat path built into the manylinux wheel (cesium-native-python issue 9).
- **Start** reuses the live modal instead of stacking a second one, so menus and keys are no longer
  dropped after Stop then Start in a script. Tiles freed and loaded again under the same key no
  longer leave an orphaned object behind.
- **Development**: the add-on no longer carries its Windows patch for cesium-native-python nor its
  own wheel workflow, since upstream merged the build fixes and a cibuildwheel workflow (#3, #4, #5,
  #7). A Screencasts page in the developer docs describes the two video capture workflows.

## 0.6.0 (2026-11-06)

**Streaming and cameras**

- *Stream for* has a third choice, **Chosen camera**: a camera object selects the tiles while you
  navigate the viewport freely. The setting is also in LOD / Streaming.
- Cap on points / vertices shown (beta), and the size of cesium-native's cache.

**Colours and metadata**

- Colour by **tile level**, **geometric error**, or a **random colour per tile**.
- An **opacity per class**: hide the ground of a LiDAR cloud.
- LiDAR classification read from COPC tiles streamed by 3dtiled, with the LAS class names and colours.
- The Color Ramp of number columns is editable in the panel.

**Point clouds**

- Attenuated point size stays between 1 and 3 px on screen by default (it was 2 to 12 px), so
  coarse tiles no longer show as large discs while finer ones load.

**Nodes**

- Every shared node group has the same row: checkbox, node editor button, reset / delete menu.
- **Demo graphs** for the shared geometry nodes: Suzanne on points, noise displacement, height reveal.
- **Atmosphere preset**: a sun, a matching sky and haze in one click.
- Shared shader nodes: sliders with ranges, albedo strength and saturation from -1 to 2, **X-ray**.
- A button opens a tile's own material. Node graphs are laid out in columns when built or reset.
- The beauty compositor switches edges, AO and haze off in a Cycles viewport, which has no passes
  for them, and back on for F12 renders.

**Raster overlays and libraries**

- Overlay **presets** from a bookmark button: OpenStreetMap, Esri World Imagery, IGN orthophotos;
  keyed ones from the library files.
- A button in the preferences opens a library file in your editor.

**Interface**

- Sidebar reorganised: overlays, clipping and the viewport-region clip in boxes of the main panel;
  panels named Nodes: Material, Geometry, Compositing, Metadata.
- A missing cesium-native backend is shown in red at the top, with the install button.
- Geometry cut for Solid view and exports is on by default.
- *Direct mesh* moved to the Developer box of the add-on preferences and applies to both backends
  (off: tiles go through the glTF importer, to compare or work around a tile).

**Tilesets**

- Tilesets without a location keep their own frame.
- Converter output with many empty levels now refines instead of showing nothing.

**Beta**

- Phases from Grease Pencil or Annotate strokes, painted or outlined; Phases in its own sidebar tab.

**Documentation**

- This site, the slide deck, and a shorter README.

## 0.5.1 (2026-11-04)

- **Quantized-mesh terrain** entries.
- Point **intensity** and other number columns on point clouds, with a custom range for the ramp.

## 0.5.0 (2026-11-04)

- **Raster overlays on point clouds**.
- Default Max SSE is 8 px.
- Voxel Volumes on Blender 4.5.

## 0.4.0 (2026-11-04)

- **Clipping**: polygons and boxes, cut or keep, inside any or all; on meshes, points and splats;
  keyframed volumes in renders; tiles fully cut are not downloaded. Switching modes is instant
  (no material or shader rebuild), and *Cut Geometry* also deletes cut faces for Solid view,
  snapping and exports.
- Several imagery overlays sharing a projection now show together instead of replacing each other.
- **Feature metadata**: tables as vertex attributes, colours per class, metadata in textures,
  per-point and tileset metadata.
- **Voxel tilesets**: blocks, volumes, and colouring other tilesets from voxel classes.
- **Local and NAS tilesets**, **tileset libraries** with search and type filters, a cap on the disk
  cache, **copy into project** (Google, ion and implicit tilesets included).
- Uncompressed Gaussian splat tiles.
- Beta: the phases timeline, material controls.
- The sidebar opens on the 3D Tiles tab. MIT licence.

## 0.3.0 (2026-10-22)

- Packaged as a **Blender extension**; the release workflow builds and validates the zip.
- The cesium-native backend installs from a **wheel on a GitHub Release**, no compiler needed.
- **Stream for the scene camera** and the **converged animation** render.
- **Clip to viewport region** (Alt+B) in Material Preview and Rendered; the *Faces* setting.
- **Shared geometry nodes** on every tile.
- One panel per sidebar section, collapsible and re-orderable.

## Before 0.3.0

The add-on started as a prototype in June 2026 and was reworked in October 2026, when this
repository's history begins: the cesium-native backend, raster overlays and the WGS84 globe, several
tilesets at once, Gaussian splat tiles on Blender 5.3, point clouds, the shared shader group and the
beauty compositor.
