"""phases.py — beta: closed meshes as phases of a monument, on a year slider.

Each mesh of the "Phases" collection is one phase, with custom properties ``code``
(1 to 255), ``year`` and optionally ``color``. A mesh with a ``brush`` property is a
painted phase: its edges are brush strokes of that radius (``phase_strokes``). They are voxelized into a class grid,
written as a plain voxel tileset, which colors other tilesets through ``voxel_lookup``.
Palette alpha says which phases exist at the slider's year. One class per cell: where
volumes overlap, the later year wins and the earlier phase is lost.
"""
from __future__ import annotations

import math
import os
import tempfile

import bpy
import numpy as np
from bpy.props import EnumProperty, FloatProperty, FloatVectorProperty, IntProperty, StringProperty
from bpy.types import Operator

from . import phase_strokes

COLLECTION = "Phases"
COLUMN = "phase"
MAX_CELLS = 11_000_000      # under the lookup's budget, so its grid keeps these cells


def volumes() -> list:
    coll = bpy.data.collections.get(COLLECTION)
    if coll is None:
        return []
    return sorted((o for o in coll.objects if o.type == "MESH" and "code" in o and "year" in o),
                  key=lambda o: o["year"])


def _world_mesh(obj):
    """(BVH, vertices, open edges) in world space, modifiers applied."""
    import bmesh
    from mathutils.bvhtree import BVHTree
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    bm = bmesh.new()
    bm.from_mesh(evaluated.to_mesh())
    bm.transform(obj.matrix_world)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    open_edges = sum(not e.is_manifold for e in bm.edges)
    verts = [v.co.copy() for v in bm.verts]
    tris = [[v.index for v in f.verts] for f in bm.faces]
    bm.free()
    evaluated.to_mesh_clear()
    return BVHTree.FromPolygons(verts, tris), np.array(verts).reshape(-1, 3), open_edges


def _strokes(obj):
    """(vertices in world space, edges) of a painted phase."""
    mesh = obj.data
    verts = np.zeros(len(mesh.vertices) * 3, np.float32)
    mesh.vertices.foreach_get("co", verts)
    edges = np.zeros(len(mesh.edges) * 2, np.int32)
    mesh.edges.foreach_get("vertices", edges)
    world = np.array(obj.matrix_world)
    return verts.reshape(-1, 3).astype(np.float64) @ world[:3, :3].T + world[:3, 3], edges.reshape(-1, 2)


def _fill(grid, obj, lo, cell) -> int:
    """Set the cells inside a closed mesh: one vertical ray per column, whose crossings
    pair up into inside spans. Returns the cells set, -1 when the mesh isn't closed.
    A painted phase sets the cells within its brush radius of its strokes."""
    from mathutils import Vector
    if "brush" in obj:
        cells = phase_strokes.brush_cells(*_strokes(obj), float(obj["brush"]), lo, cell, grid.shape)
        grid[cells[:, 0], cells[:, 1], cells[:, 2]] = int(obj["code"])
        return len(cells)
    bvh, verts, open_edges = _world_mesh(obj)
    if open_edges or not len(verts):
        return -1
    nx, ny, nz = grid.shape
    i0, j0 = np.floor((verts[:, :2].min(0) - lo[:2]) / cell).astype(int)
    i1, j1 = np.ceil((verts[:, :2].max(0) - lo[:2]) / cell).astype(int)
    start = float(verts[:, 2].min()) - 1.0
    up = Vector((0.0, 0.0, 1.0))
    code, filled = int(obj["code"]), 0
    for i in range(max(i0, 0), min(i1, nx)):
        x = lo[0] + (i + 0.5) * cell
        for j in range(max(j0, 0), min(j1, ny)):
            at, crossings = Vector((x, lo[1] + (j + 0.5) * cell, start)), []
            while True:
                hit = bvh.ray_cast(at, up)
                if hit[0] is None:
                    break
                crossings.append(hit[0].z)
                at = hit[0] + up * 1e-3
            if len(crossings) % 2:      # the ray grazed an edge: leave the column out
                continue
            for a, b in zip(crossings[::2], crossings[1::2]):
                k0 = max(int(math.ceil((a - lo[2]) / cell - 0.5)), 0)
                k1 = min(int(math.ceil((b - lo[2]) / cell - 0.5)), nz)
                if k1 > k0:
                    grid[i, j, k0:k1] = code
                    filled += k1 - k0
    return filled


