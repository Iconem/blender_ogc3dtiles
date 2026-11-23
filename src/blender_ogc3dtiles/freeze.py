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
    detail they have now, with clipping applied. Export Frozen writes them out"""
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

    @classmethod
    def poll(cls, context):
        return context.scene.camera is not None

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
        n = sc.ogc3dtiles.path_camera_count
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
        props.view_collection_viewport = False      # the path's detail only, never the viewport's
        props.view_source = "COLLECTION"
        self.report({"INFO"}, f"{n} cameras in '{PATH_COLLECTION}', frames {f0} to {f1}; streaming for them")
        return {"FINISHED"}


def _cloud(o) -> bool:
    return o.type == "MESH" and (o.modifiers.get("Points") is not None or o.modifiers.get("Splats") is not None)


def frozen_selection(context):
    """Selected frozen (or any non-tile) mesh objects."""
    return [o for o in context.selected_objects if o.type == "MESH" and "tile_url" not in o]


_EXT = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp", "TARGA": ".tga", "BMP": ".bmp", "TIFF": ".tif"}


def _write_image(img, folder) -> str:
    """The image beside the export, as its original bytes when packed. Returns the file name, or ''."""
    import os
    base = bpy.path.clean_name(img.name)
    pf = img.packed_file
    try:
        if pf is not None and pf.size:
            name = base + _EXT.get(img.file_format, ".png")
            with open(os.path.join(folder, name), "wb") as fh:
                fh.write(bytes(pf.data))
            return name
        if img.has_data or img.size[0]:
            name = base + ".png"
            img.save(filepath=os.path.join(folder, name))
            return name
    except Exception:
        pass
    return ""


def obj_textures(mtl_path, objs) -> int:
    """Blender's OBJ exporter finds no texture in tile materials (their images are packed and pass through
    other nodes): write each material's image beside the file and point the .mtl at it."""
    import os
    if not os.path.isfile(mtl_path):
        return 0
    by_name = {}
    for o in objs:
        for m in o.data.materials:
            if m is not None and m.node_tree is not None:
                img = next((n.image for n in m.node_tree.nodes if n.type == "TEX_IMAGE" and n.image is not None), None)
                if img is not None:
                    by_name[m.name] = by_name[m.name.replace(" ", "_")] = img
    folder = os.path.dirname(mtl_path)
    written, out, n = {}, [], 0
    with open(mtl_path, encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    img = None
    for ln in lines:
        if ln.startswith("newmtl "):
            if img is not None:
                out.append(f"map_Kd {written[img.name]}")
                n += 1
            img = by_name.get(ln[7:].strip())
            if img is not None and img.name not in written:
                written[img.name] = _write_image(img, folder)
            if img is not None and not written[img.name]:
                img = None
        elif img is not None and ln.startswith("Kd "):
            ln = "Kd 1.000000 1.000000 1.000000"
        elif img is not None and ln.startswith("map_Kd "):
            continue
        out.append(ln)
    if img is not None:
        out.append(f"map_Kd {written[img.name]}")
        n += 1
    with open(mtl_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out) + "\n")
    return n


def _plain_material(m):
    """A Principled material with the tile's photo as Base Color, nothing else: what glTF can say. Tile
    materials pass the photo through the shared shader group and the clip and X-ray mixes, and the glTF
    exporter then writes it again as an emissive texture, and once more for the alpha."""
    img = None
    if m is not None and m.node_tree is not None:
        img = next((n.image for n in m.node_tree.nodes if n.type == "TEX_IMAGE" and n.image is not None), None)
    pm = bpy.data.materials.new((m.name if m else "material")[:50] + " (export)")
    pm.use_nodes = True
    nt = pm.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Roughness"].default_value = 1.0
    bsdf.inputs["Metallic"].default_value = 0.0
    if img is not None:
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = img
        tex.location = (-400, 300)
        nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    elif m is not None:
        bsdf.inputs["Base Color"].default_value = tuple(m.diffuse_color)
    return pm


