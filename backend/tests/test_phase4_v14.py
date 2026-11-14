"""Phase 4 A14: the full synodic-month V-14 (validation/v14_month.py).

The month-long run itself is evidence (docs/validation_evidence/v14_month_a14_*); it is far too slow for the suite.
These tests pin its approved parameters, check the status rule (a partial run is never a pass, any failure fails),
and prove on short real runs (production or sandbox kernels) that the checker catches a missed, a shifted and an
invented event, and that its result merges through the guard.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from conftest import needs_kernels

BACKEND = Path(__file__).resolve().parents[1]


def _V():
    sys.path.insert(0, str(BACKEND))
    from validation import v14_month
    return v14_month


def test_month_parameters_are_the_approved_ones():
    """Synodic month, 3 standard sites, six edge functions, 1.0 s tolerance, 3 s matching, 2 s minimum window."""
    V = _V()
    assert V.SYNODIC_DAYS == 29.530589
    assert V.SITES == [(-89.5, 0.0), (-88.0, 120.0), (-86.5, 250.0)]
    assert V.TOL_S == 1.0 and V.MATCH_S == 3.0 and V.MIN_WINDOW_S == 2.0
    assert [k for k, _ in V.FUNCS] == ["c", "g_top", "g_bot"]
    from lunaops import settings
    assert getattr(settings, "EVENT_TOL_S", V.TOL_S) == V.TOL_S


def _fn(required=10, missed=0, over=0, spurious=0, worst=0.5, events=10):
    return {"required_edges": required, "missed": missed, "over_tolerance": over, "spurious": spurious,
            "worst_offset_s": worst, "detector_events": events}


def _site(**kw):
    return {"functions": {f"{t}_{s}": _fn(**kw) for t in ("sun", "earth") for s in ("c", "top", "bot")},
            "estimate_failures": 0}


@pytest.mark.parametrize("days,n_sites,kw,status", [
    (29.530589, 3, {}, "passed"),
    (29.53059, 3, {}, "passed"),
    (29.5305, 3, {}, "not run"),                 # short of one synodic month: never a pass
    (29.530589, 2, {}, "not run"),               # fewer than the three standard sites
    (1.0, 1, {}, "not run"),
    (1.0, 1, {"missed": 1}, "failed"),           # a failure fails even a partial run
    (29.530589, 3, {"over": 1}, "failed"),
    (29.530589, 3, {"spurious": 1}, "failed"),
])
def test_status_rule(days, n_sites, kw, status):
    V = _V()
    report = [_site(**kw) for _ in range(n_sites)]
    st, totals, detail = V.summarize(report, days, n_sites)
    assert st == status
    assert totals["required_edges"] == 60 * n_sites and totals["worst_offset_s"] == 0.5
    assert ("PARTIAL" in detail) == (st == "not run" or (st == "failed" and (days < V.SYNODIC_DAYS - 1e-6 or n_sites < 3)))


def test_worst_offset_ignores_functions_without_events():
    V = _V()
    r = _site()
    r["functions"]["earth_bot"]["worst_offset_s"] = None
    r["functions"]["sun_c"]["worst_offset_s"] = 0.9
    assert V.summarize([r, _site(), _site()], 29.530589, 3)[1]["worst_offset_s"] == 0.9
    empty = {"functions": {"sun_c": _fn(required=0, worst=None, events=0)}}
    assert V.summarize([empty] * 3, 29.530589, 3)[1]["worst_offset_s"] is None


# ------------------------------------------------------------------ the checker discriminates (short real runs)
def _tampered(V, monkeypatch, how):
    """Run check_site over 6 h at the first standard site with the detector's events tampered with."""
    from lunaops.engine.timeutil import parse_utc
    real = V.EventDetector

    class Tampered(real):
        def run(self, et0, et1):
            out = real.run(self, et0, et1)
            evs = out["events"]
            i = next(k for k, e in enumerate(evs) if e["function"] == "sun_c")
            if how == "drop":
                evs.pop(i)
            elif how == "shift":
                evs[i] = {**evs[i], "et": evs[i]["et"] + 2.0}
            elif how == "invent":
                evs.append({**evs[i], "et": evs[i]["et"] + 3600.0})
            return out
    monkeypatch.setattr(V, "EventDetector", Tampered)
    et0 = parse_utc("2026-11-14T00:00:00Z")
    lat, lon = V.SITES[0]
    return V.check_site(lat, lon, et0, et0 + 0.25 * 86400)["functions"]["sun_c"]


@needs_kernels
def test_short_run_is_clean_and_partial(kernels, monkeypatch, tmp_path):
    """6 h at one site: every required edge found within 1 s, nothing spurious, reported as a partial run
    ("not run"), and the file merges through the guard without turning a pass into anything else."""
    V = _V()
    from validation.common import merge_external, run_meta
    out = tmp_path / "v14.json"
    monkeypatch.setattr(sys, "argv", ["v14_month", "--days", "0.25", "--sites", "1", "--out", str(out)])
    V.main()
    res = json.loads(out.read_text())
    t = res["totals"]
    assert res["tests"]["V-14"]["status"] == "not run" and "PARTIAL" in res["tests"]["V-14"]["detail"]
    assert t["required_edges"] > 0 and t["missed"] == t["over_tolerance"] == t["spurious"] == 0
    assert t["worst_offset_s"] <= V.TOL_S
    assert res["algorithm_version"] and res["meta"]["script"] == "v14_month"
    assert len(res["sites"][0]["functions"]) == 6
    tests = {"V-14": {"status": "passed"}}
    assert merge_external(tests, res, run_meta("run_validation")) == []
    assert tests["V-14"]["status"] == "passed" and tests["V-14"]["external_status"] == "not run"


@needs_kernels
@pytest.mark.parametrize("how,field", [("drop", "missed"), ("shift", "over_tolerance"), ("invent", "spurious")])
def test_checker_catches_tampered_events(kernels, monkeypatch, how, field):
    """A dropped Sun-centre event is missed, one moved by 2 s is beyond the 1.0 s tolerance, and an invented one
    (1 h after a real crossing) is spurious; each would fail V-14."""
    V = _V()
    f = _tampered(V, monkeypatch, how)
    assert f[field] >= 1, f
    report = [{"functions": {"sun_c": f}}] * 3
    assert V.summarize(report, V.SYNODIC_DAYS, 3)[0] == "failed"
