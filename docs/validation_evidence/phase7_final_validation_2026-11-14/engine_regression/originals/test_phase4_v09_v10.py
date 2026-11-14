"""Phase 4 A10: V-09 / V-10 against the LOLA AVGVISIB maps (validation/v09_v10_avgvisib.py).

The real maps (51 MB each) are not in the repository; their PDS3 labels and provenance are
(validation/reference/avgvisib/). These tests check the label facts the comparison rests on, the encoding checks,
the deterministic stratified sampling inside the documented coverage, that the vectorised hourly method equals the
engine's own event detector ("any" rule, Sun with Earth occultation, oblate Earth), the scoring (the provisional
criteria can never produce a pass), and the end-to-end result with its merge.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import sys
from pathlib import Path

import numpy as np
import pytest

from conftest import needs_kernels

BACKEND = Path(__file__).resolve().parents[1]
REF = BACKEND / "validation" / "reference" / "avgvisib"


def _V():
    sys.path.insert(0, str(BACKEND))
    from validation import v09_v10_avgvisib
    return v09_v10_avgvisib


# ------------------------------------------------------------------ reference labels and provenance
def test_label_facts_and_provenance():
    """The stored labels are the ones recorded in provenance.json and state what the comparison relies on: the "any
    fraction of the disc" time fraction, DN * 0.00004 (25000 = 1), 5058 x 5058 int16, the 60 m polar grid whose
    geotransform equals PGDA's GeoTIFF, the 1737.4 km sphere and the DE421 mean-Earth frame. The two label defects
    are present (and therefore recorded, not relied on)."""
    V = _V()
    prov = json.loads((REF / "provenance.json").read_text())
    assert prov["criteria"]["status"].startswith("provisional")
    for tid, target in (("V-09", "solar"), ("V-10", "Earth")):
        p = prov["products"][tid]
        lbl = REF / p["label"]["file"]
        assert hashlib.sha256(lbl.read_bytes()).hexdigest() == p["label"]["sha256"]
        assert p["img"]["bytes"] == 51166728 and len(p["img"]["sha256"]) == 64
        lab = V.parse_label(lbl.read_text())
        assert lab["PRODUCT_ID"] == p["product_id"]
        assert f"by any fraction of the {target} disc" in lab["DESCRIPTION"]
        assert "LDEM_85S_060M" in lab["DESCRIPTION"] and "percentage of timesteps" in lab["DESCRIPTION"]
        im = lab["UNCOMPRESSED_FILE"]["IMAGE"]
        assert (im["LINES"], im["LINE_SAMPLES"], im["SAMPLE_TYPE"], im["SAMPLE_BITS"]) == (5058, 5058, "LSB_INTEGER", 16)
        assert im["SCALING_FACTOR"] == 0.00004 and im["OFFSET"] == 0.0 and "DN up to 25000, scaling to 1" in im["DESCRIPTION"]
        assert "binary value" in im["DESCRIPTION"]                             # defect 1 (see provenance)
        pr = lab["IMAGE_MAP_PROJECTION"]
        assert pr["MAP_PROJECTION_TYPE"] == "POLAR STEREOGRAPHIC" and pr["A_AXIS_RADIUS"] == (1737.4, "km")
        assert pr["COORDINATE_SYSTEM_NAME"] == "MEAN EARTH/POLAR AXIS OF DE421"
        assert V.projection(lab)[3] == [60.0, 0.0, -151740.0, 0.0, -60.0, 151740.0]   # = PGDA GeoTIFF transform
        if tid == "V-10":
            assert pr["MINIMUM_LATITUDE"] == (90.0, "deg")                    # defect 2 (south-pole product)
    assert {a["parameter"] for a in prov["assumptions"]} == {"observer height", "epoch of the 18.6-year span",
                                                           "Earth occulting the Sun"}
    assert V.CRITERIA["approved"] is False and V.YEARS == 18.6 and V.STEP_S == 3600.0 and V.COVERAGE_LAT_DEG == -85.0


def _write_map(tmp: Path, dn: np.ndarray, scale_m: float, name="AVGVISIB_TEST.IMG", scaling="0.00004") -> Path:
    """A synthetic AVGVISIB IMG plus a label built from the real one (sizes, scale and offsets replaced)."""
    n = dn.shape[0]
    text = (REF / "avgvisib_85s_060m_201608.lbl").read_text()
    off = (n - 1) / 2.0
    for key, val in (("FILE_RECORDS", n), ("RECORD_BYTES", 2 * n), ("LINES", n), ("LINE_SAMPLES", n),
                     ("LINE_LAST_PIXEL", n), ("SAMPLE_LAST_PIXEL", n)):
        text = re.sub(rf"(\b{key}\s*=\s*)\d+", rf"\g<1>{val}", text)
    text = re.sub(r"(MAP_SCALE\s*=\s*)[0-9.]+", rf"\g<1>{scale_m:g}", text)
    text = re.sub(r"((LINE|SAMPLE)_PROJECTION_OFFSET\s*=\s*)[0-9.]+", rf"\g<1>{off}", text)
    text = re.sub(r"(SCALING_FACTOR\s*=\s*)[0-9.]+", rf"\g<1>{scaling}", text)
    img = tmp / name
    dn.astype("<i2").tofile(img)
    img.with_suffix(".lbl").write_text(text)
    return img


def test_encoding_checks(tmp_path):
    V = _V()
    dn = (np.arange(64 * 64).reshape(64, 64) % 25001).astype(np.int16)
    dn[0, 0] = 25000                                                   # the documented maximum (= 1)
    frac, meta = V.read_avgvisib(str(_write_map(tmp_path, dn, 60.0)))
    assert np.array_equal(frac, dn * 0.00004) and meta["dn_max"] == 25000 and meta["geotransform"][0] == 60.0
    bad = dn.copy()
    bad[3, 3] = 25001
    with pytest.raises(ValueError, match="outside"):
        V.read_avgvisib(str(_write_map(tmp_path, bad, 60.0, "BAD.IMG")))
    with pytest.raises(ValueError, match="scaling"):
        V.read_avgvisib(str(_write_map(tmp_path, dn, 60.0, "SCL.IMG", scaling="0.0001")))
    short = _write_map(tmp_path, dn, 60.0, "SHORT.IMG")
    short.write_bytes(short.read_bytes()[:-2])
    with pytest.raises(ValueError, match="bytes"):
        V.read_avgvisib(str(short))


@pytest.mark.parametrize("n,cap,want", [(200, [10**6] * 5, [40] * 5),
                                        (200, [10**6, 10**6, 10**6, 1460, 19], [46, 45, 45, 45, 19]),
                                        (10, [1, 0, 50, 50, 50], [1, 0, 3, 3, 3]),
                                        (200, [3, 4, 5, 6, 7], [3, 4, 5, 6, 7]),
                                        (7, [9] * 5, [2, 2, 1, 1, 1])])
def test_allocation(n, cap, want):
    V = _V()
    assert V.allocate(n, cap) == want


def test_stratified_sampling_inside_coverage_and_deterministic(tmp_path):
    """A 340 km map at 1 km/pixel crosses the 85 deg S circle: every sampled pixel lies wholly inside it, each stratum
    gets its allocation, a sparse stratum's shortfall is redistributed, and the sample is reproducible."""
    V = _V()
    n = 341
    xs = (np.arange(n) - (n - 1) / 2.0) * 1000.0
    X, Y = np.meshgrid(xs, -xs)
    r = np.hypot(X, Y)
    dn = np.clip(r / 170e3 * 20000, 0, 20000).astype(np.int16)        # value rises outward, < 0.8 everywhere ...
    dn[170, 170:173] = 22000                                           # ... except 3 pixels in the top stratum
    frac, meta = V.read_avgvisib(str(_write_map(tmp_path, dn, 1000.0)))
    pts, info = V.stratified_points(frac, meta, 200, seed=4)
    r85 = 2 * 1737400.0 * math.tan(math.radians(5.0) / 2)
    assert len(pts) == 200 and info["strata"][4]["sampled"] == 3
    assert [s["sampled"] for s in info["strata"]] == V.allocate(200, [s["pixels"] for s in info["strata"]])
    for p in pts:
        assert math.hypot(abs(p["x_m"]) + 500, abs(p["y_m"]) + 500) <= r85 and p["lat"] <= -85.0
        lo, hi = info["strata"][p["stratum"]]["range"]
        assert lo <= p["reference"] <= hi and p["reference"] == frac[p["row"], p["col"]]
    assert V.stratified_points(frac, meta, 200, seed=4)[0] == pts
    assert V.stratified_points(frac, meta, 200, seed=5)[0] != pts


