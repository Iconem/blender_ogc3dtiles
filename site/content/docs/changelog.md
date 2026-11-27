---
title: "Changelog"
description: "What changed, newest first"
---

Dates are those of the commits. Versions are the tags on the Releases page; *Unreleased* is on the
main branch and not in a release zip yet.

## Unreleased

- **Blender no longer stalls while tilesets with KTX2 textures stream.** Textures that cesium-native hands
  over decoded were written as PNG before going to Blender, 0.3 to 1.5 s each in a load thread that held
  Python's lock all along, so the viewport waited on every one of them. They now go as TIFF without
  compression (2 ms for a 2048 px texture). On a 5 minute walk through the Iconem datasets over Google 3D
  Tiles, the viewport redrew 52 to 56 times per 30 s before, with gaps up to 2.8 s, and 119 to 120 times
  after; one streaming step in ten took over 1.1 s before, 0.23 s after. Tilesets with JPEG or PNG
  textures (Google) never went through this.
- **Match Height to Terrain compares open ground.** It compared the lowest height of the dataset and of the
  terrain in each ground cell, which is wrong when one of them has faces underneath: the scan of St Peter's,
  in place over Google, was moved up 21 m. Each cell now keeps its highest and lowest height, and the
  offset is read where both agree in both tilesets (one surface). St Peter's reads -0.1 m, Giza +21 m.
- **Tile materials: Lighter tiles or Instant switches** (LOD / Streaming > Viewport Performance).
  Blender goes through a material again each time nodes are added to it, so ticking Color correction
  or Terrain blending on a thousand loaded tiles froze the viewport for 4 to 7 s. With Instant
  switches every tile that loads carries both sets of nodes from the start, doing nothing until a box
  is ticked: on Giza over Google every tick and untick then redraws in about a second or less, where it
  took 5 to 13 s. A tile takes 3 ms longer to build (13.5 ms against 10.2). Instant switches is the
  default; Lighter tiles is the behaviour of before.
- **Tiles with normals build in half the time.** A profile of the tile build, line by line, on a walk
  through the Iconem datasets over Google 3D Tiles: 46 % of it was one call, the one that gives a mesh
  the normals of its tile (about 42 ms on each tile that has normals, a fifth of them). Since Blender 4.5
  normals can be a plain attribute of the vertices, read as it is: same shading, no conversion. A tile
  now takes 13.5 ms to build instead of 19.9, and 19 % more tiles are built in the same time (714
  against 600 per 30 s). Tilesets without normals (Google) are unchanged; Blender 4.2 to 4.4 keep the old
  call.
- **Tile materials from a template.** A textured tile starts from a copy of a finished material of its
  tileset and only takes its own image: 7.0 ms per tile instead of 10.1 on the same walk, the materials
  the same node for node. Off in Preferences > Developer.
- **PNG textures no longer wait on Blender's main thread.** Blender takes 21 ms to read a 1024 px PNG at a
  tile's first draw (a JPEG: 7 ms); such tiles are handed over as the pixels cesium-native decoded, read in
  2 ms.
- **Google Photorealistic 3D Tiles gets no dataset Empties** any more: its first external files passed for
  the datasets of a tileset of tilesets (38 Empties over Rome).
- **Copy Setup takes the viewport's view along**, and Paste Setup restores it with the origin when the list
  is empty.
- **A [Performance](/dev/performance) page** in the docs: where the time of a tile goes, what to change
  when the viewport stutters, how long Blender takes to read a texture by format.
- **Several tilesets share one build budget.** The build time per tick (*Imports per tick*) was given
  whole to each tileset, so two tilesets loading at once held Blender twice as long. The median
  streaming step went from 170 to 125 ms and the viewport from 120 to 147 redraws per 30 s on that walk.
  The mesh arrays are also written as attributes, not through a setter per element: a gain only on large
  tiles (9 ms instead of 19.5 at 33,000 triangles, about 1 ms on the average tile of the walk).