def build(folder, scene, pad=2.0):
    """Voxelize the collection into a tileset in ``folder``, around the volumes and in the
    scene's east, north, up axes. Returns (tileset path, names of meshes left out)."""
    from .tileset import voxels
    from .tileset.native_backend import enu_from_ecef_matrix
    props = scene.ogc3dtiles
    objs = volumes()
    boxes = []
    for o in objs:
        pts, reach = (_strokes(o)[0], float(o["brush"])) if "brush" in o else (_world_mesh(o)[1], 0.0)
        if len(pts):
            boxes += [pts.min(0) - reach, pts.max(0) + reach]
    lo, hi = np.min(boxes, axis=0) - pad, np.max(boxes, axis=0) + pad
    cell = float(np.cbrt(np.prod(hi - lo) / MAX_CELLS))
    grid = np.zeros(tuple(int(n) for n in np.ceil((hi - lo) / cell)), np.uint8)
    skipped = [o.name for o in objs if _fill(grid, o, lo, cell) < 0]
    frame = np.linalg.inv(enu_from_ecef_matrix(props.origin_lat, props.origin_lon, props.origin_height))
    center = lo + np.array(grid.shape) * cell / 2.0
    return voxels.write_class_tileset(folder, grid, frame, center, cell, COLUMN), skipped


def apply_year(scene) -> None:
    """Palette alpha from the slider, on what ``materials.write_palette`` wrote."""
    from .io import addon_pref
    from .materials import META_PALETTE
    props = scene.ogc3dtiles
    img = bpy.data.images.get(META_PALETTE)
    objs = volumes()
    if img is None or not objs or props.meta_column != COLUMN or not addon_pref("beta_phases", False):
        return
    px = np.array(img.pixels[:], np.float32).reshape(-1, 4)
    for o in objs:
        slot = int(o["code"]) + 1       # a class of whole number N sits at N + 1
        if slot < len(px):
            if "color" in o:
                px[slot, :3] = list(o["color"])[:3]
            px[slot, 3] = 1.0 if o["year"] <= props.phase_year else 0.0
    img.pixels.foreach_set(px.ravel())
    img.update()
    img.pack()


def _default_folder() -> str:
    if bpy.data.filepath:
        return bpy.path.abspath("//phases_tileset")
    return os.path.join(tempfile.gettempdir(), "ogc3d_phases")


class OGC3D_OT_PhasesBuild(Operator):
    """Voxelize the Phases collection into a voxel tileset and add it to the list"""
    bl_idname = "ogc3dtiles.phases_build"
    bl_label = "Build class grid"

    folder: StringProperty(name="Folder", subtype="DIR_PATH", options={"SKIP_SAVE"})

    @classmethod
    def poll(cls, context):
        return bool(volumes()) and context.scene.ogc3dtiles.origin_valid

    def execute(self, context):
        props = context.scene.ogc3dtiles
        path, skipped = build(bpy.path.abspath(self.folder) if self.folder else _default_folder(), context.scene)
        if not any(it.url == path for it in props.tilesets):
            item = props.tilesets.add()
            item.name, item.url = "Phases", path
        props.voxel_display = "PROJECT"
        if skipped:
            self.report({"WARNING"}, f"Not closed, left out: {', '.join(skipped)}")
        else:
            self.report({"INFO"}, "Class grid written: Start to load it")
        return {"FINISHED"}


