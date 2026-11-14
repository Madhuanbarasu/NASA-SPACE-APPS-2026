"""Phase 2: interval uncertainty and near-field flags (rules, limiting edge, propagation into events)."""
from __future__ import annotations

import math

import numpy as np
import pytest

from conftest import needs_kernels
from scene_helpers import Scene, ring


def _hp(sigma=0.1, nonlinear=(), unknown=(), near=(), sigma_bins=None, no_sigma=False):
    from lunaops.engine.visibility import HorizonProfile

    n = 3600
    sig = None if no_sigma else np.full(n, sigma)
    if sigma_bins and sig is not None:
        for i, v in sigma_bins.items():
            sig[i] = v
    flags = {"sigma_nonlinear": np.isin(np.arange(n), list(nonlinear)),
             "discrepancy_unknown": np.isin(np.arange(n), list(unknown)),
             "near_field": np.isin(np.arange(n), list(near))}
    for i in unknown:
        if sig is not None:
            sig[i] = np.nan
    return HorizonProfile(np.zeros(n), np.zeros(n, bool), sig, flags=flags)


def _smp(g, az=100.0, el=1.0, rho=0.27, fn="sun_c", tgt="sun", et=0.0):
    from lunaops.engine.events import Sample
    return Sample(et, {fn: g}, {}, {}, {tgt: {"az": az, "el": el, "rho": rho}})


def _flags(hp, state, gs, **kw):
    from lunaops.engine.events import interval_flags
    return interval_flags(hp, state, "sun_c", "sun", [_smp(g, **kw) for g in gs], k=1.0)


# ------------------------------------------------------------------ rules (stub level)
def test_window_rule():
    hp = _hp(0.2)
    assert _flags(hp, True, [0.05, 0.3, 0.1]) == {"uncertain": False, "uncertain_reasons": [], "near_field": False}
    f = _flags(hp, True, [0.05, 0.15, 0.1])
    assert f["uncertain"] is True and f["uncertain_reasons"] == ["below_k_sigma"]


def test_gap_rule_uses_the_deepest_sample():
    hp = _hp(0.2)
    # near the gap's edges g is close to 0, so g + k sigma > 0 there; a single clearly hidden interior
    # sample settles the gap's existence (the min rule). A max rule would flag every gap.
    assert _flags(hp, False, [-0.01, -0.5, -0.02])["uncertain"] is False
    f = _flags(hp, False, [-0.01, -0.15, -0.02])
    assert f["uncertain"] is True and f["uncertain_reasons"] == ["below_k_sigma"]


def test_limiting_edge_not_centre():
    # sigma 0.1 everywhere except bin 1002 (100.2 deg) inside the Sun disk's span around az 100
    hp = _hp(0.1, sigma_bins={1002: 0.5})
    assert hp.sigma_at(100.0) == pytest.approx(0.1)          # the former centre-only rule would clear it
    f = _flags(hp, True, [0.3])
    assert f["uncertain"] is True and f["uncertain_reasons"] == ["below_k_sigma"]
    assert _flags(hp, True, [0.3], az=200.0)["uncertain"] is False


def test_nonlinear_forces_uncertain_and_threshold_boundary():
    from lunaops import settings

    hp = _hp(0.1, nonlinear=[1000])
    f = _flags(hp, True, [10.0])                            # clearance far beyond the stated sigma
    assert f["uncertain"] is True and f["uncertain_reasons"] == ["sigma_nonlinear"]
    f = _flags(hp, False, [-10.0])
    assert f["uncertain"] is True and f["uncertain_reasons"] == ["sigma_nonlinear"]
    # just below the threshold the bin is not nonlinear and the normal k-sigma rule applies
    just = settings.SIGMA_NONLINEAR_DEG - 0.01
    hp2 = _hp(0.1, sigma_bins={1000: just})
    assert _flags(hp2, True, [just + 0.5])["uncertain"] is False
    assert _flags(hp2, True, [just - 0.5])["uncertain_reasons"] == ["below_k_sigma"]


def test_unknown_discrepancy_forces_uncertain():
    hp = _hp(0.1, unknown=range(990, 1010))
    f = _flags(hp, True, [10.0])
    assert f["uncertain"] is True and f["uncertain_reasons"] == ["cross_product_discrepancy_unknown"]
    hp_all = _hp(0.1, unknown=range(3600))                  # no finite sigma at all, still never cleared
    f = _flags(hp_all, False, [-10.0])
    assert f["uncertain"] is True and f["uncertain_reasons"] == ["cross_product_discrepancy_unknown"]


def test_no_sigma_or_unknown_state_gives_none():
    assert _flags(_hp(no_sigma=True), True, [0.01])["uncertain"] is None
    assert _flags(_hp(0.2), None, [0.01]) == {"uncertain": None, "uncertain_reasons": [], "near_field": False}


