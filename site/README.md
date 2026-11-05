# Documentation site

A [Fumadocs](https://fumadocs.dev) static site, deployed to GitHub Pages by `.github/workflows/docs.yml`.

- `content/docs/index.md`, `guide/`, `features/`, `dev/*.md`: the pages, written here.
- `content/docs/dev/notes/` and `public/img/`: copied from `../docs/*.md` and `../docs/img` at build time by
  `scripts/sync-content.mjs`. Edit those in `../docs`, never here (both folders are git-ignored).
- Pages are `.md` (CommonMark), so `{z}/{x}/{y}` needs no escaping; ```` ```mermaid ```` fences are drawn at build time.
- The sidebar order is each folder's `meta.json`.

```
pnpm install
pnpm dev      # http://localhost:3210/blender_ogc3dtiles/
pnpm build    # static export in out/
```
