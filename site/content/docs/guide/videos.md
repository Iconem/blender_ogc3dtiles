---
title: "Videos"
description: "Short clips of the add-on at work: streaming around the camera, navigation, and converged renders of meshes, point clouds and shading"
---

A few short clips, without sound. The first two are screen captures of Blender. The others are rendered frame by
frame: on each frame the camera moves, the tiles for that view finish loading, and then the frame renders. That is
what the converged animation render does.

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

The scripts that made these clips are in the repository (see [Screencasts](/dev/screencasts)).
