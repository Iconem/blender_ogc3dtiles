"""native_mesh splat helpers: quaternion composition and the Y-up -> Z-up
conjugation keep the splat ellipsoid consistent with the converted positions."""
import numpy as np

from blender_ogc3dtiles.tileset import native_mesh as nm


def _rot_from_quat_xyzw(q):
    x, y, z, w = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def test_quat_from_matrix_roundtrip():
    rng = np.random.default_rng(1)
    for _ in range(20):
        q = rng.normal(size=4)
        q /= np.linalg.norm(q)
        R = _rot_from_quat_xyzw(q)
        q2 = nm._quat_from_matrix(R)
        assert np.allclose(_rot_from_quat_xyzw(q2), R, atol=1e-9)


def test_quat_mul_matches_matrix_product():
    rng = np.random.default_rng(2)
    a = rng.normal(size=(5, 4)); a /= np.linalg.norm(a, axis=1, keepdims=True)
    b = rng.normal(size=(5, 4)); b /= np.linalg.norm(b, axis=1, keepdims=True)
    ab = nm._quat_mul(a, b)
    for i in range(5):
        assert np.allclose(_rot_from_quat_xyzw(ab[i]),
                           _rot_from_quat_xyzw(a[i]) @ _rot_from_quat_xyzw(b[i]), atol=1e-9)


def test_yup_to_zup_conjugation_preserves_covariance():
    """Covariance of a splat expressed in Z-up must equal M Σ Mᵀ."""
    rng = np.random.default_rng(3)
    M = nm._YUP_TO_ZUP3
    for _ in range(10):
        q = rng.normal(size=4); q /= np.linalg.norm(q)
        s = rng.uniform(0.1, 2.0, size=3)
        R = _rot_from_quat_xyzw(q)
        cov = R @ np.diag(s ** 2) @ R.T
        # the conversion used by _splat_arrays
        q2 = (q[[0, 2, 1, 3]] * np.array([1.0, -1.0, 1.0, 1.0]))
        s2 = s[[0, 2, 1]]
        R2 = _rot_from_quat_xyzw(q2)
        cov2 = R2 @ np.diag(s2 ** 2) @ R2.T
        assert np.allclose(cov2, M @ cov @ M.T, atol=1e-9)


def test_splat_unboost_restores_pre_boost_scales():
    """Apply the converter's opacity_anisotropic_v1 boost to known scales, then
    check splat_unboost brings them back and reports the source opacity."""
    rng = np.random.default_rng(4)
    n, c = 200, 0.75
    s = np.sort(rng.uniform(0.05, 2.0, size=(n, 3)), axis=1)          # s_min, s_mid, s_max
    alpha = rng.uniform(1.01, 60.0, size=n)
    alpha[:40] = rng.uniform(0.2, 1.0, size=40)                         # not boosted
    ratio = s[:, 1] / s[:, 2]
    F = np.where(alpha > 1, 1 + c * (np.sqrt(np.minimum(alpha, 1000)) - 1), 1.0)
    D = 1 - ratio + ratio ** 2
    G = 1 + (F - 1) * ratio / D
    boosted = s.copy()
    boosted[:, 2] *= G
    boosted[:, :2] *= F[:, None]
    assert (np.argmax(boosted, axis=1) == 2).all()                      # the largest axis stays largest
    f, g, display = nm.splat_unboost(alpha, ratio, c, kept=0.0)
    back = boosted.copy()
    back[:, 2] /= g
    back[:, :2] /= f[:, None]
    assert np.allclose(back, s, rtol=1e-5)
    assert np.isnan(display[:40]).all()                                 # alpha <= 1: keep SPZ opacity
    assert np.allclose(display[40:], 1.0)                               # alpha > 1 clamps to 1


def test_splat_unboost_kept_one_is_identity_and_invalid_values_fall_back():
    alpha = np.array([5.0, np.nan, -1.0, np.inf, 0.5])
    ratio = np.array([0.5, 0.5, 0.5, 0.5, 0.5])
    f, g, display = nm.splat_unboost(alpha, ratio, 0.75, kept=1.0)
    assert np.allclose(f, 1.0) and np.allclose(g, 1.0)
    f, g, display = nm.splat_unboost(alpha, ratio, 0.75, kept=0.0)
    assert f[0] > 1.0 and g[0] > 1.0 and display[0] == 1.0
    assert np.allclose(f[1:], 1.0) and np.allclose(g[1:], 1.0) and np.isnan(display[1:]).all()


def test_splat_unboost_partial_keep_is_between():
    alpha, ratio = np.array([25.0]), np.array([0.3])
    f0, g0, _ = nm.splat_unboost(alpha, ratio, 0.75, kept=0.0)
    f5, g5, d5 = nm.splat_unboost(alpha, ratio, 0.75, kept=0.5)
    f1, g1, _ = nm.splat_unboost(alpha, ratio, 0.75, kept=1.0)
    assert f1[0] < f5[0] < f0[0] and g1[0] < g5[0] < g0[0]
    assert 0.0 < d5[0] <= 1.0
