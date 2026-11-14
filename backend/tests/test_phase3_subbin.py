"""Phase 3, item 7: sub-bin azimuth peaks.

SUBBIN_RAYS = M rays per bin interval [az_k, az_k+1) (counting the node ray); the extra rays run the unchanged
horizon kernel at az_k + j bin / M. Per bin the excess is how far a sub-ray rises above the linear
interpolation between the nodes. Node values, D, W, incomplete, sigma and every Phase 2 flag are bitwise
unchanged for any M; the excess never enters the uncertainty flags; windows get a separate one-sided
`subbin_peak` flag.

The spike scenes use 4 deg bins (nbins = 90) on a 5 m synthetic DEM: the algorithm is bin-size generic, and a
spike narrower than a 0.1 deg bin yet resolved by the DEM would need a DEM of tens of millions of pixels.
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from conftest import needs_kernels
from scene_helpers import Scene, ring

NB = 90                    # 4 deg bins for the spike scenes
SPIKE_D, SPIKE_H, SIG_LAT, SIG_RAD = 3000.0, 100.0, 30.0, 200.0


def _point_dxdy(sc, az_deg, d_m):
    """Stereographic offset (DX, DY) from the site of the surface point at azimuth az, distance d (as the
    horizon kernel maps rays)."""
    from lunaops import settings
    from lunaops.engine.frames import enu_basis
    R0 = settings.R_MOON_M
    e, n, u = enu_basis(sc.lat, sc.lon)
    a, dl = math.radians(az_deg), d_m / R0
    t = math.cos(a) * n + math.sin(a) * e
    P = math.cos(dl) * u + math.sin(dl) * t
    X, Y = 2 * R0 * P[1] / (1 - P[2]), 2 * R0 * P[0] / (1 - P[2])
    return X - sc.xs, Y - sc.ys


def _spike(sc, az_deg, height=SPIKE_H):
    cx, cy = _point_dxdy(sc, az_deg, SPIKE_D)
    r = math.hypot(cx, cy)
    ur = np.array([cx, cy]) / r

    def h(DX, DY):
        rad = DX * ur[0] + DY * ur[1]
        lat = -DX * ur[1] + DY * ur[0]
        return height * np.exp(-0.5 * (lat / SIG_LAT) ** 2 - 0.5 * ((rad - r) / SIG_RAD) ** 2)
    return h


def _scene(tmp_path, monkeypatch, *spikes, extra=None):
    sc = Scene(tmp_path, monkeypatch)
    fns = [_spike(sc, a) for a in spikes]

    def height(DX, DY):
        z = np.zeros(DX.shape)
        for f in fns:
            z = z + f(DX, DY)
        if extra is not None:
            z = extra(DX, DY, z)
        return z
    sc.add("S", 5.0, 4000.0, height, priority=10)
    # flat coarse backdrop to 30 km: with a 100 m spike the stopping bound needs ~19 km of terrain before
    # every ray completes (on the 4 km product alone all rays would end incomplete)
    sc.add("C", 240.0, 30000.0, lambda DX, DY: np.zeros(DX.shape), priority=50)
    return sc, height


def _horizon(sc, M, monkeypatch, nbins=NB):
    from lunaops import settings
    from lunaops.engine.horizon import compute_horizon
    monkeypatch.setattr(settings, "SUBBIN_RAYS", M)
    return compute_horizon(sc.lat, sc.lon, 0.0, nbins=nbins)


def _reference_elev(sc, height, az_deg, step=1.0, max_d=3900.0):
    """Independent brute-force horizon elevation (deg) from the analytic height function: no DEM, no bilinear
    interpolation, 1 m steps."""
    from lunaops import settings
    from lunaops.engine.frames import enu_basis
    R0 = settings.R_MOON_M
    e, n, u = enu_basis(sc.lat, sc.lon)
    S = (R0 + float(height(np.zeros(1), np.zeros(1))[0])) * u
    d = np.arange(step, max_d, step)
    dl = d / R0
    a = math.radians(az_deg)
    t = math.cos(a) * n + math.sin(a) * e
    P = np.outer(np.cos(dl), u) + np.outer(np.sin(dl), t)
    X, Y = 2 * R0 * P[:, 1] / (1 - P[:, 2]), 2 * R0 * P[:, 0] / (1 - P[:, 2])
    hh = height(X - sc.xs, Y - sc.ys)
    V = (R0 + hh)[:, None] * P - S
    s = (V @ u) / np.linalg.norm(V, axis=1)
    return math.degrees(math.asin(s.max()))


# ------------------------------------------------------------------ definition and validation
@pytest.mark.parametrize("bad", [0, 17, -1, 2.5, "4x", "2.5", "", True, None])
def test_invalid_subbin_rays_are_rejected(bad):
    from lunaops import settings
    with pytest.raises(ValueError):
        settings.validate_subbin_rays(bad)


def test_valid_subbin_rays_and_startup_check():
    import subprocess
    import sys
    from lunaops import settings
    assert [settings.validate_subbin_rays(v) for v in (1, 4, 16, "8", np.int64(2))] == [1, 4, 16, 8, 2]
    assert settings.SUBBIN_RAYS == 4                                         # default
    r = subprocess.run([sys.executable, "-c", "import lunaops.settings"], capture_output=True, text=True,
                       env={**__import__("os").environ, "LUNAOPS_SUBBIN_RAYS": "17"},
                       cwd=__import__("pathlib").Path(__file__).resolve().parents[1])
    assert r.returncode != 0 and "SUBBIN_RAYS" in r.stderr


def test_invalid_value_set_at_run_time_is_rejected(tmp_path, monkeypatch):
    sc, _ = _scene(tmp_path, monkeypatch)
    with pytest.raises(ValueError):
        _horizon(sc, 0, monkeypatch)


# ------------------------------------------------------------------ node outputs unchanged (V-07 compatible)
def test_node_outputs_and_phase2_arrays_are_bitwise_identical_for_any_m(tmp_path, monkeypatch):
    """h_deg, D, W, incomplete, sigma and every Phase 2 array are bitwise identical for M = 1, 2, 4, 8, on a
    two-product scene with error maps (sigma, cross-product and near-field flags all exercised)."""
    sc = Scene(tmp_path, monkeypatch)
    sc.add("FINE", 20.0, 3000.0, ring(2500.0, 120.0, 300.0), priority=10, err=0.5)
    sc.add("COARSE", 240.0, 30000.0, ring(12000.0, 900.0, 2000.0), priority=50, err=2.0)
    from lunaops.engine.horizon import EXTRA_ARRAYS
    base = _horizon(sc, 1, monkeypatch, nbins=720)
    assert np.all(base.subbin_excess_deg == 0.0)                           # M = 1: no sub-rays, excess exactly 0
    names = ["h_deg", "block_dist_m", "incomplete", "sigma_deg"] + [a for a in EXTRA_ARRAYS if not a.startswith("subbin")]
    for M in (2, 4, 8):
        hz = _horizon(sc, M, monkeypatch, nbins=720)
        for name in names:
            a, b = getattr(base, name), getattr(hz, name)
            assert (a is None and b is None) or np.array_equal(a, b, equal_nan=True), (M, name)
        assert hz.params["sigma"] == base.params["sigma"]


# ------------------------------------------------------------------ sub-ray geometry
def test_subrays_are_the_finer_node_rays(tmp_path, monkeypatch):
    """Sub-ray j of bin k at M rays per bin is the node ray 4k + j of a horizon with 4x the bins: the excess
    recomputed from that finer horizon equals the stored excess to 1e-9 deg (azimuths agree to rounding)."""
    sc, _ = _scene(tmp_path, monkeypatch, 4 * 10 + 2.0, 4 * 33 + 1.48)
    hz = _horizon(sc, 4, monkeypatch)
    fine = _horizon(sc, 1, monkeypatch, nbins=4 * NB)
    H = hz.h_deg
    assert np.array_equal(fine.h_deg[::4], H)
    nxt = np.roll(H, -1)
    ex = np.zeros(NB)
    for j in (1, 2, 3):
        ex = np.maximum(ex, fine.h_deg[j::4] - (H + (j / 4) * (nxt - H)))
    assert np.max(np.abs(ex - hz.subbin_excess_deg)) < 1e-9


def test_subray_elevations_match_an_analytic_brute_force(tmp_path, monkeypatch):
    """The kernel's sub-ray elevations (as finer node rays) agree with the analytic brute-force horizon of the
    same terrain (no DEM interpolation) within 0.01 deg."""
    sc, height = _scene(tmp_path, monkeypatch, 4 * 10 + 2.0)
    fine = _horizon(sc, 1, monkeypatch, nbins=4 * NB)
    for idx in (4 * 10, 4 * 10 + 1, 4 * 10 + 2, 4 * 10 + 3, 4 * 20 + 2):
        ref = _reference_elev(sc, height, idx * 360.0 / (4 * NB))
        assert abs(fine.h_deg[idx] - ref) < 0.01, (idx, fine.h_deg[idx], ref)


# ------------------------------------------------------------------ detection, flat peaks, wrap, missing data
def test_spike_between_nodes_is_detected(tmp_path, monkeypatch):
    """A 1.9 deg spike centred between two nodes: the nodes barely see it, the mid sub-ray does; the excess of
    that bin is the spike's height above the interpolation; elsewhere the excess is negligible."""
    sc, height = _scene(tmp_path, monkeypatch, 4 * 10 + 2.0)
    hz = _horizon(sc, 4, monkeypatch)
    peak = _reference_elev(sc, height, 42.0)
    assert peak > 1.5
    assert hz.h_deg[10] < 0.05 and hz.h_deg[11] < 0.05                     # nodes 40 and 44 deg
    ex = hz.subbin_excess_deg
    assert abs(ex[10] - (peak - 0.5 * (hz.h_deg[10] + hz.h_deg[11]))) < 0.01
    assert np.max(np.delete(ex, 10)) < 0.01 and not hz.subbin_unknown.any()
    assert hz.params["subbin"]["bins_with_excess"] >= 1 and hz.params["subbin"]["max_excess_deg"] == ex[10]