def test_near_field_flag_follows_the_span():
    hp = _hp(0.1, near=[1001])
    assert _flags(hp, True, [1.0])["near_field"] is True
    assert _flags(hp, True, [1.0], az=150.0)["near_field"] is False
    assert _flags(_hp(no_sigma=True, near=[1001]), True, [1.0])["near_field"] is True   # even without sigma


def test_sample_free_interval_is_evaluated_at_its_midpoint():
    from lunaops.engine.events import FUNCS, Sample, _flag_intervals

    hp = _hp(0.2)
    calls = []

    class Det:
        def __init__(self):
            self.hp = hp

        def evaluate(self, et):
            calls.append(et)
            vals = {f: (0.1 if et < 150 else 0.9) for f in FUNCS}
            geo = {t: {"az": 100.0, "el": 1.0, "rho": 0.27} for t in ("sun", "earth")}
            return Sample(et, vals, {}, {}, geo)

    ivs = {"sun_centre": [{"start_et": 0.0, "end_et": 100.0, "state": True},
                          {"start_et": 100.0, "end_et": 400.0, "state": True},
                          {"start_et": 400.0, "end_et": 500.0, "state": None}]}
    _flag_intervals(Det(), ivs, samples=[])
    a, b, c = ivs["sun_centre"]
    assert a["uncertain"] is True and a["uncertain_reasons"] == ["below_k_sigma"]   # midpoint 0.1 < 0.2
    assert b["uncertain"] is False                                                    # midpoint 0.9 > 0.2
    assert c["uncertain"] is None
    assert sorted(calls) == [50.0, 250.0]


def test_intersect_or_semantics():
    from lunaops.engine.events import intersect

    def iv(a, b, unc, reasons=(), near=False):
        return {"start_et": a, "end_et": b, "state": True, "uncertain": unc, "uncertain_reasons": list(reasons),
                "near_field": near}

    A = [iv(0, 10, False), iv(20, 30, True, ["below_k_sigma"]), iv(40, 50, None), iv(60, 70, None), iv(80, 90, False)]
    B = [iv(5, 15, None, near=True), iv(25, 35, False), iv(45, 55, None), iv(65, 75, True, ["sigma_nonlinear"]),
         iv(85, 95, False)]
    out = intersect(A, B)
    assert [o["uncertain"] for o in out] == [False, True, None, True, False]
    assert out[1]["uncertain_reasons"] == ["below_k_sigma"] and out[3]["uncertain_reasons"] == ["sigma_nonlinear"]
    assert [o["near_field"] for o in out] == [True, False, False, False, False]


def test_summary_counts():
    from lunaops.engine.events import summarize

    ivs = [{"start_et": 0, "end_et": 10, "state": True, "duration_s": 10, "brief": True, "uncertain": True,
            "near_field": True},
           {"start_et": 10, "end_et": 20, "state": False, "duration_s": 10, "brief": False, "uncertain": True,
            "near_field": False},
           {"start_et": 20, "end_et": 30, "state": True, "duration_s": 10, "brief": True, "uncertain": False,
            "near_field": False}]
    s = summarize(ivs, 0, 30)
    assert s["uncertain_windows"] == 1 and s["uncertain_gaps"] == 1 and s["near_field_windows"] == 1


# ------------------------------------------------------------------ propagation through the detector
def _ramp_scene(tmp_path, monkeypatch):
    """Flat ground behind the observer (near-field horizon) and a 10-degree ramp starting 50 m in front
    of it (far blockers), so a 30-day run gives both near-field and other intervals."""
    sc = Scene(tmp_path, monkeypatch)
    tan10 = math.tan(math.radians(10.0))
    f = lambda DX, DY: np.clip(DX - 50.0, 0.0, 2000.0) * tan10
    sc.add("ramp20", 20.0, 3000.0, f, priority=40)
    sc.add("ramp240", 240.0, 60_000.0, f, priority=50)
    return sc


