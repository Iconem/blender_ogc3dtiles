# Slide decks

[open-slide](https://github.com/1weiho/open-slide) decks: one React file per deck in `slides/<deck>/index.tsx`,
1920 x 1080 pages, speaker notes in `notes`.

- `blender-3dtiles`: the add-on, for Blender users and for the 3D Tiles crowd.
- `under-the-hood`: how it works inside.

Screenshots are the repository's `docs/img`, shown by URL through `shot()` in `assets/shots.ts` (no copy, no import):
the deployed decks read them from the docs site's `/blender_ogc3dtiles/img/`, and `scripts/dev.mjs` and
`scripts/publish.mjs` serve `docs/img` at that path locally.

```
pnpm install
pnpm dev       # http://localhost:3211, with the inspector, comments and inline edits
pnpm static    # the static site as it will be online: http://localhost:4180/blender_ogc3dtiles/slides/
pnpm pdf       # static site in .site/, one PDF per deck in .site/pdf/
pnpm shots     # with `pnpm static` running: each deck's cover as docs/img/slides-<deck>.jpg for the docs
```

`.github/workflows/docs.yml` publishes them under `/blender_ogc3dtiles/slides/` of the docs site. The docs page is
`site/content/docs/guide/slide-decks.md`. Agent skills for authoring decks are in `.agents/skills` (`pnpm sync:skills`
updates them from `@open-slide/core`).
