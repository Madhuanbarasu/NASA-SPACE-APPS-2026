"""Phase 3, item 6: DEM window loading (performance only, bitwise output-invariant).

Every comparison is against the reference loader (LUNAOPS_WINDOW_MODE=full: whole nominal windows, the
pre-Phase-3 code path): the adaptive loader (one shared buffer, coarse products loaded up to an initial reach and
grown on demand) must give bitwise identical horizons, stopping, uncertainty and sub-bin outputs for every
allowed initial reach.
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from conftest import needs_kernels
from scene_helpers import Scene, ring

ARRAYS = ("h_deg", "block_dist_m", "incomplete", "sigma_deg", "near_field", "blocker_product", "cross_product",
          "discrepancy_unknown", "sigma_nonlinear", "sigma_lower_bound_deg", "sigma_block_m", "sigma_block_model_m",
          "block_h_m", "subbin_excess_deg", "subbin_unknown", "stop_step")


def _horizon(monkeypatch, lat, lon, mode, reach=None, obs=0.0, nbins=720, use_stop=True):
    from lunaops import settings
    from lunaops.engine.horizon import compute_horizon
    monkeypatch.setattr(settings, "WINDOW_MODE", mode)
    monkeypatch.setattr(settings, "DEM_INITIAL_REACH_M", dict(settings.DEM_INITIAL_REACH_M if reach is None else reach))
    return compute_horizon(lat, lon, obs, nbins=nbins, use_stop=use_stop)


def _assert_identical(a, b, what=""):
    for name in ARRAYS:
        x, y = getattr(a, name), getattr(b, name)
        assert (x is None and y is None) or np.array_equal(x, y, equal_nan=True), (what, name)
    assert a.params["h_max_m"] == b.params["h_max_m"], what
    assert a.params["sigma"] == b.params["sigma"], what                      # cross-product pairs, statistics
    assert a.ground_h_m == b.ground_h_m and a.site_level == b.site_level and a.levels == b.levels, what
    assert a.key == b.key, what                                               # performance settings are unkeyed
    sa, sb = a.stop_step, b.stop_step
    assert np.sum(~a.incomplete) == np.sum(~b.incomplete)
    assert np.array_equal(np.bincount(sa[sa >= 0]), np.bincount(sb[sb >= 0])), what


def _reaches(levels, values=(1_000.0, 10_000.0, 50_000.0, None)):
    from lunaops import settings
    out = []
    for v in values:
        out.append({lv: (settings.DEM_WINDOW_HALF_M[lv] if v is None else min(v, settings.DEM_WINDOW_HALF_M[lv]))
                    for lv in levels})
    return out


# ------------------------------------------------------------------ scenes
def _summit_scene(tmp_path, monkeypatch):
    """A site on a 2 km summit inside a 240 m product, a far ring: rays travel far beyond any small reach."""
    sc = Scene(tmp_path, monkeypatch)
    peak = lambda DX, DY: 2000.0 * np.exp(-0.5 * (np.hypot(DX, DY) / 3000.0) ** 2)   # noqa: E731
    sc.add("FINE", 20.0, 6000.0, peak, priority=10, err=0.5)
    sc.add("COARSE", 240.0, 60_000.0, lambda DX, DY: peak(DX, DY) + ring(45_000.0, 1500.0, 3000.0)(DX, DY),
           priority=50, err=3.0)
    return sc


def _edge_scene(tmp_path, monkeypatch):
    """A coarse product whose data end (edge) and a nodata band lie exactly at the initial reach (10 km)."""
    sc = Scene(tmp_path, monkeypatch)

    def coarse(DX, DY):
        r = np.hypot(DX, DY)
        z = ring(14_000.0, 900.0, 1500.0)(DX, DY)
        z[(r > 9_800.0) & (r < 10_200.0) & (DX > 0)] = np.nan                  # nodata band at the reach, east
        return z
    sc.add("FINE", 20.0, 4000.0, ring(3000.0, 150.0, 300.0), priority=10)
    sc.add("COARSE", 240.0, 20_000.0, coarse, priority=50)
    sc.add("EDGE", 240.0, 10_000.0, ring(8_000.0, 700.0, 800.0), priority=60)   # product edge at 10 km
    return sc


# ------------------------------------------------------------------ bitwise identity
@needs_kernels
def test_synthetic_crater_identical_for_every_reach(kernels, synthetic_crater, monkeypatch):
    ref = _horizon(monkeypatch, -89.0, 45.0, "full", nbins=3600)
    for reach in _reaches(("20m", "240m")):
        got = _horizon(monkeypatch, -89.0, 45.0, "adaptive", reach, nbins=3600)
        _assert_identical(ref, got, reach)


def test_summit_observer_forces_expansions_and_stays_identical(tmp_path, monkeypatch):
    sc = _summit_scene(tmp_path, monkeypatch)
    ref = _horizon(monkeypatch, sc.lat, sc.lon, "full", obs=2.0)
    expanded = 0
    for reach in _reaches(("20m", "240m")):
        got = _horizon(monkeypatch, sc.lat, sc.lon, "adaptive", reach, obs=2.0)
        _assert_identical(ref, got, reach)
        expanded += len(got.params["performance_settings"]["expansions"])
    assert expanded > 0                                    # small reaches really were grown on demand
    assert ref.cross_product.any() and np.isfinite(ref.sigma_deg).any()  # uncertainty paths exercised


def test_edges_and_nodata_at_the_initial_reach(tmp_path, monkeypatch):
    sc = _edge_scene(tmp_path, monkeypatch)
    ref = _horizon(monkeypatch, sc.lat, sc.lon, "full")
    for reach in ({"240m": 10_000.0, "20m": 4_000.0}, {"240m": 9_760.0}, {"240m": 10_240.0}, {"240m": 1_000.0}):
        got = _horizon(monkeypatch, sc.lat, sc.lon, "adaptive", reach)
        _assert_identical(ref, got, reach)
    assert ref.incomplete.any() and not ref.incomplete.all()              # the nodata band breaks some rays


def test_without_the_stopping_rule(tmp_path, monkeypatch):
    sc = _summit_scene(tmp_path, monkeypatch)
    ref = _horizon(monkeypatch, sc.lat, sc.lon, "full", use_stop=False, nbins=360)
    got = _horizon(monkeypatch, sc.lat, sc.lon, "adaptive", {"240m": 5_000.0, "20m": 2_000.0}, use_stop=False,
                   nbins=360)
    _assert_identical(ref, got, "use_stop=False")


def test_phase2_scene_with_error_maps_and_a_partial_coarse_window(tmp_path, monkeypatch):
    """Cross-product discrepancy reads the coarse product over the whole fine window: a coarse reach smaller
    than the fine window grows on demand and the statistics are identical."""
    sc = Scene(tmp_path, monkeypatch)
    sc.add("FINE", 20.0, 8000.0, ring(2500.0, 120.0, 300.0), priority=10, err=0.5)
    sc.add("COARSE", 240.0, 40_000.0, ring(12_000.0, 900.0, 2000.0), priority=50, err=2.0)
    ref = _horizon(monkeypatch, sc.lat, sc.lon, "full")
    got = _horizon(monkeypatch, sc.lat, sc.lon, "adaptive", {"240m": 2_000.0})
    _assert_identical(ref, got, "phase2")
    assert ref.cross_product.any() and got.params["sigma"] == ref.params["sigma"]


# ------------------------------------------------------------------ structure and loader
def test_pyramid_structure_is_the_reference_one(tmp_path, monkeypatch):
    """Same windows in the same order, nominal shapes, origins and distance bands; partial windows report the
    loaded share; reading any pixel through the window gives the reference value."""
    from lunaops import settings
    from lunaops.engine.dem import bilinear, load_pyramid
    from lunaops.engine.horizon import build_steps
    sc = _summit_scene(tmp_path, monkeypatch)
    monkeypatch.setattr(settings, "WINDOW_MODE", "full")
    ref = load_pyramid(sc.lat, sc.lon)
    monkeypatch.setattr(settings, "WINDOW_MODE", "adaptive")
    monkeypatch.setattr(settings, "DEM_INITIAL_REACH_M", {"240m": 3_000.0})
    got = load_pyramid(sc.lat, sc.lon)
    assert [w.meta["key"] for w in got] == [w.meta["key"] for w in ref]
    for a, b in zip(ref, got):
        assert (a.x0, a.y0, a.dx, a.dy, a.band_m, a.pixel_m) == (b.x0, b.y0, b.dx, b.dy, b.band_m, b.pixel_m)
        assert a.data.shape == b.shape
    assert not got[1].complete and got[1].data.size < 0.01 * ref[1].data.size
    for dd in (0.5 * ref[0].pixel_m,):
        assert all(np.array_equal(x, y) for x, y in zip(build_steps(ref, dd), build_steps(got, dd)))
    rng = np.random.default_rng(0)
    for _ in range(200):
        x = sc.xs + rng.uniform(-55_000, 55_000)
        y = sc.ys + rng.uniform(-55_000, 55_000)
        r, g = bilinear(ref[1], x, y), bilinear(got[1], x, y)
        assert (math.isnan(r) and math.isnan(g)) or r == g


def test_initial_reach_validation():
    from lunaops import settings
    from lunaops.engine.dem import initial_reach_m
    for bad in ({"80m": 0.0}, {"80m": -5.0}, {"80m": 250_001.0}, {"240m": float("nan")}, {"some_product": 0.0},
                {"80m": "100"}):
        with pytest.raises(ValueError):
            settings.validate_initial_reach(bad)
    settings.validate_initial_reach({"80m": 250_000.0, "240m": 1.0, "pgda90_80m": 5.0})
    lv = {"level": "80m", "product_id": "p"}
    assert initial_reach_m(lv, 250_000.0) == settings.DEM_INITIAL_REACH_M["80m"]
    with pytest.raises(ValueError):
        old = dict(settings.DEM_INITIAL_REACH_M)
        try:
            settings.DEM_INITIAL_REACH_M["p"] = 300_000.0           # beyond this product's nominal half-width
            initial_reach_m(lv, 250_000.0)
        finally:
            settings.DEM_INITIAL_REACH_M.clear()
            settings.DEM_INITIAL_REACH_M.update(old)


def test_performance_settings_cannot_change_coverage():
    """The only performance settings are the window mode and the initial reach; the nominal windows (which
    define coverage, bands and steps) are not among them, and the bad mode is refused at startup."""
    import os
    import subprocess
    import sys
    from pathlib import Path
    from lunaops import settings
    assert set(settings.performance_settings()) == {"window_mode", "initial_reach_m"}
    r = subprocess.run([sys.executable, "-c", "import lunaops.settings"], capture_output=True, text=True,
                       env={**os.environ, "LUNAOPS_WINDOW_MODE": "lazy"}, cwd=Path(__file__).resolve().parents[1])
    assert r.returncode != 0 and "LUNAOPS_WINDOW_MODE" in r.stderr


def test_horizon_key_ignores_performance_settings(tmp_path, monkeypatch):
    from lunaops import settings
    from lunaops.engine.horizon import horizon_key
    sc = _summit_scene(tmp_path, monkeypatch)
    k = horizon_key(sc.lat, sc.lon, 0.0, 3600)
    monkeypatch.setattr(settings, "WINDOW_MODE", "full")
    monkeypatch.setattr(settings, "DEM_INITIAL_REACH_M", {"240m": 1_000.0})
    assert horizon_key(sc.lat, sc.lon, 0.0, 3600) == k
    monkeypatch.setattr(settings, "DEM_WINDOW_HALF_M", {**settings.DEM_WINDOW_HALF_M, "240m": 500_000.0})
    assert horizon_key(sc.lat, sc.lon, 0.0, 3600) != k                    # nominal coverage is keyed


# ------------------------------------------------------------------ memory and time
def _scene_80_240(tmp_path, monkeypatch):
    sc = Scene(tmp_path, monkeypatch)
    sc.add("C80", 80.0, 90_000.0, ring(30_000.0, 1200.0, 3000.0), priority=10)
    sc.add("C240", 240.0, 240_000.0, ring(150_000.0, 2500.0, 8000.0), priority=50)
    return sc


def test_peak_memory_is_at_least_40_percent_lower(tmp_path, monkeypatch):
    """tracemalloc peak of load_pyramid + compute_horizon on an 80 m + 240 m scene: the adaptive loader (one
    buffer, default initial reach) needs at least 40% less than the reference loader, with identical output."""
    import tracemalloc
    sc = _scene_80_240(tmp_path, monkeypatch)
    _horizon(monkeypatch, sc.lat, sc.lon, "adaptive", nbins=360)            # warm-up (numba compilation)
    peaks, hz = {}, {}
    for mode in ("full", "adaptive"):
        tracemalloc.start()
        hz[mode] = _horizon(monkeypatch, sc.lat, sc.lon, mode, nbins=360)
        peaks[mode] = tracemalloc.get_traced_memory()[1]
        tracemalloc.stop()
    _assert_identical(hz["full"], hz["adaptive"], "memory scene")
    saving = 1 - peaks["adaptive"] / peaks["full"]
    print(f"peak memory: reference {peaks['full'] / 1e6:.1f} MB, adaptive {peaks['adaptive'] / 1e6:.1f} MB "
          f"({100 * saving:.0f}% lower); expansions {len(hz['adaptive'].params['performance_settings']['expansions'])}")
    assert saving >= 0.40
