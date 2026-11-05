---
title: "Libraries and local files"
description: "Local and NAS tilesets, the cache, tileset libraries, copies"
---

**Local files and NAS shares.** cesium-native's curl does not accept bare
paths. Measured with the binding: `C:\x\tileset.json`, `\\nas\share\...` and
`file://nas/share/...` all fail. `file:///C:/x/tileset.json` and
`file:////nas/share/x/tileset.json` (four slashes for UNC) work, and relative
content URIs resolve against both. The URL field therefore takes any of:
- a URL;
- a plain path (`C:\...`, `\\nas\share\...`);
- a blend-relative `//tilesets/site/tileset.json`.

Plain and blend-relative paths are turned into the working `file:` form when
the stream starts. The folder button next to the URL opens Blender's file
browser (type `\\server\share` in its path field to reach a share). With
*Relative Path* ticked it stores a blend-relative path. Otherwise it stores a
`file:` URL, with mapped drives (`Z:`) replaced by their UNC share (see
*Mapped drives as UNC* in Preferences), so the entry works on machines that
map the share to another letter. `file:` reads are never cached (see below),
so a NAS tileset is read over the network every time it streams. Copy it
into the project for heavy use.

**Disk cache.** cesium-native caches HTTP responses in an sqlite file:
`tileset.json`, tile content (b3dm, glb, pnts) and imagery, as downloaded,
not decoded meshes. It stores a response only when the server allows it:
`Cache-Control: max-age`, a future `Expires`, or an `ETag` /
`Last-Modified` to revalidate with. The cache key is the full URL, so
Google's per-session URLs miss across sessions. The binding keeps at most
4096 responses. Preferences hold the **Cache folder** (default
`%LOCALAPPDATA%\blender_ogc3dtiles\cache`) and a **Cache size cap** (GB). The
cap is enforced least-recently-used first when the first stream of a session
starts, or with the brush button. Keep the cache on a local disk: sqlite
locking over SMB is unreliable, and the keys include share-link tokens.
Private databases left by other Blender processes are deleted after a day.

**Tileset libraries.** Preferences list one or more JSON files
(`;`-separated), for example a personal one and a team one on the NAS.
*Save to library* writes the active entry (URL, type, ion id / token, SSE,
overlays and their keys) under its name, replacing an entry of the same
name. It re-reads the file just before writing and replaces it atomically.
The bookmark button under the tileset list adds an entry from any library
through a search popup, optionally only meshes, point clouds, splats or voxels (an entry's
`content` field, else guessed from its words). A .blend keeps the entry's URL once added, so it
still opens if the library entry goes away. The preferences have an *Edit ... in a text
editor* button per library file; besides `tilesets`, a file can hold `overlays`, the raster
overlay presets of the overlay list's bookmark button (same fields as an entry's own overlays).

**Copy into project.** It copies the active tileset (explicit tilesets,
external tilesets followed) into a folder, by default
`//tilesets/<name>` next to the .blend. It can crop to the bounding box of an
object; a flat object crops its footprint at any height. It can also stop at
a coarsest *Finest error* (geometric error in metres, which drops deeper
levels). Kept tiles are downloaded in parallel. A re-run resumes and skips
files already there. *Stream the copy* points the entry at it when done.
Query strings and share-link tokens are never written into the copy (its
`export.json` records only scheme, host and file name). Google tiles work
(the `key` and `session` parameters are carried down the tree, never written;
Google's terms forbid storing tiles offline, so keep such copies to tests),
as do Cesium ion assets (resolved with the entry's token, which never lands
on disk). Implicit tilesets (quadtree / octree, binary or JSON subtrees) are
written out as explicit ones, cropped while walking the subtrees; S2 volumes
and subtree metadata are not supported.