# ------------------------------------------------------------------ the vectorised method equals the engine
@needs_kernels
def test_hourly_geometry_matches_the_engine(kernels):
    V = _V()
    from lunaops.engine.ephem import Site, sample_target
    trk = V.track("2026-11-14T00:00:00Z", 4 / 365.25)
    for lat, lon, gh in ((-89.9, 0.0, 0.0), (-85.0, 250.0, -3000.0)):
        site = Site(lat, lon, gh, 0.0)
        for tg in ("sun", "earth"):
            ref = sample_target(site, tg, trk["ets"])
            mine = V.topocentric(site, trk[tg])
            ang = np.degrees(np.arccos(np.clip(np.sum(mine["unit"] * ref.unit, axis=1), -1, 1)))
            assert ang.max() < V.GUARD_DEG / 10, (tg, ang.max())


def _detector_states(site, hp, target, ets):
    from lunaops.engine.events import EventConfig, EventDetector, build_intervals
    det = EventDetector(site, hp, EventConfig())
    e0, e1 = float(ets[0]) - 60.0, float(ets[-1]) + 60.0
    run = det.run(e0, e1)
    ivs = build_intervals(det, e0, e1, run["events"], run["samples"])[f"{target}_any"]
    starts = np.array([iv["start_et"] for iv in ivs])
    return [ivs[np.searchsorted(starts, t, side="right") - 1]["state"] for t in ets], len(ivs)


