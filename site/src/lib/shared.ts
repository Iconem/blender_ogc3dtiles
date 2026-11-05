export const appName = 'OGC 3D Tiles for Blender';

// Pages sit at the app's own root; the app itself is mounted under basePath (next.config.mjs).
export const docsRoute = '/';

// Needed wherever a URL is handed to something outside the Next router: the static search index.
export const basePath = '/blender_ogc3dtiles';

// The repository lives on two accounts and each has its own Pages site: the workflow passes the owner it runs for
// (PAGES_OWNER), so links to the deck and to the repository stay on the reader's side.
const owner = process.env.PAGES_OWNER || 'jo-chemla';
export const pagesHost = `https://${owner.toLowerCase()}.github.io`;

/** Pages write links to the jo-chemla site; on another owner's site they point at that one. */
export function ownHost(href?: string): string | undefined {
  return href?.replace('https://jo-chemla.github.io', pagesHost);
}

export const gitConfig = {
  user: owner,
  repo: 'blender_ogc3dtiles',
  branch: 'main',
};
