// Blender OGC 3D Tiles add-on: takes recorded with real mouse and keyboard input
// in Blender 5.3, one title card per scene, narrator captions.
import type React from "react"
import { TransitionSeries, linearTiming } from "@remotion/transitions"
import { fade } from "@remotion/transitions/fade"
import { TakeScene, TitleCard, TRANSITION, takeFrames, type Take } from "./Demo3"
import takes from "../public/takes.json"
import timemaps from "../public/timemaps.json"

const CARD = 96
const BOTTOM = { x: 760, bottom: 70 }
const FOOT = "blender ogc 3d tiles · demo · jo-chemla/blender_ogc3dtiles"
const MIN_CAPTION = 2.0

type Scene = { eyebrow: string; title: React.ReactNode; subtitle: string; take: Take }
const secs = (src: string) => ((takes as Record<string, number>)[src] ?? 0) / 30

// cut_takes.py keeps a subset of each take's frames (static stretches dropped, quiet ones
// sped up): timemaps.json lists the kept source frame per output frame. Beats are written
// in source seconds and mapped here to the cut take's seconds.
const toCut = (src: string, s: number) => {
  const kept = (timemaps as Record<string, number[]>)[src]
  if (!kept) return s
  const f = Math.round(s * 30)
  let lo = 0, hi = kept.length
  while (lo < hi) { const mid = (lo + hi) >> 1; if (kept[mid] < f) lo = mid + 1; else hi = mid }
  return lo / 30
}
const take = (src: string, beats: Take["beats"]): Take => {
  const out = secs(src)
  const mapped = beats
    .map((b) => { const at = toCut(src, b.at); return { ...b, at, to: Math.min(out, Math.max(toCut(src, b.to), at + MIN_CAPTION)) } })
    .filter((b) => b.to - b.at >= 1.0)
  return { src, in: 0, out, spot: BOTTOM, beats: mapped }
}

