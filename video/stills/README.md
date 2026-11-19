# Stills and rendered clips: headless Blender

These scripts made the screenshots of the docs and the slide decks (`docs/img`, November 2026) and the rendered clips
of the docs' Videos page (`docs/video`). Both folders are on releases, not in git; see `scripts/docs-media.mjs`.
Nothing here drives the UI: Blender runs with `-b`, the add-on streams with `ui.stream_tick` in a loop, and each
picture renders once the tiles of its view have loaded.

| File | What it does |
|---|---|
| `hshot.py` | `blender -b --python hshot.py -- <shot>`: one shot (a scene, a camera, one or more renders) per name. Writes `slides_shots/<shot>_<variant>.png`. The helpers at the top (`add`, `at`, `camera`, `converge`, `eevee`, `cycles`, `workbench`, `light_bg`, `clip_box`, `relight`) are what the shots share |
| `hanim_shots.py` | the clips: the same helpers plus `anim(frames, step)`, which sets frame *i* up, waits for the tiles, and renders. `a_bayon_split` renders clay (Cycles) and albedo with eye-dome lighting (EEVEE) for every frame and joins them along a moving diagonal |
| `sq.sh <shot>...` | queue of stills, two tries each, log in `sq.log` |
| `aq.sh <shot>...` | queue of clips: builds `hanim.py` from the helpers of `hshot.py` and `hanim_shots.py`, log in `aq.log` |
| `mkimg2.sh` | the PNG stills to the JPEGs of `docs/img`, over the page grey, cropped where needed |
| `enc_anim.sh <shot> <clip> [crf] [first] [last] [hold]` | the frames of a clip to `docs/video/<clip>.mp4` (H.264, 1280×720, 24 fps) and its poster; `first`..`last` keep part of the frames, `hold` repeats the last one before the loop. The Geghard clips: `a_reveal geghard_reveal 24 10 110 18` (the demo wraps at frame 111) and `a_geghard geghard_section 29 62 143 12` (the box reaches the roof at frame 76) |

The queues work in `%TEMP%\ogc_tests\r9`: copy the two Python files there, and run `mkimg2.sh` and `enc_anim.sh`
from the repository. The tilesets are looked up by name in the tileset library of the add-on preferences. The
library on the machine that made the clips is private (it holds share links and keys), so the shots that use a
private tileset need an entry with the same name.

Lessons:

- EDL needs an opaque film. A transparent film turns the beauty compositor's eye-dome lighting off. `light_bg()`
  gives camera rays a light grey while the sky still lights the scene.
- Tile objects are meshes even for point clouds: read `o.data.vertices` for their positions.
- Frame a scene from measured points (`world_to_camera_view` on the apexes and base corners, as in `gizeh_fit`),
  not from guessed distances.
- A Google view that reaches the horizon never settles at Max SSE 6: more than 1,000 tiles were still loading
  after 40 s a frame. At 10 to 16 every frame converges, in 6 to 10 s.
- Point clouds with eye-dome lighting render with speckle (Sacre-Coeur, 406M points): known, not fixed yet.
- A camera that moves slowly needs only a short settle per frame: the tiles of the next frame are mostly the
  same ones. The Giza clip renders at about 1 s a frame in Workbench; Google tiles in EEVEE take about 10 s.