- **Origin to Sun Position** (Scene Origin panel): gives the origin's latitude and longitude to Blender's
  Sun Position extension, north along +Y, and adds a Sun light when there is none. Date and time are set
  in World Properties > Sun Position.
- **Install with updates from Blender.** The releases are a repository Blender reads: add
  `https://github.com/Iconem/blender_ogc3dtiles/releases/latest/download/index.json` once in Preferences
  > Get Extensions > Repositories, and Blender offers each new version.
- **Copy URL gives a whole address** when the tileset of tilesets names its datasets by a relative path.
- **Markers are per tileset.** The checkbox, the dot radius and *Also the datasets not loaded yet* of
  *Markers - datasets locations* were the scene's; each tileset of tilesets now has its own, like
  Clipping and Raster overlays. A scene saved before starts from the defaults.
- **Copy URL of a dataset.** With a dataset's Empty active, the Markers box shows its name and a button
  that copies the address of its tileset.json. It is also the Empty's custom property `ogc3dtiles_dataset`.
- **Match to is a plain list of the other tilesets** again, by name, in place of Blender's object picker.
- **A tile's part in Terrain blending is a property of its object** (`ogc3d_blend_role`), and the
  coverage is placed by a matrix kept in scene properties, not by an Empty the shader points at:
  moving that Empty made Blender go through every tile material again (3 s for 1,400).
- **Sliders of Terrain blending and Color correction no longer freeze the viewport.** Their numbers
  were held in nodes of a shared group, and Blender looks at every material using a group again when
  one of its nodes changes: with 1,000 tile materials, one slider step froze the viewport for 3 to 4 s
  (Blender 5.3, measured), and so did each update of the blend coverage while tiles streamed in. The
  numbers are now custom properties of the scene (`ogc3d_...`) read by Attribute nodes: 0.05 s.
  Ticking a box on a thousand tiles already loaded still takes a few seconds, once.
- **Terrain blending reaches every tile at once.** Ticking the box, or editing one of its settings, now puts
  the blend in all the tiles shown in one go. It was left to the streaming tick, a few tiles at a time: with
  a thousand Google tiles on a scene at rest, 369 had it after 25 s, and Google stayed in front of the
  dataset where it was not done. Tiles that stream in later get it faster too while many wait.
- **The boxes of a tileset, in a new order:** Properties, Clipping, Raster overlays, Color correction,
  Markers, Terrain blending. Markers shows only for a tileset of tilesets.
- **Scene Origin: no more Keep current.** Custom does the same: its fields hold the current origin, so
  switching from Auto keeps it. A scene saved on Keep current comes back without a mode: pick one.
- **Copy Setup and Paste Setup.** Two buttons beside the tilesets list: the whole list as JSON text on the
  clipboard, with the overlays, clips, color correction, blend settings and scene origin, to paste in
  another scene or send to someone. The text holds keys and tokens as they are.
- **A click on the name of a box folds it,** as on a Blender panel header: Properties, Clipping, Raster
  overlays, Color correction, Markers, Terrain blending. The arrow still does too.
- **Match to lists tilesets only:** the root Empty of each other streaming tileset, no longer every tile.
- **Markers stays folded** until you unfold it, ticked or not.
- **Docs site on its own domain:** blender-3dtiles.iconem.com.
- **Docs:** a download button on the home and Installation pages, a sitemap, and a canonical address and
  social tags on every page.

## 0.6.10 (2026-11-26)

- **Icons on the boxes of a tileset.** Raster overlays, Markers, Clipping, Color correction and Terrain
  blending each carry an icon beside their checkbox, as Properties already did.
- **Library search: an Aggregate filter.** Beside Mesh, Points, Splats and Voxels, it keeps only the
  tilesets of tilesets, whatever they hold.
- **Match Colors keeps more contrast.** The gamma is now between the regression slope and the ratio of the
  two spreads. The slope alone reads low when the cells are noisy, and it flattened the colors: on Giza
  over Google the gamma sat at its lower limit, 0.8.
