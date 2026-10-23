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
