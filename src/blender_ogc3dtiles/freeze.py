"""Freeze the loaded tiles into plain Blender objects, and place cameras along an animation for streaming.

Freeze: every visible tile (what is on screen now, at the detail it has now) is copied with its modifiers applied
(clipping volumes, shared geometry nodes), except the Points and Splats display, and the copies of each tileset are
joined into one object per kind: meshes, points, splats. Point and splat objects get their display modifier back,
so they look as before, and stay a cloud of vertices underneath: exported without modifiers they are points.

Cameras along the animation: copies of the scene camera at frames of the animation, in one collection. With
"Stream for: Cameras of a collection" every one of them selects tiles at once, so the detail a whole camera path
needs is loaded together, and Freeze keeps it.
"""
from __future__ import annotations

import bpy
from bpy.props import BoolProperty, EnumProperty, IntProperty
from bpy.types import Operator

FROZEN_COLLECTION = "Frozen tiles"
PATH_COLLECTION = "OGC3D Path Cameras"


def _tile_root(o):
    p = o
    for _ in range(6):
        if p is None:
            return None
        if p.get("ogc3dtiles_root"):
            return p
        p = p.parent
    return None


def _visible(o) -> bool:
    p = o
    while p is not None:
        if p.hide_viewport:
            return False
        p = p.parent
    return True


def _kind(o) -> str:
    if o.get("splats"):
        return "splats"
    if o.modifiers.get("Points") is not None:
        return "points"
    return "mesh"


def visible_tiles(context):
    """{(root name, kind): [objects]} of the tiles shown now."""
    from .materials import _is_tile_object
    groups = {}
    for o in context.scene.objects:
        if o.type != "MESH" or o.data is None or not _is_tile_object(o) or not _visible(o):
            continue
        if o.get("tile_bbox"):
            continue
        root = _tile_root(o)
        groups.setdefault((root.name if root else "tiles", _kind(o)), []).append(o)
    return groups


def _frozen_name(root_name: str, kind: str) -> str:
    base = root_name.replace("3D Tiles · ", "")
    return f"Frozen {kind} · {base}"[:62]


