import numpy as np

from blender_ogc3dtiles import blend_raster as br


def flat(x, y, z=0.0):
    return br.pack(x.ravel(), y.ravel()), np.full(x.size, z, np.float32)


def test_cell_size_is_a_power_of_two_that_fits_the_grid():
    for extent in (30.0, 1900.0, 50_000.0):
        c = br.cell_size(extent)
        assert np.log2(c) == round(np.log2(c))
        assert extent / c <= br.GRID - 32 < 2 * extent / c + 1


def test_pack_round_trips_negative_cells():
    ix, iy = np.array([-5, 0, 7]), np.array([3, -9, 0])
    assert [list(v) for v in br.unpack(br.pack(ix, iy))] == [list(ix), list(iy)]


def test_merge_keeps_the_lowest_height_of_a_cell():
    a = (br.pack(np.array([0, 1]), np.array([0, 0])), np.array([3.0, 9.0], np.float32))
    b = (br.pack(np.array([1, 2]), np.array([0, 0])), np.array([4.0, 7.0], np.float32))
    keys, z = br.merge([a, b])
    assert list(br.unpack(keys)[0]) == [0, 1, 2] and list(z) == [3.0, 4.0, 7.0]


def test_a_large_triangle_covers_its_inside_with_its_heights():
    xyz = np.array([(0.0, 0.0, 5.0), (40.0, 0.0, 5.0), (0.0, 40.0, 45.0)])
    cells, z = br.cells_of_triangles(xyz, [(0, 1, 2)], 1.0)
    ix, iy = br.unpack(cells)
    got = set(zip(ix.tolist(), iy.tolist()))
    inside = {(x, y) for x in range(40) for y in range(40) if x + y < 38}
    assert inside <= got
    assert not any(x + y > 41 for x, y in got)
    assert z.min() == 5.0 and abs(z[(ix == 0) & (iy == 20)][0] - 25.0) <= 1.0


def test_sparse_points_fill_their_gaps():
    g = np.arange(0.0, 60.0, 5.0)
    xyz = np.array([(x, y, 0.0) for x in g for y in g])
    assert len(br.cells_of_points(xyz, 1.0, spacing=5.0)[0]) > 55 * 55
    assert len(br.cells_of_points(xyz, 1.0)[0]) == len(xyz)


def test_coverage_distance_grows_from_the_border():
    x, y = np.meshgrid(np.arange(100), np.arange(60))
    cells = (br.pack(x.ravel(), y.ravel()), (x.ravel() * 0.5).astype(np.float32))
    dist, low, x0, y0, c = br.coverage([cells], 2.0, max_m=40.0)
    assert c == 2.0 and (x0, y0) == (-6.0, -6.0)
    assert dist[0].max() == 0 and dist[:, 0].max() == 0          # a border of uncovered cells
    row = dist[3 + 30, 3:3 + 12]                                   # from the west border inwards
    assert np.allclose(row, (np.arange(12) + 0.5) * 2.0)
    assert dist.max() >= 40.0
    assert low[3 + 30, 3 + 10] == 5.0 and low[3 + 30, 1] == 0.0  # the height, and its fill past the border


def test_a_long_fade_or_a_wide_footprint_coarsens_the_raster():
    x, y = np.meshgrid(np.arange(400), np.arange(400))
    assert br.coverage([flat(x, y)], 1.0, max_m=20.0)[4] == 1.0
    assert br.coverage([flat(x, y)], 1.0, max_m=200.0)[4] == 5.0  # 200 cells of fade: more than MAX_STEPS
    x, y = np.meshgrid(np.arange(2000), np.arange(10))
    d, _low, _x0, _y0, c = br.coverage([flat(x, y)], 1.0, max_m=5.0)
    assert c == 4.0 and d.shape[1] <= br.GRID


def test_no_cells_no_coverage():
    assert br.coverage([br.EMPTY], 1.0, 10.0) is None