def test_flat_peak_gives_no_excess(tmp_path, monkeypatch):
    """A ring ridge wider than any bin (a flat-topped horizon in azimuth): sub-rays add nothing beyond the
    curvature of the interpolation, below 1e-3 deg everywhere."""
    sc = Scene(tmp_path, monkeypatch)
    sc.add("R", 5.0, 4000.0, ring(3000.0, 100.0, 200.0))
    hz = _horizon(sc, 8, monkeypatch)
    assert np.max(hz.subbin_excess_deg) < 1e-3 and np.min(hz.subbin_excess_deg) >= 0.0


def test_spike_in_the_last_bin_wraps_to_node_zero(tmp_path, monkeypatch):
    sc, height = _scene(tmp_path, monkeypatch, 358.0)
    hz = _horizon(sc, 4, monkeypatch)
    assert hz.subbin_excess_deg[NB - 1] > 1.5
    assert np.max(hz.subbin_excess_deg[:NB - 1]) < 0.01


def test_missing_data_seen_only_by_subrays_makes_the_excess_unknown(tmp_path, monkeypatch):
    """A nodata strip between two nodes (about 0.5 deg wide, from 1 km out): the nodes stay complete, the sub-ray
    that crosses it is incomplete, so that bin's excess is unknown; neighbouring bins are known."""
    def hole(DX, DY, z):
        sc_ = holder["sc"]
        cx, cy = _point_dxdy(sc_, 22.0, 1500.0)
        ur = np.array([cx, cy]) / math.hypot(cx, cy)
        rad = DX * ur[0] + DY * ur[1]
        lat = -DX * ur[1] + DY * ur[0]
        z = z.copy()
        z[(rad > 1000.0) & (np.abs(lat) < 0.004 * rad)] = np.nan
        return z
    holder = {}
    sc = Scene(tmp_path, monkeypatch)
    holder["sc"] = sc
    # a ring ridge beyond the strip keeps every ray going past 1 km (the stopping bound needs higher terrain)
    sc.add("H", 5.0, 4000.0, lambda DX, DY: hole(DX, DY, ring(3500.0, 300.0, 150.0)(DX, DY)))
    hz = _horizon(sc, 4, monkeypatch)
    assert not hz.incomplete[5] and not hz.incomplete[6]                    # nodes 20 and 24 deg
    assert hz.subbin_unknown[5]
    assert not hz.subbin_unknown[4] and not hz.subbin_unknown[6]


