---
title: "Slide decks"
description: "Two presentations of the add-on, live with a presenter view, and as PDFs"
---

Two decks, written as React pages with [open-slide](https://github.com/1weiho/open-slide) in the
repository's `slides/` folder, in the style of the open-geodata-catalog and Terrain Viewer decks.
They reuse this site's screenshots and are deployed with it. The PDFs are on the
[Media: slide decks](https://github.com/Iconem/blender_ogc3dtiles/releases/tag/slide-decks) release.

| Deck | What it covers | Live | PDF |
|---|---|---|---|
| **3D Tiles, streamed into Blender** · 29 pages | why, how it works, tiles as Blender objects, what streams, the sidebar, level of detail and tile bounds, the scene origin, the shared shader (albedo, clay, relight, X-ray), clipping, point clouds and the height reveal demo, splats, the beauty pass, cameras seen from above, converged animation, files and export, raster overlays, metadata, voxels, datasets tested, install | [present](https://iconem.github.io/blender_ogc3dtiles/slides/s/blender-3dtiles/) | [blender-3dtiles.pdf](https://github.com/Iconem/blender_ogc3dtiles/releases/download/slide-decks/blender-3dtiles.pdf) |
| **Under the hood** · 12 pages | the three layers, one tick of the modal operator, where the time goes, the two backends, the tile preparer, shared node groups, clipping in three layers, view states for each camera, the cesium-native-python wheels, tests and releases | [present](https://iconem.github.io/blender_ogc3dtiles/slides/s/under-the-hood/) | [under-the-hood.pdf](https://github.com/Iconem/blender_ogc3dtiles/releases/download/slide-decks/under-the-hood.pdf) |

![3D Tiles, streamed into Blender: the cover](/img/slides-blender-3dtiles.jpg)

[3D Tiles, streamed into Blender](https://iconem.github.io/blender_ogc3dtiles/slides/s/blender-3dtiles/)

![Under the hood: the cover](/img/slides-under-the-hood.jpg)

[Under the hood](https://iconem.github.io/blender_ogc3dtiles/slides/s/under-the-hood/)

## Presenting

Open a deck, then **F** for full screen and **P** for the presenter window: the current slide, the
next one, the speaker notes and a timer, kept in step with the audience window (both in the same
browser). Arrows, Space or Page Down move on; **O** shows every page. Every page has speaker notes.
The presenter window also opens at `.../s/<deck>/presenter/`.

The online decks are read-only: the inspector, its comments and the inline text edits write back to
the slide sources, so they only run with `pnpm dev` on a checkout.

## Working on them

`slides/` is a pnpm project of its own, next to `site/`:

```bash
pnpm --dir slides install
pnpm --dir slides dev       # the editor, with inspector and comments: http://localhost:3211
pnpm --dir slides static    # the static site as it will be online: http://localhost:4180/blender_ogc3dtiles/slides/
pnpm --dir slides pdf       # the static site and one PDF per deck, in slides/.site/
pnpm --dir slides shots     # the cover of each deck as docs/img/slides-<deck>.jpg, for this page (static site up)
```

Each deck is one file, `slides/slides/<deck>/index.tsx`: one React component per page, the speaker
notes in `notes`. The screenshots are the repository's `docs/img`, shown by URL
(`slides/assets/shots.ts`): the deployed decks read them from this site's `/img/`, the dev and static
servers serve the folder themselves, so the repository holds each picture once. A push to `main` that
touches `slides/`, `site/` or `docs/` runs the *docs site* workflow, which builds both and deploys
them to GitHub Pages, and replaces the PDFs on the `slide-decks` release. Neither the built decks nor the
PDFs are ever committed.