@needs_kernels
@pytest.mark.parametrize("target", ["sun", "earth"])
def test_vectorised_equals_event_detector(kernels, target):
    """10 days, every 20 minutes, on the synthetic V-14 horizon (frequent crossings): the vectorised verdict equals
    the detector's "any" interval at every epoch."""
    V = _V()
    from lunaops.engine.ephem import Site
    from lunaops.testing import v14_horizon
    site = Site(-88.0, 120.0, 0.0, 0.0)
    trk = V.track("2026-11-14T00:00:00Z", 10 / 365.25, 1200.0)
    hp = v14_horizon(site, trk["ets"][0], 10.2)
    vis, stats = V.visible_any(site, hp, target, trk)
    st, nint = _detector_states(site, hp, target, trk["ets"])
    assert nint > 1 and 0 < vis.sum() < vis.size and None not in st
    assert [bool(s) for s in st] == [bool(v) for v in vis]


@needs_kernels
def test_earth_occultation_of_the_sun_matches_the_detector(kernels):
    """3 March 2026 total lunar eclipse, every 2 minutes, flat -10 deg horizon: only Earth hides the Sun; the hours
    it does are found and equal the detector's."""
    V = _V()
    from lunaops.engine.ephem import Site
    from lunaops.engine.visibility import HorizonProfile
    hp = HorizonProfile(np.full(3600, -10.0), np.zeros(3600, bool))
    site = Site(-87.0, 20.0, 0.0, 0.0)
    trk = V.track("2026-03-03T08:00:00Z", 8 / 24 / 365.25, 120.0)
    vis, stats = V.visible_any(site, hp, "sun", trk)
    st, _ = _detector_states(site, hp, "sun", trk["ets"])
    assert 20 < stats["hidden_by_earth_hours"] == int((~vis).sum()) and stats["exact_hours"] >= stats["hidden_by_earth_hours"]
    assert [bool(s) for s in st] == [bool(v) for v in vis]


@needs_kernels
def test_guard_band_only_routes_to_the_engine(kernels):
    """Sending every hour to the engine (huge guard) gives exactly the same verdicts as the vectorised path."""
    V = _V()
    from lunaops.engine.ephem import Site
    from lunaops.testing import v14_horizon
    site = Site(-89.5, 0.0, 0.0, 0.0)
    trk = V.track("2026-11-20T00:00:00Z", 2 / 365.25)
    hp = v14_horizon(site, trk["ets"][0], 2.2)
    for tg in ("sun", "earth"):
        fast, s1 = V.visible_any(site, hp, tg, trk)
        slow, s2 = V.visible_any(site, hp, tg, trk, guard=90.0)
        assert s2["exact_hours"] == trk["ets"].size and np.array_equal(fast, slow)


class _FakeHorizon:
    def __init__(self, h, incomplete=()):
        self.h_deg = np.full(3600, h, dtype=float)
        self.incomplete = np.zeros(3600, bool)
        self.incomplete[list(incomplete)] = True
        self.ground_h_m = 0.0
        self.sigma_deg = None
        self.params = {"h_max_m": 0.0}


@needs_kernels
def test_incomplete_or_missing_terrain_is_inconclusive(kernels):
    V = _V()
    from lunaops.engine.dem import TerrainError
    trk = V.track("2026-11-14T00:00:00Z", 1 / 365.25)
    r = V.evaluate_point(-88.0, 10.0, "sun", trk, horizon_fn=lambda *a: _FakeHorizon(-5.0, [7]))
    assert r["outcome"] == "inconclusive" and "incomplete" in r["reason"] and "computed" not in r

    def none(*_a):
        raise TerrainError("no registered terrain")
    r = V.evaluate_point(-88.0, 10.0, "earth", trk, horizon_fn=none)
    assert r["outcome"] == "inconclusive" and "no terrain horizon" in r["reason"]
    ok = V.evaluate_point(-88.0, 10.0, "sun", trk, horizon_fn=lambda *a: _FakeHorizon(-30.0))
    assert ok["outcome"] == "scored" and ok["computed"] == 1.0


# ------------------------------------------------------------------ scoring
def _pts(diffs, inconclusive=0):
    out = [{"stratum": i % 5, "outcome": "scored", "reference": 0.5, "computed": 0.5 + d / 100.0}
           for i, d in enumerate(diffs)]
    return out + [{"stratum": 0, "outcome": "inconclusive", "reference": 0.5}] * inconclusive


