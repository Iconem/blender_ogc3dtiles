import numpy as np

from blender_ogc3dtiles import color_match as cm


def _colors(n=4000, seed=1):
    rng = np.random.default_rng(seed)
    return rng.uniform(0.02, 0.9, (n, 3))


def test_fit_recovers_a_gain_and_a_gamma():
    src = _colors()
    gain, gamma = np.array([1.4, 0.8, 1.1]), np.array([0.8, 1.0, 1.3])
    g, p = cm.fit(src, cm.apply(src, gain, gamma))
    assert np.allclose(g, gain, rtol=0.03)
    assert np.allclose(p, gamma, rtol=0.03)


def test_fit_of_a_set_on_itself_changes_nothing():
    src = _colors()
    g, p = cm.fit(src, src)
    assert np.allclose(g, 1.0, atol=1e-3) and np.allclose(p, 1.0, atol=1e-3)


def test_fit_brings_the_means_together_under_noise():
    src = _colors()
    rng = np.random.default_rng(2)
    ref = cm.apply(src, [1.6, 1.2, 0.7], [1.0, 1.0, 1.0]) * rng.uniform(0.85, 1.15, src.shape)
    g, p = cm.fit(src, ref)
    out = cm.apply(src, g, p)
    assert np.allclose(out.mean(0), ref.mean(0), rtol=0.06)


def test_fit_stays_inside_its_limits():
    src = _colors()
    g, p = cm.fit(src, src * 40.0)
    assert (g <= cm.GAIN_RANGE[1]).all() and (p >= cm.GAMMA_RANGE[0]).all() and (p <= cm.GAMMA_RANGE[1]).all()


def test_fit_needs_enough_bright_cells():
    assert cm.fit(_colors(8), _colors(8)) is None
    assert cm.fit(np.zeros((100, 3)), _colors(100)) is None


def test_cell_means_and_shared():
    keys = np.array([5, 5, 9, 2])
    rgb = np.array([[1, 0, 0], [0, 0, 0], [0, 1, 0], [0, 0, 1]], np.float32)
    k, m = cm.cell_means(keys, rgb)
    assert k.tolist() == [2, 5, 9]
    assert np.allclose(m, [[0, 0, 1], [0.5, 0, 0], [0, 1, 0]])
    a, b = cm.shared(k, m, np.array([5, 7, 9]), np.array([[1, 1, 1], [2, 2, 2], [3, 3, 3]], np.float32))
    assert np.allclose(a, [[0.5, 0, 0], [0, 1, 0]]) and np.allclose(b, [[1, 1, 1], [3, 3, 3]])


def test_srgb_to_linear():
    assert np.allclose(cm.srgb_to_linear(np.array([0.0, 1.0, 0.5])), [0.0, 1.0, 0.2140], atol=1e-3)
