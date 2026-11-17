// The repository's screenshots (docs/img), by URL rather than imported: the published decks sit inside the docs site,
// at /blender_ogc3dtiles/slides/, and the docs site already serves the same files at /blender_ogc3dtiles/img/
// (site/scripts/sync-content.mjs copies them in). An import would make Vite emit a hashed copy of each into the
// slides build, a second copy in the Pages artifact. In dev, scripts/dev.mjs serves docs/img at that path; the static
// site of scripts/publish.mjs serves it too. A deck published elsewhere sets VITE_SCREENSHOTS_BASE to the full URL of
// the folder, e.g. https://jo-chemla.github.io/blender_ogc3dtiles/img/.
const base: string = import.meta.env.VITE_SCREENSHOTS_BASE ?? '/blender_ogc3dtiles/img/';

export const shot = (file: string) => `${base}${file}`;