# ------------------------------------------------------------------ nested refinement and convergence
def test_nested_m_is_monotone_and_converges(tmp_path, monkeypatch):
    """Nested M (1, 2, 4, 8, 16): every ray of M is a ray of 2M (bitwise the same azimuth), so the excess is
    non-decreasing per bin, bitwise. Against a dense reference (M = 64) the deficit is >= 0 and non-increasing.
    A spike centred mid-bin is caught exactly from M = 2 (deficit < 0.01 deg at M = 4); one off the sub-ray grid
    (0.37 bin) shows why no fixed M bounds the deficit for features narrower than its spacing: large at M = 4,
    then shrinking."""
    sc, _ = _scene(tmp_path, monkeypatch, 4 * 10 + 2.0, 4 * 33 + 1.48)
    exs = {M: _horizon(sc, M, monkeypatch).subbin_excess_deg for M in (1, 2, 4, 8, 16)}
    for a, b in ((1, 2), (2, 4), (4, 8), (8, 16)):
        assert np.all(exs[b] >= exs[a]), (a, b)
    from lunaops import settings
    monkeypatch.setattr(settings, "validate_subbin_rays", lambda v: int(v))   # M = 64 is a test-only reference
    ref = _horizon(sc, 64, monkeypatch).subbin_excess_deg
    deficits = {M: ref - exs[M] for M in exs}
    for M in exs:
        assert np.all(deficits[M] >= -1e-12), M
    for a, b in ((1, 2), (2, 4), (4, 8), (8, 16)):
        assert np.all(deficits[b] <= deficits[a] + 1e-12), (a, b)
    assert deficits[4][10] < 0.01                                           # mid-bin spike
    assert deficits[4][33] > 0.05 and deficits[16][33] < 0.5 * deficits[4][33]   # off-grid spike
    print("deficit (deg) at the off-grid spike, M = 1, 2, 4, 8, 16:",
          [round(float(deficits[M][33]), 4) for M in (1, 2, 4, 8, 16)])


