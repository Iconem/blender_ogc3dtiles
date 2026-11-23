#!/usr/bin/env node
// Keeps heavy media out of git: a blob in history stays in every clone for good. Run by the docs workflow on every
// push, and by hand: `node scripts/check-media.mjs`.
//
// Where the files go instead: the docs screenshots (docs/img) on the "Media: screenshots" release and the docs clips
// (docs/video) on "Media: videos", both through scripts/docs-media.mjs; the deck PDFs on "Media: slide decks"; the
// full-length demo videos on their own release. Only the README's pictures stay in docs/img, since GitHub shows the
// README from git.
import { execFileSync } from "node:child_process"
import { statSync } from "node:fs"

const MEDIA = /\.(png|jpe?g|webp|gif|avif|mp4|webm|mov|mkv|mp3|wav|zip|tar|gz|7z|pdf|tiff?|glb|gltf|b3dm|pnts|bin|blend|las|laz|ply|spz|exr)$/i
const VIDEO = /\.(mp4|webm|mov|mkv)$/i
const README_IMG = new Set(["docs/img/rome_google_3dtiles.jpg", "docs/img/sidebar.jpg"])
const MAX_FILE = 800e3 // one recompressed picture fits; a raw screenshot or a clip does not
const MAX_TOTAL = 3e6 // every tracked media file together

const files = execFileSync("git", ["ls-files", "-z"], { encoding: "utf8", maxBuffer: 64e6 }).split("\0").filter(Boolean)
const problems = []
let total = 0
for (const f of files) {
  if (f.startsWith("docs/img/") && !README_IMG.has(f)) { problems.push(`${f}: docs/img lives on the "Media: screenshots" release (node scripts/docs-media.mjs push screenshots)`); continue }
  if (f.startsWith("docs/video/") || VIDEO.test(f)) { problems.push(`${f}: videos live on releases (node scripts/docs-media.mjs push videos)`); continue }
  if (!MEDIA.test(f)) continue
  let size = 0
  try { size = statSync(f).size } catch { continue }
  total += size
  if (size > MAX_FILE) problems.push(`${f}: ${Math.round(size / 1e3)} KB, over ${MAX_FILE / 1e3} KB (recompress it, or put it on a release)`)
}
// Private data never goes in git: the Iconem dataset manifest (kept in %LOCALAPPDATA%\blender_ogc3dtiles\private)
// and real Iconem share links, which open the data to anyone who has them.
for (const f of files) {
  if (/iconem_manifest[^/]*\.json$|(^|\/)private\//i.test(f)) problems.push(`${f}: private data, keep it out of git`)
}
try {
  const hits = execFileSync("git", ["grep", "-I", "-l", "-E", "api\.iconem\.com/s/[A-Za-z0-9_-]{16,}"], { encoding: "utf8" })
  for (const f of hits.split("\n").filter(Boolean)) problems.push(`${f}: contains an Iconem share link, keep it out of git`)
} catch {} // git grep exits 1 when nothing matches
if (total > MAX_TOTAL) problems.push(`tracked media add up to ${(total / 1e6).toFixed(1)} MB, over ${MAX_TOTAL / 1e6} MB`)
if (problems.length) {
  console.error("check-media: files that must not be in git\n  " + problems.join("\n  "))
  process.exit(1)
}
console.log(`check-media: ${files.length} files, media ${(total / 1e6).toFixed(1)} MB, all under the limits`)
