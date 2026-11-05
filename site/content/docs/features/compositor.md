---
title: "Compositor"
description: "The beauty compositor tree: edges, AO, haze"
---

The "Compositor" sub-panel builds the 'OGC3D Beauty' tree on the current
scene (`compositor.py`: edges, AO, ASC-CDL grade, depth haze, glare) and
switches every 3D viewport's compositor to *Always*, so Rendered shading
shows it live; the Compositing workspace shows the nodes.  The tree holds
both edge branches; *Edges* (eye-dome lighting from depth, Sobel creases
from normals, or both), *EDL strength*, *Crease strength*, *AO* and *Haze*
drive Value nodes of the existing tree, so they update live without a
rebuild (*Reset to default* in the row's menu rebuilds the tree and re-derives the
haze range from the loaded extent).
Cycles gives the viewport compositor the image only, no depth, normal or AO pass: in a
Cycles Rendered viewport the tree keeps its grade and glare, and edges, AO and haze are
switched off (the panel says so) until an F12 render, which has every pass.
Viewport quirks handled: the viewport compositor's Depth pass is 0 / NaN
where nothing is drawn (sanitised to "far"), its Mist and AO passes are 1
everywhere (haze is a ramp on Depth instead), and Rendered shading lights
the scene with the world only — *Build* brightens Blender's default
dark-grey world once when the scene has no sun lamp, otherwise the tiles
look black next to Material Preview's studio HDRI.  *Stable viewport*
(default on) renders the viewport with one TAA sample while the tree is
built: EEVEE jitters every accumulated sample by a sub-pixel offset and the
Depth / Normal passes are not accumulated, so EDL and creases shimmer by a
pixel in four directions until the view converges; one sample removes the
shimmer at the cost of viewport anti-aliasing (Remove restores the count).
`scripts/compositor_demo.py` reuses the same builder for headless renders.
