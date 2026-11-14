"""V-14 event detection and U-0x interface tests (blueprint Sections 10.1-10.2)."""
from __future__ import annotations

import math
import time

import numpy as np
import pytest

from conftest import needs_kernels


def _brute(site, hp, et0, et1, step, fn="g_top", target="sun"):
    from lunaops.engine.ephem import sample_target
    from lunaops.engine.visibility import disk_state

    ets = np.arange(et0, et1, step)
    s = sample_target(site, target, ets)
    v = np.array([disk_state(hp, s.az[i], s.el[i], s.rho[i])[fn] for i in range(ets.size)])
    on = v > 0
    wins, start = [], None
    for i, flag in enumerate(on):
        if flag and start is None:
            start = ets[i]
        if not flag and start is not None:
            wins.append((start, ets[i]))
            start = None
    if start is not None:
        wins.append((start, ets[-1]))
    return wins


def _detector_windows(run, fn, et0, et1, initially_on):
    evs = [e for e in run["events"] if e["function"] == fn]
    t, on, wins = et0, initially_on, []
    for e in evs:
        if e["direction"] == +1:
            t = e["et"]
            on = True
        else:
            if on:
                wins.append((t, e["et"]))
            on = False
    if on:
        wins.append((t, et1))
    return wins


@needs_kernels
def test_V14_narrow_notch_and_grazing_windows(kernels):
    """Adaptive detection vs brute-force 1 s sampling on horizons with one-bin notches and a grazing case."""
    from lunaops.engine.ephem import Site, sample_target
    from lunaops.engine.events import EventConfig, EventDetector
    from lunaops.engine.timeutil import parse_utc
    from lunaops.engine.visibility import HorizonProfile

    site = Site(-89.5, 0.0, 0.0, 0.0)
    et0 = parse_utc("2026-11-14T00:00:00Z")
    et1 = et0 + 12 * 3600.0
    s = sample_target(site, "sun", np.arange(et0, et1, 600.0))
    top = float(np.median(s.el + s.rho))
    H = np.full(3600, top + 0.4)                     # Sun hidden except in notches
    az_path = s.az % 360
    # one-bin notches along the Sun's path, with depths giving short and long windows
    for k, depth in zip(range(5), (0.402, 0.405, 0.42, 0.6, 1.0)):
        i = int(round(az_path[10 + 12 * k] / 0.1)) % 3600
        H[i] = top + 0.4 - depth
    hp = HorizonProfile(H, np.zeros(3600, bool))
    det = EventDetector(site, hp, EventConfig())
    t = time.time()
    run = det.run(et0, et1)
    elapsed = time.time() - t
    ref = _brute(site, hp, et0, et1, 1.0)
    got = _detector_windows(run, "sun_top", et0, et1, initially_on=False)
    long_ref = [w for w in ref if w[1] - w[0] >= 2.0]
    assert long_ref, "test construction should yield windows"
    for a, b in long_ref:
        match = [g for g in got if abs(g[0] - a) <= 2.0 and abs(g[1] - b) <= 2.0]
        assert match, f"missed window {b - a:.1f} s at {a:.0f}"
    print(f"V-14: {len(long_ref)} reference windows >= 2 s, {len(got)} detected, {det.log.samples} samples, "
          f"{len(det.log.estimate_failures)} estimate failures, {elapsed:.1f} s")


@needs_kernels
def test_V14_zero_rate_step_is_finite(kernels):
    from lunaops.engine.events import EventDetector

    assert math.isfinite(EventDetector._tau(0.01, 0.0, 1e-9))           # R0 = 0, A > 0 -> sqrt(2|g|/A)
    assert abs(EventDetector._tau(0.01, 0.0, 1e-9) - math.sqrt(2 * 0.01 / 1e-9)) < 1e-6
    assert EventDetector._tau(0.01, 0.0, 0.0) == math.inf              # capped by the 10-minute rule
    assert EventDetector._tau(0.0, 1.0, 1.0) == 0.0


