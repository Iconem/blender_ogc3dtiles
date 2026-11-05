import type { OpenSlideConfig } from '@open-slide/core';

// SLIDES_BASE: the sub-path the built decks are served from (.github/workflows/docs.yml puts them at
// /blender_ogc3dtiles/slides/, inside the docs site); "/" for dev and local previews.
const openSlideConfig: OpenSlideConfig = {
  base: process.env.SLIDES_BASE ?? '/',
  port: 3211,
};

export default openSlideConfig;
