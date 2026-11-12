# Screencasts: how the demo videos were made

Everything under `video/` is what produced the Blender OGC 3D Tiles demo reel and
its raw takes in November 2026. The videos themselves are not in git: they are
attached to the `videos-2026-11` GitHub release (a draft until Jonathan publishes
it), and the originals live in `Videos\blender_ogc3dtiles_screencasts\` on the
recording machine.

Paths that pointed into the recording session's scratchpad are written
`%OGC_SCRATCH%` here. Private inputs (Google Map Tiles key, Iconem share links)
were read from files outside the repo and are not included; see `docs/HANDOFF.md`
section 0 for where they live.

## 1. Recording a take (`harness/`)

Real input, real Blender 5.3, no fake cursor:

- `gui_repl.py`: start Blender with `blender --python gui_repl.py`. A timer polls
  `cmd.py` next to it, `exec`s it and writes `out.txt`. `take.blender(code)` is the
  shell side of that loop.
- `human.py`: mouse and keyboard through `SendInput` (scan codes, so Blender sees
  them as a person). `orbit`, `wheel`, `drag`, `border_zoom`, `key("shift+b")`,
  `type_text`.
- `take.py`: the take API. `layout()` reads the viewport and sidebar rectangles
  from Blender; `locate(name)` finds a UI element by OpenCV template matching
  (`tpl/<name>.png`, grey, threshold 0.88); `scroll_until(name)` scrolls the
  sidebar until the template appears; `take_start(name, rect)` / `take_stop(name)`
  run ffmpeg (gdigrab, h264_qsv, 30 fps) on the Blender client area and write the
  mark file; `mark(label)` stamps the current time with a label; `wait_visible(n)`
  waits until n tile objects are visible.
- `prep*.py`: run inside Blender through `take.blender`, they set the scene up
  before a take (clear tiles, add the tileset, shading, view, panel state). The
  take itself then shows no URL typing beyond what the script wants to show.
- `scene*.py`: one take each, run from the shell. Each starts with a comment
  saying which prep it expects. Numbering follows the take names below
  (`scene4d.py` records `s4d_eiffel_points`, `scene_nodes.py` records
  `s13_shared_nodes_eevee_cycles`, `scene_sp.py` `s14_san_pietro`,
  `scene_lublin.py` `s15_shramko_lublin`).
- `dry*.py`, `reset*.py`: dry runs and scene resets used while developing a take.
  Kept for the UI-driving tricks they contain, not needed to re-record.
- `takes/<name>.json`: the mark file of every take, `[[seconds, label], ...]`.
  It is the transcript of what happens when; the cutter and the reel read it.
- `library/demo_library.json`: the add-on library presets used by the takes
  (public tilesets only).
- `fix_orphans.py`: cleanup of orphaned tile objects between takes.

Pitfalls met, so the next person does not meet them again:

- Blender slows to a crawl (tens of seconds per command, 10 GB) after three or
  four takes in one session: restart it between take chains.
- Template matching needs the sidebar at the same width and zoom as when the
  template was cut; `make_tpl` cuts a new one from a screenshot.
- Dropdown menus sometimes miss the click: the scene scripts fall back to `esc`
  plus a `bpy` assignment so the take continues.
- Scene state leaks between takes (metadata colouring, origin, render engine):
  every prep resets what the previous take touched.
- `human.key` names: `esc`, `enter`, `home`, `shift+b`, `ctrl+space`.

## 2. Cutting (`reel/activity.py`, `reel/cut_takes.py`, `reel/plan.json`)

1. `activity.py <takes dir> <out dir> <take.mp4> ...` writes
   `idle/<take>.activity.json`: per-frame count of changed pixels at 960x540.
2. `plan.json` lists, per take, the source file, its activity file and the
   `keep` ranges in seconds (`null` = to the end). The first seconds of URL
   pasting are dropped here.
3. `cut_takes.py` re-encodes each take: fully static runs are shortened to a short
   beat, cursor-only stretches (small changes, after 1.5 s) play at 3x, everything
   else at 1x. It writes `public/<take>.mp4`, `public/timemaps.json` (original
   time to cut time, so the captions still land on the right moment) and
   `public/takes.json` (cut lengths in frames). Runs at below-normal priority.

## 3. The reel (`reel/`, Remotion)

- `pnpm install`, then `render4.bat` (or
  `npx remotion render src/index.ts BlenderDemo out/blender-ogc3dtiles-demo.mp4`).
- `src/BlenderDemo.tsx`: `ALL_SCENES` describes every take with its captions
  (keyed to the original mark times, remapped through `timemaps.json`); `PICK`
  selects and orders the scenes in the reel. Change `PICK` to change the reel.
- `src/Demo3.tsx`: title, scene and end cards, the Geist and Geist Mono fonts
  loaded from `public/fonts` through `FontFace`, caption component with a 2 s
  minimum on screen.
- `src/components/remocn`: the backdrop and card components.
- `remotion.config.ts`: jpeg frames, ANGLE for the WebGL backdrops, the `@/`
  alias.

The 2026-11-11 reel is 6:17 and holds, in order: Google and Bing, Sacré-Coeur
splat, clipping, shared nodes with EEVEE and Cycles, IGN points, classes,
overlay on Clermont.

## 4. Takes

Length is the raw take. Steps come from the mark file. Takes without a length
were superseded and their video deleted; their mark file stays as a record.

| Take | Length | Marks | Steps (from the mark file) |
|---|---|---|---|
| `s11_google_split_camera` | 77 s | 5 | LOD panel → stream for: scene camera → walk navigation in the camera → walk done → select the camera, grab it in the top view |
| `s11b_google_split_camera` | 71 s | 4 | stream for: scene camera → walk navigation in the camera (left); right view stays put → walk done → grab the camera in the top view |
| `s12_google_bing` | 78 s | 4 | google: orbit the colosseum → add bing via 3dtiled → untick google, restart → bing: 44 tiles |
| `s12b_google_bing_eyes` |  | 8 | google + bing, both on the colosseum → shift+b on the colosseum → hide google: bing only → show google, hide bing: google only → solid shading: the tiled mesh itself → bing back on, solid → google off: bing alone, solid → material preview again |
| `s13_shared_nodes_eevee_cycles` | 123 s | 12 | shift+b cathedral → material panel → shared shader nodes → atmosphere preset → rendered → albedo to clay → albedo back → demo graphs: suzanne on points → beauty compositor → edges: normal creases → cycles → back to eevee |
| `s14_san_pietro` | 43 s | 8 | home → orbit → shift+b arena → interior on → exterior off → 29 interior tiles → home → shift+b interior |
| `s15_shramko_lublin` | 60 s | 6 | start → 189 coarse tiles → home → orbit → shift+b → shift+b tighter |
| `s1_splat` | 43 s | 12 | paste tileset path → add → rename → origin panel → start → 78 tiles visible → home → orbit → wheel in → shift+b → rendered → orbit rendered |
| `s1b_fronton` | 26 s | 5 | shift+b facade → orbit → shift+b horses → orbit around → wheel in |
| `s1c_sacre_coeur_full` | 49 s | 13 | paste tileset path → add → rename → scene origin: auto → start → 173 tiles → home → rendered → orbit to the north side → shift+b facade → orbit → shift+b horses → orbit around |
| `s1d_sacre_coeur_full` | 55 s | 15 | paste tileset path → add → rename → scene origin panel → origin modes → auto → start → 173 tiles → home → rendered → orbit to the north side → shift+b fronton → orbit → shift+b horses → orbit around |
| `s3a_clermont_place` | 44 s | 12 | paste url → add → rename → scene origin → search place → pick result → start → material preview → 44 tiles → collapse origin → shift+b cathedral → orbit |
| `s3b_clermont_shader_sun_cycles` | 71 s | 9 | shared shader nodes → albedo to clay → albedo back → scroll sidebar → atmosphere preset → rendered → select sun → rotate sun → cycles |
| `s3c_clermont_shader_sun_cycles` | 89 s | 10 | material panel → shared shader nodes → scroll sidebar → atmosphere preset → rendered → albedo to clay → albedo back → select sun → rotate sun about Z → cycles |
| `s4a_eiffel_points` | 62 s | 14 | paste path → add → rename → start → 91 tiles → home → orbit → shift+b tower → shift+b tighter → scroll the sidebar to the Radius controls → radius modes → it_attenuated → it_uniform → it_screen_pixels |
| `s4b_eiffel_classes_overlay` | 98 s | 11 | home → shift+b tower → material preview → metadata panel → read feature metadata → stop, clear, start → 122 tiles reloaded → color tiles by classification → raster overlays → overlay from presets → IGN orthophotos WMTS |
| `s4c_eiffel_overlay` | 50 s | 6 | home → shift+b tower → raster overlays → overlay from presets → IGN orthophotos WMTS → orbit |
| `s4d_eiffel_points` | 58 s | 11 | start → 104 tiles → home → shift+b tower → orbit → shift+b tighter → scroll the sidebar to the Radius controls → radius modes → it_uniform → it_screen_pixels → it_attenuated |
| `s4e_eiffel_classes` | 77 s | 6 | metadata panel → read feature metadata → stop, clear, start → 157 tiles reloaded → color tiles by classification → material preview |
| `s4e_eiffel_overlay_classes` |  | 9 | raster overlays → overlay from presets → IGN orthophotos WMTS → material preview → metadata panel → read feature metadata → stop, clear, start → 162 tiles reloaded → color tiles by classification |
| `s4f_clermont_overlay` | 36 s | 5 | shift+b → raster overlays → overlay from presets → IGN orthophotos WMTS → opacity |
| `s5_camera_stream` | 67 s | 7 | camera to view → stream for: scene camera → walk navigation → walk done → leave camera, top view → select camera → grab camera |
| `s5b_camera_stream` | 65 s | 8 | camera to view → stream for: scene camera → walk navigation → walk done → leave camera → select camera → top view on the camera → grab camera |
| `s6a_geometry_compositor` |  | 6 | home → shift+b tower → demo graphs: suzanne on points → rendered → beauty compositor → edges: normal creases |
| `s6b_clermont_suzanne_compositor` | 61 s | 5 | shift+b cathedral → demo graphs: suzanne on points → rendered → beauty compositor → edges: normal creases |
| `s7_clipping` | 84 s | 9 | add cube → scale cube → display as bounds → clipping on → add cube as clipping box → grab cube → rotate cube → add circle polygon → add circle as clip polygon |
| `s7b_clipping_london` | 91 s | 9 | add cube → scale cube → display as bounds → clipping on → add cube as clipping box → grab cube → rotate cube → add circle polygon → add circle as clip polygon |
| `s8_splat_eevee_cycles` | 52 s | 5 | shift+b facade → ctrl+space maximise → ctrl+space back → cycles → back to eevee |
| `s8b_splat_cycles` | 56 s | 2 | cycles → back to eevee |
| `s9_library_strasbourg` | 63 s | 10 | save to library → ok → add from library → pick strasbourg → untick clermont → scene origin: search place → pick result → stop, then start → 40 tiles → shift+b |

Datasets: Sacré-Coeur (streamed SOG through 3dtiled), Clermont-Ferrand (Iconem
mesh), Eiffel (IGN LiDAR HD COPC tiles, local copy), Google Map Tiles and Bing
through 3dtiled (key needed for Google), London (Google), San Pietro (Iconem
share links, private), Strasbourg (library preset), Shramko Lublin (103 M
splats, 3dtiled merged tiles, local copy). The scene scripts' headers say which
prep and which dataset each take expects.