@needs_kernels
def test_V14_step_halving_independence(kernels):
    from lunaops.engine.ephem import Site
    from lunaops.engine.events import EventConfig, EventDetector
    from lunaops.engine.timeutil import parse_utc
    from lunaops.engine.visibility import HorizonProfile

    H = np.full(3600, 1.6)
    H[1000:1400] = 1.0
    H[2000] = 0.9
    hp = HorizonProfile(H, np.zeros(3600, bool))
    site = Site(-89.5, 0.0, 0.0, 0.0)
    et0 = parse_utc("2026-11-14T00:00:00Z")
    a = EventDetector(site, hp, EventConfig()).run(et0, et0 + 3 * 86400)
    b = EventDetector(site, hp, EventConfig(cap_s=300.0)).run(et0, et0 + 3 * 86400)
    ea = [(e["function"], e["direction"], e["et"]) for e in a["events"]]
    eb = [(e["function"], e["direction"], e["et"]) for e in b["events"]]
    assert len(ea) == len(eb)
    for x, y in zip(ea, eb):
        assert x[:2] == y[:2] and abs(x[2] - y[2]) <= 1.0


# ----------------------------------------------------------------- U-01
def test_U01_coordinate_validation():
    from lunaops.engine.frames import CoordinateError, validate_latlon

    assert validate_latlon(-90, 0) == (-90.0, 0.0)
    assert validate_latlon(-85, -10) == (-85.0, 350.0)
    assert validate_latlon(-85, 360) == (-85.0, 0.0)
    for bad in [(-91, 0), (95, 0), ("x", 0), (float("nan"), 0), (0, 400)]:
        with pytest.raises(CoordinateError):
            validate_latlon(*bad)


@needs_kernels
def test_U01_coverage_refusal(kernels, synthetic_crater):
    from lunaops.engine.dem import coverage_check

    assert coverage_check(-89.9, 10)["covered"]
    out = coverage_check(-30.0, 10)
    assert not out["covered"] and out["reason"]


# ----------------------------------------------------------------- U-02
@needs_kernels
def test_U02_time_validation(kernels):
    from lunaops.engine.timeutil import TimeInputError, check_window, parse_utc

    with pytest.raises(TimeInputError):
        parse_utc("14/11/2026")
    with pytest.raises(TimeInputError):
        parse_utc("2026-13-01T00:00:00Z")
    a, b = parse_utc("2026-11-14T00:00:00Z"), parse_utc("2026-11-15T00:00:00Z")
    with pytest.raises(TimeInputError):
        check_window(b, a, 60, 400)
    with pytest.raises(TimeInputError):
        check_window(a, b, 0.5, 400)
    with pytest.raises(TimeInputError):
        check_window(parse_utc("2200-01-01T00:00:00Z"), parse_utc("2200-01-02T00:00:00Z"), 60, 400)


# ------------------------------------------------------- U-03, U-05, U-07
@pytest.fixture(scope="module")
def client(synthetic_crater):
    from fastapi.testclient import TestClient
    from lunaops.api.main import app
    return TestClient(app)


def _wait(client, jid):
    for _ in range(600):
        j = client.get(f"/api/jobs/{jid}").json()
        if j["status"] in ("done", "error"):
            return j
        time.sleep(0.2)
    raise AssertionError("job timeout")


@needs_kernels
def test_U03_compare_4x3_equals_single_site(client):
    """U-03 (Section 10.2): 4 sites x 3 windows; every comparison value equals the single-site API value."""
    sites = [{"lat": -89.9, "lon": 10.0, "name": "A"}, {"lat": -89.7, "lon": 200.0, "name": "B"},
             {"lat": -89.8, "lon": 300.0, "name": "C"}, {"lat": -89.6, "lon": 90.0, "name": "D"}]
    windows = [{"start_utc": "2026-11-14T00:00:00Z", "end_utc": "2026-11-14T12:00:00Z"},
               {"start_utc": "2026-12-13T12:00:00Z", "end_utc": "2026-12-14T00:00:00Z"},
               {"start_utc": "2027-01-12T00:00:00Z", "end_utc": "2027-01-12T12:00:00Z"}]
    body = {"sites": sites, "windows": windows, "step_s": 3600}
    j = _wait(client, client.post("/api/compare", json=body).json()["job_id"])
    assert j["status"] == "done", j
    cmp_ = client.get(f"/api/compare/{j['result_id']}").json()
    assert len(cmp_["cells"]) == 12
    for cell in cmp_["cells"]:
        assert cell["error"] is None, cell["error"]
        single = client.post("/api/analysis", json={"lat": cell["site"]["lat"], "lon": cell["site"]["lon"],
                                                    "site_name": cell["site"]["name"],
                                                    "start_utc": cell["window"]["start_utc"],
                                                    "end_utc": cell["window"]["end_utc"], "step_s": 3600}).json()
        rid = single["result_id"] or _wait(client, single["job_id"])["result_id"]
        assert rid == cell["result_id"]
        res = client.get(f"/api/results/{rid}").json()
        assert res["summary"] == cell["summary"]
        assert res["labels"] == cell["labels"]


