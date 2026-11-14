"""Known numerical terrain examples for the landing kernels (no DEM files, no registry)."""
from __future__ import annotations

import math

import numpy as np
import pytest

from lunaops_landing import kernels as K


def _grid(n=40):
    r, c = np.mgrid[0:n, 0:n].astype(np.float64)
    return r, c


@pytest.mark.parametrize("deg", [0.0, 2.5, 10.0, 30.0, 60.0])
def test_slope_of_tilted_plane_is_exact(deg):
    r, c = _grid()
    dx = 5.0
    z = math.tan(math.radians(deg)) * dx * c
    s = K.slope_horn(z, np.full(z.shape, dx), np.full(z.shape, dx))
    inner = s[1:-1, 1:-1]
    assert np.allclose(inner, deg, atol=1e-4)
    assert np.isnan(s[0]).all() and np.isnan(s[:, -1]).all()          # outer ring has no complete stencil


def test_slope_of_oblique_plane_and_anisotropic_spacing():
    r, c = _grid()
    gx, gy = 4.0, 6.0
    a, b = 0.07, -0.11                         # dz/dx, dz/dy in metres per metre
    z = a * gx * c + b * gy * r
    s = K.slope_horn(z, np.full(z.shape, gx), np.full(z.shape, gy))
    assert np.allclose(s[1:-1, 1:-1], math.degrees(math.atan(math.hypot(a, b))), atol=1e-4)


def test_slope_never_uses_missing_samples():
    r, c = _grid(12)
    z = 0.1 * c
    z[6, 6] = np.nan
    s = K.slope_horn(z, np.ones(z.shape), np.ones(z.shape))
    assert np.isnan(s[5:8, 5:8]).all()                                   # every stencil touching the gap
    assert np.isfinite(s[1:4, 1:-1]).all()


def test_detrended_rms_matches_least_squares_reference():
    rng = np.random.default_rng(7)
    z = rng.normal(0, 1, (30, 30)) + 0.3 * np.mgrid[0:30, 0:30][1] + 1500.0   # offset tests numerical stability
    for half in (1, 2, 3):
        out = K.detrended_rms(z, half)
        w = 2 * half + 1
        v, u = np.mgrid[-half:half + 1, -half:half + 1]
        A = np.column_stack([np.ones(w * w), u.ravel(), v.ravel()])
        for (rr, cc) in [(half, half), (10, 17), (29 - half, 29 - half)]:
            win = z[rr - half:rr + half + 1, cc - half:cc + half + 1].ravel()
            coef, *_ = np.linalg.lstsq(A, win, rcond=None)
            ref = math.sqrt(np.mean((win - A @ coef) ** 2))
            assert out[rr, cc] == pytest.approx(ref, rel=1e-5)


def test_detrended_rms_of_plane_is_zero_and_needs_complete_window():
    r, c = _grid(20)
    z = 3.0 * c - 2.0 * r + 100.0
    z[10, 10] = np.nan
    out = K.detrended_rms(z, 2)
    assert np.nanmax(out) < 1e-4
    assert np.isnan(out[8:13, 8:13]).all()


def test_tri_matches_definition():
    rng = np.random.default_rng(3)
    z = rng.normal(0, 2, (10, 10))
    t = K.tri_riley(z)
    r, c = 4, 6
    ref = math.sqrt(sum((z[r + i, c + j] - z[r, c]) ** 2 for i in (-1, 0, 1) for j in (-1, 0, 1)))
    assert t[r, c] == pytest.approx(ref, rel=1e-6)


def _bowl(n=81, depth=5.0, rad=20.0, cx=40, cy=40):
    r, c = _grid(n)
    d = np.hypot(r - cy, c - cx)
    return np.where(d < rad, -depth * (1 - (d / rad) ** 2), 0.0)


def test_fill_depth_of_closed_bowl():
    z = _bowl()
    d = K.fill_depth(z)
    assert d[40, 40] == pytest.approx(5.0, abs=1e-9)
    assert np.nanmax(np.where(np.hypot(*np.mgrid[0:81, 0:81] - 40) > 21, d, 0)) == 0.0
    lab, n = K.label8(d > 0.01)
    assert n == 1


def test_depth_counts_only_below_a_data_gap_or_window_edge():
    z = _bowl()
    z[40, 25] = np.nan                       # a gap inside the bowl: the hollow could drain into it ...
    d = K.fill_depth(z)
    ring = z[39:42, 24:27][np.isfinite(z[39:42, 24:27])]
    assert np.nanmax(d) == pytest.approx(ring.min() - z[40, 40], abs=1e-6)   # ... so depth counts only below the gap's rim
    assert np.nanmax(d) < 5.0 and np.isnan(d[40, 25])
    z2 = _bowl(cx=3)                         # bowl cut by the window edge: only the part below the edge counts
    assert np.nanmax(K.fill_depth(z2)) == pytest.approx(5.0 * (3 / 20) ** 2, abs=1e-6)


def test_fill_depth_spill_level_of_tilted_rim():
    # bowl on a tilted plane: water spills over the lowest rim point, so depth is below that spill level
    r, c = _grid(81)
    z = _bowl() + 0.05 * c
    d = K.fill_depth(z)
    assert 0.0 < np.nanmax(d) < 5.0


def test_label8_diagonal_connectivity():
    m = np.zeros((5, 5), dtype=np.bool_)
    m[0, 0] = m[1, 1] = m[2, 2] = True
    m[4, 0] = True
    lab, n = K.label8(m)
    assert n == 2 and lab[0, 0] == lab[2, 2] != lab[4, 0]
