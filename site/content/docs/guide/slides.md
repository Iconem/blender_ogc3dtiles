---
title: "Slides"
description: "The add-on in fifteen slides, for Blender users and for the 3D Tiles crowd"
---

A deck that walks through the add-on: why it exists, how it streams, what it reads, and each main
feature on a slide. It is made with [open-slide](https://github.com/1weiho/open-slide) and built
with this site.

- **[Open the deck](https://jo-chemla.github.io/blender_ogc3dtiles/slides/s/blender-3dtiles/)** in the browser.
- **[Download the PDF](https://jo-chemla.github.io/blender_ogc3dtiles/slides/pdf/blender-3dtiles.pdf)**, one page per slide.

## Presenting

| Key | Action |
|---|---|
| **F** | Present: the slide fills the window. Esc leaves. |
| **Right / Left arrow**, **Space** | Next and previous slide. |

The deck has speaker notes. The presenter view, with the notes and the next slide, opens in a
second window at [.../s/blender-3dtiles/presenter/](https://jo-chemla.github.io/blender_ogc3dtiles/slides/s/blender-3dtiles/presenter/); it
follows the main window, so put the main one on the projector.

## Editing the deck

The source is `slides/slides/blender-3dtiles/index.tsx` in the repository: one React component per
slide, and the screenshots of `docs/img`. `pnpm dev` in `slides/` opens it with live reload.