@needs_kernels
def test_U05_reproducible_bytes(client):
    from lunaops.engine import cache
    from lunaops.engine.analysis import AnalysisRequest, analyze

    req = AnalysisRequest(lat=-89.8, lon=45.0, start_utc="2026-11-14T00:00:00Z", end_utc="2026-11-14T12:00:00Z",
                          step_s=1800)
    a = analyze(req)
    cache.clear()
    b = analyze(req)
    assert a["sha256"] == b["sha256"]
    p = a["provenance"]
    for key in ("code_version", "algorithm_version", "kernels", "terrain", "parameters", "horizon"):
        assert p.get(key) is not None
    assert all(f.get("sha256") for f in p["kernels"]["files"])


@needs_kernels
def test_U07_export_matches_result(client):
    r = client.post("/api/analysis", json={"lat": -89.8, "lon": 45.0, "start_utc": "2026-11-14T00:00:00Z",
                                           "end_utc": "2026-11-14T12:00:00Z", "step_s": 1800}).json()
    rid = r["result_id"] or _wait(client, r["job_id"])["result_id"]
    res = client.get(f"/api/results/{rid}").json()
    csv_text = client.get(f"/api/results/{rid}/series.csv").text
    rows = [ln.split(",") for ln in csv_text.splitlines() if ln and not ln.startswith("#")][1:]
    for i, row in enumerate(rows):
        assert float(row[1]) == res["series"]["sun"]["az"][i]
        assert float(row[2]) == res["series"]["sun"]["el"][i]


# ------------------------------------------------------------- V-14 (expanded)
def _windows(ets, v):
    on = v > 0
    out, start = [], None
    for i, flag in enumerate(on):
        if flag and start is None:
            start = ets[i]
        if not flag and start is not None:
            out.append((start, ets[i]))
            start = None
    return out


