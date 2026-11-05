---
title: "Roadmap"
description: "Done and planned"
---

- [x] Frustum culling, dynamic SSE, REPLACE gating, priority loads
- [x] Disk cache, budgeted imports, selection preserved
- [x] cesium-native backend against the real binding API
- [x] Several tilesets at once (one root Empty each)
- [x] Raster overlays (cesium-native) draped on tiles, and a WGS84 globe
- [x] Gaussian splat tiles (`KHR_gaussian_splatting`, SPZ) as Blender 5.3 splats
- [x] `pnts` point clouds on the native path (Angkor tilesets verified)
- [ ] `pnts` / `i3dm` on the pure Python path
- [x] Feature tables → vertex attributes and per-class colors
- [x] Per-point metadata on point clouds
- [x] Tileset, group, tile and content metadata from `tileset.json`
- [x] Metadata stored in textures (feature ids and property textures)
- [x] Voxel tilesets: box and region tiles as blocks, box tiles as OpenVDB Volumes ([notes](/dev/notes/voxels))
- [x] Voxel classes colored onto another tileset, with a boolean intersect
- [x] Beta: phases on a year slider, from closed meshes
- [x] Beta: paint or outline phases with Grease Pencil or Annotate strokes on the surface
- [ ] Beta: write the class grid as an octree pyramid
- [ ] Beta: try [OpenVDB's `meshToVolume`](https://openvdb.org/documentation/doxygen/MeshToVolume_8h.html) and [trimesh](https://github.com/mikedh/trimesh) as voxelizers
- [ ] Beta: burn classes into point clouds with PDAL ([draft](https://github.com/jo-chemla/blender_ogc3dtiles/blob/main/scripts/pdal_burn_classes.py))
- [x] Raster overlays on point clouds
- [x] Intensity and other number columns on point clouds, with *Custom range* for the ramp
- [x] Intensity and classification from 3dtiled's live COPC tiles (`&attributes=intensity,classification`)
- [x] Quantized-mesh terrain entries