- **Wider panel popups.** Tilesets and Nodes: Metadata opened from a shortcut are wide enough for their
  labels and buttons.
- **Docs home page**: the two deck covers open their slide deck instead of a zoomed picture.
- **Release workflow**: the platform zips wait for the release to exist before they are attached. On 0.6.9
  one repository built them before its release was made and failed there; a rerun attached them.

## 0.6.9 (2026-11-26)

- **Color correction reaches every tile at once.** Ticking the box, or Match Colors on a tileset that had it
  off, now corrects all the tiles the tileset has loaded, shown or not. It used to be left to the streaming
  tick, one tile at a time: 5 of 82 materials after 6 s on a scene at rest, and Match Colors even took the
  correction out again on its next tick. Tiles changed color one by one for a minute.
- **Match Colors no longer burns the light surfaces.** The gamma is the slope of the reference over the
  tileset, cell by cell, between 0.8 and 1.3, and the gain keeps the bright end under the reference's. On
  Giza over Google the old fit gave gain 2.6, 3.0, 3.1 with gamma up to 1.3 and a white site; the new one
  1.45, 1.44, 1.35 with gamma 0.8.
- **Globe Navigation follows Blender's own tools.** A view moved by Shift+B, View Selected, a numpad view or
  the gizmo also moves the scene origin under it and levels the Globe, as after a gesture of the mode.
- **Match Height to Terrain no longer freezes, and no longer reads the far side of the Earth.** A terrain tile
  is now read only where it is under the dataset. On the Autzen point cloud over Cesium World Terrain it
  took 66 s and found nothing; it takes 0.5 s and moves the cloud down 316 m (2.2 s over Google, same
  316 m). Terrain tiles on the other side of the globe lie under every place seen from above and were
  taken as the ground: they are left out, in Match Colors too.
- **Terrain blending: a new tile no longer stalls the view.** The coverage of a tile with large triangles
  took about 1.2 s since the tiles are drawn from their triangles; it takes about 0.25 s.
- **Color correction with raster overlays.** A tile whose color is an overlay (a terrain with imagery) showed
  uncorrected for up to 2.3 s after it loaded; it is corrected as the overlay arrives. **Match Colors** reads
  the overlays of the reference as they are drawn, and only the triangles that reach into the area compared.
- **Match to** is Blender's own object picker: a list with a search, and an eyedropper that takes a tile of
  the reference tileset in the 3D view, or its root Empty in the Outliner.
- **Boxes fold whether ticked or not**, as a Blender panel with a checkbox in its header: the content of an
  unticked box is shown greyed. Ticking a box opens it; boxes start folded.
- **Globe Navigation: the vertical resets itself.** After each move the Globe is levelled at the new scene
  origin, with every 3D view turned with it, so nothing changes on screen and the vertical never leans by more
  than the last few kilometres. *Reset Vertical* worked but the panel kept reading 0.03° off, a rounding
  error: it reads 0.00° now, and the button reports the angle before and after.
- **Globe Navigation: View Selected glides** over 0.3 s, and is also in the View menu and the panel as *Frame
  Selected (Globe)*. Blender's own *View > Frame Selected* moves the view but leaves the world at its scale.
- **Read feature metadata** is under *Property* only, once; its warning is no longer red.
- **Terrain blending: no holes in a dataset.** The coverage of a mesh tile is now always drawn from its
  triangles. A tile with many vertices on a building and a few large triangles on the flat ground beside it
  was drawn from its vertices alone, which left holes there: the dataset faded around them, as at its border.
- **Tilesets list: only the tile counts** on a row. The N or P of the backend and the pause icon are gone
  (the eye and the checkbox already say paused).
- **Properties** of a tileset (type, address, own Max SSE, root) are a box that folds, like the ones under it.
  **Markers - datasets locations** is a box with a checkbox and an arrow, like *Raster overlays* and *Clipping*.
- **Overlay library with a search box**: the bookmark button of the overlays opens a list that narrows down as
  you type.