@needs_kernels
def test_V14_synthetic_window_durations(kernels):
    """Windows of about 0.5, 1.5, 5 and 60 s built with one-node notches; all of 1.5 s and longer must be found."""
    from lunaops.engine.ephem import Site, sample_target
    from lunaops.engine.events import EventConfig, EventDetector
    from lunaops.engine.timeutil import parse_utc
    from lunaops.engine.visibility import HorizonProfile, disk_edges_many

    site = Site(-89.5, 0.0, 0.0, 0.0)
    et0 = parse_utc("2026-11-14T00:00:00Z")
    ets = np.arange(et0, et0 + 7200.0, 0.05)
    s = sample_target(site, "sun", ets)
    node = int(round(float(s.az[ets.size // 2]) / 0.1)) % 3600
    top = float(np.median(s.el + s.rho))
    near = np.abs(((s.az - node * 0.1) + 180) % 360 - 180) < 0.8

    def horizon(depth):
        h = np.full(3600, top + 0.5)
        h[node] = top + 0.5 - depth
        return HorizonProfile(h, np.zeros(3600, bool))

    def longest(depth):
        g = np.full(ets.size, -1.0)
        g[near] = disk_edges_many(horizon(depth), s.az[near], s.el[near], s.rho[near])["g_top"]
        w = _windows(ets, g)
        return max(w, key=lambda x: x[1] - x[0]) if w else None

    results = []
    for target in (0.5, 1.5, 5.0, 60.0):
        lo, hi = 0.3, 1.5
        for _ in range(40):
            mid = 0.5 * (lo + hi)
            w = longest(mid)
            d = (w[1] - w[0]) if w else 0.0
            if abs(d - target) <= 0.1 * target + 0.05:
                break
            lo, hi = (mid, hi) if d < target else (lo, mid)
        assert w is not None and abs((w[1] - w[0]) - target) <= 0.1 * target + 0.05, (target, w)
        run = EventDetector(site, horizon(mid), EventConfig()).run(et0, et0 + 7200.0)
        evs = sorted(e["et"] for e in run["events"] if e["function"] == "sun_top")
        d0 = min((abs(x - w[0]) for x in evs), default=1e9)
        d1 = min((abs(x - w[1]) for x in evs), default=1e9)
        found = d0 <= 1.1 and d1 <= 1.1
        results.append((target, round(w[1] - w[0], 2), found, round(max(d0, d1), 3)))
        if target >= 1.5:
            assert found, f"missed the {w[1] - w[0]:.2f} s window (offsets {d0:.2f}, {d1:.2f} s)"
    print("V-14 synthetic windows (target s, actual s, found, worst offset s):", results)


def _v14_horizon(site, et0):
    from lunaops.engine.ephem import sample_target
    from lunaops.engine.visibility import HorizonProfile

    s = sample_target(site, "sun", np.arange(et0, et0 + 2 * 86400, 3600.0))
    top = float(np.median(s.el + s.rho))
    rng = np.random.default_rng(int(abs(site.lat * 1000 + site.lon)))
    h = top + 0.3 + 0.5 * np.sin(np.radians(np.arange(3600) * 0.1 * 5))
    for i in rng.choice(3600, 40, replace=False):
        h[i] -= rng.uniform(0.25, 1.2)
    return HorizonProfile(h, np.zeros(3600, bool))


@needs_kernels
def test_V14_three_sites_brute_force(kernels):
    """Three sites, Sun and Earth, centre/top/bottom clearances vs 1 s brute force over 1 day.

    Direction-aware: every edge of every reference window >= 2 s (including windows open at either
    end of the day) needs a detector event of the same function and direction within 1 s; every
    detector event without a reference crossing must be confirmed by dense evaluation (no false events).
    """
    from lunaops.engine.ephem import Site, sample_target
    from lunaops.engine.events import EventConfig, EventDetector
    from lunaops.engine.timeutil import parse_utc
    from lunaops.engine.visibility import disk_edges_many
    from lunaops.testing import (CrossingAccumulator, confirm_event, match_events, required_crossings,
                                 target_edges, v14_horizon)

    et0 = parse_utc("2026-11-14T00:00:00Z")
    et1 = et0 + 86400.0
    summary = []
    worst = 0.0
    for lat, lon in ((-89.5, 0.0), (-88.0, 120.0), (-86.5, 250.0)):
        site = Site(lat, lon, 0.0, 0.0)
        hp = v14_horizon(site, et0, 1.0)
        det = EventDetector(site, hp, EventConfig())
        run = det.run(et0, et1)
        ets = np.arange(et0, et1, 1.0)
        n_req = n_confirmed = 0
        for target in ("sun", "earth"):
            edges = target_edges(site, hp, target, ets)          # Earth: exact oblate limb (Phase 3)
            for key, fn in (("c", f"{target}_c"), ("g_top", f"{target}_top"), ("g_bot", f"{target}_bot")):
                acc = CrossingAccumulator()
                acc.add(ets, edges[key])
                req = required_crossings(acc.crossings, acc.first_on, acc.t0, acc.t1, 2.0)
                evs = [e for e in run["events"] if e["function"] == fn]
                offsets, missed, unmatched = match_events(req, acc.crossings, [e["et"] for e in evs],
                                                          [e["direction"] for e in evs], 3.0)
                assert not missed, f"{fn}: missed window edges {missed[:3]} at {lat}, {lon}"
                assert all(o <= 1.0 for o in offsets), f"{fn}: worst offset {max(offsets):.3f} s (limit 1 s)"

                def values(t, target=target, key=key):
                    t = np.atleast_1d(np.asarray(t, dtype=float))
                    return target_edges(site, hp, target, t, coarse_s=0.0)[key]

                bad = [u for u in unmatched if not confirm_event(values, u[0], u[1])]
                assert not bad, f"{fn}: detector events with no real crossing {bad[:3]}"
                n_req += len(req)
                n_confirmed += len(unmatched)
                worst = max([worst] + offsets)
        summary.append({"site": (lat, lon), "required_edges": n_req, "confirmed_subsecond_events": n_confirmed,
                        "samples": det.log.samples, "estimate_failures": len(det.log.estimate_failures)})
        assert n_req >= 10, f"V-14 horizon produced only {n_req} required window edges at {lat}, {lon}"
    print("V-14 three-site brute force (1 day each):", summary, f"worst event offset {worst:.3f} s")


@needs_kernels
def test_V14_curvature_estimates_vs_minute_grid(kernels):
    """The inflated hourly curvature estimates must cover second derivatives seen on a 1-minute grid."""
    from lunaops.engine.ephem import Site, sample_target, separation_deg
    from lunaops.engine.events import EventConfig, EventDetector
    from lunaops.engine.timeutil import parse_utc
    from lunaops.engine.visibility import HorizonProfile

    et0 = parse_utc("2026-11-14T00:00:00Z")
    et1 = et0 + 2 * 86400.0
    for lat, lon in ((-89.5, 0.0), (-86.5, 250.0)):
        site = Site(lat, lon, 0.0, 0.0)
        det = EventDetector(site, HorizonProfile(np.full(3600, 0.5), np.zeros(3600, bool)), EventConfig())
        det.run(et0, et1)
        cv = det.log.curvature
        ets = np.arange(et0, et1, 60.0)
        s, e = sample_target(site, "sun", ets), sample_target(site, "earth", ets)
        g, _ = separation_deg(s, e)
        d2 = lambda v: float(np.max(np.abs(np.diff(v, 2)))) / 3600.0
        for name, t in (("sun", s), ("earth", e)):
            assert cv[name]["el"] >= d2(t.el), (name, "el")
            assert cv[name]["az"] >= d2(np.degrees(np.unwrap(np.radians(t.az)))), (name, "az")
            assert cv[name]["rho"] >= d2(t.rho), (name, "rho")
        assert cv["ecl"]["gamma"] >= d2(g)


@needs_kernels
def test_V14_eclipse_boundaries(kernels):
    """Eclipse events (contact, Sun centre behind Earth, totality, combined visibility) vs 1 s brute force.

    The eclipse is located by scanning the ephemeris itself (no catalogue dates are assumed);
    the catalogue comparison is V-13 (validation/v13_eclipse.py).
    """
    from lunaops.engine.ephem import Site, sample_target, separation_deg
    from lunaops.engine.events import EventConfig, EventDetector, full_state
    from lunaops.engine.timeutil import parse_utc, to_utc
    from lunaops.engine.visibility import HorizonProfile

    site = Site(0.0, 0.0, 0.0, 0.0)
    scan = np.arange(parse_utc("2026-01-01T00:00:00Z"), parse_utc("2027-12-31T00:00:00Z"), 3600.0)
    s, e = sample_target(site, "sun", scan), sample_target(site, "earth", scan)
    g, _ = separation_deg(s, e)
    contact = g - (s.rho + e.rho)
    assert (contact < 0).any(), "no Earth occultation of the Sun found at the sub-Earth point in 2026-2027"
    tmin = float(scan[int(np.argmin(contact))])
    t0, t1 = tmin - 4 * 3600.0, tmin + 4 * 3600.0
    hp = HorizonProfile(np.full(3600, -30.0), np.zeros(3600, bool))
    det = EventDetector(site, hp, EventConfig())
    run = det.run(t0, t1)
    ets = np.arange(t0, t1, 1.0)
    s, e = sample_target(site, "sun", ets), sample_target(site, "earth", ets)
    g, _ = separation_deg(s, e)
    # Earth's occulting radius (Phase 3): the limb ellipse's radius toward the Sun's centre, per sample
    from lunaops.engine.ephem import earth_geo
    from lunaops.engine.visibility import earth_limb_enu, earth_radius_toward_sun
    re = np.array([earth_radius_toward_sun({"az": s.az[i], "el": s.el[i]},
                                           {"az": e.az[i], "el": e.el[i], "rho": e.rho[i],
                                            "limb": earth_limb_enu(earth_geo(e, i))}) for i in range(ets.size)])
    refs = {"ecl_contact": g - (s.rho + re), "ecl_centre": g - re, "ecl_total": g - (re - s.rho)}
    found = {}
    for fn, v in refs.items():
        ref_t = [0.5 * (ets[i] + ets[i + 1]) for i in range(ets.size - 1) if (v[i] > 0) != (v[i + 1] > 0)]
        evs = [x["et"] for x in run["events"] if x["function"] == fn]
        assert len(evs) == len(ref_t), (fn, len(evs), len(ref_t))
        for a, b in zip(sorted(evs), ref_t):
            assert abs(a - b) <= 1.5, (fn, a - b)
        found[fn] = [to_utc(x, 0) for x in evs]
    # combined visibility: with terrain far below, the Sun is hidden exactly during totality
    vis = sorted(x["et"] for x in run["events"] if x["function"] == "sun_vis")
    tot = sorted(x["et"] for x in run["events"] if x["function"] == "ecl_total")
    assert len(vis) == len(tot) and all(abs(a - b) <= 1.5 for a, b in zip(vis, tot))
    # the centre rule changes state exactly at the Sun-centre events
    cen = sorted(x["et"] for x in run["events"] if x["function"] == "ecl_centre")
    if len(cen) >= 2:
        mid = 0.5 * (cen[0] + cen[1])
        assert full_state(det, mid)["rules"]["sun_centre"] is False
        assert full_state(det, cen[0] - 30.0)["rules"]["sun_centre"] is True
    print("V-14 eclipse boundaries:", found, "estimate failures", len(det.log.estimate_failures))