const ALL_SCENES: Scene[] = [
  {
    eyebrow: "Gaussian splats", title: <>Iconem splat,<br />tiled and streamed</>,
    subtitle: "A .splat from the Iconem platform, tiled with 3dtiled, streamed as native Blender 5.3 splats",
    take: take("s1d_sacre_coeur_full.mp4", [
      { at: 1.0, to: 5.0, text: "Paste a tileset path, add it to the list." },
      { at: 9.5, to: 16.5, text: "Scene origin: Auto, Keep current, Custom or Search place." },
      { at: 18.0, to: 22.5, text: "Start: 280 SPZ tiles load in a few seconds." },
      { at: 24.5, to: 28.0, text: "Rendered view, orbit with the middle mouse button." },
      { at: 32.7, to: 36.3, text: "Shift+B on the fronton." },
      { at: 40.0, to: 44.0, text: "And on the horses: the finest tiles." },
      { at: 44.5, to: 52.0, text: "Orbit around the facade." },
    ]),
  },
  {
    eyebrow: "Meshes", title: <>A city mesh,<br />found by name</>,
    subtitle: "Clermont-Ferrand open-data photomesh, origin set by place search",
    take: take("s3a_clermont_place.mp4", [
      { at: 1.0, to: 5.0, text: "The CRAIG tileset URL, pasted." },
      { at: 9.5, to: 14.0, text: "Scene origin: Search place." },
      { at: 15.0, to: 20.0, text: "Type the cathedral, pick the Photon result." },
      { at: 22.0, to: 27.0, text: "Start, in Material Preview." },
      { at: 28.7, to: 33.0, text: "Shift+B on the cathedral: tiles refine where you look." },
    ]),
  },
  {
    eyebrow: "Shading", title: <>Shared shader,<br />sun and Cycles</>,
    subtitle: "One node group on every tile: atmosphere preset, albedo to clay, a sun you can rotate",
    take: take("s3c_clermont_shader_sun_cycles.mp4", [
      { at: 1.0, to: 6.5, text: "Material panel: shared shader nodes on." },
      { at: 14.3, to: 20.0, text: "Atmosphere preset: a sun, a sky, haze." },
      { at: 21.8, to: 27.5, text: "Rendered view." },
      { at: 28.5, to: 35.0, text: "Albedo strength down: the city as clay, in sunlight." },
      { at: 35.4, to: 39.0, text: "And back to the photo albedo." },
      { at: 41.9, to: 54.5, text: "Rotate the sun about Z: the shadows swing." },
      { at: 55.5, to: 70.0, text: "Switch the engine to Cycles." },
      { at: 72.0, to: 86.0, text: "Orbit in a Cycles preview." },
    ]),
  },
  {
    eyebrow: "Point clouds (old)", title: <>IGN LiDAR HD,<br />tile by tile</>,
    subtitle: "A COPC tile converted with 3dtiled, point size attenuated, uniform or in pixels",
    take: take("s4a_eiffel_points.mp4", [
      { at: 1.0, to: 5.0, text: "The converted tileset, from disk." },
      { at: 11.5, to: 16.5, text: "Start, Home, orbit." },
      { at: 20.5, to: 26.0, text: "Shift+B on the tower, twice." },
      { at: 34.5, to: 38.0, text: "Scroll the sidebar to the point options." },
      { at: 39.5, to: 44.5, text: "Radius: attenuated by tile spacing, clamped in pixels." },
      { at: 45.5, to: 50.0, text: "Uniform metres." },
      { at: 51.0, to: 56.0, text: "Or a fixed size on screen." },
    ]),
  },
  {
    eyebrow: "Metadata and overlays", title: <>Classes,<br />and imagery on top</>,
    subtitle: "LAS classification as colours, an IGN orthophoto draped on the points",
    take: take("s4b_eiffel_classes_overlay.mp4", [
      { at: 12.5, to: 18.0, text: "Read feature metadata, then reload the tiles." },
      { at: 43.5, to: 50.0, text: "Colour tiles by classification: ground, vegetation, buildings." },
      { at: 60.0, to: 66.0, text: "Raster overlays: a preset from the list." },
      { at: 76.5, to: 84.0, text: "IGN orthophotos, draped live." },
    ]),
  },
  {
    eyebrow: "Streaming for a camera", title: <>Inside the camera,<br />and from above</>,
    subtitle: "Tiles chosen for the scene camera, watched from a top view",
    take: take("s5b_camera_stream.mp4", [
      { at: 3.9, to: 7.5, text: "Align the camera to the view." },
      { at: 7.6, to: 13.0, text: "Stream for: Scene camera." },
      { at: 14.0, to: 35.0, text: "Walk navigation: the camera moves, the tiles follow it." },
      { at: 36.5, to: 42.0, text: "Leave the camera: a top view on it, display size 100 m." },
      { at: 42.7, to: 64.0, text: "Grab the camera: tiles load ahead, unload behind." },
    ]),
  },
  {
    eyebrow: "Geometry and compositing", title: <>Nodes on<br />every tile</>,
    subtitle: "A shared geometry graph, then the beauty compositor",
    take: take("s6b_clermont_suzanne_compositor.mp4", [
      { at: 8.0, to: 14.0, text: "Demo graphs: Suzanne on points." },
      { at: 15.0, to: 22.0, text: "A monkey on a share of every tile's vertices." },
      { at: 29.5, to: 34.0, text: "Rendered view." },
      { at: 34.5, to: 44.0, text: "Beauty compositor: eye-dome lighting, AO, haze." },
      { at: 46.5, to: 54.0, text: "Edges: normal creases." },
    ]),
  },
  {
    eyebrow: "Clipping", title: <>Cut with<br />any object</>,
    subtitle: "Google Photorealistic 3D Tiles over Westminster: a box and an extruded polygon, live",
    take: take("s7b_clipping_london.mp4", [
      { at: 1.0, to: 8.5, text: "Add a cube, scale it to 220 m." },
      { at: 12.2, to: 17.5, text: "Shown as bounds. Clipping on." },
      { at: 18.1, to: 28.0, text: "The cube added as a box: a hole in the Parliament block." },
      { at: 29.7, to: 44.5, text: "Grab it: the cut follows." },
      { at: 45.0, to: 56.0, text: "Rotate it." },
      { at: 57.7, to: 69.0, text: "A circle, scaled." },
      { at: 69.3, to: 88.0, text: "Added as an extruded polygon." },
    ]),
  },
  {
    eyebrow: "Libraries", title: <>Save it,<br />pick it back</>,
    subtitle: "Tileset libraries: an entry saved to a file, another city picked from the list",
    take: take("s9_library_strasbourg.mp4", [
      { at: 4.0, to: 9.0, text: "Save the entry to a library file." },
      { at: 10.5, to: 17.0, text: "Add from library: search, pick Strasbourg." },
      { at: 18.4, to: 19.5, text: "Untick Clermont: the next stream is Strasbourg's." },
    ]),
  },
  {
    eyebrow: "Google and Bing", title: <>Two world<br />meshes</>,
    subtitle: "Google Photorealistic 3D Tiles with your key, Bing Maps 3D through 3dtiled, each on its own, in Material Preview and Solid",
    take: take("s12c_google_bing_solid.mp4", [
      { at: 1.8, to: 6.0, text: "Google and Bing, both added over the Colosseum." },
      { at: 6.5, to: 9.0, text: "Shift+B on the arena." },
      { at: 23.4, to: 41.0, text: "Eye on Google off: Bing alone, finer on the arena." },
      { at: 44.8, to: 62.0, text: "Google back, Bing off: Google alone." },
      { at: 65.3, to: 71.0, text: "Solid shading: the tiled mesh itself, no texture." },
      { at: 71.9, to: 75.5, text: "Bing back on, in Solid." },
      { at: 88.3, to: 94.5, text: "Bing's mesh alone." },
      { at: 95.5, to: 102.5, text: "Back to Material Preview." },
    ]),
  },
  {
    eyebrow: "Camera stream, two views", title: <>In the camera,<br />and over it</>,
    subtitle: "Left: the scene camera walking. Right: a fixed top view of the tiles it loads and drops",
    take: take("s11b_google_split_camera.mp4", [
      { at: 1.5, to: 8.5, text: "Stream for: Scene camera." },
      { at: 9.0, to: 37.5, text: "Walk navigation inside the camera frame; the right view stays put and shows the loaded footprint." },
      { at: 38.0, to: 70.0, text: "Grab the camera in the top view: tiles load ahead and unload behind." },
    ]),
  },
  {
    eyebrow: "Point clouds", title: <>IGN LiDAR HD,<br />tile by tile</>,
    subtitle: "A COPC tile converted with 3dtiled: point size uniform, in screen pixels, or attenuated by tile spacing",
    take: take("s4d_eiffel_points.mp4", [
      { at: 0.8, to: 5.0, text: "Start: the converted tileset, from disk." },
      { at: 5.9, to: 7.8, text: "Home." },
      { at: 8.0, to: 12.5, text: "Shift+B on the tower." },
      { at: 15.9, to: 20.0, text: "And tighter: the finest tiles." },
      { at: 23.3, to: 27.0, text: "Scroll the sidebar to the Radius controls." },
      { at: 27.8, to: 34.0, text: "Uniform: one radius in metres." },
      { at: 35.7, to: 42.0, text: "Screen pixels: a fixed size on screen." },
      { at: 43.7, to: 52.0, text: "Attenuated by tile spacing, clamped 2 to 8 px." },
    ]),
  },
  {
    eyebrow: "Metadata", title: <>Classes<br />as colours</>,
    subtitle: "LAS classification read as vertex attributes, tiles coloured per class",
    take: take("s4e_eiffel_classes.mp4", [
      { at: 3.8, to: 9.0, text: "Nodes: Metadata panel." },
      { at: 24.5, to: 30.0, text: "Read feature metadata." },
      { at: 31.1, to: 36.0, text: "Stop, clear, start: the tiles reload with their attributes." },
      { at: 51.2, to: 55.0, text: "157 tiles back." },
      { at: 52.0, to: 60.0, text: "Colour tiles by classification." },
      { at: 63.7, to: 75.0, text: "Material Preview: ground, vegetation, buildings." },
    ]),
  },
  {
    eyebrow: "Overlays", title: <>Imagery<br />draped live</>,
    subtitle: "An IGN orthophoto WMTS over the Clermont-Ferrand photomesh",
    take: take("s4f_clermont_overlay.mp4", [
      { at: 0.8, to: 4.5, text: "Shift+B on the centre." },
      { at: 5.3, to: 8.5, text: "Raster overlays on." },
      { at: 8.7, to: 11.0, text: "A preset from the list." },
      { at: 11.3, to: 18.0, text: "IGN orthophotos, draped as the tiles reload." },
      { at: 24.0, to: 34.0, text: "Orbit: the imagery follows the mesh." },
    ]),
  },
  {
    eyebrow: "Shared nodes", title: <>One graph,<br />every tile</>,
    subtitle: "Shader, geometry and compositor node groups shared by all tiles, in EEVEE then Cycles",
    take: take("s13_shared_nodes_eevee_cycles.mp4", [
      { at: 0.8, to: 4.5, text: "Shift+B on the cathedral." },
      { at: 5.3, to: 11.0, text: "Nodes: Material." },
      { at: 11.6, to: 14.5, text: "Shared shader nodes on." },
      { at: 14.7, to: 22.0, text: "Atmosphere preset: a sun, a sky, haze." },
      { at: 29.1, to: 33.0, text: "Rendered view, EEVEE." },
      { at: 34.4, to: 39.5, text: "Albedo strength down: clay in sunlight." },
      { at: 39.7, to: 42.5, text: "And back." },
      { at: 43.0, to: 52.0, text: "Shared geometry nodes: Suzanne on points." },
      { at: 57.8, to: 66.0, text: "Beauty compositor: eye-dome lighting, AO, haze." },
      { at: 70.8, to: 78.0, text: "Edges: normal creases." },
      { at: 81.8, to: 100.0, text: "Cycles: the same groups, path traced." },
      { at: 114.4, to: 120.0, text: "Back to EEVEE." },
    ]),
  },
  {
    eyebrow: "San Pietro", title: <>Arena,<br />outside and in</>,
    subtitle: "Iconem's San Pietro scan as two tilesets: the exterior mesh, then the interior",
    take: take("s14_san_pietro.mp4", [
      { at: 0.8, to: 2.8, text: "Home." },
      { at: 7.1, to: 12.0, text: "Shift+B on the arena." },
      { at: 18.4, to: 21.5, text: "Interior tileset on, exterior off." },
      { at: 25.3, to: 36.0, text: "Shift+B inside." },
    ]),
  },
  {
    eyebrow: "103 M splats", title: <>Shramko's Lublin,<br />as 3D Tiles</>,
    subtitle: "A 103 M-splat PLY, four LODs with splat-transform, tiled by 3dtiled with a 100 k splat budget per tile",
    take: take("s15_shramko_lublin.mp4", [
      { at: 0.8, to: 6.0, text: "Start, origin Auto." },
      { at: 7.2, to: 11.5, text: "The coarse level: the whole scan in seconds." },
      { at: 17.1, to: 24.0, text: "Shift+B: finer tiles replace the coarse ones." },
      { at: 32.5, to: 42.0, text: "And tighter." },
    ]),
  },
]

