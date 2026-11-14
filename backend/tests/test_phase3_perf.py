"""Phase 3, item 8: performance and code quality, with scientific outputs unchanged.

Every optimisation here is bitwise output-preserving: an explicit cross product with np.cross's arithmetic,
per-site caching of the local basis, the event detector skipping Earth's visible fraction (recomputed where a
state is evaluated), and the exact-ellipse kernel refining only pieces that can hold the extreme clearance.
"""
from __future__ import annotations

import math
import time

import numpy as np
import pytest

from conftest import needs_kernels
from earth_helpers import E_AX, N_AX, U_AX, random_case


# ------------------------------------------------------------------ bitwise building blocks
def test_cross3_is_bitwise_np_cross():
    from lunaops.engine.frames import cross3
    rng = np.random.default_rng(0)
    a = rng.normal(size=(1_000_000, 3)) * 10 ** rng.uniform(-8, 8, (1_000_000, 1))
    b = rng.normal(size=(1_000_000, 3)) * 10 ** rng.uniform(-8, 8, (1_000_000, 1))
    assert np.array_equal(cross3(a, b), np.cross(a, b))
    assert np.array_equal(cross3(a[:1], b), np.cross(a[:1], b))                 # broadcasting (1, 3) x (n, 3)
    assert np.array_equal(cross3(a[0], b[0]), np.cross(a[0], b[0]))             # single vectors


def test_pruned_kernel_is_bitwise_the_unpruned_one():
    """g_top, g_bot, f and the span statistics of the exact-ellipse kernel are bitwise identical with and without
    pruning, on 3000 random limbs and horizons (with and without f) and on circular cones; pruning skips most
    Brent refinements."""
    from lunaops import settings
    from lunaops.engine.earth import cap_limb, earth_disk_kernel
    sv = settings.EARTH_SOLVER
    rng = np.random.default_rng(3)
    for k in range(3000):
        geo, hp, _kind = random_case(rng)
        if k % 3 == 0:
            geo = {**geo, **dict(zip(("Q0", "QA", "QB"), cap_limb(geo["az"], geo["el"], geo["alpha"], E_AX, N_AX, U_AX)))}
        args = (geo["Q0"], geo["QA"], geo["QB"], U_AX, E_AX, N_AX, math.radians(geo["az"]), math.radians(geo["el"]),
                hp.h, hp.inc, hp.bin, k % 2 == 0, sv["bracket"], sv["tol"], sv["maxiter"])
        a = earth_disk_kernel(*args, True)
        b = earth_disk_kernel(*args, False)
        for x, y in zip(a, b):
            assert x == y or (isinstance(x, float) and math.isnan(x) and math.isnan(y)), (k, a, b)


def test_pruning_speeds_up_the_kernel():
    """Benchmark on 400 near-horizon limbs (the detector's typical case): pruning is at least 1.5x faster."""
    from lunaops import settings
    from lunaops.engine.earth import earth_disk_kernel
    sv = settings.EARTH_SOLVER
    rng = np.random.default_rng(7)
    cases = []
    while len(cases) < 400:
        geo, hp, _ = random_case(rng)
        cases.append((geo["Q0"], geo["QA"], geo["QB"], U_AX, E_AX, N_AX, math.radians(geo["az"]),
                      math.radians(geo["el"]), hp.h, hp.inc, hp.bin, False, sv["bracket"], sv["tol"], sv["maxiter"]))
    for c in cases[:3]:
        earth_disk_kernel(*c, True), earth_disk_kernel(*c, False)
    times = {}
    for prune in (True, False):
        best = math.inf
        for _ in range(3):
            t = time.perf_counter()
            for c in cases:
                earth_disk_kernel(*c, prune)
            best = min(best, time.perf_counter() - t)
        times[prune] = best
    print(f"exact-ellipse kernel, 400 cases: unpruned {times[False] * 1e3:.0f} ms, pruned {times[True] * 1e3:.0f} ms "
          f"({times[False] / times[True]:.1f}x)")
    assert times[False] / times[True] >= 1.5


def test_site_caches_are_exact_and_safe():
    from lunaops.engine.ephem import Site
    from lunaops.engine.frames import enu_basis, latlon_to_xyz_m
    s = Site(-89.3, 123.4, 1500.0, 2.0)
    for v, w in zip(s.basis, enu_basis(-89.3, 123.4)):
        assert np.array_equal(v, w)
    assert np.array_equal(s.pos_km, latlon_to_xyz_m(-89.3, 123.4, 1502.0) / 1000.0)
    e, n, u = s.basis
    e[:] = 0.0                                              # a caller cannot alter the cached value
    assert np.array_equal(s.basis[0], enu_basis(-89.3, 123.4)[0])
    s.lat = -85.0                                           # a changed field gives a fresh value
    assert np.array_equal(s.basis[2], enu_basis(-85.0, 123.4)[2])
    assert np.array_equal(s.pos_km, latlon_to_xyz_m(-85.0, 123.4, 1502.0) / 1000.0)


