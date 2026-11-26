export const appName = 'OGC 3D Tiles for Blender';

// Pages sit at the app's own root; the app itself is mounted under basePath (next.config.mjs).
export const docsRoute = '/';

// Needed wherever a URL is handed to something outside the Next router: the static search index.
export const basePath = process.env.SITE_BASE ?? '/blender_ogc3dtiles';

// The repository lives on two accounts and each has its own Pages site: the workflow passes the owner it runs for
// (PAGES_OWNER), so links to the deck and to the repository stay on the reader's side.
const owner = process.env.PAGES_OWNER || 'jo-chemla';
// Iconem's site has its own domain, at the root; any other owner's is a GitHub project site under basePath.
export const pagesHost = owner.toLowerCase() === 'iconem' ? 'https://blender-3dtiles.iconem.com' : `https://${owner.toLowerCase()}.github.io`;

// The site search engines should index: the other Pages site names it as canonical.
export const canonicalHost = 'https://blender-3dtiles.iconem.com';

/** Pages write links to one of the sites; on another owner's site they point at that one. */
export function ownHost(href?: string): string | undefined {
  return href?.replace(/https:\/\/(?:(?:jo-chemla|iconem)\.github\.io\/blender_ogc3dtiles|blender-3dtiles\.iconem\.com)(?=\/|$)/, `${pagesHost}${basePath}`);
}

export const gitConfig = {
  user: owner,
  repo: 'blender_ogc3dtiles',
  branch: 'main',
};
