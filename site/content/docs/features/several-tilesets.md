---
title: "Several tilesets"
description: "Lists of tilesets, entry types, ion, globe, terrain"
---

The sidebar opens on the **3D Tiles** tab when Blender starts or a file loads (a
preference turns that off). It holds a list of tilesets (add / remove, per-entry type, source
and SSE).  An entry is one of three types: **3D Tiles** (a `tileset.json`
URL or local path), **Cesium ion** (asset id and access token; the token is
only sent to Cesium ion) or **WGS84 globe** (cesium-native's procedural
ellipsoid, a bare globe to drape imagery on).  Each entry has a *Raster
overlays* checkbox, off for 3D Tiles and ion entries and switched on when
the type becomes globe; the overlay list only shows when it is ticked, and
ticking it while streaming adds or removes the overlays live.  Ion and globe
entries need the cesium-native backend.

![Entry types: WGS84 globe with an OpenStreetMap overlay, 3D Tiles URL with overlays off, Cesium ion asset](/img/tileset_types.png)

Every entry becomes its own stream with its own backend instance,
download manager, root Empty (`3D Tiles · <name>`) and sub-collection
(`Tiles · <name>`), all sharing the scene origin and the viewport camera.
Moving, rotating or scaling a root Empty is honoured by culling and SSE for
that tileset only.

Per row: the checkbox **pauses** the stream (nothing is loaded or evicted,
loaded tiles stay as they are), the eye hides its sub-collection (same as the
outliner).  Entries added, ticked or removed while streaming are picked up on
the next tick.  **Max SSE** (LOD / Streaming sub-panel) is the live renderer setting for
every stream; tick *Own SSE* on an entry to override it for that tileset.  It compares
the error a tile declares, in pixels, so what a value looks like depends on the data and
its tiler.  At 8 px on Google tiles the median triangle edge was 3.3 px.  On a COPC point
cloud declaring more error than its point spacing, 1.2 px between points at 3.2 px of error,
16 to 32 px may be enough.
Both re-select immediately on both backends.  *Start* discards the tiles a
previous *Stop* left on screen (they belong to a dead selection).  Two
entries with the same label get separate collections (`… - 2`; the list
entry is renamed to match).  Editing the URL of a running entry restarts
that stream with the new URL.  **+** adds an empty entry (or one prefilled
from the URL field when that URL is not in the list yet); share links
(`/s/<token>/<asset>.json`) are labelled by the asset, never by the token.

Load order (Python backend): the tree is walked with a stack (depth-first)
but every requested tile goes into one queue that is sorted before download,
so the walk order does not matter.  The sort key is depth first (all missing
ancestors before any deeper tile), then CesiumJS-style foveated: shallow tiles first,
then by screen-space error weighted towards the view centre (*Foveation
cone* = fraction of the view half-angle); *Edge SSE relax* > 0 additionally
lets the periphery stay coarser.  cesium-native orders its own queue the same
way internally.  "Hide relation lines" (Nodes: Geometry sub-panel) switches off the
dashed object→parent overlay in every 3D viewport on Start — it is a
per-viewport overlay, Blender has no per-object switch.
