// Copies into the site what lives elsewhere in the repository, at build time, so nothing is kept twice:
//   ../docs/img/*      -> public/img/            (the screenshots; ../scripts/docs-media.mjs pulls them from a release)
//   ../docs/video/*    -> public/video/          (the clips of the Videos page, pulled the same way)
//   ../docs/<note>.md  -> content/docs/dev/notes (long developer notes, edited in ../docs only)
// Both targets are git-ignored. The other pages of content/docs are written by hand and committed.
import { cpSync, existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const site = join(dirname(fileURLToPath(import.meta.url)), '..');
const repo = join(site, '..');
const GH = 'https://github.com/Iconem/blender_ogc3dtiles/blob/main';

// note file -> [slug, title when the file's first heading is not wanted as is]
const NOTES = [
  ['clipping.md', 'clipping'],
  ['voxels.md', 'voxels'],
];

rmSync(join(site, 'public', 'img'), { recursive: true, force: true });
cpSync(join(repo, 'docs', 'img'), join(site, 'public', 'img'), { recursive: true, filter: (f) => !f.endsWith('.media-sha') });
rmSync(join(site, 'public', 'video'), { recursive: true, force: true });
if (existsSync(join(repo, 'docs', 'video'))) cpSync(join(repo, 'docs', 'video'), join(site, 'public', 'video'), { recursive: true, filter: (f) => !f.endsWith('.media-sha') });

const out = join(site, 'content', 'docs', 'dev', 'notes');
rmSync(out, { recursive: true, force: true });
mkdirSync(out, { recursive: true });
for (const [file, slug] of NOTES) {
  let text = readFileSync(join(repo, 'docs', file), 'utf8').replace(/\r\n/g, '\n');
  const heading = text.match(/^# (.+)$/m);
  const title = heading ? heading[1].trim() : slug;
  if (heading) text = text.replace(heading[0], '');
  text = text
    .replaceAll('](img/', '](/img/')
    .replaceAll('](../README.md', `](${GH}/README.md`)
    .replace(/\]\((clipping|voxels)\.md/g, '](/dev/notes/$1')
    .replace(/\]\(\.\.\/(src|scripts|tests)\//g, `](${GH}/$1/`);
  writeFileSync(join(out, `${slug}.md`), `---\ntitle: ${JSON.stringify(title)}\n---\n${text}`);
}
writeFileSync(join(out, 'meta.json'), JSON.stringify({ title: 'Notes', pages: NOTES.map(([, slug]) => slug) }, null, 2) + '\n');
console.log(`synced ${NOTES.length} notes, docs/img and docs/video`);
