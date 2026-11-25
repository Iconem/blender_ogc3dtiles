#!/usr/bin/env node
// The docs' screenshots and video clips live on two GitHub releases of Iconem/blender_ogc3dtiles, not in git: every
// retake used to add its full weight to the history for good. Each set has a tracked lock file naming the archive the
// commit wants (content-addressed: <set>-<sha256 prefix>.tar), and this script brings the folder in line with it.
//
//   set          folder      release (tag)                   lock
//   screenshots  docs/img    "Media: screenshots" (media-screenshots)  docs/media-screenshots.lock
//   videos       docs/video  "Media: videos" (media-videos)            docs/media-videos.lock
//
//   node scripts/docs-media.mjs pull [set]            download and unpack the sets (all by default) not at their lock
//   node scripts/docs-media.mjs pull [set] --strict   same, and fail the process when it cannot (CI builds)
//   node scripts/docs-media.mjs push <set>            pack the folder, upload it to the release (gh), rewrite the lock
//   node scripts/docs-media.mjs status                say whether each folder matches its lock
//
// The files of a folder that git tracks (the README's two pictures in docs/img) stay in git: they are left out of the
// archive and never deleted by a pull. `pull` runs before the docs and slides dev servers and builds. After a retake:
// `push screenshots`, then commit the lock with the pages that use the picture. Old archives stay on the release, so
// an older commit still builds.
import { createHash } from "node:crypto"
import { createReadStream, createWriteStream, existsSync } from "node:fs"
import { mkdir, readFile, readdir, rename, rm, stat, writeFile } from "node:fs/promises"
import { execFileSync } from "node:child_process"
import { dirname, join, resolve } from "node:path"
import { fileURLToPath } from "node:url"
import { Readable } from "node:stream"
import { pipeline } from "node:stream/promises"

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..")
const DOCS = join(ROOT, "docs")
const CACHE = join(ROOT, ".cache", "docs-media")
const REPO = "Iconem/blender_ogc3dtiles"
const SETS = {
  screenshots: {
    folder: "img", tag: "media-screenshots", title: "Media: screenshots",
    notes: "The screenshots of the docs site and the slide decks, as content-addressed tar archives (screenshots-<sha256 prefix>.tar). docs/media-screenshots.lock in the repository names the one a commit uses; scripts/docs-media.mjs pulls and pushes them. Older archives stay so older commits still build.",
  },
  videos: {
    folder: "video", tag: "media-videos", title: "Media: videos",
    notes: "The short clips of the docs site's Videos page, as content-addressed tar archives (videos-<sha256 prefix>.tar). docs/media-videos.lock in the repository names the one a commit uses; scripts/docs-media.mjs pulls and pushes them. Older archives stay so older commits still build.",
  },
}
const STAMP = ".media-sha"

const args = process.argv.slice(2).filter((a) => !a.startsWith("--"))
const mode = args[0] ?? "pull"
const strict = process.argv.includes("--strict")
const only = args[1]
if (only && !SETS[only]) { console.error(`docs-media: unknown set "${only}" (${Object.keys(SETS).join(", ")})`); process.exit(1) }
const sets = only ? [only] : Object.keys(SETS)

const sha256 = (file) => new Promise((ok, ko) => {
  const h = createHash("sha256")
  createReadStream(file).on("data", (d) => h.update(d)).on("end", () => ok(h.digest("hex"))).on("error", ko)
})
const paths = (name) => {
  const dir = join(DOCS, SETS[name].folder)
  return { dir, lock: join(DOCS, `media-${name}.lock`), stamp: join(dir, STAMP) }
}
const readLock = async (name) => { const f = paths(name).lock; return existsSync(f) ? JSON.parse(await readFile(f, "utf8")) : null }
const readStamp = async (name) => { const f = paths(name).stamp; return existsSync(f) ? (await readFile(f, "utf8")).trim() : null }
// the folder's files that git tracks, relative to the folder: kept out of the archive, never removed
function tracked(name) {
  try {
    const out = execFileSync("git", ["ls-files", "-z", "--", `docs/${SETS[name].folder}`], { cwd: ROOT, encoding: "utf8" })
    return new Set(out.split("\0").filter(Boolean).map((f) => f.slice(`docs/${SETS[name].folder}/`.length)))
  } catch { return new Set() }
}
async function untrackedFiles(name) {
  const { dir } = paths(name)
  if (!existsSync(dir)) return []
  const keep = tracked(name), found = []
  const walk = async (sub) => {
    for (const e of await readdir(join(dir, sub), { withFileTypes: true })) {
      const rel = sub ? `${sub}/${e.name}` : e.name
      if (e.isDirectory()) await walk(rel)
      else if (rel !== STAMP && !keep.has(rel)) found.push(rel)
    }
  }
  await walk("")
  return found.sort()
}
// relative paths and a cwd: GNU tar (Git Bash) reads "C:\..." as a remote host
const tar = (tarArgs, cwd) => execFileSync("tar", tarArgs, { cwd, stdio: ["ignore", "inherit", "inherit"] })
const upTo = (from) => "../".repeat(from.slice(ROOT.length + 1).split(/[\\/]/).length)

