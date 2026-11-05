"""Places the nodes of a tree the add-on built: columns by link depth, left to
right, no node on top of another.

Run when a group is built or reset, never on a group the user may have edited
by hand.
"""

GAP_X = 70.0
GAP_Y = 30.0
_ROW = 22.0
_EXTRA = {                       # rows of buttons a node draws besides its sockets
    "ShaderNodeValToRGB": 6, "ShaderNodeTexImage": 8, "ShaderNodeMapRange": 3,
    "ShaderNodeMath": 2, "ShaderNodeVectorMath": 1, "ShaderNodeMix": 4,
    "ShaderNodeAttribute": 2, "ShaderNodeValue": 1, "ShaderNodeRGB": 8,
    "ShaderNodeGroup": 1, "GeometryNodeGroup": 1, "CompositorNodeGroup": 1,
    "ShaderNodeBsdfPrincipled": 14, "CompositorNodeRLayers": 10,
    "FunctionNodeCompare": 3, "GeometryNodeDeleteGeometry": 2,
    "ShaderNodeClamp": 1, "FunctionNodeRandomValue": 1, "ShaderNodeSeparateColor": 1,
    "ShaderNodeCombineColor": 1, "GeometryNodeSwitch": 1, "GeometryNodeInputNamedAttribute": 1,
    "GeometryNodeStoreNamedAttribute": 2, "FunctionNodeBooleanMath": 1,
}


def _height(node) -> float:
    if node.hide:
        return 40.0
    rows = sum(1 for s in node.outputs if s.enabled and not s.hide)
    rows += sum(1 for s in node.inputs if s.enabled and not s.hide)
    return 40.0 + _ROW * (rows + _EXTRA.get(node.bl_idname, 1))


def arrange(tree) -> bool:
    """Lay ``tree`` out. False (nothing moved) when it holds frames or
    reroutes, which only a person adds."""
    nodes = list(tree.nodes)
    if not nodes or any(n.bl_idname in ("NodeFrame", "NodeReroute") for n in nodes):
        return False
    consumers = {n: [] for n in nodes}            # node -> [(consumer, input index)]
    for link in tree.links:
        a, b = link.from_node, link.to_node
        if a in consumers and b in consumers and a != b:
            index = next((i for i, s in enumerate(b.inputs) if s == link.to_socket), 0)
            consumers[a].append((b, index))

    depth = {}

    def _depth(n, trail=()):
        if n in depth:
            return depth[n]
        if n in trail:                             # a cycle: stop
            return 0
        d = 1 + max((_depth(c, trail + (n,)) for c, _ in consumers[n]), default=-1)
        depth[n] = d
        return d

    for n in nodes:
        _depth(n)
    fed = {link.to_node for link in tree.links}
    deepest = max(depth.values())
    for n in nodes:
        if n.bl_idname == "NodeGroupInput" and consumers[n]:
            depth[n] = max(depth[n], deepest)      # inputs in the leftmost column
        elif not consumers[n] and n not in fed:
            depth[n] = deepest + 1                 # unused nodes: a column of their own

    columns = {}
    for n in nodes:
        columns.setdefault(depth[n], []).append(n)
    x = 0.0
    top = {}
    for d in sorted(columns):
        col = columns[d]
        width = max(n.width for n in col)
        x -= width + GAP_X if d else 0.0

        def wanted(n):
            ys = [top[c] - _ROW * (2 + i) for c, i in consumers[n] if c in top]
            return sum(ys) / len(ys) if ys else 0.0

        want = {n: wanted(n) for n in col}
        col.sort(key=lambda n: -want[n])
        y = None
        placed = []
        for n in col:
            ny = want[n] if y is None else min(want[n], y - GAP_Y)
            placed.append((n, ny))
            y = ny - _height(n)
        # the stack drifts down when nodes want the same place: centre it back
        shift = (sum(want[n] for n in col) - sum(ny for _, ny in placed)) / len(col)
        for n, ny in placed:
            top[n] = ny + shift
            n.location = (x, ny + shift)
    return True