class _PlainMaterials:
    """For the export only: frozen meshes get plain materials, put back afterwards."""
    def __init__(self, objs):
        self.objs, self.swaps, self.made = objs, [], {}

    def __enter__(self):
        for o in self.objs:
            for i, slot in enumerate(o.material_slots):
                m = slot.material
                key = m.name if m else ""
                if key not in self.made:
                    self.made[key] = _plain_material(m)
                self.swaps.append((slot, m))
                slot.material = self.made[key]
        return self

    def __exit__(self, *exc):
        for slot, m in self.swaps:
            slot.material = m
        for pm in self.made.values():
            bpy.data.materials.remove(pm)
        return False


class OGC3D_OT_ExportFrozen(Operator):
    """Export the selected frozen tiles with the settings they need. Glb or glTF: meshes with their textures,
    clouds as POINTS with their colours. PLY: clouds or meshes, without textures. OBJ: meshes with their
    textures copied beside the file"""
    bl_idname = "ogc3dtiles.export_frozen"
    bl_label = "Export Frozen"
    bl_options = {"REGISTER"}

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    filter_glob: bpy.props.StringProperty(default="*.glb;*.gltf;*.ply;*.obj", options={"HIDDEN"})

    @classmethod
    def poll(cls, context):
        return bool(frozen_selection(context))

    def invoke(self, context, event):
        if not self.filepath:
            sel = frozen_selection(context)
            ext = ".ply" if sel and all(_cloud(o) for o in sel) else ".glb"
            self.filepath = bpy.path.clean_name(context.active_object.name if context.active_object else "frozen") + ext
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        path = bpy.path.abspath(self.filepath)
        sel = frozen_selection(context)
        if not sel:
            self.report({"WARNING"}, "Select frozen objects (Freeze Tiles makes them)")
            return {"CANCELLED"}
        clouds = [o for o in sel if _cloud(o)]
        low = path.lower()
        if not low.endswith((".glb", ".gltf", ".ply", ".obj")):
            path += ".ply" if len(clouds) == len(sel) else ".glb"
            low = path.lower()
        if low.endswith(".obj") and clouds:
            self.report({"WARNING"}, "OBJ has no point clouds: the clouds are left out (use PLY or glb)")
            sel = [o for o in sel if not _cloud(o)]
            if not sel:
                return {"CANCELLED"}
        keep = list(context.selected_objects)
        for o in keep:
            o.select_set(o in sel)
        try:
            # No display modifier applied: clouds stay vertices (frozen meshes have no modifiers left)
            if low.endswith((".glb", ".gltf")):
                with _PlainMaterials([o for o in sel if not _cloud(o)]):
                    bpy.ops.export_scene.gltf(filepath=path, use_selection=True, export_apply=False,
                                              use_mesh_vertices=bool(clouds),
                                              export_vertex_color="ACTIVE" if clouds else "MATERIAL",
                                              export_format="GLB" if low.endswith(".glb") else "GLTF_SEPARATE")
            elif low.endswith(".obj"):
                bpy.ops.wm.obj_export(filepath=path, export_selected_objects=True, apply_modifiers=False,
                                      export_materials=True, path_mode="STRIP")
                obj_textures(path[:-4] + ".mtl", sel)
            else:
                bpy.ops.wm.ply_export(filepath=path, export_selected_objects=True, apply_modifiers=False,
                                      export_normals=not clouds, export_uv=not clouds)
        finally:
            for o in keep:
                o.select_set(True)
        nv = sum(len(o.data.vertices) for o in sel if _cloud(o))
        nf = sum(len(o.data.polygons) for o in sel if not _cloud(o))
        what = ", ".join(x for x in (f"{nv:,} points" if nv else "", f"{nf:,} faces" if nf else "") if x)
        self.report({"INFO"}, f"{what} written to {path}")
        return {"FINISHED"}


_classes = (OGC3D_OT_FreezeTiles, OGC3D_OT_CamerasAlongPath, OGC3D_OT_ExportFrozen)


def register():
    for c in _classes:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(_classes):
        bpy.utils.unregister_class(c)
