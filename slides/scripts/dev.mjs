// `open-slide dev` with one addition: the repository's screenshots (docs/img), which the decks show by URL
// (assets/shots.ts), served at /blender_ogc3dtiles/img/ as the docs site serves them once deployed. open-slide builds
// its Vite config itself (configFile: false), so this reuses that config through its public entry and adds a
// middleware. Port and base come from open-slide.config.ts as before. vite is a devDependency so this resolves the
// same vite 8 open-slide runs on.
import { createServer, mergeConfig } from "vite"
import { createViteConfig } from "@open-slide/core/vite"
import { IMG_PATH, serveImg } from "./serve-img.mjs"

const base = await createViteConfig({ userCwd: process.cwd(), mode: "serve" })
const server = await createServer(mergeConfig(base, {
  plugins: [{
    name: "docs-img",
    configureServer(s) { s.middlewares.use((req, res, next) => { if (!serveImg(req, res)) next() }) },
  }],
}))
await server.listen()
server.printUrls()
console.log(`  ${IMG_PATH} -> docs/img`)
if (process.stdin.isTTY) server.bindCLIShortcuts({ print: true })