async function pull(name) {
  const lock = await readLock(name)
  const { dir, stamp } = paths(name)
  if (!lock) { console.log(`docs-media: no docs/media-${name}.lock, nothing to pull`); return }
  if ((await readStamp(name)) === lock.sha256) { console.log(`docs-media: ${name} at ${lock.sha256.slice(0, 12)} (${lock.files} files), up to date`); return }
  await mkdir(CACHE, { recursive: true })
  const archive = join(CACHE, lock.asset)
  if (!existsSync(archive) || (await sha256(archive)) !== lock.sha256) {
    const url = `https://github.com/${REPO}/releases/download/${lock.release}/${lock.asset}`
    console.log(`docs-media: downloading ${lock.asset} (${Math.round(lock.size / 1e6)} MB) from the ${lock.release} release`)
    const res = await fetch(url)
    if (!res.ok || !res.body) throw new Error(`HTTP ${res.status} for ${url}`)
    await pipeline(Readable.fromWeb(res.body), createWriteStream(archive))
    const got = await sha256(archive)
    if (got !== lock.sha256) { await rm(archive, { force: true }); throw new Error(`checksum mismatch for ${lock.asset}: ${got}`) }
  }
  // a clean folder (a retake may have removed a picture), the tracked files aside
  await mkdir(dir, { recursive: true })
  for (const f of await untrackedFiles(name)) {
    try { await rm(join(dir, f), { force: true }) } catch { console.warn(`docs-media: ${f} is in use, unpacking over it`) }
  }
  tar(["-xf", upTo(DOCS) + `.cache/docs-media/${lock.asset}`], DOCS)
  await writeFile(stamp, lock.sha256 + "\n")
  console.log(`docs-media: unpacked ${lock.files} files into docs/${SETS[name].folder}`)
}

async function push(name) {
  const { dir, stamp, lock: lockFile } = paths(name)
  const files = await untrackedFiles(name)
  if (!files.length) throw new Error(`docs/${SETS[name].folder} has no untracked files to pack`)
  // a file of zeros (a crash or a full disk while it was written) once went up as a picture and broke every docs build
  for (const f of files) {
    const head = (await readFile(join(dir, f))).subarray(0, 64)
    if (!head.length || head.every((v) => v === 0)) throw new Error(`docs/${SETS[name].folder}/${f} is empty or all zeros: restore it before pushing`)
  }
  await mkdir(CACHE, { recursive: true })
  const list = join(CACHE, `${name}-files.txt`), tmp = join(CACHE, `${name}-new.tar`)
  await writeFile(list, files.map((f) => `${SETS[name].folder}/${f}`).join("\n") + "\n")
  await rm(tmp, { force: true })
  // sorted names, no owner or time: the same pictures give the same archive, so an unchanged folder is no new upload
  const base = upTo(DOCS) + ".cache/docs-media/"
  tar(["-cf", `${base}${name}-new.tar`, "--format=ustar", "-T", `${base}${name}-files.txt`], DOCS)
  const sha = await sha256(tmp)
  const lock = await readLock(name)
  if (lock?.sha256 === sha) { await writeFile(stamp, sha + "\n"); console.log(`docs-media: ${name} unchanged since the lock`); return }
  const asset = `${name}-${sha.slice(0, 12)}.tar`
  const archive = join(CACHE, asset)
  await rm(archive, { force: true })
  await rename(tmp, archive)
  const { tag, title, notes } = SETS[name]
  const gh = (a) => execFileSync("gh", a, { cwd: ROOT, stdio: ["ignore", "pipe", "inherit"], encoding: "utf8" })
  try { gh(["release", "view", tag, "-R", REPO, "--json", "tagName"]) } catch {
    gh(["release", "create", tag, "-R", REPO, "--prerelease", "--latest=false", "--title", title, "--notes", notes])
  }
  gh(["release", "upload", tag, archive, "-R", REPO, "--clobber"])
  const size = (await stat(archive)).size
  await writeFile(lockFile, JSON.stringify({ release: tag, asset, sha256: sha, size, files: files.length, pushed: new Date().toISOString().slice(0, 10) }, null, 2) + "\n")
  await writeFile(stamp, sha + "\n")
  console.log(`docs-media: uploaded ${asset} (${Math.round(size / 1e6)} MB, ${files.length} files); commit docs/media-${name}.lock`)
}

async function status(name) {
  const lock = await readLock(name), at = await readStamp(name)
  const where = lock ? `lock ${lock.asset} (${lock.files} files, ${Math.round(lock.size / 1e6)} MB, pushed ${lock.pushed})` : "no lock"
  const state = at ? `folder at ${at.slice(0, 12)}${lock && at === lock.sha256 ? ", matches" : ", DIFFERS from the lock"}` : existsSync(paths(name).dir) ? "folder present, never stamped" : "folder missing"
  console.log(`${name}: ${where}; ${state}`)
}

let failed = false
for (const name of sets) {
  try {
    if (mode === "pull") await pull(name)
    else if (mode === "push") { if (!only) throw new Error("push takes a set: screenshots or videos"); await push(name) }
    else if (mode === "status") await status(name)
    else throw new Error(`unknown mode "${mode}" (pull, push, status)`)
  } catch (e) {
    if (mode === "pull" && !strict) {
      // a dev server without network should still start, with missing or stale pictures
      console.warn(`docs-media: ${e.message} - continuing without the current ${name}`)
    } else {
      console.error(`docs-media: ${e.message}`)
      failed = true
    }
  }
}
if (failed) process.exit(1)
