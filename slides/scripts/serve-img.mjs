// The path the decks read the screenshots from (assets/shots.ts), and the folder that holds them: docs/img, the one
// copy in the repository. Shared by scripts/dev.mjs (Vite middleware) and scripts/publish.mjs (the static server).
import { existsSync, statSync, readFileSync } from "node:fs"
import { join, dirname, extname, resolve } from "node:path"
import { fileURLToPath } from "node:url"

export const IMG_PATH = "/blender_ogc3dtiles/img/"
export const IMG_DIR = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..", "docs", "img")
const TYPES = { ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp", ".svg": "image/svg+xml" }

// true when it answered the request (a file of docs/img, or a 404 under IMG_PATH)
export function serveImg(req, res) {
  const path = decodeURIComponent(new URL(req.url, "http://x").pathname)
  if (!path.startsWith(IMG_PATH)) return false
  const file = join(IMG_DIR, path.slice(IMG_PATH.length))
  if (!file.startsWith(IMG_DIR) || !existsSync(file) || !statSync(file).isFile()) { res.writeHead(404).end(); return true }
  res.writeHead(200, { "content-type": TYPES[extname(file).toLowerCase()] ?? "application/octet-stream" }).end(readFileSync(file))
  return true
}
