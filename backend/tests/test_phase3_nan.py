"""Phase 3, item 3: NaN-safe integration and interpolation (C08: unknown is never invented).

Before Phase 3, window_metrics concatenated the known samples and integrated them with the trapezoid
rule, so a run of unknown samples was bridged by a straight line and counted as interpolated light, and
coverage counted samples rather than time. The regularized error-variance grid could also fill an
interior cell with no error-map data within reach from a neighbouring cell.
"""
from __future__ import annotations

import math

import numpy as np
import pytest

H = 3600.0


def _old_bridged(t, p):
    """The pre-Phase-3 computation, kept here only to document what changed."""
    ok = np.isfinite(p)
    tt, vv = t[ok], p[ok]
    integral = float(np.trapezoid(vv, tt)) if hasattr(np, "trapezoid") else float(np.trapz(vv, tt))
    return integral, float(ok.mean())


def test_gap_is_not_bridged():
    from lunaops.engine.power import window_metrics

    t = np.arange(11) * H                       # 0 .. 10 h
    p = np.ones(11)
    p[[4, 5]] = np.nan                          # samples at 4 h and 5 h unknown -> intervals 3-6 h unknown
    m = window_metrics(t, p)
    assert m["known_hours"] == pytest.approx(7.0)
    assert m["unknown_hours"] == pytest.approx(3.0)
    assert m["equivalent_full_sun_h"] == pytest.approx(7.0)
    assert m["mean"] == pytest.approx(1.0)
    assert m["coverage"] == pytest.approx(0.7)
    assert m["lower_bound"] is True
    old_integral, old_cov = _old_bridged(t, p)
    assert old_integral / H == pytest.approx(10.0)          # the old code counted the 3 unknown hours as light
    assert old_cov == pytest.approx(9 / 11)                 # and counted samples, not time


def test_known_part_integral_is_analytic():
    from lunaops.engine.power import window_metrics

    t = np.linspace(0.0, 10.0, 41) * H
    p = (t / H) ** 2 / 100.0                    # smooth, non-constant
    gap = (t > 2.6 * H) & (t < 6.1 * H)
    p[gap] = np.nan
    m = window_metrics(t, p)
    ok = np.isfinite(p)
    seg = ok[:-1] & ok[1:]
    known = np.diff(t)[seg].sum()
    # exact integral of x^2/100 over the fully known intervals (trapezoid error is checked separately)
    lo, hi = t[:-1][seg] / H, t[1:][seg] / H
    exact = float(np.sum((hi ** 3 - lo ** 3) / 300.0))
    assert m["known_hours"] == pytest.approx(known / H)
    assert m["equivalent_full_sun_h"] == pytest.approx(exact, rel=2e-3)   # trapezoid on a 15 min grid
    assert m["mean"] == pytest.approx(m["equivalent_full_sun_h"] / m["known_hours"])


def test_coverage_is_time_weighted():
    from lunaops.engine.power import window_metrics

    t = np.array([0.0, 1.0, 10.0, 11.0]) * H
    p = np.array([1.0, 1.0, np.nan, 1.0])
    m = window_metrics(t, p)
    assert m["coverage"] == pytest.approx(1.0 / 11.0)       # one known hour of eleven
    assert m["known_hours"] == pytest.approx(1.0) and m["unknown_hours"] == pytest.approx(10.0)


def test_isolated_known_sample_adds_no_time():
    from lunaops.engine.power import window_metrics

    t = np.arange(5) * H
    p = np.array([np.nan, np.nan, 0.8, np.nan, np.nan])
    m = window_metrics(t, p)
    assert m["mean"] is None and m["equivalent_full_sun_h"] is None
    assert m["coverage"] == 0.0 and m["unknown_hours"] == pytest.approx(4.0) and m["lower_bound"] is True