@needs_kernels
def test_near_field_propagates_into_intervals_and_results(kernels, tmp_path, monkeypatch):
    from lunaops.engine.analysis import AnalysisRequest, analyze
    from lunaops.engine.ephem import Site, sample_target
    from lunaops.engine.visibility import HorizonProfile

    sc = _ramp_scene(tmp_path, monkeypatch)
    hz = sc.horizon(0.0)
    assert 0.2 < hz.near_field.mean() < 0.8, hz.near_field.mean()
    req = AnalysisRequest(lat=sc.lat, lon=sc.lon, start_utc="2026-11-14T00:00:00Z", end_utc="2026-12-14T00:00:00Z",
                          step_s=21600.0)
    res = analyze(req)
    assert res["horizon"]["near_field_share"] == pytest.approx(hz.near_field.mean())
    assert any("near_field" in w for w in res["warnings"])
    hp = HorizonProfile(hz.h_deg, hz.incomplete, None, flags=hz.flag_arrays())
    site = Site(sc.lat, sc.lon, hz.ground_h_m, 0.0)
    checked = {True: 0, False: 0}
    for key in ("sun_any", "sun_centre", "earth_any", "earth_full"):
        tgt = key.split("_")[0]
        for iv in res["intervals"][key]:
            if iv["state"] is None:
                continue
            n = max(25, int((iv["end_et"] - iv["start_et"]) / 600))
            ets = np.linspace(iv["start_et"], iv["end_et"], n + 2)[1:-1]     # independent dense grid
            t = sample_target(site, tgt, ets)
            touch = [hp.span_flags(float(a), float(r) / max(math.cos(math.radians(float(e))), 1e-9))["near_field"]
                     for a, e, r in zip(t.az, t.el, t.rho)]
            if all(touch):
                assert iv["near_field"] is True, (key, iv)
                checked[True] += 1
            elif not any(touch):
                assert iv["near_field"] is False, (key, iv)
                checked[False] += 1
    assert checked[True] >= 2 and checked[False] >= 2, checked
    for key, s in res["summary"].items():
        if isinstance(s, dict) and "near_field_windows" in s:
            ivs = res["intervals"][key]
            assert s["near_field_windows"] == sum(1 for iv in ivs if iv["state"] is True and iv["near_field"])
    ov = res["intervals"]["overlap"]
    for o in (o for o in ov if o["state"] is True):        # overlap windows inherit near_field (OR)
        parents = [iv for k in ("sun_any", "earth_centre") for iv in res["intervals"][k]
                   if iv["state"] is True and iv["start_et"] <= o["start_et"] + 1e-6 and iv["end_et"] >= o["end_et"] - 1e-6]
        assert o["near_field"] == any(p["near_field"] for p in parents)
    # at 2 m the same terrain has no near-field bins and no near-field intervals or warning
    res2 = analyze(AnalysisRequest(lat=sc.lat, lon=sc.lon, start_utc="2026-11-14T00:00:00Z",
                                   end_utc="2026-11-15T00:00:00Z", observer_h_m=2.0, observer_profile="equipment"))
    assert res2["horizon"]["near_field_share"] == 0.0
    assert not any(iv["near_field"] for ivs in res2["intervals"].values() for iv in ivs)
    assert not any("near_field" in w for w in res2["warnings"])


@needs_kernels
def test_unknown_discrepancy_flags_every_affected_interval(kernels, tmp_path, monkeypatch):
    from lunaops.engine.analysis import AnalysisRequest, analyze

    sc = Scene(tmp_path, monkeypatch)
    sc.add("A", 20.0, 200.0, lambda DX, DY: np.zeros_like(DX), priority=40, err=0.5)
    rg = ring(6000.0, 300.0, 400.0)
    sc.add("B", 20.0, 20_000.0, lambda DX, DY: np.where(np.maximum(abs(DX), abs(DY)) < 190.0, np.nan, rg(DX, DY)),
           priority=50, err=3.0)
    res = analyze(AnalysisRequest(lat=sc.lat, lon=sc.lon, start_utc="2026-11-14T00:00:00Z",
                                  end_utc="2026-11-15T00:00:00Z"))
    assert any(w.startswith("Cross-product terrain discrepancy could not be measured") for w in res["warnings"])
    n = 0
    for key, ivs in res["intervals"].items():
        if key == "overlap":
            continue
        for iv in ivs:
            if iv["state"] is not None:
                assert iv["uncertain"] is True and "cross_product_discrepancy_unknown" in iv["uncertain_reasons"], (key, iv)
                n += 1
    assert n >= 6


@needs_kernels
def test_nonlinear_bins_flag_intervals_in_results(kernels, tmp_path, monkeypatch):
    from lunaops.engine.analysis import AnalysisRequest, analyze

    sc = Scene(tmp_path, monkeypatch)
    # 40 m error-map uncertainty over a region much wider than L_corr around a near ridge: every
    # direction is beyond first-order validity (about 7.7 deg at the ridge, more in the near field)
    sc.add("A", 20.0, 3000.0, ring(250.0, 60.0, 30.0), err=lambda DX, DY: np.where(
        np.maximum(abs(DX), abs(DY)) < 2000.0, 40.0, 0.5))
    hz = sc.horizon(0.0)
    assert hz.sigma_nonlinear.mean() > 0.9
    res = analyze(AnalysisRequest(lat=sc.lat, lon=sc.lon, start_utc="2026-11-14T00:00:00Z",
                                  end_utc="2026-11-15T00:00:00Z"))
    assert any("beyond the range where first-order propagation is trusted" in w for w in res["warnings"])
    flagged = [iv for k, ivs in res["intervals"].items() if k != "overlap" for iv in ivs if iv["state"] is not None]
    assert flagged and all(iv["uncertain"] is True and "sigma_nonlinear" in iv["uncertain_reasons"] for iv in flagged)
