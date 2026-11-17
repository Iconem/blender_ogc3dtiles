// The title slide of every deck as a JPEG for the docs' Slide decks page: docs/img/slides-<deck>.jpg, 960 px wide,
// next to the other screenshots (site/scripts/sync-content.mjs copies docs/img into the site). Reads the static site,
// so serve it first:
//   pnpm static                   (serves http://localhost:4180/blender_ogc3dtiles/slides/)
//   pnpm shots [http://localhost:4180/blender_ogc3dtiles/slides/]
// playwright-core's channel "chrome" uses the system's Chrome, no bundled browser.
import { chromium } from "playwright-core"
import { existsSync, readdirSync, writeFileSync } from "node:fs"
import { join, dirname } from "node:path"
import { fileURLToPath } from "node:url"
import { IMG_DIR } from "./serve-img.mjs"

const root = join(dirname(fileURLToPath(import.meta.url)), "..")
const base = (process.argv[2] ?? "http://localhost:4180/blender_ogc3dtiles/slides/").replace(/\/?$/, "/")
const decks = readdirSync(join(root, "slides")).filter((d) => existsSync(join(root, "slides", d, "index.tsx")))

const browser = await chromium.launch(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : { channel: "chrome" })
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 })
for (const deck of decks) {
  await page.goto(`${base}s/${deck}/`, { waitUntil: "networkidle" })
  await page.waitForFunction(() => !/LOADING ASSETS/.test(document.body.innerText), null, { timeout: 120000 })
  // Play mode fills the viewport with the page alone (no thumbnails, no toolbar).
  await page.keyboard.press("f")
  await page.waitForTimeout(1500)
  await page.evaluate(() => document.fonts.ready)
  const shot = await page.screenshot({ type: "jpeg", quality: 90 })
  // 960 px wide: drawn on a canvas in the page, then saved.
  const scaled = await page.evaluate(async (b64) => {
    const img = new Image(); img.src = "data:image/jpeg;base64," + b64; await img.decode()
    const c = document.createElement("canvas"); c.width = 960; c.height = 540
    const g = c.getContext("2d"); g.imageSmoothingQuality = "high"; g.drawImage(img, 0, 0, 960, 540)
    return c.toDataURL("image/jpeg", 0.85).split(",")[1]
  }, shot.toString("base64"))
  const file = join(IMG_DIR, `slides-${deck}.jpg`)
  writeFileSync(file, Buffer.from(scaled, "base64"))
  console.log(`${deck}: ${file}`)
  await page.keyboard.press("Escape")
}
await browser.close()
