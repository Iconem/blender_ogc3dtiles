"""Element cap: the SSE multiplier grows over the cap and relaxes under it."""
from blender_ogc3dtiles.tileset.budget import MAX_FACTOR, cap_factor


def test_no_cap_means_no_coarsening():
    assert cap_factor(3.0, 5e6, 0.0) == 1.0


def test_over_the_cap_coarsens_and_is_bounded():
    assert cap_factor(1.0, 4e6, 1e6) == 2.0                 # one step at most doubles
    assert 1.05 <= cap_factor(1.0, 1.01e6, 1e6) < 1.06      # and always moves
    f = 1.0
    for _ in range(40):
        f = cap_factor(f, 9e9, 1e6)
    assert f == MAX_FACTOR


def test_relaxes_only_when_settled_and_well_under():
    assert cap_factor(2.0, 0.9e6, 1e6) == 2.0               # inside the band: hold
    assert cap_factor(2.0, 0.3e6, 1e6, settled=False) == 2.0
    assert cap_factor(2.0, 0.3e6, 1e6) == 1.6
    assert cap_factor(1.1, 0.0, 1e6) == 1.0


def test_converges_on_a_square_law_scene():
    cap, full, f = 1e6, 20e6, 1.0
    for _ in range(30):
        f = cap_factor(f, full / f ** 2, cap)
    assert 0.8 * cap <= full / f ** 2 <= cap