@pytest.mark.parametrize("p", [np.full(6, np.nan), np.array([])])
def test_all_unknown_or_empty(p):
    from lunaops.engine.power import window_metrics

    t = np.arange(p.size) * H
    m = window_metrics(t, p)
    assert m["mean"] is None and m["equivalent_full_sun_h"] is None and m["coverage"] == 0.0


def test_fully_known_series_is_unchanged():
    """With every sample known the result is exactly the plain trapezoid over the grid (as before)."""
    from lunaops.engine.power import window_metrics

    rng = np.random.default_rng(3)
    t = np.cumsum(rng.uniform(600, 1200, 300))
    p = rng.uniform(0, 1.2, 300)
    m = window_metrics(t, p)
    old_integral, old_cov = _old_bridged(t, p)
    assert m["equivalent_full_sun_h"] == old_integral / H                 # bitwise
    assert m["mean"] == old_integral / (t[-1] - t[0])
    assert m["coverage"] == old_cov == 1.0 and m["lower_bound"] is False and m["unknown_hours"] == 0.0


def test_p_rel_keeps_unknown_unknown():
    from lunaops.engine.power import p_rel

    out = p_rel([np.nan, 0.5, 1.0], [1.496e8] * 3, [0.0] * 3, [1.0] * 3, "vertical_tracking")
    assert math.isnan(out[0]) and np.isfinite(out[1:]).all()


# ------------------------------------------------------------------ variance grid (Phase 2 regularization)
def _grid():
    sig2 = np.full((6, 6), 0.25)
    sig2[2:4, 2:4] = np.nan                       # interior cells with no error-map data within reach
    return sig2, 0.0, 0.0, 50.0, -50.0            # centres at x = 50 j, y = -50 i


def test_interior_unknown_variance_is_not_borrowed():
    from lunaops.engine.horizon import sample_variance_grid

    sig2, x0, y0, dx, dy = _grid()
    # inside the grid, next to (and inside) the NaN block: bilinear has a NaN neighbour -> unknown
    xs = np.array([80.0, 125.0, 150.0, 30.0])     # the last point's four neighbours are cells (0..1, 0..1)
    ys = np.array([-80.0, -125.0, -150.0, -30.0])
    v = sample_variance_grid(sig2, x0, y0, dx, dy, xs, ys)
    assert np.isnan(v[:3]).all(), v
    assert v[3] == pytest.approx(0.25)             # all four neighbours known


def test_border_points_take_the_nearest_cell():
    from lunaops.engine.horizon import sample_variance_grid

    sig2, x0, y0, dx, dy = _grid()
    xs = np.array([-20.0, 270.0, 100.0])           # left of / right of / inside the outer cell centres
    ys = np.array([-100.0, -100.0, 20.0])
    v = sample_variance_grid(sig2, x0, y0, dx, dy, xs, ys)
    assert np.allclose(v, 0.25)


def test_regularized_sigma_far_from_any_error_data_is_unknown(tmp_path):
    """End to end: an error map whose left part is nodata over more than the 3 L kernel reach gives NaN
    sigma there (never a neighbour's value), and finite sigma within reach of the data."""
    from scene_helpers import _write
    from lunaops.engine.horizon import regularized_error_sigma

    n, px = 800, 5.0                                # 4 km x 4 km
    arr = np.full((n, n), 0.5)
    arr[:, :500] = np.nan                           # x < 2500 m: no error data
    p = tmp_path / "err.tif"
    _write(p, arr, 0.0, 4000.0, px, None)
    em = {"path": str(p), "transform": [px, 0.0, 0.0, 0.0, -px, 4000.0], "width": n, "height": n,
          "nodata": None, "scale": 1.0, "offset": 0.0}
    x = np.arange(0.0, 4000.0, 25.0)
    s = regularized_error_sigma(em, x, np.full_like(x, 2000.0))
    far = x < 2500.0 - 3 * 250.0 - 100.0            # beyond the kernel reach plus a cell margin
    near = x >= 2500.0
    assert np.isnan(s[far]).all()
    assert np.isfinite(s[near]).all() and np.allclose(s[x >= 3300.0], 0.5)