def freeze(context, merge=True) -> list:
    """Copies of the visible tiles, joined per tileset and kind. Returns the new objects."""
    from . import io
    groups = visible_tiles(context)
    if not groups:
        return []
    display = {"Points", "Splats"}
    tiles = [o for objs in groups.values() for o in objs]
    off = []
    for o in tiles:                                     # the display modifiers off while the meshes are taken
        for m in o.modifiers:
            if m.name in display and m.show_viewport:
                m.show_viewport = False
                off.append(m)
    context.view_layer.update()
    dg = context.evaluated_depsgraph_get()
    coll = bpy.data.collections.get(FROZEN_COLLECTION)
    if coll is None:
        coll = bpy.data.collections.new(FROZEN_COLLECTION)
        context.scene.collection.children.link(coll)
    out = []
    mats, imgs = {}, {}

    def own(m):
        """A copy of a tile material and of its images: evicting or clearing the live tiles removes theirs."""
        if m is None:
            return None
        if m.name not in mats:
            c = m.copy()
            for n in (c.node_tree.nodes if c.node_tree else ()):
                if n.type == "TEX_IMAGE" and n.image is not None:
                    if n.image.name not in imgs:
                        imgs[n.image.name] = n.image.copy()
                    n.image = imgs[n.image.name]
            mats[m.name] = c
        return mats[m.name]
    try:
        for (root_name, kind), objs in groups.items():
            parts, radii = [], []
            for o in objs:
                me = bpy.data.meshes.new_from_object(o.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
                me.transform(o.matrix_world)
                for i, m in enumerate(me.materials):
                    # point tiles all have the same material: one for the whole cloud
                    me.materials[i] = own(objs[0].data.materials[0] if kind != "mesh" and objs[0].data.materials
                                          else m)
                ob = bpy.data.objects.new(me.name, me)
                coll.objects.link(ob)
                parts.append(ob)
                if kind != "mesh":
                    radii += [float(o.get("point_radius_auto", o.get("point_radius", 0.05)))] * max(len(me.vertices), 1)
            if not parts:
                continue
            if merge and len(parts) > 1:
                with context.temp_override(active_object=parts[0], object=parts[0], selected_objects=parts,
                                           selected_editable_objects=parts):
                    bpy.ops.object.join()
                parts = [parts[0]]
            for ob in parts:
                ob.name = _frozen_name(root_name, kind)
                ob.data.name = ob.name
                if kind == "splats" and io.splats_supported():
                    ob["splats"] = True
                    io._add_splats_modifier(ob)
                elif kind in ("points", "splats"):
                    radii.sort()
                    r = radii[len(radii) // 2] if radii else 0.05
                    ob["point_radius_auto"] = r
                    io._add_points_modifier(ob, r, getattr(context.scene.ogc3dtiles, "point_display", "POINTS"))
                out.append(ob)
    finally:
        for m in off:
            m.show_viewport = True
    return out


class OGC3D_OT_FreezeTiles(Operator):
    """Copy the tiles shown now into plain objects, one per tileset and kind (meshes, points, splats), at the
    detail they have now, with clipping applied. Points stay points: export them without modifiers"""
    bl_idname = "ogc3dtiles.freeze_tiles"
    bl_label = "Freeze Tiles"
    bl_options = {"REGISTER"}

    after: EnumProperty(
        name="Then",
        items=[("CLEAR", "Stop and remove the streamed tiles", "The frozen objects replace the live tiles"),
               ("STOP", "Stop streaming", "Keep the live tiles too, hidden"),
               ("KEEP", "Keep streaming", "The frozen objects sit on top of the live tiles")],
        default="CLEAR",
    )
    merge: BoolProperty(name="One object per tileset and kind", default=True,
                        description="Join the copies; off, one object per tile")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=360)

    def draw(self, context):
        n = sum(len(v) for v in visible_tiles(context).values())
        self.layout.label(text=f"{n} tiles shown now", icon="INFO")
        self.layout.prop(self, "merge")
        self.layout.prop(self, "after", text="Then")

    def execute(self, context):
        props = context.scene.ogc3dtiles
        if self.after != "KEEP" and props.is_streaming:
            bpy.ops.ogc3dtiles.stop_stream()
        new = freeze(context, self.merge)
        if not new:
            self.report({"WARNING"}, "No tile is shown: nothing to freeze")
            return {"CANCELLED"}
        if self.after == "CLEAR":
            bpy.ops.ogc3dtiles.clear_tiles()
        elif self.after == "STOP":
            from .ui import _state
            for st in _state["streams"].values():
                coll = bpy.data.collections.get(st.get("coll") or "")
                if coll is not None:
                    coll.hide_viewport = True
        verts = sum(len(o.data.vertices) for o in new)
        self.report({"INFO"}, f"Frozen into {len(new)} object{'s' if len(new) != 1 else ''}, {verts:,} vertices, "
                              f"in the '{FROZEN_COLLECTION}' collection")
        return {"FINISHED"}


class OGC3D_OT_CamerasAlongPath(Operator):
    """Copies of the scene camera at frames of the animation, in one collection, and 'Stream for' set to that
    collection: the detail the whole path needs loads at once (then Freeze Tiles keeps it)"""
    bl_idname = "ogc3dtiles.cameras_along_path"
    bl_label = "Cameras Along the Animation"
    bl_options = {"REGISTER", "UNDO"}

    count: IntProperty(name="Cameras", default=12, min=2, max=64,
                       description="How many cameras, spread evenly over the frame range")
    viewport: BoolProperty(name="And the viewport", default=False,
                           description="Select tiles for the 3D viewport too")

    @classmethod
    def poll(cls, context):
        return context.scene.camera is not None

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        sc = context.scene
        src = sc.camera
        coll = bpy.data.collections.get(PATH_COLLECTION)
        if coll is None:
            coll = bpy.data.collections.new(PATH_COLLECTION)
            sc.collection.children.link(coll)
        for o in list(coll.objects):
            bpy.data.objects.remove(o)
        f0, f1, keep = sc.frame_start, sc.frame_end, sc.frame_current
        n = self.count
        try:
            for i in range(n):
                f = round(f0 + (f1 - f0) * i / (n - 1))
                sc.frame_set(f)
                cam = bpy.data.objects.new(f"{src.name} @ {f}", src.data)
                cam.matrix_world = src.matrix_world.copy()
                coll.objects.link(cam)
                cam.hide_render = True
        finally:
            sc.frame_set(keep)
        props = sc.ogc3dtiles
        props.view_collection = coll
        props.view_collection_viewport = self.viewport
        props.view_source = "COLLECTION"
        self.report({"INFO"}, f"{n} cameras in '{PATH_COLLECTION}', frames {f0} to {f1}; streaming for them")
        return {"FINISHED"}


def _cloud(o) -> bool:
    return o.type == "MESH" and (o.modifiers.get("Points") is not None or o.modifiers.get("Splats") is not None)


class OGC3D_OT_ExportPoints(Operator):
    """Export the selected point objects (frozen tiles) as a point cloud with its colours: PLY, or glTF POINTS.
    Blender's own exporters, with the settings a cloud needs (no display modifiers, loose vertices, colours)"""
    bl_idname = "ogc3dtiles.export_points"
    bl_label = "Export Points"
    bl_options = {"REGISTER"}

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    filter_glob: bpy.props.StringProperty(default="*.ply;*.glb;*.gltf", options={"HIDDEN"})

    @classmethod
    def poll(cls, context):
        return any(_cloud(o) for o in context.selected_objects)

    def invoke(self, context, event):
        if not self.filepath:
            self.filepath = bpy.path.clean_name(context.active_object.name if context.active_object else "points") + ".ply"
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        path = bpy.path.abspath(self.filepath)
        sel = [o for o in context.selected_objects if _cloud(o)]
        if not sel:
            self.report({"WARNING"}, "Select point objects (Freeze Tiles makes them)")
            return {"CANCELLED"}
        keep = list(context.selected_objects)
        for o in keep:
            o.select_set(o in sel)
        try:
            if path.lower().endswith((".glb", ".gltf")):
                bpy.ops.export_scene.gltf(filepath=path, use_selection=True, export_apply=False,
                                          use_mesh_vertices=True, export_vertex_color="ACTIVE",
                                          export_format="GLB" if path.lower().endswith(".glb") else "GLTF_SEPARATE")
            else:
                if not path.lower().endswith(".ply"):
                    path += ".ply"
                bpy.ops.wm.ply_export(filepath=path, export_selected_objects=True, apply_modifiers=False,
                                      export_normals=False, export_uv=False)
        finally:
            for o in keep:
                o.select_set(True)
        n = sum(len(o.data.vertices) for o in sel)
        self.report({"INFO"}, f"{n:,} points written to {path}")
        return {"FINISHED"}


_classes = (OGC3D_OT_FreezeTiles, OGC3D_OT_CamerasAlongPath, OGC3D_OT_ExportPoints)


def register():
    for c in _classes:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(_classes):
        bpy.utils.unregister_class(c)
