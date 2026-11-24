"""Adaptive point size for additive point clouds, after Potree.

An ADD-refined tile stays on screen with its children: where a child is shown, the parent's points sit
among denser ones and must shrink to their spacing, and where it is not they must keep their own size
or the cloud has holes. Potree packs the tree of visible nodes in a texture and walks it per point in
the vertex shader. Here every tile gets one integer instead, which its Geometry Nodes group reads:

    3 bits per octant of the tile's box (24 bits): how many finer levels are shown in that octant,
    0 to 7. A point's radius is its tile's radius over 2 ** that number.

The depth is the deepest shown chain of the octant, not the shallowest: a parent point that is too small
is harmless, since each shown level covers its own area at its own spacing wherever its children are
missing.

A selection change only touches the ancestors of the tiles that appeared or disappeared (``Masks.update``).
No bpy here: boxes are (centre, half axes) with one half axis per row, in any one frame.
"""
import numpy as np

MAX_DEPTH = 7
_SIGNS = np.array([[1.0 if o >> i & 1 else -1.0 for i in range(3)] for o in range(8)])   # octant -> ±1 per axis


def octant_of(box, point) -> int:
    """Octant of ``box`` a point falls in: bit i set on the positive side of half axis i."""
    c, h = box
    d = np.asarray(point, np.float64) - np.asarray(c, np.float64)
    return sum(1 << i for i in range(3) if float(d @ np.asarray(h[i], np.float64)) > 0.0)


def octant_bits(parent_box, child_box, slack=0.02) -> int:
    """Which octants of the parent a child tile covers, as 8 bits: those whose centre is inside the child's
    box. One for an octree, two for a quadtree's child, four for a binary split. A child that holds no octant
    centre (a tight box) gets the octant of its own centre."""
    pc, ph = np.asarray(parent_box[0], np.float64), np.asarray(parent_box[1], np.float64)
    cc, ch = np.asarray(child_box[0], np.float64), np.asarray(child_box[1], np.float64)
    centres = pc + 0.5 * (_SIGNS @ ph)                       # (8, 3)
    len2 = np.maximum((ch * ch).sum(axis=1), 1e-30)          # squared length of each child half axis
    along = np.abs((centres - cc) @ ch.T) / len2             # (8, 3): 1 = on the child's face
    inside = (along <= 1.0 + slack).all(axis=1)
    bits = sum(1 << o for o in range(8) if inside[o])
    return bits or 1 << octant_of(parent_box, cc)


def pack(depths) -> int:
    """Eight depths (0 to 7) as one integer, octant 0 in the low bits. Below 2 ** 24: exact as a float."""
    return sum(min(max(int(d), 0), MAX_DEPTH) << (3 * o) for o, d in enumerate(depths))


def unpack(mask: int):
    return [(int(mask) >> (3 * o)) & 7 for o in range(8)]


class Masks:
    """The tiles of one tileset: who is whose parent, and each tile's integer."""

    def __init__(self):
        self.parent = {}        # key -> parent key
        self.children = {}      # key -> {child key: octant bits}
        self.mask = {}          # key -> packed depths, only where not 0

    def link(self, key, parent_key, bits) -> bool:
        """``key`` is shown over octants ``bits`` of ``parent_key``. True when that is news."""
        if key == parent_key or not bits:
            return False
        old = self.parent.get(key)
        if old == parent_key and self.children.get(parent_key, {}).get(key) == bits:
            return False
        if old is not None and old != parent_key:
            self.children.get(old, {}).pop(key, None)
        self.parent[key] = parent_key
        self.children.setdefault(parent_key, {})[key] = bits
        return True

    def unlink(self, key) -> None:
        """A tile was freed. Its children keep their link: it may come back under the same key."""
        self.mask.pop(key, None)

    def ancestors(self, keys) -> set:
        out = set()
        for k in keys:
            hops = 0
            p = self.parent.get(k)
            while p is not None and p not in out and hops < 64:
                out.add(p)
                p, hops = self.parent.get(p), hops + 1
        return out

    def update(self, changed, visible) -> dict:
        """``changed``: tiles that appeared, disappeared, or were just linked. ``visible``: a set of keys, or
        anything with ``in``. Returns {key: new integer} for the ancestors whose integer changed."""
        todo = self.ancestors(changed)
        done, out = {}, {}

        def depth_of(k) -> int:          # finer levels shown under k, k itself not counted
            m = calc(k) if k in todo else self.mask.get(k, 0)
            return max(unpack(m)) if m else 0

        def calc(k) -> int:
            if k in done:
                return done[k]
            done[k] = self.mask.get(k, 0)          # a cycle cannot recurse for ever
            depths = [0] * 8
            for c, bits in self.children.get(k, {}).items():
                if c not in visible:
                    continue
                d = min(1 + depth_of(c), MAX_DEPTH)
                for o in range(8):
                    if bits >> o & 1 and d > depths[o]:
                        depths[o] = d
            done[k] = pack(depths)
            return done[k]

        for k in todo:
            m = calc(k)
            if m != self.mask.get(k, 0):
                out[k] = m
                if m:
                    self.mask[k] = m
                else:
                    self.mask.pop(k, None)
        return out