def test_provisional_criteria_never_pass():
    """Metrics are reported, but with the criteria unapproved the status is "not run" (never a pass); with approved
    criteria the same metrics would pass, fail or be inconclusive; a partial span is never decided."""
    V = _V()
    good = _pts([1.0, -1.0, 0.5, -0.5] * 50)
    st, m, detail = V.score(good, 18.6)
    assert st == "not run" and "provisional" in detail and m["within_provisional_criteria"] is True
    assert m["rmse_pp"] == pytest.approx(math.sqrt(0.625)) and m["bias_pp"] == pytest.approx(0.0)
    approved = {**V.CRITERIA, "approved": True}
    met = (True, "")
    assert V.score(good, 18.6, approved, met)[0] == "passed"
    assert V.score(_pts([6.0] * 200), 18.6, approved, met)[0] == "failed"            # RMSE 6 > 5
    assert V.score(_pts([3.5, 1.0] * 100), 18.6, approved, met)[0] == "failed"       # RMSE 2.6 <= 5, |bias| 2.25 > 2
    assert V.score(_pts([2.5, 1.0] * 100), 18.6, approved, met)[0] == "passed"       # bias 1.75, RMSE 1.9
    assert V.score(_pts([1.0] * 199, inconclusive=1), 18.6, approved, met)[0] == "inconclusive"
    assert V.score(good, 1.0, approved, met)[0] == "not run" and "PARTIAL" in V.score(good, 1.0, approved, met)[2]
    assert V.score([], 18.6, approved, met)[0] == "not run"


def test_approved_criteria_never_decide_without_the_terrain_gate():
    """Phase 4 A6: even with approved criteria, a run whose terrain does not meet the shared terrain acceptance gate
    is "not run" (preliminary), whatever its metrics; the default is "not checked", never met."""
    V = _V()
    approved = {**V.CRITERIA, "approved": True}
    good, bad = _pts([1.0, -1.0, 0.5, -0.5] * 50), _pts([6.0] * 200)
    for pts in (good, bad):
        st, m, detail = V.score(pts, 18.6, approved, (False, "A6 acceptance missing for 80m / 240m"))
        assert st == "not run" and "PRELIMINARY" in detail and "80m / 240m" in detail and m["rmse_pp"] is not None
    assert V.score(good, 18.6, approved)[0] == "not run" and "not checked" in V.score(good, 18.6, approved)[2]


# ------------------------------------------------------------------ end to end
@needs_kernels
def test_end_to_end_and_merge(kernels, monkeypatch, tmp_path):
    """Synthetic Sun and Earth maps (value 1 everywhere) with a horizon far below: every scored point computes 1.0
    over a short span, the run reports metrics with status "not run" (provisional criteria, partial span), and the
    result merges through the guard."""
    V = _V()
    from validation.common import merge_external, run_meta
    n = 341
    dn = np.full((n, n), 25000, np.int16)
    sun = _write_map(tmp_path, dn, 1000.0, "SUN.IMG")
    earth = _write_map(tmp_path, dn, 1000.0, "EARTH.IMG")
    real = V.evaluate_point
    monkeypatch.setattr(V, "evaluate_point", lambda lat, lon, target, trk, obs=0.0, horizon_fn=None:
                        real(lat, lon, target, trk, obs, horizon_fn=lambda *a: _FakeHorizon(-30.0)))
    out = tmp_path / "v.json"
    monkeypatch.setattr(sys, "argv", ["v09_v10", "--sun-img", str(sun), "--earth-img", str(earth), "--points", "10",
                                      "--years", "0.01", "--out", str(out)])
    V.main()
    res = json.loads(out.read_text())
    for tid in ("V-09", "V-10"):
        assert res["tests"][tid]["status"] == "not run" and "provisional" in res["tests"][tid]["detail"]
        r = res["results"][tid]
        assert r["metrics"]["scored"] == 10 and all(p["computed"] == 1.0 and p["lat"] <= -85 for p in r["points"])
        assert r["metrics"]["rmse_pp"] == 0.0 and r["reference"]["scaling_factor"] == 0.00004
    assert res["meta"]["script"] == "v09_v10_avgvisib" and res["assumptions"]["observer_height_m"] == 0.0
    gate = res["meta"]["terrain_gate"]
    assert gate["ok"] is False and gate["acceptance_digest"] == res["meta"]["terrain_acceptance_digest"]
    tests = {"V-09": {"status": "not run"}, "V-10": {"status": "not run"}}
    assert merge_external(tests, res, run_meta("run_validation")) == []
    assert tests["V-09"]["status"] == tests["V-10"]["status"] == "not run"
