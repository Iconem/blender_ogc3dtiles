import { createMDX } from 'fumadocs-mdx/next';
import { fileURLToPath } from 'url';

const withMDX = createMDX();

// Static export for GitHub Pages, where a project site lives under /<repository name>/ (the same name on both
// remotes: jo-chemla.github.io/blender_ogc3dtiles and iconem.github.io/blender_ogc3dtiles). basePath is set in dev
// too, so `pnpm dev` has the URL shape of the deployed site.
/** @type {import('next').NextConfig} */
const config = {
  output: 'export',
  reactStrictMode: true,
  basePath: '/blender_ogc3dtiles',
  assetPrefix: '/blender_ogc3dtiles',
  trailingSlash: true,          // Pages serves directories: /features/clipping/index.html
  images: { unoptimized: true },
  turbopack: { root: fileURLToPath(new URL('.', import.meta.url)) },
};

export default withMDX(config);