@needs_kernels
def test_smooth_crater_deficit_is_tiny(kernels, synthetic_crater, monkeypatch):
    """On the smooth synthetic crater (0.1 deg bins) the M = 4 excess is within 1e-3 deg of an M = 16 reference."""
    from lunaops import settings
    from lunaops.engine.horizon import compute_horizon
    monkeypatch.setattr(settings, "SUBBIN_RAYS", 4)
    e4 = compute_horizon(-89.0, 45.0, 0.0).subbin_excess_deg
    monkeypatch.setattr(settings, "SUBBIN_RAYS", 16)
    e16 = compute_horizon(-89.0, 45.0, 0.0).subbin_excess_deg
    assert np.all(e16 >= e4) and np.max(e16 - e4) < 1e-3


# ------------------------------------------------------------------ window flag
def _hp(excess, unknown=()):
    from lunaops.engine.visibility import HorizonProfile
    n = 3600
    ex = np.zeros(n)
    for i, v in excess.items():
        ex[i] = v
    return HorizonProfile(np.zeros(n), np.zeros(n, bool), np.full(n, 0.01),
                          flags={"subbin_excess_deg": ex, "subbin_unknown": np.isin(np.arange(n), list(unknown))})


def _smp(g, az=100.0):
    from lunaops.engine.events import Sample
    return Sample(0.0, {"sun_top": g}, {}, {}, {"sun": {"az": az, "el": 1.0, "rho": 0.27}})


def test_window_flag_rule():
    from lunaops.engine.events import subbin_peak
    hp = _hp({1001: 0.2})
    assert subbin_peak(hp, True, "sun_top", "sun", [_smp(0.05), _smp(0.15)]) is True       # never clears 0.2
    assert subbin_peak(hp, True, "sun_top", "sun", [_smp(0.05), _smp(0.25)]) is False      # one sample clears it
    assert subbin_peak(hp, True, "sun_top", "sun", [_smp(0.05)], ) is True
    assert subbin_peak(hp, True, "sun_top", "sun", [_smp(0.05, az=200.0)]) is False          # spike not under the disk
    assert subbin_peak(_hp({}), True, "sun_top", "sun", [_smp(1e-6)]) is False              # M = 1 / no excess


def test_gaps_never_flagged_and_unknown_cases():
    from lunaops.engine.events import subbin_peak
    from lunaops.engine.visibility import HorizonProfile
    hp = _hp({1001: 5.0}, unknown=(1003,))
    assert subbin_peak(hp, False, "sun_top", "sun", [_smp(-0.01)]) is False                # gaps: never
    assert subbin_peak(hp, None, "sun_top", "sun", [_smp(0.01)]) is None                    # unknown interval
    assert subbin_peak(hp, True, "sun_top", "sun", [_smp(9.0)]) is None                     # unknown excess spanned
    no_data = HorizonProfile(np.zeros(3600), np.zeros(3600, bool))
    assert subbin_peak(no_data, True, "sun_top", "sun", [_smp(0.1)]) is None                # not computed