class OGC3D_OT_PhaseFromStrokes(Operator):
    """Strokes drawn with Annotate or the active Grease Pencil object become a phase: painted over the surface, or outlines turned into prisms"""
    bl_idname = "ogc3dtiles.phase_from_strokes"
    bl_label = "Phase from strokes"
    bl_options = {"REGISTER", "UNDO"}

    code: IntProperty(name="Code", description="Class of this phase in the grid",
                      default=1, min=1, max=255)
    year: IntProperty(name="Year", default=1500, min=-5000, max=3000)
    color: FloatVectorProperty(name="Color", subtype="COLOR", size=3, min=0.0, max=1.0,
                               default=(0.9, 0.5, 0.2))
    mode: EnumProperty(name="Strokes are", items=[
        ("PAINT", "Painted areas", "Everything within the brush radius of a stroke is in the phase: "
                                   "scribble over the area. Follows curved surfaces"),
        ("OUTLINE", "Outlines", "Each stroke is the outline of a flat area, turned into a prism through "
                                "the surface"),
    ], default="PAINT")
    brush: FloatProperty(name="Brush radius (m)", description="Painted areas: how far around a stroke "
                         "the phase reaches, in depth too", default=0.5, min=0.01, max=1000.0)
    back: FloatProperty(name="Behind (m)", description="How far the volume goes behind the outline",
                        default=1.0, min=0.0, max=1000.0)
    front: FloatProperty(name="In front (m)", description="How far the volume comes toward the viewer",
                         default=0.25, min=0.0, max=1000.0)

    def invoke(self, context, event):
        used = {int(o["code"]) for o in volumes()}
        self.code = next(c for c in range(1, 256) if c not in used)
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        for name in ("code", "year", "color", "mode"):
            layout.prop(self, name)
        for name in (("brush",) if self.mode == "PAINT" else ("back", "front")):
            layout.prop(self, name)

    def _add(self, coll, verts, edges, faces):
        mesh = bpy.data.meshes.new(f"Phase {self.year}")
        mesh.from_pydata(verts, edges, faces)
        mesh.update()
        obj = bpy.data.objects.new(mesh.name, mesh)
        coll.objects.link(obj)
        obj["code"], obj["year"], obj["color"] = self.code, self.year, list(self.color)
        obj.display_type = "WIRE"
        obj.hide_render = True
        return obj

    def execute(self, context):
        from mathutils import Vector
        loops = phase_strokes.stroke_loops(context)
        if not loops:
            self.report({"WARNING"}, "No strokes: draw with Annotate or a Grease Pencil object first")
            return {"CANCELLED"}
        rv3d = context.region_data
        toward = np.array(rv3d.view_rotation @ Vector((0.0, 0.0, 1.0))) if rv3d is not None else None
        coll = bpy.data.collections.get(COLLECTION) or bpy.data.collections.new(COLLECTION)
        if coll.name not in context.scene.collection.children:
            context.scene.collection.children.link(coll)
        made = 0
        if self.mode == "PAINT":
            verts, edges = [], []
            for loop in loops:
                edges += [(len(verts) + i, len(verts) + i + 1) for i in range(len(loop) - 1)]
                verts += loop.tolist()
            self._add(coll, verts, edges, [])["brush"] = self.brush
            made = 1
        for loop in (loops if self.mode == "OUTLINE" else ()):
            solid = phase_strokes.prism(loop, toward, self.front, self.back, min_step=0.02)
            if solid is None:
                continue
            self._add(coll, solid[0].tolist(), [], solid[1])
            made += 1
        if not made:
            self.report({"WARNING"}, "The strokes outline no area")
            return {"CANCELLED"}
        self.report({"INFO"}, f"{made} volume(s) added to '{COLLECTION}': Build class grid next")
        return {"FINISHED"}



def draw_panel(layout, context) -> None:
    from .io import addon_pref
    props = context.scene.ogc3dtiles
    objs = volumes()
    if addon_pref("beta_phase_strokes", False):
        box = layout.box()
        box.label(text="Paint or outline a phase on the surface", icon="GREASEPENCIL")
        box.label(text="Annotate (placement: Surface), then:")
        box.operator(OGC3D_OT_PhaseFromStrokes.bl_idname, icon="MOD_SOLIDIFY")
    if not objs:
        layout.label(text=f"Add closed meshes to a '{COLLECTION}' collection,", icon="INFO")
        layout.label(text="with custom properties code and year")
        return
    layout.prop(props, "phase_year")
    layout.prop(props, "voxel_cut", text="Clip to phases")
    col = layout.column(align=True)
    for o in objs:
        row = col.row()
        row.active = o["year"] <= props.phase_year
        row.label(text=f"{o['year']}: {o.name}")
    layout.operator(OGC3D_OT_PhasesBuild.bl_idname, icon="MOD_REMESH")
    if not props.origin_valid:
        layout.label(text="Set the scene origin first", icon="INFO")
