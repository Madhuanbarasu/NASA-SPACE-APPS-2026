"""Phase 2 correction: variance-field regularization at the correlation length.

Real-data finding (PGDA 78 Site01, observer 0 m): near-field sigma reached 2.84 deg at 2.5 m. Cause: the
general covariance C = rho sigma_b sigma_s was fed pointwise (nearest-pixel) error-map values, so as d -> 0
the implied relative height error tends to |sigma_b - sigma_s| - a field that jumps at every pixel edge,
contradicting the approved correlation model (errors correlated over L_corr = 250 m, an uncalibrated
assumption). By Cauchy-Schwarz no correlation can fix that while the variances stay pointwise, so within
the site product the variance itself is regularized at L: sigma~^2 = G_L * sigma^2. These tests reproduce
the failure synthetically and pin down the properties of the correction.
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from scene_helpers import Scene, _write

L = 250.0


def _em(tmp_path, arr, pixel=5.0, x0=0.0, y0=0.0, name="err"):
    """Error-map record for a raster whose top-left corner is (x0, y0)."""
    p = tmp_path / f"{name}.tif"
    _write(p, arr, x0, y0, pixel, None)
    return {"path": str(p), "transform": [pixel, 0.0, x0, 0.0, -pixel, y0], "width": arr.shape[1],
            "height": arr.shape[0], "nodata": None, "scale": 1.0, "offset": 0.0}


def _centres(em, cols, rows):
    a, _, c, _, e, f = em["transform"]
    return c + (np.asarray(cols) + 0.5) * a, f + (np.asarray(rows) + 0.5) * e


# ------------------------------------------------------------------ the real-data failure, reproduced
def _textured_site(tmp_path, monkeypatch, seed=1):
    sc = Scene(tmp_path, monkeypatch, lat=-89.463163, lon=222.510447)   # Site01's coordinates
    rng = np.random.default_rng(seed)
    # smooth 0.26 m total-error level with 0.07 m pixel-scale texture, like a total-error map
    err = lambda DX, DY: 0.26 + 0.07 * rng.standard_normal(DX.shape).clip(-2, 2)
    sc.add("site5m", 5.0, 2000.0, lambda DX, DY: 3.0 * np.sin(DX / 37.0) * np.cos(DY / 53.0), err=err)
    return sc


def test_pixel_texture_no_longer_inflates_near_field_sigma(tmp_path, monkeypatch):
    from lunaops.engine.frames import enu_basis
    from lunaops import settings
    from lunaops.engine.horizon import correlation, elevation_gradients, propagate_sigma

    sc = _textured_site(tmp_path, monkeypatch)
    hz = sc.horizon(0.0)
    near = np.where(hz.block_dist_m <= 2.5)[0]
    assert near.size > 1000
    # the model: about |g| sigma~ sqrt(2 (1 - rho(2.5 m))) = 0.4 * 0.27 * 0.01 rad, i.e. ~0.06 deg
    assert float(np.nanmax(hz.sigma_deg[near])) < 0.15
    # the defect it replaces: the same bins with pointwise error-map values give degrees
    e, n, u = enu_basis(sc.lat, sc.lon)
    a = 2 * np.pi * near / hz.nbins
    t = np.outer(np.cos(a), n) + np.outer(np.sin(a), e)
    dl = hz.block_dist_m[near] / settings.R_MOON_M
    p = np.outer(np.cos(dl), u) + np.sin(dl)[:, None] * t
    gb, gs, _ = elevation_gradients(u, p, hz.block_h_m[near], settings.R_MOON_M + hz.ground_h_m)
    pointwise = np.degrees(propagate_sigma(gb, gs, hz.sigma_block_m[near], hz.params["sigma"]["site_sigma_m"],
                                           correlation(hz.block_dist_m[near]), 0.0))
    assert float(np.nanmax(pointwise)) > 1.0
    # pointwise values are still reported for transparency; the model values are regularized
    assert hz.params["sigma"]["site_sigma_m"] != pytest.approx(hz.params["sigma"]["site_sigma_model_m"])
    assert np.nanstd(hz.sigma_block_model_m[near]) < 1e-3 < np.nanstd(hz.sigma_block_m[near])


# ------------------------------------------------------------------ properties of the regularization
def test_constant_map_is_unchanged(tmp_path):
    from lunaops.engine.horizon import regularized_error_sigma

    em = _em(tmp_path, np.full((400, 400), 0.73))
    xs, ys = _centres(em, [0, 5, 200, 399], [0, 300, 200, 399])
    np.testing.assert_allclose(regularized_error_sigma(em, xs, ys), float(np.float32(0.73)), rtol=1e-9)   # GeoTIFF float32


def test_mean_variance_is_preserved(tmp_path):
    from lunaops.engine.horizon import regularized_error_sigma

    rng = np.random.default_rng(7)
    arr = np.abs(0.3 + 0.1 * rng.standard_normal((600, 600)))
    em = _em(tmp_path, arr)
    # interior points (more than 3 L = 150 px from every edge)
    cols, rows = np.meshgrid(np.arange(160, 440, 7), np.arange(160, 440, 7))
    xs, ys = _centres(em, cols.ravel(), rows.ravel())
    sig = regularized_error_sigma(em, xs, ys)
    assert np.mean(sig ** 2) == pytest.approx(np.mean(arr[100:500, 100:500] ** 2), rel=5e-3)
    assert np.std(sig) < 0.05 * np.std(arr)       # pixel texture is gone at the correlation scale


def test_step_map_transition_and_gradient_bound(tmp_path):
    """sigma 0.2 m left of x = 0 and 0.6 m right of it. Gaussian smoothing of a bounded field obeys
    |d(sigma~^2)/dx| <= (max - min)/2 * sqrt(2/pi) / L (tight at a step), and reaches the two levels
    3 L away from the step."""
    from lunaops.engine.horizon import regularized_error_sigma

    n, px = 800, 5.0
    arr = np.where(np.arange(n)[None, :] < n // 2, 0.2, 0.6) * np.ones((n, 1))
    em = _em(tmp_path, arr, pixel=px, x0=-n / 2 * px, y0=n / 2 * px)
    x = np.linspace(-3.2 * L, 3.2 * L, 129)
    s2 = regularized_error_sigma(em, x, np.zeros_like(x)) ** 2
    assert np.all(np.diff(s2) >= -1e-12)                                    # monotone across the step
    assert s2[np.argmin(abs(x))] == pytest.approx((0.04 + 0.36) / 2, rel=0.05)
    assert s2[0] == pytest.approx(0.04, rel=0.02) and s2[-1] == pytest.approx(0.36, rel=0.02)
    bound = (0.36 - 0.04) / 2 * math.sqrt(2 / math.pi) / L
    assert np.max(np.diff(s2) / np.diff(x)) <= 1.1 * bound


def test_nodata_is_excluded_not_zero(tmp_path):
    from lunaops.engine.horizon import regularized_error_sigma

    arr = np.full((400, 400), 0.5)
    arr[180:220, 180:220] = np.nan                  # a hole smaller than L
    arr[:, :20] = np.nan                            # a nodata strip at the edge
    em = _em(tmp_path, arr)
    xs, ys = _centres(em, [200, 10, 300], [200, 200, 100])
    np.testing.assert_allclose(regularized_error_sigma(em, xs, ys), 0.5, rtol=1e-9)
    allnan = _em(tmp_path, np.full((50, 50), np.nan), name="nan")
    assert np.isnan(regularized_error_sigma(allnan, *_centres(allnan, [25], [25]))).all()


def test_covariance_stays_positive_semidefinite(tmp_path):
    from lunaops.engine.horizon import correlation, regularized_error_sigma

    rng = np.random.default_rng(3)
    em = _em(tmp_path, np.abs(0.3 + 0.15 * rng.standard_normal((400, 400))))
    cols, rows = rng.integers(0, 400, 150), rng.integers(0, 400, 150)
    xs, ys = _centres(em, cols, rows)
    s = regularized_error_sigma(em, xs, ys)
    d = np.hypot(xs[:, None] - xs[None, :], ys[:, None] - ys[None, :])
    K = s[:, None] * s[None, :] * correlation(d)
    assert np.linalg.eigvalsh(K).min() >= -1e-10 * np.abs(K).max()


def test_mean_square_continuity_in_a_horizon(tmp_path, monkeypatch):
    """Within the site product the implied relative height error vanishes like d / L as d -> 0."""
    from lunaops.engine.horizon import correlation

    sc = _textured_site(tmp_path, monkeypatch, seed=11)
    hz = sc.horizon(0.0)
    same = (hz.blocker_product == hz.params["site_product"]["index"]) & np.isfinite(hz.sigma_deg)
    d = hz.block_dist_m[same]
    sb = hz.sigma_block_model_m[same]
    ss = hz.params["sigma"]["site_sigma_model_m"]
    rho = correlation(d)
    dh = np.sqrt((sb - rho * ss) ** 2 + (1 - rho ** 2) * ss ** 2)   # std of (delta_b - delta_s)
    assert np.all(dh <= 2.0 * max(sb.max(), ss) * d / L + 1e-6)


def test_cross_product_blockers_keep_pointwise_values(tmp_path, monkeypatch):
    from scene_helpers import add_fns, hill, ring

    sc = Scene(tmp_path, monkeypatch)
    rng = np.random.default_rng(5)
    terrain = add_fns(hill(1500.0, 0.0, 200.0, 150.0), ring(6000.0, 300.0, 400.0))
    sc.add("A", 20.0, 3000.0, terrain, priority=40, err=0.5)
    sc.add("B", 20.0, 20_000.0, lambda DX, DY: terrain(DX, DY) + 3.0, priority=50,
           err=lambda DX, DY: 3.0 + 0.5 * rng.standard_normal(DX.shape).clip(-2, 2))
    hz = sc.horizon(0.0)
    byB = hz.blocker_product == sc.level_index(hz, "B")
    assert byB.sum() > 100
    np.testing.assert_array_equal(hz.sigma_block_model_m[byB], hz.sigma_block_m[byB])