- **Globe Navigation: numpad period** frames the selection like Blender's View Selected, and brings the world
  back to the scale that fits it. A dataset Empty is framed with its tiles, a marker with its dataset's size.
- **Reload Tiles with their Properties.** Ticking *Read feature metadata* while streaming used to leave
  "No property loaded yet" until Clear All Tiles and Start. A red line now says the tiles on screen were loaded
  without their properties, with one button that loads them again.
- **`max_km`** also leaves out the datasets whose size the server does not know.
- **Release workflow**: the platform zips read the wheel release with the job's token and download with
  retries. Two releases failed on GitHub's limit for anonymous clients and on one failed Blender download.

## 0.6.8 (2026-11-25)

- **Markers - datasets locations.** The two dataset settings have a box of their own in the main panel, always
  shown: *An Empty and a dot per dataset* and *Also the datasets not loaded yet (beta)*. A dot can be clicked:
  it selects the dataset's Empty. A dot behind a tile is drawn faint instead of vanishing as the dataset's
  tiles load, and a hidden dataset or tileset has none.
- **Dataset Empties on the ground.** A dataset whose bounding volume has its centre far above or under the
  ground (country-wide LiDAR in a projected grid: up to 2000 km up) gets its Empty on the ellipsoid there.
- **Terrain blending: no stale hole.** When no dataset is shown any more (hidden, stopped, removed), the terrain
  is whole again; it used to keep the last coverage. A dataset far from the last one gets a new frame.
- **Match to is a list of the other tilesets**, without the tileset itself.
- **3dtiled aggregate: `max_km=20`** in Parameters keeps the datasets up to 20 km wide. Two more public sets
  in the library picker: the open data that is 3D Tiles already, and the open scans up to 20 km wide.
- **Vertical off, in red.** When the vertical leans by half a degree or more after Globe Navigation, the first
  panel says so in red beside *Reset Vertical*, which now works with Globe Navigation off too.
- **A hidden tileset stops streaming.** Closing a tileset's eye in the list pauses it, as unticking it does.
- **URL overlays: `{q}` Bing quadkeys and `{0-3}` subdomain ranges** in a template.
- **Match Colors over the overlap only, in both directions, and to a corrected reference.** The area the two
  tilesets share is what is sampled, so Google can be matched to a small mesh. A reference with its own color
  correction is matched as it looks. Tiles get their color group as they are built. Gamma and Gain are two
  columns of R, G, B.
- **Match Height to Terrain, without terrain blending.** A button on every dataset entry that streams: the
  tileset moves up or down onto the terrain, Google or Bing 3D Tiles under it, by the median difference of
  their lowest heights. In a tileset of tilesets each dataset with tiles shown moves by its own amount. See
  [Heights and colors between tilesets](/features/height-references), which also has a diagram of the height
  references (ellipsoid, geoid, national datums) and what each background measured.
- **Color correction per tileset, and Match Colors.** A box under *Clipping*: exposure, gain and gamma per
  channel, saturation, contrast, in the tile materials. *Match Colors* fills gain and gamma from another
  tileset, sampled where the two overlap.
