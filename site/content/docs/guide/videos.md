---
title: "Videos"
description: "Short clips of the add-on at work: streaming around the camera, navigation, and converged renders of meshes, point clouds and shading"
---

A few short clips, without sound. The first two are screen captures of Blender. The others are rendered frame by
frame: on each frame the camera moves, the tiles for that view finish loading, and then the frame renders. That is
what the converged animation render does.

## Highlights

<video src="/video/highlights.mp4" poster="/video/highlights.jpg" controls loop preload="none" muted playsinline style="width:100%;height:auto;aspect-ratio:auto 16/9;border-radius:8px"></video>

Seven of the rendered clips below in one 42 second reel: Giza, Venice, Tokyo, Notre-Dame, the Bayon, the three
camera projections and the Colosseum clip box.

## In the Blender window

<video src="/video/camera_split_rome.mp4" poster="/video/camera_split_rome.jpg" controls muted playsinline preload="none" style="width:100%;height:auto;aspect-ratio:auto 16/9;border-radius:8px"></video>

**The camera decides what streams.** Google Photorealistic 3D Tiles over Rome. On the left is the camera view; on
the right, a top view shows which tiles load around the camera. As the camera moves, tiles follow its frustum and
fade out behind it.

<video src="/video/navigate_rome.mp4" poster="/video/navigate_rome.jpg" controls muted playsinline preload="none" style="width:100%;height:auto;aspect-ratio:auto 16/9;border-radius:8px"></video>

**Navigating as usual.** Wheel zoom, Shift+B zoom to a region, and middle-drag orbit. The tiles refine where the
view goes, and the sidebar shows the counts live.

## Rendered frame by frame

<video src="/video/gizeh_orbit.mp4" poster="/video/gizeh_orbit.jpg" autoplay loop muted playsinline style="width:100%;height:auto;aspect-ratio:auto 16/9;border-radius:8px"></video>

**Khafre and Khufu, Giza.** A photogrammetry mesh tileset in the Solid view with the normal matcap.

<video src="/video/ign_classes.mp4" poster="/video/ign_classes.jpg" autoplay loop muted playsinline style="width:100%;height:auto;aspect-ratio:auto 16/9;border-radius:8px"></video>

**IGN LiDAR HD around the Eiffel Tower.** COPC tiles streamed by 3dtiled, coloured by LAS class, with eye-dome
lighting from the beauty compositor.

<video src="/video/geghard_section.mp4" poster="/video/geghard_section.jpg" autoplay loop muted playsinline style="width:100%;height:auto;aspect-ratio:auto 16/9;border-radius:8px"></video>

**A section through the Geghard monastery, Armenia.** The interior and exterior point clouds, both served through
3dtiled. One clip box per tileset comes down until the vaults open.

<video src="/video/geghard_reveal.mp4" poster="/video/geghard_reveal.jpg" autoplay loop muted playsinline style="width:100%;height:auto;aspect-ratio:auto 16/9;border-radius:8px"></video>

**The height reveal demo.** One shared geometry graph runs on every tile, and the monastery builds up from the
ground.

<video src="/video/bayon_shading.mp4" poster="/video/bayon_shading.jpg" autoplay loop muted playsinline style="width:100%;height:auto;aspect-ratio:auto 16/9;border-radius:8px"></video>

<video src="/video/bayon_split.mp4" poster="/video/bayon_split.jpg" autoplay loop muted playsinline style="width:100%;height:auto;aspect-ratio:auto 16/9;border-radius:8px"></video>

**Clay against albedo, the Bayon, Angkor.** Left of the line: the shared shader with the albedo off, rendered in
Cycles. Right: the photogrammetry albedo with eye-dome lighting, in EEVEE. Same tiles, same frame.

**The shared shader on the Bayon.** Clay first, then the photogrammetry albedo with eye-dome lighting, then
relit by the sun, on every tile at once.

<video src="/video/venice_solid.mp4" poster="/video/venice_solid.jpg" autoplay loop muted playsinline style="width:100%;height:auto;aspect-ratio:auto 16/9;border-radius:8px"></video>

**Piazza San Marco, Venice, in the Solid view.**

<video src="/video/tokyo.mp4" poster="/video/tokyo.jpg" autoplay loop muted playsinline style="width:100%;height:auto;aspect-ratio:auto 16/9;border-radius:8px"></video>

**Tokyo Tower.** Google Photorealistic 3D Tiles in EEVEE.

<video src="/video/canyon.mp4" poster="/video/canyon.jpg" autoplay loop muted playsinline style="width:100%;height:auto;aspect-ratio:auto 16/9;border-radius:8px"></video>

**The Grand Canyon from Yavapai Point.** Google Photorealistic 3D Tiles in EEVEE.

<video src="/video/notredame_tiles.mp4" poster="/video/notredame_tiles.jpg" autoplay loop muted playsinline style="width:100%;height:auto;aspect-ratio:auto 16/9;border-radius:8px"></video>

**One colour per tile, Notre-Dame.** Left of the line: Google Photorealistic 3D Tiles in EEVEE. Right: the same
tiles, each in its own colour. As the camera pushes in, the tiles split into smaller, more detailed ones.

<video src="/video/camera_projections.mp4" poster="/video/camera_projections.jpg" autoplay loop muted playsinline style="width:100%;height:auto;aspect-ratio:auto 16/9;border-radius:8px"></video>

**One camera, three projections, at the Colosseum.** Perspective, then orthographic straight down, then
panoramic, in Cycles. The inset is a top view of the tiles that camera selected, each in its own colour, with
its view volume in white: a pyramid, a box, then every direction around the camera.

<video src="/video/colosseum_clip.mp4" poster="/video/colosseum_clip.jpg" autoplay loop muted playsinline style="width:100%;height:auto;aspect-ratio:auto 16/9;border-radius:8px"></video>

**A clip box closes in on the Colosseum.** Google Photorealistic 3D Tiles in EEVEE. The box shrinks from the
city to the amphitheatre, and the tiles are cut as it moves.

<video src="/video/sanpietro_xray.mp4" poster="/video/sanpietro_xray.jpg" autoplay loop muted playsinline style="width:100%;height:auto;aspect-ratio:auto 16/9;border-radius:8px"></video>

**X-ray on San Pietro.** The interior mesh seen from outside. X-ray fades in on the shared shader, and the nave
and the chapels appear through the walls.

The scripts that made these clips are in the repository (see [Screencasts](/dev/screencasts)).
