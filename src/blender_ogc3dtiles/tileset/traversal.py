"""
Tile traversal — pure Python 3D Tiles selection (no bpy, no numpy required).

What this module does
---------------------
  - Tile tree with bounding volumes, geometric error, content URI and the
    accumulated ``transform`` of every node (tileset.json transforms are
    column-major 4x4 and compose down the tree).
  - Screen-space error:  sse = ge * viewport_h * p11 / (2 * dist)
    where p11 is the [1][1] entry of the projection matrix (1/tan(fov_y/2)
    for a perspective view).  ``compute_sse`` keeps the old
    (tile, camera_pos, screen_h, fov_y) signature for tests.
  - ``select()`` is the real traversal used by the add-on:
      * frustum culling against the viewport's own frustum planes (ECEF),
      * horizon / max-distance culling,
      * distance-scaled threshold  thr(d) = max_sse * (1 + d / detail_falloff)
        (CesiumJS "dynamic screen space error": detail concentrates near the
        camera, far regions settle at coarse LODs so streaming converges),
      * REPLACE refinement keeps the parent visible until every visible child
        subtree is ready (no holes while loading),
      * ADD refinement renders parent and children together,
      * external tileset.json nodes are requested and grafted by the caller,
      * load requests come back ordered by priority (largest SSE first).

References: cesium-native Cesium3DTilesSelection/src/TilesetTraversal.cpp,
OGC 3D Tiles 1.1 (https://docs.ogc.org/cs/22-025r4/22-025r4.html).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

MAX_DEPTH = 64


class TileState(Enum):
    UNLOADED = auto()
    LOADING = auto()
    LOADED = auto()
    RENDERED = auto()
    FAILED = auto()


# ── small 4x4 helpers (row-major nested lists) ───────────────────────────────

def mat_identity() -> List[List[float]]:
    return [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]]


def mat_mul(a: Sequence[Sequence[float]], b: Sequence[Sequence[float]]) -> List[List[float]]:
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def mat_from_column_major(t: Sequence[float]) -> List[List[float]]:
    """tileset.json ``transform`` is 16 floats, column-major."""
    return [[float(t[c * 4 + r]) for c in range(4)] for r in range(4)]


def mat_apply(m: Sequence[Sequence[float]], p: Sequence[float]) -> Tuple[float, float, float]:
    x, y, z = p
    return (m[0][0] * x + m[0][1] * y + m[0][2] * z + m[0][3],
            m[1][0] * x + m[1][1] * y + m[1][2] * z + m[1][3],
            m[2][0] * x + m[2][1] * y + m[2][2] * z + m[2][3])


def mat_translation(v: Sequence[float]) -> List[List[float]]:
    m = mat_identity()
    m[0][3], m[1][3], m[2][3] = float(v[0]), float(v[1]), float(v[2])
    return m


def _max_scale(m: Sequence[Sequence[float]]) -> float:
    return max(math.sqrt(m[0][c] ** 2 + m[1][c] ** 2 + m[2][c] ** 2) for c in range(3)) or 1.0


# ── bounding volumes ─────────────────────────────────────────────────────────

@dataclass
class BoundingVolume:
    """Union of the three OGC 3D Tiles bounding volume types."""
    region: Optional[List[float]] = None   # [west, south, east, north, minH, maxH] rad/m
    box: Optional[List[float]] = None      # [cx,cy,cz, hx(3), hy(3), hz(3)] 12-element OBB
    sphere: Optional[List[float]] = None   # [cx,cy,cz, radius]

    @classmethod
    def from_dict(cls, d: Dict) -> "BoundingVolume":
        return cls(region=d.get("region"), box=d.get("box"), sphere=d.get("sphere"))

    def center_ecef(self, transform: Optional[Sequence[Sequence[float]]] = None) -> tuple:
        """ECEF centre. ``box``/``sphere`` live in the tile frame and need the
        accumulated tile transform; ``region`` is already geodetic."""
        if self.region:
            west, south, east, north, minH, maxH = self.region
            return _geodetic_to_ecef(math.degrees((south + north) / 2),
                                     math.degrees((west + east) / 2),
                                     (minH + maxH) / 2)
        if self.sphere:
            c = tuple(self.sphere[:3])
        elif self.box:
            c = tuple(self.box[:3])
        else:
            return (0.0, 0.0, 0.0)
        return mat_apply(transform, c) if transform is not None else c

    def geometric_radius(self, transform: Optional[Sequence[Sequence[float]]] = None) -> float:
        """Conservative bounding-sphere radius in metres."""
        s = _max_scale(transform) if transform is not None else 1.0
        if self.sphere:
            return self.sphere[3] * s
        if self.box:
            hx = self.box[3:6]
            hy = self.box[6:9]
            hz = self.box[9:12]
            return s * (math.sqrt(sum(v * v for v in hx)) + math.sqrt(sum(v * v for v in hy))
                        + math.sqrt(sum(v * v for v in hz)))
        if self.region:
            west, south, east, north, minH, maxH = self.region
            lat = (south + north) / 2
            dlat = (north - south) * 6371000
            dlon = (east - west) * 6371000 * math.cos(lat)
            dh = (maxH - minH)
            return math.sqrt(dlat ** 2 + dlon ** 2 + dh ** 2) / 2
        return 1.0


# ── tiles ────────────────────────────────────────────────────────────────────

@dataclass
class Tile:
    bounding_volume: BoundingVolume
    geometric_error: float               # metres
    content_uri: Optional[str]           # resolved absolute URI or None
    children: List["Tile"] = field(default_factory=list)
    refine: str = "ADD"                  # 'ADD' or 'REPLACE'
    state: TileState = TileState.UNLOADED
    blender_obj_name: Optional[str] = None
    request_handle: Any = None
    _cache_key: Optional[str] = None
    transform: List[List[float]] = field(default_factory=mat_identity)   # accumulated (world)
    parent: Optional["Tile"] = field(default=None, repr=False, compare=False)
    grafted: bool = False                # external tileset.json already merged
    _sphere: Optional[Tuple[float, float, float, float]] = field(default=None, repr=False)

    @classmethod
    def from_dict(cls, d: Dict, base_url: str,
                  parent_transform: Optional[Sequence[Sequence[float]]] = None,
                  parent_refine: str = "ADD") -> "Tile":
        bv = BoundingVolume.from_dict(d["boundingVolume"])
        ge = float(d.get("geometricError", 0.0))
        refine = d.get("refine", parent_refine).upper()
        world = list(parent_transform) if parent_transform is not None else mat_identity()
        if "transform" in d and d["transform"]:
            world = mat_mul(world, mat_from_column_major(d["transform"]))
        content_uri = None
        if "content" in d:
            uri = d["content"].get("uri") or d["content"].get("url", "")
            content_uri = _resolve_uri(uri, base_url) if uri else None
        tile = cls(bounding_volume=bv, geometric_error=ge, content_uri=content_uri,
                   refine=refine, transform=world)
        tile.children = [Tile.from_dict(c, base_url, world, refine) for c in d.get("children", [])]
        for c in tile.children:
            c.parent = tile
        return tile

    # cached ECEF bounding sphere ------------------------------------------------
    def sphere_ecef(self) -> Tuple[float, float, float, float]:
        if self._sphere is None:
            cx, cy, cz = self.bounding_volume.center_ecef(self.transform)
            self._sphere = (cx, cy, cz, self.bounding_volume.geometric_radius(self.transform))
        return self._sphere

    def invalidate_cache(self) -> None:
        self._sphere = None

    @property
    def is_external_tileset(self) -> bool:
        return bool(self.content_uri) and is_tileset_uri(self.content_uri)

    @property
    def has_drawable(self) -> bool:
        return bool(self.content_uri) and not is_tileset_uri(self.content_uri)


def is_tileset_uri(uri: str) -> bool:
    return uri.split("?", 1)[0].lower().endswith(".json")


# ── camera / view state ──────────────────────────────────────────────────────

@dataclass
class ViewState:
    """Everything the traversal needs, in ECEF. Built by camera.CesiumCameraAdapter."""
    position: Tuple[float, float, float]
    direction: Tuple[float, float, float] = (0.0, 0.0, -1.0)
    up: Tuple[float, float, float] = (0.0, 0.0, 1.0)
    viewport_width: int = 1920
    viewport_height: int = 1080
    p11: float = 1.0 / math.tan(math.radians(30.0))   # projection[1][1]
    p00: float = 1.0 / math.tan(math.radians(30.0)) / (16 / 9)
    is_persp: bool = True
    frustum_planes: Optional[List[Tuple[float, float, float, float]]] = None  # (nx,ny,nz,d) in ECEF
    signature: tuple = ()

    @property
    def fov_y(self) -> float:
        return 2.0 * math.atan(1.0 / self.p11) if self.is_persp else math.radians(1.0)

    @property
    def fov_x(self) -> float:
        return 2.0 * math.atan(1.0 / self.p00) if self.is_persp else math.radians(1.0)

    @classmethod
    def from_simple(cls, position, screen_height_px: int, fov_y_rad: float) -> "ViewState":
        """Legacy constructor: position + vertical FOV, no frustum culling."""
        p11 = 1.0 / math.tan(fov_y_rad / 2.0)
        return cls(position=tuple(position), viewport_height=int(screen_height_px),
                   viewport_width=int(screen_height_px * 16 / 9), p11=p11,
                   p00=p11 * 9 / 16, frustum_planes=None,
                   signature=(tuple(round(v, 1) for v in position), screen_height_px, round(p11, 4)))


def frustum_planes_from_matrix(m: Sequence[Sequence[float]]) -> List[Tuple[float, float, float, float]]:
    """Gribb/Hartmann planes from a clip = m @ world matrix (row-major).
    Planes are (nx, ny, nz, d) with n·x + d >= 0 inside."""
    rows = [list(m[i]) for i in range(4)]
    raw = [
        [rows[3][i] + rows[0][i] for i in range(4)],   # left
        [rows[3][i] - rows[0][i] for i in range(4)],   # right
        [rows[3][i] + rows[1][i] for i in range(4)],   # bottom
        [rows[3][i] - rows[1][i] for i in range(4)],   # top
        [rows[3][i] + rows[2][i] for i in range(4)],   # near
        [rows[3][i] - rows[2][i] for i in range(4)],   # far
    ]
    out = []
    for a, b, c, d in raw:
        n = math.sqrt(a * a + b * b + c * c)
        if n < 1e-12:
            continue
        out.append((a / n, b / n, c / n, d / n))
    return out


def transform_planes(planes, rot: Sequence[Sequence[float]], origin: Sequence[float]):
    """Planes expressed in a frame F (x_world = rot @ x_F + origin) → world frame."""
    out = []
    ox, oy, oz = origin
    for nx, ny, nz, d in planes:
        wx = rot[0][0] * nx + rot[0][1] * ny + rot[0][2] * nz
        wy = rot[1][0] * nx + rot[1][1] * ny + rot[1][2] * nz
        wz = rot[2][0] * nx + rot[2][1] * ny + rot[2][2] * nz
        out.append((wx, wy, wz, d - (wx * ox + wy * oy + wz * oz)))
    return out


def sphere_in_frustum(cx, cy, cz, r, planes) -> bool:
    if not planes:
        return True
    for nx, ny, nz, d in planes:
        if nx * cx + ny * cy + nz * cz + d < -r:
            return False
    return True


# ── screen space error ───────────────────────────────────────────────────────

def _sse(ge: float, dist: float, view: ViewState) -> float:
    if ge <= 0.0:
        return 0.0
    if view.is_persp:
        return ge * view.viewport_height * view.p11 / (2.0 * max(dist, 1e-6))
    return ge * view.viewport_height * view.p11 / 2.0


def compute_sse(tile: Tile, camera_pos_ecef: tuple, screen_height_px: int,
                fov_y_rad: float) -> float:
    """Legacy helper: SSE = geometricError / distance * (screenHeight / (2 tan(fov/2)))."""
    if tile.geometric_error == 0:
        return 0.0
    cx, cy, cz, r = tile.sphere_ecef()
    px, py, pz = camera_pos_ecef
    dist = math.sqrt((cx - px) ** 2 + (cy - py) ** 2 + (cz - pz) ** 2)
    dist = max(dist - r, 1.0)
    ssf = screen_height_px / (2.0 * math.tan(fov_y_rad / 2.0))
    return (tile.geometric_error / dist) * ssf


# ── selection ────────────────────────────────────────────────────────────────

@dataclass
class Selection:
    render: List[Tile] = field(default_factory=list)         # visible this frame
    load: List[Tuple[float, Tile]] = field(default_factory=list)   # (priority, tile) desc
    keep: set = field(default_factory=set)                   # ids touched (eviction grace)
    visited: int = 0
    culled: int = 0


def select(root: Tile, view: ViewState, max_sse: float,
           is_ready: Callable[[Tile], bool],
           detail_falloff: float = 600.0,
           max_dist: float = float("inf"),
           max_depth: int = MAX_DEPTH) -> Selection:
    """SSE traversal with frustum + distance culling, dynamic SSE and REPLACE
    gating. ``is_ready(tile)`` must say whether the tile's content is imported
    (external-tileset nodes count as ready once grafted)."""
    sel = Selection()
    queued: set = set()
    px, py, pz = view.position

    def want(node: Tile, prio: float, depth: int = 0) -> None:
        """Queue a load. Ancestors go first (CesiumJS does the same): while a
        parent is missing nothing can be shown for its whole region, so a
        shallow tile is always worth more than a deep one."""
        if id(node) not in queued:
            queued.add(id(node))
            sel.load.append((prio - depth * 1e5, node))

    def visible(node: Tile):
        """→ (dist, err) or None when culled."""
        cx, cy, cz, r = node.sphere_ecef()
        if not sphere_in_frustum(cx, cy, cz, r, view.frustum_planes):
            return None
        dist = math.sqrt((cx - px) ** 2 + (cy - py) ** 2 + (cz - pz) ** 2) - r
        if dist > max_dist:
            return None
        dist = max(dist, 1.0)
        return dist, _sse(node.geometric_error, dist, view)

    def wants_children(node: Tile, dist: float, err: float) -> bool:
        thr = max_sse * (1.0 + dist / max(detail_falloff, 1.0))
        return (err > thr or not node.has_drawable) and bool(node.children)

    def child_ready(node: Tile, depth: int) -> bool:
        """Can ``node`` stand in for its parent right now?  Like CesiumJS
        (without skipLevelOfDetail): a parent refines as soon as each visible
        child is *renderable* — its own content imported, or, for a
        contentless / not-yet-grafted node, its children renderable.  We do
        NOT require the grandchildren the child itself may want: the child
        renders itself until they arrive, so a zoom only ever falls back one
        level, never to the root."""
        if depth > max_depth:
            return True
        if visible(node) is None:
            return True                      # culled: nothing to show anyway
        if node.is_external_tileset:
            return node.grafted and all(child_ready(c, depth + 1) for c in node.children)
        if node.has_drawable:
            return is_ready(node)
        return all(child_ready(c, depth + 1) for c in node.children)

    def subtree_ready(node: Tile, depth: int) -> bool:
        return all(child_ready(c, depth + 1) for c in node.children)

    # (node, depth, load_only): load_only walks a REPLACE subtree whose parent
    # is still rendering and requests the content that will replace it.
    stack: List[Tuple[Tile, int, bool]] = [(root, 0, False)]
    while stack:
        node, depth, load_only = stack.pop()
        sel.visited += 1
        v = visible(node)
        if v is None:
            sel.culled += 1
            continue
        dist, err = v
        sel.keep.add(id(node))
        wc = wants_children(node, dist, err) and depth < max_depth

        if node.is_external_tileset and not node.grafted:
            want(node, err + 1e7, depth)     # tileset.json first, always
            continue

        if node.refine == "ADD":
            if node.has_drawable:
                if not load_only:
                    sel.render.append(node)
                if not is_ready(node):
                    want(node, err, depth)
            if wc:
                for c in node.children:
                    stack.append((c, depth + 1, load_only))
            continue

        # REPLACE
        if not wc:
            if node.has_drawable:
                if not is_ready(node):
                    want(node, err, depth)
                    # zoom-out: this coarser tile is not in yet but the finer
                    # children we were showing are — keep them on screen
                    # instead of dropping to nothing until it arrives
                    if node.children and subtree_ready(node, depth):
                        for c in node.children:
                            stack.append((c, depth + 1, load_only))
                        continue
                if not load_only:
                    sel.render.append(node)
            continue
        if load_only:
            # the parent above us waits for *this* node's content (one-level
            # gating), so request it even though we would refine it later
            if node.has_drawable and not is_ready(node):
                want(node, err, depth)
            for c in node.children:
                stack.append((c, depth + 1, True))
            continue
        if subtree_ready(node, depth) or not node.has_drawable:
            for c in node.children:
                stack.append((c, depth + 1, False))
        else:
            sel.render.append(node)          # keep parent until children are in
            if not is_ready(node):
                want(node, err, depth)
            for c in node.children:
                stack.append((c, depth + 1, True))

    sel.load.sort(key=lambda t: -t[0])
    return sel


class TilesetTraversal:
    """Stateful wrapper: diff of the render set between frames.

    ``update_view(camera_pos, screen_h, fov_y)`` is the legacy entry point
    (no culling); ``update_view_state(view, is_ready)`` is the full one."""

    def __init__(self, root: Tile = None, max_sse: float = 16.0, max_tiles: int = 200,
                 detail_falloff: float = 600.0, max_dist: float = float("inf")):
        self.root = root
        self.max_sse = max_sse
        self.max_tiles = max_tiles
        self.detail_falloff = detail_falloff
        self.max_dist = max_dist
        self._render_set: Dict[int, Tile] = {}
        self.last_selection: Optional[Selection] = None

    def update_view_state(self, view: ViewState,
                          is_ready: Callable[[Tile], bool] = None) -> tuple:
        if self.root is None:
            return [], [], []
        if is_ready is None:
            def is_ready(t):   # noqa: E306
                return t.state in (TileState.LOADED, TileState.RENDERED)
        sel = select(self.root, view, self.max_sse, is_ready,
                     detail_falloff=self.detail_falloff, max_dist=self.max_dist)
        self.last_selection = sel
        new_render = {id(t): t for t in sel.render}
        to_unload = [self._render_set[k] for k in set(self._render_set) - set(new_render)]
        self._render_set = new_render
        return [t for _p, t in sel.load], list(new_render.values()), to_unload

    def update_view(self, camera_pos_ecef: tuple, screen_height_px: int,
                    fov_y_rad: float) -> tuple:
        """Legacy signature. REPLACE gating is disabled here (everything counts
        as ready) so the selection reflects the camera alone."""
        view = ViewState.from_simple(camera_pos_ecef, screen_height_px, fov_y_rad)
        return self.update_view_state(view, is_ready=lambda t: True)


# ── tileset.json parsing ─────────────────────────────────────────────────────

def parse_tileset(data: dict, base_url: str,
                  parent_transform: Optional[Sequence[Sequence[float]]] = None) -> Tile:
    """Parse a tileset.json dict and return the root Tile."""
    root_dict = data["root"]
    if "geometricError" not in root_dict:
        root_dict["geometricError"] = data.get("geometricError", 500.0)
    return Tile.from_dict(root_dict, base_url, parent_transform)


def graft_external(parent: Tile, data: dict, base_url: str) -> int:
    """Merge an external tileset.json into ``parent`` (whose content was the
    .json). Returns the number of children grafted."""
    sub_root = parse_tileset(data, base_url, parent.transform)
    if sub_root.children and not sub_root.has_drawable and \
            abs(sub_root.geometric_error - parent.geometric_error) < 1e-9:
        # external root is a pure container equal to the parent: adopt children
        parent.children = sub_root.children
        for c in parent.children:
            c.parent = parent
        parent.content_uri = None
    else:
        parent.children = [sub_root]
        sub_root.parent = parent
        parent.content_uri = None
    parent.grafted = True
    parent.invalidate_cache()
    return len(parent.children)


# ── coordinate utilities ─────────────────────────────────────────────────────

def _geodetic_to_ecef(lat_deg: float, lon_deg: float, height_m: float) -> tuple:
    """WGS84 geodetic → ECEF XYZ (metres)."""
    a = 6378137.0
    e2 = 6.69437999014e-3
    lat = math.radians(lat_deg)
    lon = math.radians(lon_deg)
    N = a / math.sqrt(1 - e2 * math.sin(lat) ** 2)
    x = (N + height_m) * math.cos(lat) * math.cos(lon)
    y = (N + height_m) * math.cos(lat) * math.sin(lon)
    z = (N * (1 - e2) + height_m) * math.sin(lat)
    return (x, y, z)


def geodetic_to_ecef(lat_deg: float, lon_deg: float, height_m: float) -> tuple:
    """Public alias of _geodetic_to_ecef."""
    return _geodetic_to_ecef(lat_deg, lon_deg, height_m)


def ecef_to_geodetic(x: float, y: float, z: float) -> tuple:
    """ECEF → (lat_deg, lon_deg, height_m), iterative."""
    a = 6378137.0
    e2 = 6.69437999014e-3
    p = math.sqrt(x * x + y * y)
    lon = math.atan2(y, x)
    lat = math.atan2(z, p * (1 - e2))
    for _ in range(6):
        N = a / math.sqrt(1 - e2 * math.sin(lat) ** 2)
        lat = math.atan2(z + e2 * N * math.sin(lat), p)
    N = a / math.sqrt(1 - e2 * math.sin(lat) ** 2)
    h = p / max(math.cos(lat), 1e-12) - N
    return (math.degrees(lat), math.degrees(lon), h)


def build_enu_to_ecef_matrix(lat_deg: float, lon_deg: float, height_m: float = 0.0):
    """4x4 row-major: ENU (E=X, N=Y, U=Z) at the origin → ECEF."""
    lat = math.radians(lat_deg)
    lon = math.radians(lon_deg)
    sl, cl = math.sin(lat), math.cos(lat)
    so, co = math.sin(lon), math.cos(lon)
    e = (-so, co, 0.0)
    n = (-sl * co, -sl * so, cl)
    u = (cl * co, cl * so, sl)
    ox, oy, oz = _geodetic_to_ecef(lat_deg, lon_deg, height_m)
    return [[e[0], n[0], u[0], ox],
            [e[1], n[1], u[1], oy],
            [e[2], n[2], u[2], oz],
            [0.0, 0.0, 0.0, 1.0]]


def build_ecef_to_enu_matrix(lat_deg: float, lon_deg: float, height_m: float = 0.0):
    """4x4 row-major inverse of build_enu_to_ecef_matrix (rigid, so R^T)."""
    m = build_enu_to_ecef_matrix(lat_deg, lon_deg, height_m)
    r = [[m[j][i] for j in range(3)] for i in range(3)]   # transpose
    ox, oy, oz = m[0][3], m[1][3], m[2][3]
    t = [-(r[i][0] * ox + r[i][1] * oy + r[i][2] * oz) for i in range(3)]
    return [[r[0][0], r[0][1], r[0][2], t[0]],
            [r[1][0], r[1][1], r[1][2], t[1]],
            [r[2][0], r[2][1], r[2][2], t[2]],
            [0.0, 0.0, 0.0, 1.0]]


def ecef_to_enu(ecef: tuple, origin_lat: float, origin_lon: float, origin_height: float) -> tuple:
    """Convert an ECEF point to ENU coordinates relative to origin."""
    ox, oy, oz = _geodetic_to_ecef(origin_lat, origin_lon, origin_height)
    dx, dy, dz = ecef[0] - ox, ecef[1] - oy, ecef[2] - oz
    lat = math.radians(origin_lat)
    lon = math.radians(origin_lon)
    sl, cl = math.sin(lat), math.cos(lat)
    so, co = math.sin(lon), math.cos(lon)
    east = -so * dx + co * dy
    north = -sl * co * dx - sl * so * dy + cl * dz
    up = cl * co * dx + cl * so * dy + sl * dz
    return (east, north, up)


def blender_to_ecef(xyz: tuple, origin_lat: float, origin_lon: float, origin_height: float) -> tuple:
    """Blender XYZ (= ENU) → ECEF."""
    east, north, up = xyz
    lat = math.radians(origin_lat)
    lon = math.radians(origin_lon)
    sl, cl = math.sin(lat), math.cos(lat)
    so, co = math.sin(lon), math.cos(lon)
    ox, oy, oz = _geodetic_to_ecef(origin_lat, origin_lon, origin_height)
    x = ox + (-so * east - sl * co * north + cl * co * up)
    y = oy + (co * east - sl * so * north + cl * so * up)
    z = oz + (cl * north + sl * up)
    return (x, y, z)


def rotate_enu_to_ecef(enu_vec: tuple, lat_deg: float, lon_deg: float) -> tuple:
    """Rotate an ENU direction into ECEF (no translation)."""
    lat = math.radians(lat_deg)
    lon = math.radians(lon_deg)
    sl, cl = math.sin(lat), math.cos(lat)
    so, co = math.sin(lon), math.cos(lon)
    e, n, u = enu_vec
    return (-so * e - sl * co * n + cl * co * u,
            co * e - sl * so * n + cl * so * u,
            cl * n + sl * u)


def _resolve_uri(uri: str, base_url: str) -> str:
    """Resolve a (possibly relative) URI against the tileset URL.

    Query parameters of the base URL (SAS tokens, Google session keys, ion
    access tokens) are inherited by the child unless the child already sets
    the same parameter."""
    bs = urlsplit(base_url)
    if uri.startswith(("http://", "https://", "file://")):
        target = urlsplit(uri)
    else:
        base_path = bs.path.rsplit("/", 1)[0] if "/" in bs.path else ""
        rel = urlsplit(uri)
        path = rel.path
        if not path.startswith("/"):
            path = f"{base_path}/{path}"
        target = bs._replace(path=path, query=rel.query, fragment=rel.fragment)
    if bs.query and target.netloc == bs.netloc:   # never leak tokens to other hosts
        own = dict(parse_qsl(target.query, keep_blank_values=True))
        inherited = [(k, v) for k, v in parse_qsl(bs.query, keep_blank_values=True) if k not in own]
        if inherited:
            q = urlencode(list(own.items()) + inherited)
            target = target._replace(query=q)
    return urlunsplit(target)