@needs_kernels
def test_detector_skips_earth_fraction_but_states_keep_it(kernels):
    """The detector's Earth event values are identical with and without the visible fraction; full_state
    reports the same Earth fraction as the full computation."""
    import spiceypy as sp
    from earth_helpers import horizon
    from lunaops.engine.earth import earth_disk_state
    from lunaops.engine.ephem import Site
    from lunaops.engine.events import EventConfig, EventDetector, full_state
    det = EventDetector(Site(-89.0, 45.0, 0.0, 0.0), horizon("sloped", 312.6, -3.0, 0.8), EventConfig())
    et0 = sp.str2et("2026-11-14T12:00:00")
    for k in range(40):
        et = et0 + k * 1800.0
        smp = det.evaluate(et)
        g = smp.geo["earth"]["g"]
        full = earth_disk_state(det.hp, g, want_f=True)
        for f in ("c", "g_top", "g_bot", "unknown", "quick", "method"):
            assert smp.geo["earth"]["state"][f] == full[f], f
        st = full_state(det, et)["earth"]
        assert st["f"] == full["f"] or (math.isnan(st["f"]) and math.isnan(full["f"]))


@needs_kernels
def test_analysis_identical_with_and_without_pruning(kernels, synthetic_crater, monkeypatch):
    """A full 2-day analysis (events, intervals, series, summaries) is identical with the kernel's pruning
    switched off."""
    from lunaops.engine import earth
    from lunaops.engine.analysis import AnalysisRequest, analyze
    req = AnalysisRequest(lat=-89.0, lon=45.0, start_utc="2026-11-16T00:00:00Z", end_utc="2026-11-18T00:00:00Z")
    a = analyze(req)
    real = earth.earth_disk_kernel

    def unpruned(*args):
        return real(*args, False)
    monkeypatch.setattr(earth, "earth_disk_kernel", unpruned)
    b = analyze(req)
    for k in ("events", "intervals", "series", "summary", "labels", "warnings"):
        assert a[k] == b[k], k


# ------------------------------------------------------------------ determinism and import hygiene
@needs_kernels
def test_future_warning_follows_the_leap_second_kernel_not_the_clock(kernels):
    import inspect
    from lunaops.engine import timeutil
    assert timeutil.last_leap_second_utc() == "2017-01-01T00:00:00"          # the loaded test LSK's last entry
    src = inspect.getsource(timeutil)
    assert "datetime.now" not in src and "_now_et" not in src
    w_past = timeutil.check_window(timeutil.parse_utc("2016-03-01T00:00:00"), timeutil.parse_utc("2016-03-02T00:00:00"),
                                   600.0, 400)
    w_late = timeutil.check_window(timeutil.parse_utc("2018-03-01T00:00:00"), timeutil.parse_utc("2018-03-02T00:00:00"),
                                   600.0, 400)
    assert not any("leap second" in x for x in w_past)
    assert any("last leap second" in x and "2017-01-01" in x for x in w_late)


def test_importing_the_engine_creates_no_folders(tmp_path):
    """Importing settings and the engine modules has no side effects on disk; ensure_dirs creates the folders."""
    import os
    import subprocess
    import sys
    from pathlib import Path
    root = tmp_path / "fresh_data"
    code = ("import lunaops.settings as s, lunaops.engine.analysis, lunaops.engine.horizon, lunaops.engine.dem, "
            "lunaops.engine.cache, lunaops.engine.catalog, lunaops.engine.limb_darkening; "
            "import pathlib; print(pathlib.Path(s.DATA_DIR).exists()); s.ensure_dirs(); "
            "print(all(d.is_dir() for d in (s.PRODUCTION_KERNEL_DIR, s.DEMO_KERNEL_DIR, s.DEM_DIR, s.CATALOG_DIR, "
            "s.CACHE_DIR)))")
    env = {k: v for k, v in os.environ.items() if not k.startswith("LUNAOPS_")} | {"LUNAOPS_DATA_DIR": str(root)}
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env,
                       cwd=Path(__file__).resolve().parents[1])
    assert r.returncode == 0, r.stderr
    assert r.stdout.split() == ["False", "True"]


def test_dead_code_is_gone():
    from lunaops import settings
    from lunaops.engine import horizon, visibility
    for name in ("_circ_int", "_chords", "_disk_tangent"):
        assert not hasattr(visibility, name), name
    assert not hasattr(settings, "HORIZON_STOP_MARGIN_RAD")
    assert not hasattr(horizon, "HAVE_NUMBA")
