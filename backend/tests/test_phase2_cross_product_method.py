"""Cross-product allowance: which sampling method and region it uses, and why the 2026-11 audit's
5 m vs 80 m statistics (nearest-neighbour, 4-8 km annulus) are not the allowance.

The grids here are the real ones: PGDA 78 Site01 5 m (corner -19000, -4000, 3200 x 3200 px) and PGDA 90
80 m (corner -304000, 304000). Every 16th Site01 pixel centre lies at the same offset (+2.5, +37.5) m from
the nearest 80 m pixel centre, so nearest-neighbour sampling of the 80 m DEM adds grad(h) . o to every
difference - a slope term, not a product disagreement. The approved definition (CROSS_PRODUCT_SAMPLING)
uses bilinear interpolation between 80 m pixel centres over the intersection of the two windows.
"""
from __future__ import annotations

import numpy as np
import pytest

F_X0, F_Y0, F_PX, F_N = -19000.0, -4000.0, 5.0, 3200       # Site01 5 m corner, pixel, size
C_X0, C_Y0, C_PX = -304000.0, 304000.0, 80.0                # PGDA 90 80 m corner, pixel


def _windows(h, fine_n=F_N, stride_cells=None):
    """Fine (5 m) and coarse (80 m) LevelWindows sampling the same surface h(x, y) at pixel centres."""
    from lunaops.engine.dem import LevelWindow

    fx = F_X0 + F_PX * (np.arange(fine_n) + 0.5)
    fy = F_Y0 - F_PX * (np.arange(fine_n) + 0.5)
    FX, FY = np.meshgrid(fx, fy)
    fine = LevelWindow("5m", h(FX, FY).astype(np.float32), fx[0], fy[0], F_PX, -F_PX, 8000.0, F_PX,
                       {"key": "5m:Site01"})
    # 80 m window covering the fine window plus a margin, on the PGDA 90 grid
    c0 = int(np.floor((F_X0 - 800 - C_X0) / C_PX))
    r0 = int(np.floor((C_Y0 - (F_Y0 + 800)) / C_PX))
    nc = int(np.ceil((fine_n * F_PX + 1600) / C_PX)) + 1
    cx = C_X0 + C_PX * (c0 + np.arange(nc) + 0.5)
    cy = C_Y0 - C_PX * (r0 + np.arange(nc) + 0.5)
    CX, CY = np.meshgrid(cx, cy)
    coarse = LevelWindow("80m", h(CX, CY).astype(np.float64), cx[0], cy[0], C_PX, -C_PX, 250_000.0, C_PX,
                         {"key": "80m:PGDA90"})
    return fine, coarse


def _lattice(fine, stride=16):
    rows = np.arange(0, fine.data.shape[0], stride)
    R, C = np.meshgrid(rows, rows, indexing="ij")
    xs = fine.x0 + C.ravel() * fine.dx
    ys = fine.y0 + R.ravel() * fine.dy
    return xs, ys, fine.data[R.ravel(), C.ravel()].astype(float)


def _nearest(coarse, xs, ys):
    """Value of the coarse pixel containing each point (what rasterio's sample() returns)."""
    c = np.floor((xs - (coarse.x0 - 0.5 * coarse.dx)) / coarse.dx).astype(int)
    r = np.floor((ys - (coarse.y0 - 0.5 * coarse.dy)) / coarse.dy).astype(int)
    return coarse.data[r, c].astype(float), xs - (coarse.x0 + c * coarse.dx), ys - (coarse.y0 + r * coarse.dy)


def test_real_grids_put_every_lattice_point_at_one_fixed_offset():
    fine, coarse = _windows(lambda x, y: np.zeros_like(x))
    xs, ys, _ = _lattice(fine)
    assert xs.size == 40_000                                 # 200 x 200: the n of the approved statistic
    _, ox, oy = _nearest(coarse, xs, ys)
    assert np.allclose(ox, 2.5) and np.allclose(oy, 37.5)
    d = np.hypot(xs + 11000.0, ys + 12000.0)                 # the audit's annulus around the footprint centre
    assert int(((d >= 4000.0) & (d <= 8000.0)).sum()) == 23_572   # exactly the audit's point count


def test_allowance_is_bilinear_over_the_window_intersection():
    """On a tilted plane the two products agree exactly: the bilinear allowance is 0, while the audit's
    nearest-neighbour statistic shows the pure slope term grad(h) . o."""
    from lunaops.engine.horizon import cross_product_discrepancy

    ax, ay = 0.05, 0.20                                      # 2.9 and 11.3 deg slope components
    plane = lambda x, y: 1500.0 + ax * (x + 11000.0) + ay * (y + 12000.0)
    fine, coarse = _windows(plane)
    st = cross_product_discrepancy(fine, coarse)
    assert st["status"] == "measured" and st["n"] == 40_000
    assert abs(st["mean_m"]) < 1e-3 and st["rms_m"] < 1e-3
    xs, ys, hf = _lattice(fine)
    hn, ox, oy = _nearest(coarse, xs, ys)
    nn = hf - hn
    assert np.mean(nn) == pytest.approx(ax * 2.5 + ay * 37.5, abs=1e-3)   # = 7.625 m of pure slope
    assert np.std(nn) < 1e-3


def test_nearest_neighbour_spread_is_the_slope_term():
    """On rough terrain the nearest-neighbour spread is about |o| x slope variability, far above the
    bilinear allowance; the decomposition nearest = bilinear + grad(h) . o holds to first order."""
    from lunaops.engine.horizon import bilinear_many, cross_product_discrepancy

    surf = lambda x, y: 60.0 * np.sin(y / 300.0) + 25.0 * np.cos(x / 210.0)
    fine, coarse = _windows(surf, fine_n=1600)
    st = cross_product_discrepancy(fine, coarse)
    xs, ys, hf = _lattice(fine)
    hn, ox, oy = _nearest(coarse, xs, ys)
    nn = hf - hn
    gy = 60.0 / 300.0 * np.cos(ys / 300.0)
    gx = -25.0 / 210.0 * np.sin(xs / 210.0)
    pred = (hf - bilinear_many(coarse, xs, ys)) + gx * ox + gy * oy
    assert np.std(nn) > 4.0 * st["std_m"]                     # method, not product disagreement
    assert np.std(nn - pred) < 0.15 * np.std(nn)              # first-order slope term explains it
    assert np.std(nn) == pytest.approx(37.5 * np.std(gy), rel=0.1)
