"""V-14 (full form): adaptive event detection vs brute-force 1 s sampling over one synodic month.

    python -m validation.v14_month --out v14.json [--days 29.530589] [--sites 3]

Detection, not terrain, is under test, so each site uses the synthetic V-14 horizon from
lunaops.testing.v14_horizon (oscillating with a 1.5 deg period about each body's typical top-edge
elevation, plus one-bin notches), which the Sun and Earth both cross often.

For the Sun and Earth centre, top-edge and bottom-edge clearances the event function is evaluated
every second over the whole interval as one continuous series (crossings are carried across the
daily chunks used to bound memory). Reference crossings are placed by linear interpolation between
the 1 s samples. Pass criteria, all required:

- every edge of every reference window lasting 2 s or more (windows open at either end count with
  their in-interval duration; only interior edges are required) has a detector event of the same
  function and the same direction within 3 s (otherwise it is missed);
- every matched event lies within 1.0 s of its reference crossing;
- every detector event with no reference crossing of the same direction within 3 s is confirmed by
  evaluating the event function every 0.02 s within 1.5 s of it (otherwise it is spurious);
- the run covers at least one synodic month (29.530589 days) at the three standard sites.

A shorter run is reported as "not run" (partial) unless it found a failure, which is reported as
"failed". This is heavy (about 2.6 million epochs per body per site) and takes many minutes.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lunaops.engine.ephem import Site  # noqa: E402
from lunaops.engine.events import EventConfig, EventDetector  # noqa: E402
from lunaops.engine.timeutil import parse_utc  # noqa: E402
from lunaops.testing import (CrossingAccumulator, confirm_event, match_events,  # noqa: E402
                             required_crossings, target_edges, v14_horizon)

SITES = [(-89.5, 0.0), (-88.0, 120.0), (-86.5, 250.0)]
SYNODIC_DAYS = 29.530589
MATCH_S = 3.0
TOL_S = 1.0
MIN_WINDOW_S = 2.0
FUNCS = (("c", "c"), ("g_top", "top"), ("g_bot", "bot"))


def check_site(lat: float, lon: float, et0: float, et1: float, chunk_s: float = 86400.0) -> dict:
    site = Site(lat, lon, 0.0, 0.0)
    hp = v14_horizon(site, et0, (et1 - et0) / 86400.0)
    t = time.time()
    det = EventDetector(site, hp, EventConfig())
    run = det.run(et0, et1)
    t_adapt = time.time() - t
    acc = {(tg, key): CrossingAccumulator() for tg in ("sun", "earth") for key, _ in FUNCS}
    t = time.time()
    for tg in ("sun", "earth"):
        for c0 in np.arange(et0, et1, chunk_s):
            ets = np.arange(c0, min(c0 + chunk_s, et1), 1.0)
            edges = target_edges(site, hp, tg, ets)          # Earth: exact oblate limb (Phase 3)
            for key, _ in FUNCS:
                acc[(tg, key)].add(ets, edges[key])
    t_brute = time.time() - t
    out = {"site": [lat, lon], "days": round((et1 - et0) / 86400.0, 6), "functions": {},
           "adaptive_samples": det.log.samples, "estimate_failures": len(det.log.estimate_failures),
           "adaptive_s": round(t_adapt, 1), "brute_force_s": round(t_brute, 1)}
    for tg in ("sun", "earth"):
        for key, suffix in FUNCS:
            fn = f"{tg}_{suffix}"
            a = acc[(tg, key)]
            req = required_crossings(a.crossings, a.first_on, a.t0, a.t1, MIN_WINDOW_S)
            evs = [e for e in run["events"] if e["function"] == fn]
            offsets, missed, unmatched = match_events(req, a.crossings, [e["et"] for e in evs],
                                                      [e["direction"] for e in evs], MATCH_S)

            def values(ets, tg=tg, key=key):
                return target_edges(site, hp, tg, np.atleast_1d(ets), coarse_s=0.0)[key]

            spurious = [u for u in unmatched if not confirm_event(values, u[0], u[1])]
            out["functions"][fn] = {
                "reference_crossings": len(a.crossings), "required_edges": len(req),
                "detector_events": len(evs), "missed": len(missed),
                "worst_offset_s": round(max(offsets), 4) if offsets else None,
                "over_tolerance": int(sum(1 for o in offsets if o > TOL_S)),
                "unmatched_confirmed": len(unmatched) - len(spurious), "spurious": len(spurious),
                "missed_examples": [[round(x, 3), d] for x, d in missed[:5]],
                "spurious_examples": [[round(x, 3), d] for x, d in spurious[:5]]}
    return out


def summarize(report: list[dict], days: float, n_sites: int) -> tuple[str, dict, str]:
    """Status, totals and detail from the per-site results (the pass criteria in the module docstring)."""
    fns = [f for r in report for f in r["functions"].values()]
    totals = {"required_edges": sum(f["required_edges"] for f in fns), "missed": sum(f["missed"] for f in fns),
              "over_tolerance": sum(f["over_tolerance"] for f in fns), "spurious": sum(f["spurious"] for f in fns),
              "worst_offset_s": max((f["worst_offset_s"] for f in fns if f["worst_offset_s"] is not None),
                                    default=None),
              "detector_events": sum(f["detector_events"] for f in fns),
              "estimate_failures": sum(r.get("estimate_failures", 0) for r in report)}
    failed = totals["missed"] or totals["over_tolerance"] or totals["spurious"]
    full = days >= SYNODIC_DAYS - 1e-6 and n_sites >= 3 and len(report) >= 3
    status = "failed" if failed else ("passed" if full else "not run")
    detail = (f"{'full' if full else 'PARTIAL'} V-14: {days:g} days x {len(report)} site(s), 1 s brute force; "
              f"{totals['required_edges']} required window edges, {totals['missed']} missed, "
              f"{totals['over_tolerance']} beyond {TOL_S} s, {totals['spurious']} spurious; "
              f"worst offset {totals['worst_offset_s']} s")
    if not full and not failed:
        detail += f" (full form needs >= {SYNODIC_DAYS} days at 3 sites)"
    return status, totals, detail


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2026-11-14T00:00:00Z")
    ap.add_argument("--days", type=float, default=SYNODIC_DAYS)
    ap.add_argument("--sites", type=int, default=3)
    ap.add_argument("--out", default="v14.json")
    a = ap.parse_args()
    et0 = parse_utc(a.start)
    et1 = et0 + a.days * 86400
    report = []
    for lat, lon in SITES[:a.sites]:
        r = check_site(lat, lon, et0, et1)
        report.append(r)
        print(json.dumps(r))
    status, totals, detail = summarize(report, a.days, a.sites)
    from lunaops import ALGORITHM_VERSION
    from validation.common import run_meta
    out = {"tests": {"V-14": {"status": status, "detail": detail}},
           "parameters": {"start": a.start, "days": a.days, "sites": SITES[:a.sites], "match_s": MATCH_S,
                          "tolerance_s": TOL_S, "min_window_s": MIN_WINDOW_S},
           "algorithm_version": ALGORITHM_VERSION,
           "totals": totals, "sites": report, "meta": run_meta("v14_month")}
    Path(a.out).write_text(json.dumps(out, indent=2))
    print(status.upper() + ":", detail)


if __name__ == "__main__":
    main()
