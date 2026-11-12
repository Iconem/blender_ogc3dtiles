import sys
A = """    batch = []
    for key in backend.pop_freed():
        rec = tiles.pop(key, None)
"""
A2 = """    batch = []
    live = st.setdefault("live", {})
    for key in backend.pop_freed():
        # a tile freed and loaded again in the same update is rebuilt (inside
        # backend.tick) before we get here: this free is for the object that
        # _build_native_tile already replaced, the record is the new one
        n = live.get(key, 0) - 1
        if n > 0:
            live[key] = n
            continue
        live.pop(key, None)
        rec = tiles.pop(key, None)
"""
B = """    if r:
        st["tiles"][rt.key] = _Rec(r[0], r[1])
"""
B2 = """    if r:
        live = st.setdefault("live", {})
        live[rt.key] = live.get(rt.key, 0) + 1
        st["tiles"][rt.key] = _Rec(r[0], r[1])
"""
C = """    root_obj, coll = _root_and_coll(scene, st)
    m = blender_matrix_for_tile(rt.transform_ecef, *_frame(props, st), rt.rtc, rt.up_axis)
"""
C2 = """    root_obj, coll = _root_and_coll(scene, st)
    old = st["tiles"].pop(rt.key, None)
    if old is not None:
        # same content loaded a second time: without this the first object is
        # orphaned and stays visible over the finer tiles
        remove_tiles([(old.holder, old.data)])
    m = blender_matrix_for_tile(rt.transform_ecef, *_frame(props, st), rt.rtc, rt.up_axis)
"""
for p in sys.argv[1:]:
    s = open(p, encoding="utf-8").read()
    for a, b in ((A, A2), (B, B2), (C, C2)):
        assert s.count(a) == 1, (p, a[:40], s.count(a))
        s = s.replace(a, b)
    open(p, "w", encoding="utf-8", newline="").write(s); print("patched", p)
