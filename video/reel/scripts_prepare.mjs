// Copies takes into public/ at 1920x1080 30 fps and writes public/takes.json (frames per take).
// usage: node scripts_prepare.mjs <takes dir> [name ...]
import { execFileSync } from "node:child_process"
import { writeFileSync, readdirSync, existsSync, readFileSync } from "node:fs"
import { join } from "node:path"
const FF = "C:/Users/cnj/AppData/Local/Microsoft/WinGet/Packages/Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe/ffmpeg-9.0.2-full_build/bin/"
const src = process.argv[2]
const only = process.argv.slice(3)
const root = process.cwd()
const jsonPath = join(root, "public", "takes.json")
const frames = existsSync(jsonPath) ? JSON.parse(readFileSync(jsonPath, "utf8")) : {}
for (const f of readdirSync(src).filter((f) => f.endsWith(".mp4") && (only.length === 0 || only.includes(f)))) {
  const out = join(root, "public", f)
  execFileSync(FF + "ffmpeg.exe", ["-y", "-loglevel", "error", "-i", join(src, f), "-vf", "scale=1920:1080:flags=lanczos,fps=30", "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-an", out])
  frames[f] = Number(execFileSync(FF + "ffprobe.exe", ["-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", out]).toString().trim())
}
writeFileSync(jsonPath, JSON.stringify(frames, null, 2))
console.log(frames)