// The reel: the five scenes Jonathan picked (2026-11-11). The others stay in ALL_SCENES.
const PICK = ["Google and Bing", "Gaussian splats", "Clipping", "Shared nodes", "Point clouds", "Metadata", "Overlays"]
export const SCENES: Scene[] = []
for (const e of PICK) { const sc = ALL_SCENES.find((x) => x.eyebrow === e); if (sc) SCENES.push(sc) }

export const blenderDemoDuration = () =>
  SCENES.reduce((s, sc) => s + CARD + takeFrames(sc.take), 0) - (2 * SCENES.length - 1) * TRANSITION

const crossFade = (key: string) => (
  <TransitionSeries.Transition key={key} presentation={fade()} timing={linearTiming({ durationInFrames: TRANSITION })} />
)

export const BlenderDemo: React.FC = () => (
  <TransitionSeries>
    {SCENES.flatMap((sc, i) => [
      ...(i > 0 ? [crossFade(`x${i}`)] : []),
      <TransitionSeries.Sequence key={`c${i}`} durationInFrames={CARD}>
        <TitleCard fadeIn={i === 0} n={i + 1} total={SCENES.length} eyebrow={sc.eyebrow} title={sc.title} subtitle={sc.subtitle} foot={FOOT} />
      </TransitionSeries.Sequence>,
      crossFade(`y${i}`),
      <TransitionSeries.Sequence key={`t${i}`} durationInFrames={takeFrames(sc.take)}>
        <TakeScene take={sc.take} />
      </TransitionSeries.Sequence>,
    ])}
  </TransitionSeries>
)
