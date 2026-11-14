"""Phase 2: horizon uncertainty model, product identity, discrepancy allowance, near field, cache keys.

Math tests need nothing but NumPy. Scene tests build small synthetic products in an isolated DEM folder
(tests/scene_helpers.py); none of them touches the session's synthetic crater or any real data.
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from conftest import needs_kernels
from scene_helpers import Scene, add_fns, hill, ring

R0 = 1_737_400.0
LCORR_TEXT = ("L_corr = 250 m is an uncalibrated assumption (no published source); "
              "horizon uncertainty and uncertain flags depend on it")
KIND_TEXT = "conservative allowance (includes measured bias); not a calibrated random 1-sigma"


def _geometry(lat, lon, az_rad, d):
    from lunaops.engine.frames import enu_basis
    e, n, u = enu_basis(lat, lon)
    t = math.cos(az_rad) * n + math.sin(az_rad) * e
    dl = d / R0
    return u, math.cos(dl) * u + math.sin(dl) * t


def _geometry3(lat, lon, az_rad, d):
    """u, p and p - u, the last built without cancellation: -2 sin^2(d/2R) u + sin(d/R) t."""
    from lunaops.engine.frames import enu_basis
    e, n, u = enu_basis(lat, lon)
    t = math.cos(az_rad) * n + math.sin(az_rad) * e
    dl = d / R0
    return u, math.cos(dl) * u + math.sin(dl) * t, -2.0 * math.sin(0.5 * dl) ** 2 * u + math.sin(dl) * t


def _exact_e(u, p, pmu, h_b, s_off):
    """Exact elevation of the blocker (R0 + h_b) p seen from (R0 + s_off) u, in plain float64 on any platform.

    v = R0 (p - u) + h_b p - s_off u equals (R0 + h_b) p - (R0 + s_off) u algebraically but never subtracts
    two ~1.7e6 m vectors, so v keeps full relative precision even 2.5 m from the observer. An earlier
    version relied on np.longdouble instead, which is only 64-bit on Windows (MSVC): there the reference
    itself carried ~1e-10 rad of rounding noise and 20 of these cases failed at 1e-6. Accepts complex
    heights (complex-step derivative)."""
    v = R0 * pmu + h_b * p - s_off * u
    return np.arcsin(np.sum(v * u) / np.sqrt(np.sum(v * v)))


_CASES = [(d, slope, H) for d in (2.5, 500.0, 50_000.0) for slope in (0.0, 10.0, 25.0, 40.0) for H in (0.0, 2.0)]


# ------------------------------------------------------------------ propagation mathematics
@pytest.mark.parametrize("d,slope,H", _CASES)
def test_gradients_match_finite_differences(d, slope, H):
    """Central differences of the cancellation-free elevation; truncation error dh^2 |e'''| / 6 < 1e-9."""
    from lunaops.engine.horizon import elevation_gradients

    hs = 100.0
    for az in (0.0, 1.3, 2.9, 5.1):
        u, p, pmu = _geometry3(-89.5, 0.0, az, d)
        s_off = hs + H
        hb = s_off + d * math.tan(math.radians(slope))
        g_b, g_s, e = elevation_gradients(u, p[None, :], np.array([hb]), R0 + s_off)
        dh = 1e-4
        fd_b = (_exact_e(u, p, pmu, hb + dh, s_off) - _exact_e(u, p, pmu, hb - dh, s_off)) / (2 * dh)
        fd_s = (_exact_e(u, p, pmu, hb, s_off + dh) - _exact_e(u, p, pmu, hb, s_off - dh)) / (2 * dh)
        assert g_b[0] == pytest.approx(fd_b, rel=1e-6, abs=1e-12)
        assert g_s[0] == pytest.approx(fd_s, rel=1e-6, abs=1e-12)
        assert e[0] == pytest.approx(float(_exact_e(u, p, pmu, hb, s_off)), abs=1e-9)  # engine's float64 e


@pytest.mark.parametrize("d,slope,H", _CASES)
def test_gradients_match_complex_step(d, slope, H):
    """Complex-step derivative Im e(h + i k) / k involves no subtraction, so it is exact to rounding and
    checks g_b and g_s at 1e-9 (1000 times tighter than finite differences) on every platform."""
    from lunaops.engine.horizon import elevation_gradients

    hs, k = 100.0, 1e-30
    for az in (0.0, 1.3, 2.9, 5.1):
        u, p, pmu = _geometry3(-89.5, 0.0, az, d)
        s_off = hs + H
        hb = s_off + d * math.tan(math.radians(slope))
        g_b, g_s, _ = elevation_gradients(u, p[None, :], np.array([hb]), R0 + s_off)
        cs_b = float(np.imag(_exact_e(u, p, pmu, hb + 1j * k, s_off))) / k
        cs_s = float(np.imag(_exact_e(u, p, pmu, hb, s_off + 1j * k))) / k
        assert g_b[0] == pytest.approx(cs_b, rel=1e-9)
        assert g_s[0] == pytest.approx(cs_s, rel=1e-9)


def test_reference_needs_no_extended_precision():
    """Guard: the float64 reference equals an independent closed form to ~1e-12 rad, including 2.5 m from
    the observer where the naive (R0 + h_b) p - r_s u form carries ~1e-11..1e-10 rad of rounding noise."""
    for az, d, dh in ((1.3, 2.5, 2.0), (0.0, 2.5, -0.5), (2.9, 500.0, 40.0), (5.1, 50_000.0, 900.0)):
        u, p, pmu = _geometry3(-89.5, 0.0, az, d)
        s_off = 100.0
        hb = s_off + dh
        stable = float(_exact_e(u, p, pmu, hb, s_off))
        # tan e = (rb cos d - rs) / (rb sin d), numerator written without cancellation:
        # rb cos d - rs = (h_b - s_off) - rb * 2 sin^2(d / 2)
        dl = d / R0
        rb = R0 + hb
        exact = math.atan2((hb - s_off) - rb * 2.0 * math.sin(0.5 * dl) ** 2, rb * math.sin(dl))
        assert abs(stable - exact) < 1e-12, (az, d)


def test_propagation_algebra():
    from lunaops.engine.horizon import propagate_sigma

    g = 0.01
    for s in (0.3, 1.0, 5.0):
        for rho in (0.0, 0.3, 0.9, 1.0):
            # equal sigmas with g_b = -g_s: the structure function 2 sigma^2 (1 - rho)
            assert propagate_sigma(g, -g, s, s, rho) == pytest.approx(g * math.sqrt(2 * s * s * (1 - rho)), abs=1e-15)
    # rho = 1, unequal sigmas: |sigma_b - sigma_s| (not 0, as the pre-Phase-2 formula gave)
    assert propagate_sigma(g, -g, 2.0, 0.5, 1.0) == pytest.approx(g * 1.5)
    # rho = 0: root-sum-square (the site term is no longer dropped)
    assert propagate_sigma(g, -0.7 * g, 2.0, 0.5, 0.0) == pytest.approx(math.hypot(g * 2.0, 0.7 * g * 0.5))
    # allowance adds in quadrature on the blocker side
    assert propagate_sigma(g, -g, 0.0, 0.0, 0.0, 3.0) == pytest.approx(g * 3.0)
    gb, gs, sb, ss, rho = np.meshgrid([1e-4, 0.01, 0.4], [-0.4, -0.01, -1e-4], [0, 0.5, 30], [0, 0.5, 30],
                                      np.linspace(0, 1, 11))
    out = propagate_sigma(gb, gs, sb, ss, rho, 0.0)
    assert np.all(np.isfinite(out)) and np.all(out >= 0)


@pytest.mark.parametrize("rho,sig_x", [(0.0, 0.0), (0.5, 0.0), (0.95, 0.0), (0.0, 1.0)])
def test_monte_carlo_matches_first_order_propagation(rho, sig_x):
    from lunaops.engine.horizon import elevation_gradients, propagate_sigma

    u, p = _geometry(-89.5, 0.0, 0.7, 500.0)
    hs, H = 100.0, 0.0
    hb = hs + 500.0 * math.tan(math.radians(5.0))
    rs = R0 + hs + H
    sb, ss = 0.3, 0.4
    rng = np.random.default_rng(20261107)
    N = 200_000
    cov = [[sb * sb, rho * sb * ss], [rho * sb * ss, ss * ss]]
    db, ds = rng.multivariate_normal([0, 0], cov, size=N).T
    db = db + rng.normal(0, sig_x, size=N) if sig_x else db
    P = (R0 + hb + db)[:, None] * p[None, :]
    V = P - (rs + ds)[:, None] * u[None, :]
    e = np.arcsin((V @ u) / np.linalg.norm(V, axis=1))
    g_b, g_s, e0 = elevation_gradients(u, p[None, :], np.array([hb]), rs)
    want = float(propagate_sigma(g_b, g_s, sb, ss, rho, sig_x)[0])
    assert np.std(e - e0[0]) == pytest.approx(want, rel=0.02)


def test_nonlinear_threshold_unit():
    from lunaops import settings
    from lunaops.engine.horizon import elevation_gradients, propagate_sigma

    for d, nonlinear in ((20.0, True), (2000.0, False)):
        u, p = _geometry(-89.5, 0.0, 0.0, d)
        g_b, g_s, _ = elevation_gradients(u, p[None, :], np.array([0.0]), R0)
        sig = math.degrees(float(propagate_sigma(g_b, g_s, 5.0, 0.0, 0.0)[0]))
        assert (sig > settings.SIGMA_NONLINEAR_DEG) is nonlinear, sig
    # 5 m at 20 m: about 14.3 deg (first order); 5 m at 2 km: about 0.14 deg


def test_correlation_model():
    from lunaops.engine.horizon import correlation

    assert correlation(0.0) == 1.0
    r = correlation([0, 100, 250, 1000])
    assert np.all(np.diff(r) < 0) and r[2] == pytest.approx(math.exp(-0.5))
    with pytest.raises(ValueError):
        correlation(10.0, model="exponential")


# ------------------------------------------------------------------ cross-product discrepancy (unit)
def _win(key, data, x0, y0, pixel):
    from lunaops.engine.dem import LevelWindow
    return LevelWindow("20m", np.asarray(data, np.float32), x0, y0, pixel, -pixel, 1e9, pixel, {"key": key})


def _discrepancy_pair(n_valid_fine: int):
    f = lambda x, y: 0.01 * x + 0.02 * y   # linear, so bilinear interpolation is exact
    xs = np.arange(10) * 20.0
    ys = -np.arange(10) * 20.0
    X, Y = np.meshgrid(xs, ys)
    fine = f(X, Y).astype(np.float32)
    flat = fine.ravel()
    flat[n_valid_fine:] = np.nan
    cx = -100.0 + np.arange(40) * 20.0
    cy = 100.0 - np.arange(40) * 20.0
    CX, CY = np.meshgrid(cx, cy)
    coarse = f(CX, CY) + 3.0
    return _win("fine.tif", flat.reshape(10, 10), 0.0, 0.0, 20.0), _win("coarse.tif", coarse, -100.0, 100.0, 20.0)


def test_discrepancy_boundary_at_min_pairs():
    from lunaops.engine.horizon import cross_product_discrepancy

    a, b = _discrepancy_pair(100)
    st = cross_product_discrepancy(a, b)
    assert st["status"] == "measured" and st["n"] == 100
    assert st["mean_m"] == pytest.approx(-3.0, abs=1e-4) and st["rms_m"] == pytest.approx(3.0, abs=1e-4)
    assert st["allowance_m"] == st["rms_m"] and st["kind"] == KIND_TEXT
    a, b = _discrepancy_pair(99)
    st = cross_product_discrepancy(a, b)
    assert st["status"] == "unknown" and st["n"] == 99 and st["allowance_m"] is None   # never 0


def test_discrepancy_uses_min_pairs_setting(monkeypatch):
    from lunaops import settings
    from lunaops.engine.horizon import cross_product_discrepancy

    monkeypatch.setitem(settings.CROSS_PRODUCT_SAMPLING, "min_pairs", 99)
    a, b = _discrepancy_pair(99)
    assert cross_product_discrepancy(a, b)["status"] == "measured"


# ------------------------------------------------------------------ scenes
def test_site_window_identity_not_level(tmp_path, monkeypatch):
    """Two 20 m products; the first has no data at the site. The site product is the second (by window
    index), and its own error map gives the site sigma. The former level lookup took the first."""
    sc = Scene(tmp_path, monkeypatch)
    flat = lambda DX, DY: np.where(np.hypot(DX, DY) < 100.0, np.nan, 0.0)
    sc.add("P1", 20.0, 2000.0, flat, priority=40, err=0.2)
    sc.add("P2", 20.0, 2000.0, lambda DX, DY: np.zeros_like(DX), priority=50, err=0.8)
    hz = sc.horizon(0.0)
    i1, i2 = sc.level_index(hz, "P1"), sc.level_index(hz, "P2")
    assert hz.levels[i1]["level"] == hz.levels[i2]["level"] == "20m" and i1 < i2
    assert hz.params["site_product"]["index"] == i2 and hz.params["site_product"]["key"] == sc.keys["P2"]
    assert hz.params["sigma"]["site_sigma_m"] == pytest.approx(0.8, abs=1e-6)


@pytest.mark.parametrize("pixel,a_half,b_half,hill_args,ring_args", [
    (20.0, 3000.0, 20_000.0, (1500.0, 0.0, 200.0, 150.0), (6000.0, 300.0, 400.0)),
    (5.0, 800.0, 5000.0, (400.0, 0.0, 60.0, 40.0), (3000.0, 150.0, 200.0)),
])
def test_same_resolution_products_keep_identity(tmp_path, monkeypatch, pixel, a_half, b_half, hill_args, ring_args):
    from lunaops import settings
    from lunaops.engine.frames import enu_basis
    from lunaops.engine.horizon import correlation, elevation_gradients, propagate_sigma

    sc = Scene(tmp_path, monkeypatch)
    terrain = add_fns(hill(*hill_args), ring(*ring_args))
    sc.add("A", pixel, a_half, terrain, priority=40, err=0.5)
    sc.add("B", pixel, b_half, lambda DX, DY: terrain(DX, DY) + 3.0, priority=50, err=3.0)
    hz = sc.horizon(0.0)
    iA, iB = sc.level_index(hz, "A"), sc.level_index(hz, "B")
    assert hz.levels[iA]["level"] == hz.levels[iB]["level"]     # same resolution ...
    byB, byA = hz.blocker_product == iB, hz.blocker_product == iA
    assert byB.sum() > 100 and byA.sum() > 10
    assert np.all(hz.cross_product[byB]) and not np.any(hz.cross_product[byA])   # ... still different products
    np.testing.assert_allclose(hz.sigma_block_m[byB], 3.0, rtol=1e-6)
    np.testing.assert_allclose(hz.sigma_block_m[byA], 0.5, rtol=1e-6)
    pairs = hz.params["sigma"]["cross_product_discrepancy_allowance"]
    key = f"{sc.keys['A']} | {sc.keys['B']}"
    assert list(pairs) == [key]                                     # keyed by product, not "20m | 20m"
    st = pairs[key]
    assert st["status"] == "measured" and st["kind"] == KIND_TEXT
    assert st["mean_m"] == pytest.approx(-3.0, abs=1e-3) and st["rms_m"] == pytest.approx(3.0, abs=1e-3)
    # final sigma = exact propagation: rho = 0 plus allowance for B; Gaussian rho, no allowance for A
    e, n, u = enu_basis(sc.lat, sc.lon)
    a = 2 * np.pi * np.arange(hz.nbins) / hz.nbins
    t = np.outer(np.cos(a), n) + np.outer(np.sin(a), e)
    dl = hz.block_dist_m / settings.R_MOON_M
    p = np.outer(np.cos(dl), u) + np.sin(dl)[:, None] * t
    rs = settings.R_MOON_M + hz.ground_h_m
    gb, gs, _ = elevation_gradients(u, p[byB], hz.block_h_m[byB], rs)
    np.testing.assert_allclose(hz.sigma_deg[byB], np.degrees(propagate_sigma(gb, gs, 3.0, 0.5, 0.0, st["rms_m"])),
                               rtol=1e-5)
    gb, gs, _ = elevation_gradients(u, p[byA], hz.block_h_m[byA], rs)
    np.testing.assert_allclose(hz.sigma_deg[byA], np.degrees(
        propagate_sigma(gb, gs, 0.5, 0.5, correlation(hz.block_dist_m[byA]), 0.0)), rtol=1e-5, atol=1e-12)
    assert not hz.discrepancy_unknown.any()


def _unknown_scene(tmp_path, monkeypatch):
    """Site product A (20 m, +/-200 m) inside B (20 m) whose data stop at the site product's outer ring:
    rays continue seamlessly into B, but A and B share only 76 valid pixel pairs (< 100)."""
    sc = Scene(tmp_path, monkeypatch)
    sc.add("A", 20.0, 200.0, lambda DX, DY: np.zeros_like(DX), priority=40, err=0.5)
    rg = ring(6000.0, 300.0, 400.0)
    sc.add("B", 20.0, 20_000.0, lambda DX, DY: np.where(np.maximum(abs(DX), abs(DY)) < 190.0, np.nan, rg(DX, DY)),
           priority=50, err=3.0)
    return sc


def test_unknown_discrepancy_is_never_zero(tmp_path, monkeypatch):
    sc = _unknown_scene(tmp_path, monkeypatch)
    hz = sc.horizon(0.0)
    iB = sc.level_index(hz, "B")
    st = hz.params["sigma"]["cross_product_discrepancy_allowance"][f"{sc.keys['A']} | {sc.keys['B']}"]
    assert st["status"] == "unknown" and st["n"] < 100 and st["allowance_m"] is None, st
    byB = hz.blocker_product == iB
    assert byB.sum() > 3000 and not hz.incomplete[byB].any()
    assert np.all(hz.discrepancy_unknown == byB)
    assert np.all(np.isnan(hz.sigma_deg[byB]))                       # unknown, not error-map-only
    assert np.all(np.isfinite(hz.sigma_lower_bound_deg[byB]))        # reported separately as a lower bound
    assert hz.params["sigma"]["bins_discrepancy_unknown"] == int(byB.sum())
    j = hz.to_json()
    k = int(np.where(byB)[0][0])
    assert j["sigma_deg"][k] is None and j["sigma_lower_bound_deg"][k] is not None and j["discrepancy_unknown"][k]


def test_sigma_nonlinear_bins(tmp_path, monkeypatch):
    from lunaops import settings

    sc = Scene(tmp_path, monkeypatch)
    # a large region of 60 m error-map uncertainty (much wider than L_corr, so it survives the variance
    # regularization): first-order sigma for the hill 200 m away is about
    # 60 m * sqrt(2 (1 - rho(200 m))) * cos^2 e / |v| ~ 8 deg > 5 deg
    err = lambda DX, DY: np.where(np.maximum(abs(DX), abs(DY)) < 1500.0, 60.0, 0.5)
    sc.add("A", 20.0, 2000.0, hill(200.0, 0.0, 120.0, 40.0), err=err)
    hz = sc.horizon(0.0)
    nl = hz.sigma_nonlinear
    assert nl.sum() > 5 and np.all(hz.sigma_deg[nl] > settings.SIGMA_NONLINEAR_DEG)
    assert np.all(hz.sigma_block_m[nl] == pytest.approx(60.0))
    np.testing.assert_allclose(hz.sigma_block_model_m[nl], 60.0, rtol=1e-6)   # region interior: unchanged
    hill_bins = nl & (hz.block_dist_m > 100.0)
    assert hill_bins.sum() > 5 and np.all(hz.sigma_deg[hill_bins] > settings.SIGMA_NONLINEAR_DEG)
    assert np.all(~nl[np.isfinite(hz.sigma_deg) & (hz.sigma_deg <= settings.SIGMA_NONLINEAR_DEG)])
    assert hz.params["sigma"]["bins_nonlinear"] == int(nl.sum())
    assert hz.params["sigma"]["sigma_nonlinear_deg"] == settings.SIGMA_NONLINEAR_DEG


def test_near_field_on_tilted_plane(tmp_path, monkeypatch):
    sc = Scene(tmp_path, monkeypatch)
    tan10 = math.tan(math.radians(10.0))
    sc.add("plane", 20.0, 3000.0, lambda DX, DY: DX * tan10)
    hz0 = sc.horizon(0.0)
    assert hz0.near_field.all() and hz0.params["near_field"]["bins"] == hz0.nbins
    assert hz0.params["near_field"]["distance_m"] == pytest.approx(40.0)
    assert float(hz0.h_deg.max()) == pytest.approx(10.0, abs=0.05)
    assert np.all(hz0.block_dist_m <= 40.0)
    hz2 = sc.horizon(2.0)
    assert not hz2.near_field.any()
    assert hz2.to_json()["near_field_share"] == 0.0 and hz0.to_json()["near_field_share"] == 1.0


# ------------------------------------------------------------------ cache keys (Safeguard C)
@needs_kernels
def test_cache_keys_cover_uncertainty_settings(kernels, synthetic_crater, monkeypatch):
    from lunaops import settings
    from lunaops.engine.analysis import AnalysisRequest, get_horizon, result_id
    from lunaops.engine.horizon import horizon_key

    args = (-89.0, 45.0, 0.0, 3600)
    base = horizon_key(*args)
    changes = [("HORIZON_CORR_LENGTH_M", 500.0), ("HORIZON_CORR_MODEL", "gaussian-alt"),
               ("SIGMA_NONLINEAR_DEG", 4.0), ("HORIZON_NEAR_FIELD_PIXELS", 3.0), ("UNCERTAIN_SIGMA_K", 2.0)]
    for name, new in changes:
        old = getattr(settings, name)
        monkeypatch.setattr(settings, name, new)
        assert horizon_key(*args) != base, name
        monkeypatch.setattr(settings, name, old)
        assert horizon_key(*args) == base, name
    for k, new in (("min_pairs", 101), ("max_points", 39_999), ("stride", "x"), ("region", "x"),
                   ("interpolation", "x"), ("statistic", "x")):
        old = settings.CROSS_PRODUCT_SAMPLING[k]
        monkeypatch.setitem(settings.CROSS_PRODUCT_SAMPLING, k, new)
        assert horizon_key(*args) != base, k
        monkeypatch.setitem(settings.CROSS_PRODUCT_SAMPLING, k, old)
        assert horizon_key(*args) == base, k
    for k, new in (("kernel", "x"), ("truncation_L", 4.0), ("cell_fraction_of_L", 0.1), ("applies_to", "x")):
        old = settings.VARIANCE_REGULARIZATION[k]
        monkeypatch.setitem(settings.VARIANCE_REGULARIZATION, k, new)
        assert horizon_key(*args) != base, k
        monkeypatch.setitem(settings.VARIANCE_REGULARIZATION, k, old)
        assert horizon_key(*args) == base, k
    req = AnalysisRequest(lat=-89.0, lon=45.0, start_utc="2026-11-14T00:00:00Z", end_utc="2026-11-15T00:00:00Z")
    rid = result_id(req)
    monkeypatch.setattr(settings, "UNCERTAIN_SIGMA_K", 2.0)
    assert result_id(req) != rid
    monkeypatch.setattr(settings, "UNCERTAIN_SIGMA_K", 1.0)
    assert result_id(req) == rid
    # a cached horizon is never served under another setting
    h1 = get_horizon(-89.0, 45.0, 0.0)
    monkeypatch.setattr(settings, "HORIZON_CORR_LENGTH_M", 400.0)
    h2 = get_horizon(-89.0, 45.0, 0.0)
    assert h2.key != h1.key and h2.params["sigma"]["L_corr_m"] == 400.0 and h1.params["sigma"]["L_corr_m"] == 250.0


# ------------------------------------------------------------------ fallback folders
def test_fallback_dirs_are_explicit(tmp_path, monkeypatch):
    from lunaops import settings
    from lunaops.engine.dem import file_problem, resolve_dem_path_source

    sc = Scene(tmp_path, monkeypatch)
    rec = sc.add("F", 20.0, 2000.0, lambda DX, DY: np.zeros_like(DX))
    other = tmp_path / "other"
    (other / "sub").mkdir(parents=True)
    src = sc.dem / "SYNTH_F.tif"
    src.rename(other / "sub" / "SYNTH_F.tif")
    rec["path"] = "sub/SYNTH_F.tif"
    from lunaops.engine.dem import write_registry
    write_registry({"products": [rec], "error_maps": {}})
    path, source = resolve_dem_path_source(rec["path"])
    assert source == "unresolved" and not path.exists() and "missing" in file_problem(rec)
    monkeypatch.setattr(settings, "DEM_FALLBACK_DIRS", [other])
    path, source = resolve_dem_path_source(rec["path"])
    assert path == other / "sub" / "SYNTH_F.tif" and source == f"fallback:{other}" and file_problem(rec) is None
    hz = sc.horizon(0.0)
    assert hz.levels[0]["resolved_from"] == f"fallback:{other}"


# ------------------------------------------------------------------ labels and provenance
@needs_kernels
def test_l_corr_label_everywhere_sigma_is_used(kernels, tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from lunaops.api.main import app
    from lunaops.engine.analysis import AnalysisRequest, analyze
    from lunaops.engine.cache import put_result
    from lunaops.engine.horizon import l_corr_label

    assert l_corr_label() == LCORR_TEXT
    sc = Scene(tmp_path, monkeypatch)
    terrain = add_fns(hill(1500.0, 0.0, 200.0, 150.0), ring(6000.0, 300.0, 400.0))
    sc.add("A", 20.0, 3000.0, terrain, priority=40, err=0.5)
    sc.add("B", 20.0, 20_000.0, lambda DX, DY: terrain(DX, DY) + 3.0, priority=50, err=3.0)
    res = analyze(AnalysisRequest(lat=sc.lat, lon=sc.lon, start_utc="2026-11-14T00:00:00Z",
                                  end_utc="2026-11-15T00:00:00Z"))
    assert LCORR_TEXT + "." in res["warnings"]
    for q in ("horizon", "events", "power_indicator"):
        assert LCORR_TEXT in res["labels"][q]["reasons"] and res["labels"][q]["validation"] != "Validated"
    assert LCORR_TEXT not in res["labels"]["disk_visibility"]["reasons"]
    hu = res["provenance"]["parameters"]["horizon_uncertainty"]
    assert hu["L_corr_label"] == LCORR_TEXT and hu["L_corr_status"] == "uncalibrated assumption"
    assert hu["sigma_computed"] is True
    sig = res["provenance"]["horizon"]["params"]["sigma"]
    assert sig["L_corr_label"] == LCORR_TEXT and sig["L_corr_status"] == "uncalibrated assumption"
    assert all(v["kind"] == KIND_TEXT for v in sig["cross_product_discrepancy_allowance"].values())
    put_result(res)
    csv = TestClient(app).get(f"/api/results/{res['id']}/intervals.csv").text
    assert f"# {LCORR_TEXT}" in csv and "uncertain_reasons,near_field" in csv


@needs_kernels
def test_no_l_corr_label_without_sigma(kernels, synthetic_crater):
    from lunaops.engine.analysis import AnalysisRequest, analyze

    res = analyze(AnalysisRequest(lat=-89.0, lon=45.0, start_utc="2026-11-14T00:00:00Z",
                                  end_utc="2026-11-14T06:00:00Z"))
    assert res["horizon"]["sigma_deg"] is None
    assert not any("L_corr" in w for w in res["warnings"])
    assert not any("L_corr" in r for q in res["labels"].values() for r in q["reasons"])
    assert res["provenance"]["parameters"]["horizon_uncertainty"]["sigma_computed"] is False
