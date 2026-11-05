---
title: "Libraries and local files"
description: "Local and network tilesets, the disk cache, tileset libraries, copying a tileset into the project"
---

## Local files and network shares

The URL field of an entry takes any of:

- a URL;
- a plain path: `C:\data\site\tileset.json`, `\\nas\share\site\tileset.json`;
- a path relative to the .blend: `//tilesets/site/tileset.json`.

The folder button next to the field opens Blender's file browser; type `\\server\share` in its path
field to reach a share. With *Relative Path* ticked it stores a path relative to the .blend.

Files are read from disk every time and never cached, so a tileset on a network share is slow to
revisit. For heavy use, copy it into the project (below).

A drive letter mapped to a share (`Z:`) is stored as the share itself, so the entry also works on a
computer that maps the share to another letter. *Mapped drives as UNC* in the preferences turns that
off.

## Disk cache

Downloads are kept in a cache on disk, so coming back to a place is fast. The add-on preferences
hold:

- **Cache folder**: by default `%LOCALAPPDATA%\blender_ogc3dtiles\cache`. Keep it on a local disk.
- **Cache size cap** (GB): the least recently used downloads are dropped when the first stream of a
  session starts, or with the brush button.

What to expect:

- A download is kept only when its server allows caching.
- Google Photorealistic 3D Tiles use addresses that change with every session, so they are downloaded
  again in a new session.
- The cache holds what was downloaded (tilesets, tiles, imagery), not Blender meshes.

## Tileset libraries

A library is a JSON file listing tilesets ready to stream, with their URLs and keys. Keep a personal
one, share a team one on the NAS: the preferences take several files, separated by `;`.

- The **bookmark button** under the tileset list adds an entry from a library, through a search box.
  It can show only meshes, point clouds, splats or voxels.
- **Save to library** writes the selected entry under its name: URL, type, ion id and token, SSE, its
  overlays and their keys. An entry of the same name is replaced.
- **Edit ... in a text editor**, in the preferences, opens a library file.

A .blend keeps the URL of an entry once added, so it still opens if the library changes.

A library can also hold raster overlay presets, in an `overlays` list next to `tilesets`. They show
in the bookmark menu of the overlay list: that is the place for overlays that need a key.

```json
{
  "version": 1,
  "tilesets": [
    {"name": "My site", "kind": "TILESET", "url": "https://example.com/site/tileset.json",
     "group": "Sites", "content": "MESH"}
  ],
  "overlays": [
    {"name": "Google satellite", "kind": "GOOGLE", "key": "YOUR_KEY", "layer": "satellite"}
  ]
}
```

## Copy into project

*Copy into project* downloads the selected tileset into a folder, by default `//tilesets/<name>` next
to the .blend.

- **Crop** to the bounding box of an object. A flat object crops its footprint at any height.
- **Finest error** stops at a level of detail, given as a geometric error in metres.
- A second run resumes and skips the files already there.
- **Stream the copy** points the entry at the copy when it is done.

Keys and share-link tokens are never written into the copy. Cesium ion assets work. Google tiles
work too, but Google's terms forbid storing them offline: keep such copies to tests.

## Details

- cesium-native reads local files through `file:` URLs: `file:///C:/x/tileset.json`, and
  `file:////nas/share/x/tileset.json` with four slashes for a share. Plain paths are converted when
  the stream starts.
- The cache is cesium-native's sqlite cache of HTTP responses. A response is stored when it carries
  `Cache-Control: max-age`, a future `Expires`, or an `ETag` / `Last-Modified`. The binding keeps at
  most 4096 responses. sqlite locking over SMB is unreliable, and the cache keys include share-link
  tokens: two more reasons to keep it local.
- A library file is re-read just before *Save to library* writes it, and replaced atomically.
- A copy follows external tilesets. Implicit tilesets (quadtree or octree) are written as explicit
  ones; S2 volumes and subtree metadata are not supported. The copy's `export.json` records only the
  scheme, host and file name of the source.