def test_window_flag_never_touches_the_uncertainty_flags():
    """interval_flags (Phase 2) returns exactly the same dict with and without sub-bin excess data."""
    from lunaops.engine.events import interval_flags
    a = interval_flags(_hp({1001: 5.0}), True, "sun_top", "sun", [_smp(0.05)], k=1.0)
    b = interval_flags(_hp({}), True, "sun_top", "sun", [_smp(0.05)], k=1.0)
    assert a == b and "subbin_peak" not in a


# ------------------------------------------------------------------ keys, cache, analysis
def test_subbin_rays_are_in_the_horizon_key(monkeypatch, tmp_path):
    from lunaops import settings
    from lunaops.engine.horizon import horizon_key
    sc, _ = _scene(tmp_path, monkeypatch)
    k4 = horizon_key(sc.lat, sc.lon, 0.0, 3600)
    monkeypatch.setattr(settings, "SUBBIN_RAYS", 8)
    assert horizon_key(sc.lat, sc.lon, 0.0, 3600) != k4
    monkeypatch.setattr(settings, "SUBBIN_RAYS", 4)
    assert horizon_key(sc.lat, sc.lon, 0.0, 3600) == k4


def test_cached_horizon_keeps_the_excess(tmp_path, monkeypatch):
    from lunaops.engine.cache import get_cached_horizon, put_cached_horizon
    sc, _ = _scene(tmp_path, monkeypatch, 42.0)
    hz = _horizon(sc, 4, monkeypatch)
    put_cached_horizon(hz)
    back = get_cached_horizon(hz.key)
    assert np.array_equal(back.subbin_excess_deg, hz.subbin_excess_deg)
    assert np.array_equal(back.subbin_unknown, hz.subbin_unknown)


@needs_kernels
def test_analysis_phase2_flags_identical_for_m1_and_m4(kernels, synthetic_crater, monkeypatch):
    """Golden window: events, interval states and edges, uncertain, uncertain_reasons, near_field and the summary
    counts are identical for M = 1 and M = 4; subbin_peak is reported on windows only, gaps never flagged."""
    from lunaops import settings
    from lunaops.engine import cache
    from lunaops.engine.analysis import AnalysisRequest, analyze
    from test_phase2_golden import SNAP
    out = {}
    for M in (1, 4):
        monkeypatch.setattr(settings, "SUBBIN_RAYS", M)
        cache.clear()
        out[M] = analyze(AnalysisRequest(**SNAP["request"]))
    a, b = out[1], out[4]
    assert a["events"] == b["events"]
    for k in a["intervals"]:
        for x, y in zip(a["intervals"][k], b["intervals"][k]):
            for f in ("state", "start_et", "end_et", "uncertain", "uncertain_reasons", "near_field", "brief"):
                assert x[f] == y[f], (k, f)
            if y["state"] is False:
                assert y["subbin_peak"] is False
    for k, v in a["summary"].items():
        if isinstance(v, dict) and "windows" in v:
            for f in ("uncertain_windows", "uncertain_gaps", "near_field_windows", "windows", "hours"):
                assert v[f] == b["summary"][k][f], (k, f)
    assert a["horizon"]["h_deg"] == b["horizon"]["h_deg"]
    assert b["provenance"]["horizon"]["params"]["subbin"]["rays_per_bin"] == 4


@needs_kernels
def test_m4_horizon_cost(kernels, synthetic_crater, monkeypatch):
    """Acceptance: the M = 4 horizon takes at most 4.5x the node-only time (best of three runs)."""
    import time
    from lunaops import settings
    from lunaops.engine.horizon import compute_horizon
    times = {}
    for M in (1, 4):
        monkeypatch.setattr(settings, "SUBBIN_RAYS", M)
        compute_horizon(-89.0, 45.0, 0.0)                                    # warm-up (compilation, file cache)
        best = math.inf
        for _ in range(3):
            t = time.perf_counter()
            compute_horizon(-89.0, 45.0, 0.0)
            best = min(best, time.perf_counter() - t)
        times[M] = best
    ratio = times[4] / times[1]
    print(f"horizon time: node-only {times[1]:.3f} s, M = 4 {times[4]:.3f} s, ratio {ratio:.2f}")
    assert ratio <= 4.5
