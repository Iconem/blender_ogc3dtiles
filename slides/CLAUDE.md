# open-slide — Agent Guide

You are authoring **slides** in this repo. Every slide is arbitrary React code that you write.

## Hard rules

- Put your slide under `slides/<kebab-case-id>/`.
- The entry is `slides/<id>/index.tsx`.
- Put slide-specific images/videos/fonts under `slides/<id>/assets/`. For assets reused across decks or themes (logos, avatars), use the global `assets/` folder and import via `@assets/...`. The repository's screenshots (`../docs/img`) are not imported: `shot('sidebar.jpg')` from `@assets/shots` gives their URL under `/blender_ogc3dtiles/img/` (served in dev by `scripts/dev.mjs`, by `scripts/publish.mjs` for the static site, by the docs site once deployed).
- Never put tileset URLs, share links, dataset hosts or API keys (Google, Cesium ion) on a slide or in a screenshot.
- Do **not** touch `package.json`, `open-slide.config.ts`, or other slides.
- Do not add dependencies. Use only `react` and standard web APIs.
- Match the existing decks: the same deck kit at the top of each file, short factual lines, no marketing words.

## Which skill to use

- **Drafting a new deck** — use the `create-slide` skill. It walks through scoping questions, structure, and hand-off.
- **Applying inspector comments** (`@slide-comment` markers in a page) — use the `apply-comments` skill.
- **Creating or extracting a theme** — use the `create-theme` skill. Themes live as markdown under `themes/<id>.md` and are read by `create-slide` before authoring.
- **Resolving "this page" / "this element"** — when the user references the current slide or selection without naming it, consult the `current-slide` skill. It reads the dev server's `node_modules/.open-slide/current.json` to find which slide, page, and inspector-picked element they mean.
- **Writing a speech script / speaker notes** — use the `notes` export in the slide's `index.tsx`, index-aligned with the page array and shown in the presenter view. See the **Speaker notes** section of the `slide-authoring` skill. Never deliver a script as a markdown or text file.
- **Any other slide edit** — read the `slide-authoring` skill before writing. It is the technical reference for everything inside `slides/<id>/`: file contract, the 1920×1080 canvas, type scale, palette, layout, assets, self-review checklist, and anti-patterns.

Keep this file short: hard rules only. All deeper guidance lives in the skills above.

## Updating skills

The skills in `.agents/skills` are managed by `@open-slide/core`. Do not edit them in place. To pull the latest versions:

```
pnpm up @open-slide/core
pnpm sync:skills
```
