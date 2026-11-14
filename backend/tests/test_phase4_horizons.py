"""Phase 4 A8/A9: the V-04 / V-05 Horizons comparison (validation/horizons_compare.py), offline.

The live comparison needs ssd.jpl.nasa.gov; these tests run without it:
  * parsing and header checks on a verbatim Horizons response (tests/reference/horizons_probe_sun_south_polar_a.json,
    fetched 2026-11-09: Sun from 89.5 S 0 E, 2026-11-14 00:00-03:00 TT, hourly);
  * the V-05 crossing, matching and verdict logic;
  * an end-to-end run of the script against a simulated Horizons built from the engine itself, which shows that
    V-05 is its own measurement: an elevation bias V-04 accepts makes V-05 fail;
  * merging V-04 and V-05 into the validation report as separate results.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pytest

from conftest import needs_kernels

BACKEND = Path(__file__).resolve().parents[1]
PROBE = json.loads((Path(__file__).resolve().parent / "reference" / "horizons_probe_sun_south_polar_a.json").read_text())


def _H():
    sys.path.insert(0, str(BACKEND))
    from validation import horizons_compare
    return horizons_compare


def test_parse_probe_rows_and_header():
    H = _H()
    text = PROBE["result"]
    rows = H.parse_rows(text)
    assert [r[0] for r in rows] == ["2026-Nov-14 00:00", "2026-Nov-14 01:00", "2026-Nov-14 02:00", "2026-Nov-14 03:00"]
    assert rows[0][1:] == (126.637091612, 1.258266061)
    f = H.header_facts(text)
    assert f["center_radii"] == "1737.4, 1737.4, 1737.4 km" and f["center_pole_equ"] == "MEAN_ME (high precision)"
    assert f["refraction"] == "NO (AIRLESS)" and f["time_type"] == "TT" and f["ephemeris_source"] == "DE441"
    with pytest.raises(RuntimeError):
        H.parse_rows("no table here")


@needs_kernels
def test_probe_agrees_with_engine_within_v04(kernels):
    """The four probe epochs against the engine (any kernel set): within the V-04 tolerance; with the production
    set the agreement is at the 1e-9 deg print precision of the table."""
    H = _H()
    from lunaops.engine.ephem import Site, sample_target

    rows = H.parse_rows(PROBE["result"])
    s = sample_target(Site(-89.5, 0.0, 0.0, 0.0), "sun", [H.tt_tag_to_et(r[0]) for r in rows])
    for (_, haz, hel), az, el in zip(rows, s.az, s.el):
        daz = abs((az - haz + 180) % 360 - 180) * math.cos(math.radians(el))
        assert daz <= H.V04_TOL_DEG and abs(el - hel) <= H.V04_TOL_DEG
        if kernels.profile == "production":
            assert daz < 1e-7 and abs(el - hel) < 1e-7


@needs_kernels
def test_time_conversions_round_trip(kernels):
    H = _H()
    et = H.tt_tag_to_et("2026-Nov-14 00:00")
    assert H.et_to_tt_tag(et) == "JD 2461358.500000000"           # 2026-11-14 00:00 TT
    for dt in (0.0, 1234.567, -86399.123):
        assert abs(H.tt_tag_to_et(H.et_to_tt_tag(et + dt)) - (et + dt)) < 1e-4
    assert H.tt_tag_to_et("2026-Nov-14 00:00:00.000") == et


def test_crossing_detection_and_interpolation():
    H = _H()
    # pairs touching a NaN sample are skipped (no crossing invented across the gap); the others are found
    assert H.sign_crossings([0, 1, 2, 3, 4], [1.0, -1.0, math.nan, -0.5, 0.2]) == [(0, 1, -1), (3, 4, +1)]
    assert H.sign_crossings([0, 1, 2], [-1.0, math.nan, 1.0]) == []
    assert H.sign_crossings([0, 1, 2], [-0.5, 0.25, 0.5]) == [(0, 1, +1)]
    assert H.interpolate_crossing(10.0, 11.0, -0.25, 0.75) == 10.25


def _ev(body, d, et):
    return {"body": body, "direction": d, "et": et}


def test_v05_verdict_is_its_own():
    H = _H()
    ref = [_ev("sun", +1, 1000.0), _ev("earth", -1, 5000.0)]
    ok = [_ev("sun", +1, 1000.4), _ev("earth", -1, 4999.6)]
    p, m, s = H.match_events(ref, ok)
    assert len(p) == 2 and not m and not s and H.v05_status(p, m, s)[0] == "passed"
    p, m, s = H.match_events(ref, [_ev("sun", +1, 1001.2), _ev("earth", -1, 5000.0)])
    assert H.v05_status(p, m, s)[0] == "failed"                       # 1.2 s > 1.0 s
    p, m, s = H.match_events(ref, [_ev("sun", +1, 1000.0)])
    assert len(m) == 1 and H.v05_status(p, m, s)[0] == "failed"       # missed Earth set
    p, m, s = H.match_events(ref, ok + [_ev("sun", -1, 9000.0)])
    assert len(s) == 1 and H.v05_status(p, m, s)[0] == "failed"       # spurious Sun set
    p, m, s = H.match_events(ref, [_ev("sun", -1, 1000.0), _ev("earth", -1, 5000.0)])
    assert len(m) == 1 and len(s) == 1                                # direction must match
    p, m, s = H.match_events(ref, [_ev("sun", +1, 1700.0), _ev("earth", -1, 5000.0)])
    assert len(m) == 1 and len(s) == 1                                # outside the 600 s matching window
    assert H.v05_status([], [], [])[0] == "not run"                   # nothing to compare is never a pass


def _fake_horizons(H, bias_el_deg: float):
    """A stand-in for Horizons.table: the engine's own Sun/Earth az/el (plus a constant elevation bias) in the
    Horizons CSV layout, for the requested start/stop/step."""
    import spiceypy as sp
    from lunaops.engine.ephem import Site, sample_target

    def table(self, tag, target, lat, lon, start, stop, step, seconds=False):
        t0, t1 = H.tt_tag_to_et(start), H.tt_tag_to_et(stop)
        n = int(round((t1 - t0) / 3600.0)) if step == "1h" else int(step)
        tags = [sp.timout(t0 + (t1 - t0) * k / n, "YYYY-Mon-DD HR:MN:SC.### ::TDT ::RND") for k in range(n + 1)]
        ets = [H.tt_tag_to_et(t) for t in tags]
        s = sample_target(Site(lat, lon, 0.0, 0.0), "sun" if target == "10" else "earth", ets)
        body = "\n".join(f" {t},*, ,{az:.9f},{el + bias_el_deg:.9f}," for t, az, el in zip(tags, s.az, s.el))
        text = ("Target body name: x {source: DE441}\nCenter body name: Moon (301) {source: DE441}\n"
                f"Start time : A.D. {tags[0]} TT\nCenter pole/equ : MEAN_ME (high precision)\n"
                "Center radii : 1737.4, 1737.4, 1737.4 km {Equator_a, b, pole_c}\n"
                f"Atmos refraction: NO (AIRLESS)\n$$SOE\n{body}\n$$EOE\n")
        self.files.append({"file": tag, "sha256": "simulated", "bytes": len(text), "query": {}})
        return text, H.parse_rows(text)
    return table


@needs_kernels
@pytest.mark.parametrize("bias,v04,v05", [(0.0, "passed", "passed"), (0.005, "passed", "failed")])
def test_end_to_end_v05_independent_of_v04(kernels, monkeypatch, tmp_path, bias, v04, v05):
    """South-polar B, Sun, 2026-11-16 (a Sun set near 10:02 UTC). With the simulated Horizons equal to the engine,
    both tests pass and the crossing matches within the detector's 0.5 s resolution. With a 0.005 deg elevation
    bias, V-04 still passes (tolerance 0.01 deg) but the Sun, rising or setting at about 1e-5 deg/s there, crosses
    the horizon minutes later, so V-05 fails."""
    H = _H()
    monkeypatch.setattr(H, "SITES", [("south-polar B", -86.0, 210.0)])
    monkeypatch.setattr(H, "TARGETS", (("10", "sun"),))
    monkeypatch.setattr(H.Horizons, "table", _fake_horizons(H, bias))
    out = tmp_path / "h.json"
    monkeypatch.setattr(sys, "argv", ["horizons_compare", "--start", "2026-11-16 00:00", "--days", "1",
                                      "--out", str(out)])
    H.main()
    res = json.loads(out.read_text())
    assert res["tests"]["V-04"]["status"] == v04 and res["tests"]["V-05"]["status"] == v05, res["tests"]
    assert res["meta"]["script"] == "horizons_compare"
    assert (tmp_path / "h_v04_residuals.csv").exists()
    if v05 == "passed":
        ev = res["v05"]["events"]
        assert len(ev) == 1 and ev[0]["direction"] == -1 and abs(ev[0]["dt_s"]) <= 0.5 + 1e-6


@needs_kernels
def test_report_merges_v04_and_v05_separately(kernels):
    """A Horizons result with V-04 passed and V-05 failed merges as two separate entries; V-05 keeps its own
    status and detail."""
    sys.path.insert(0, str(BACKEND))
    from validation.common import merge_external, run_meta

    now = run_meta("run_validation")
    ext = {"meta": run_meta("horizons_compare"),
           "tests": {"V-04": {"status": "passed", "detail": "a"}, "V-05": {"status": "failed", "detail": "b"}}}
    tests = {"V-04": {"status": "not run"}, "V-05": {"status": "not run"}}
    assert merge_external(tests, ext, now) == []
    assert tests["V-04"]["status"] == "passed" and tests["V-05"]["status"] == "failed"
    assert tests["V-05"]["detail"] == "b" and tests["V-05"]["script"] == "horizons_compare"
