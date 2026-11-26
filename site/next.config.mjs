import { createMDX } from 'fumadocs-mdx/next';
import { fileURLToPath } from 'url';

const withMDX = createMDX();

// Static export for GitHub Pages, where a project site lives under /<repository name>/ (the same name on both
// remotes: jo-chemla.github.io/blender_ogc3dtiles and iconem.github.io/blender_ogc3dtiles). basePath is set in dev
// too, so `pnpm dev` has the URL shape of the deployed site.
// SITE_BASE: "" for the Iconem site, which has its own domain (blender-3dtiles.iconem.com); the workflow sets it.
const base = process.env.SITE_BASE ?? '/blender_ogc3dtiles';

/** @type {import('next').NextConfig} */
const config = {
  output: 'export',
  reactStrictMode: true,
  basePath: base || undefined,
  assetPrefix: base || undefined,
  env: { SITE_BASE: base, PAGES_OWNER: process.env.PAGES_OWNER ?? '' },   // read by src/lib/shared.ts, in the browser too
  trailingSlash: true,          // Pages serves directories: /features/clipping/index.html
  images: { unoptimized: true },
  turbopack: { root: fileURLToPath(new URL('.', import.meta.url)) },
};

export default withMDX(config);
