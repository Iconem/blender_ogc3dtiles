---
title: "Changelog"
description: "What changed, newest first"
---

Dates are those of the commits. Versions are the tags on the Releases page; *Unreleased* is on the
main branch and not in a release zip yet.

## Unreleased

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
  keyframed volumes in renders; tiles fully cut are not downloaded.
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