- **Entry type 3dtiled aggregate.** A set name of a 3dtiled server, or a manifest file that is sent to it on
  Start and answered with a set only the file's holders can open. The public open-data sets are in the
  library picker without a library file. See
  [A 3dtiled aggregate set](/features/several-tilesets#a-3dtiled-aggregate-set).
- **The per-tileset boxes fold.** *Raster overlays*, *Clipping*, *Color correction* and *Terrain blending
  (beta)* (renamed from *Blend datasets into this terrain*) get an arrow once ticked.
- Terrain blending: the settings diagram redrawn, with the two opacities against the distance.
- Fixed: a tileset of tilesets whose datasets span continents was taken for a background by terrain blending,
  so it got the *Terrain blending* box and did not blend into a terrain.
- **Terrain blending (beta): distances from the dataset's size, and Match Dataset Heights to Terrain.** The
  three distances follow the smallest dataset shown unless you untick *Distances from the dataset's size*. A
  button moves every dataset up or down onto the terrain, once. The coverage image follows the tiles at most
  every 3 seconds while navigating.
- **Max SSE in the first panel**, under Start / Stop, Freeze and Clear All Tiles. It is the same setting as in
  *LOD / Streaming*.
- **Terrain blending (beta).** A dataset shown over a globe, a terrain layer, Google or Bing 3D Tiles: the
  background becomes transparent under the dataset, and the dataset's border fades into it. Tick *Terrain
  blending* in the add-on preferences (Beta features), then *Blend datasets into this terrain* on the
  background entry. Live settings: *Dataset fade*, *Terrain inset*, *Terrain fade*, and *Keep terrain below*,
  which only removes the terrain that would poke through the dataset. See
  [Terrain blending](/features/beta#terrain-blending).
- **A hidden dataset stops streaming.** In an aggregate, closing the eye (or unticking) a dataset's collection, or
  closing the eye of its Empty, takes the dataset out of the selection: its tiles go, nothing more of it loads,
  and it comes back when shown again.
- **Dataset names from the `NAME` semantic.** A dataset's Empty is named after the property that carries the
  3D Tiles 1.1 semantic `NAME` in the aggregate's schema, whatever the property is called, before `name`,
  `title`, `scene` and `label`. Only a schema inside the `tileset.json` is read, not a `schemaUri`.
- **Dataset dots: none behind the globe.** A dot is left out when the Earth is between it and the eye.
- Adaptive point size also applies to point clouds under X-ray (it already did; the docs said otherwise).

## 0.6.7 (2026-11-25)

- **Point size: adaptive under finer tiles (beta).** In point clouds that add detail (Potree octrees through
  3dtiled, most LiDAR tilesets), a coarse tile's points now shrink where finer tiles are shown over them, per
  point, as Potree's adaptive size does. On by default in *Attenuated* and *Per tile*; the checkbox
  *Adaptive size under finer tiles*, under the radius fields of *Nodes: Geometry*. See
  [Point clouds](/features/point-clouds#adaptive-size-under-finer-tiles-beta).

- **X-ray on meshes, and one X-ray preset.** *X-ray* now applies to mesh tiles as well as point clouds and
  splats (a *Meshes* checkbox under its settings, ticked by default, leaves them out): every face adds its
  texture colour as light and hides nothing, so rooms, vaults and far walls show through. *Mesh edges* goes from
  a double exposure of the textures (0) to a line drawing of walls and outlines (3, the default). *X-ray Mono* is
  gone: the *Tint* slider does it, from the tiles' own colours (0) to one colour (1). One *Strength* for points,
  splats and meshes. See [X-ray on meshes](/features/point-clouds#x-ray-on-meshes).
- **Nodes: Material.** *Shared shader nodes* comes before the presets, and ticking it goes back to *Lit*.
- **Markers for every dataset of an aggregate (beta).** Under *An Empty per dataset*: an Empty for each dataset
  the aggregate's `tileset.json` lists, before any of its tiles, so *Scene Origin > Dataset* can go to any of them.
  See [Several tilesets](/features/several-tilesets#a-tileset-of-tilesets).
- **Scene origin, Auto: the first tileset of the list.** The origin goes to the first tileset that is ticked,
  visible and has a place, not to whichever answered first. Google, a terrain layer or the bare globe no longer
  fix the origin where the panel had it. The others wait up to 10 s for it.
- **Clipping.** *Keep inside any* is the default mode (it was *Cut inside any*: a tileset saved with clipping
  objects and the mode never touched now keeps what it used to cut; set the mode back once). *Clip to viewport
  region* is the first row of the Clipping box.
- **LOD / Streaming.** *Stream for* first, a *Settings* title over the sliders, and *Advanced* is now *Cache*,
  open by default, with *Viewport Performance* folded after it. *Cameras Along the Animation* is offered for the
  scene camera and a chosen camera too, and samples the chosen one.
- **Color tiles by Property, Elevation, Tile or Tileset.** *Property* is the former *Column*, with a new
  **feature id** entry: one colour per feature (a building, say). *Elevation* colours by height above the
  ellipsoid through the Color Ramp (range from the loaded tiles, or a custom one), in true metres at any world
  scale of the Globe. *Tile* gives every tile a random colour, *Tileset* one colour per tileset or per dataset of
  an aggregate. The last three need no metadata. *Tile* has three values, **Random**, **Level** and **Error**:
  the last two were entries of the property list (*tile level*, *tile error*) and needed *Read feature
  metadata*; a file saved with one of them picked goes back to the first property. Clicking a source ticks
  *Color tiles by*. *All columns as attributes* is now *Keep every property as an attribute*.
- Fixed: *Color tiles by > Tileset* could show every tileset in one colour in the viewport, and close hues for
  different tilesets. Hues are now spread, kept on each tileset's Empty, and the viewport redraws.
- **Datasets of an aggregate: a dot and a collection each.** Every dataset Empty gets a white dot in the 3D
  viewport, of a fixed size on screen (*Dot px* beside *An Empty per dataset*, 5 pixels by default), whatever
  the distance and the Globe scale, so small sites show from space: Blender draws an Empty no larger than a
  kilometre. Every dataset also gets its own collection under the tileset's, with its Empty and its tiles: its
  eye hides one dataset among overlapping ones.
- *Scene Origin* is open by default.
- The *Nodes* panels are in the order Geometry, Material, Metadata, Compositing. *Keep every property as an
  attribute* sits under *Read feature metadata*.
- **Sidebar.** A first panel, *OGC 3D Tiles*, has the status line and Start / Stop, Freeze, Clear All Tiles; the
  list is in *Tilesets* below it. *Max points / vertices* moved to *Viewport Performance*. The per-tileset
  statistics lines (visited, culled, ms per tile) are gone from LOD / Streaming.
- **Copy into project** is no longer a button under the tileset's URL: it downloads the whole tileset. The
  operator stays in the F3 search; Freeze keeps what is on screen.
- **X-ray settings.** *Strength* comes before *Tint*.
- **Nodes: Metadata.** *Color tiles by* is always shown. The voxel settings are a *Voxels* section, shown only
  with a voxel tileset.
- **Globe Navigation.** Typing a world scale resizes the Globe under a view that stays put (it used to move the
  view to match, so nothing seemed to happen). *To 1:1, keeping the view* is on its own row, the labels are beside
  the fields, and *Parent Selection to Globe* comes first.
- Fixed: 3D BAG, and other tiles with `EXT_meshopt_compression` and quantized positions, failed to load
  ("the model has 2 buffers").
- Fixed: Globe Navigation raised "matrix does not have an inverse" after an extreme world scale.
- **Datasets named from their metadata.** In a tileset of tilesets, a dataset's Empty, and so the list of
  *Scene Origin > Dataset*, takes the dataset's `name` from the aggregate's tile metadata when it has one,
  instead of a part of its URL (an identifier, for share links).
- **Globe Navigation: world scale as a multiplier too.** Two fields for the one value: ×0.01 and 1:100.
- Fixed: turning the shared shader nodes on or off while an X-ray look was on brought the tiles back opaque.
- **Sidebar layout.** The first panel is now *OGC 3D Tiles tilesets*. *Globe Navigation (beta)* is no longer a folded
  section: it is open whenever *Scene Origin* is. Its world scale is a number field: type N for 1:N and the world
  zooms about the point the view looks at, the view moving to match. In *Nodes: Material*, the Shadeless and X-ray checkboxes
  are gone, since the presets already set them; the X-ray strength and tint show while an X-ray look is on.
- **New library file:** the file dialog proposes `blender-ogc3dtiles-library.json`.

## 0.6.6 (2026-11-23)

- cesium-native-python: a wheel that is installed but does not load now says so, with the import error, instead of "Not installed"; the full traceback goes to the system console once. Installing from GitHub checks with a real import.
- *Reload* (and the install check) no longer drop an already loaded native module: doing so broke every later import in the session, and the backend read "Not installed" until Blender restarted.
- The add-on loaded before the wheel was installed picks up the native backend without a restart.
- Preferences say which build is installed: packaged (the wheel comes inside the extension, no download button) or Python-only (the wheel is downloaded from GitHub).

## 0.6.5 (2026-11-23)

- **Freeze Tiles** (button next to *Clear All Tiles*): the tiles shown now become plain objects, one per
  tileset and kind (meshes, points, splats), at the detail they have, with clipping volumes applied and
  their own copies of materials and textures. Then streaming stops and the live tiles go, or stay. See
  [Freeze and export](/features/rendering#freeze-and-export).
- **Export Frozen**: frozen tiles to glb or glTF (meshes with their textures, each photo stored once; clouds
  as points with their colours), PLY, or OBJ (meshes with their textures). Blender's exporters with their
  default settings write nothing for a cloud.
- **Material presets** (Nodes: Material panel): Lit, Shadeless, X-ray and X-ray Mono, one click for every
  tile. See [Presets](/features/nodes-material#presets).
- **Stream for: Cameras of a collection.** Every camera of a collection selects tiles at once, each at the
  render resolution, panoramic ones all around: two 360° panoramas, or the cameras *Cameras Along the
  Animation* places on a camera path (how many: the field beside its button), so the detail the whole path
  needs is loaded together (then frozen).
  cesium-native only. See [Several cameras](/features/lod-streaming#several-cameras-at-once).
- **X-ray for point clouds and Gaussian splats** (Nodes: Material panel). Every point adds a little light and
  hides nothing, so walls seen edge-on, vaults and the far side of a building show through, as on a
  radiograph. It is a shared shader group, `OGC3D X-ray`, in front of each point material: points keep the
  shape their display gives them. Splats become points while it is on, since Blender's splat renderer
  ignores materials. Needs a dark background. See [X-ray](/features/point-clouds#x-ray), and the clip on
  the [Videos](/guide/videos) page.
- **Point clouds are shaded by the scene's lights**, as mesh tiles are: sun, lamps, world and shadows act on
  them. Before, their colours were shown without any light. Files saved with an older version are shaded
  the same way when opened. See [Lighting](/features/point-clouds#lighting).
- **Shadeless** (Nodes: Material panel): every tile shows its colours without any light, for scans that carry
  their own. With the shared shader nodes it sets their Baked Light to 1. Off by default.
- The shared shader nodes now work on point clouds too: they took a flat grey instead of the point colours.
- Attenuated point size now stays between 4 and 12 px on screen by default (it was 1 to 3 px), and Screen
  pixels mode draws 4 px points.
- **A moved dataset has a selection of its own.** In a tileset of tilesets, each dataset moved by its Empty
  is selected in a separate pass for a camera moved the other way, limited to that dataset, and the main
  pass leaves it out. Nothing loads any more for the place the dataset was at, and 32 different offsets are
  followed instead of 6. This is how Cesium for Unreal and Unity handle a moved tileset.
- **Globe navigation: Reset Vertical.** The panel shows how far the ground under the view leans from
  Blender's +Z after a long way on the globe, and *Reset* levels it without changing the picture. The
  section is now unfolded in the Scene Origin panel.
- **Tileset libraries**: with no library file chosen, the bookmark button and *Save to library* now open a
  message with a button to the preferences, instead of a line in the status bar. Long names in the picker
  no longer push their row to the left of the others.
- **Installing the backend where Blender's folder is read-only** (Program Files, a system package): the wheel
  now goes to the Blender user folder and the install is checked. Before, it reported a success and the
  backend was still missing after a restart.
- Platform zips for extensions.blender.org start at Blender 5.0.
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
  the offset is kept per dataset URL with the scene. Level of detail and culling follow the offset (without
  that, a 100 m offset under a low camera lost 45% of the splats on screen). See [A tileset of tilesets](/features/several-tilesets#a-tileset-of-tilesets).
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
