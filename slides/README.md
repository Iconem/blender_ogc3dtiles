# Slide decks

[open-slide](https://github.com/1weiho/open-slide) decks: one React file per deck in `slides/<deck>/index.tsx`,
1920 x 1080 pages, speaker notes in `notes`. Screenshots are the repository's `docs/img`, imported as
`@assets/img/<file>` and copied in by `scripts/sync-assets.mjs` (git-ignored here).

```
pnpm install
pnpm dev       # http://localhost:3211, with the inspector and inline edits
pnpm pdf       # static site in .site/, one PDF per deck in .site/pdf/
```

`.github/workflows/docs.yml` publishes them under `/blender_ogc3dtiles/slides/` of the docs site.
