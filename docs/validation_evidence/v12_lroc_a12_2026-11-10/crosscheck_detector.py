"""A12: V-12's vectorised Sun visibility under the any, centre and full rules against the engine's event detector.

    python -I crosscheck_detector.py > crosscheck_detector.txt

The detector's "sun_any", "sun_centre" and "sun_full" intervals are looked up at every sampled epoch and compared
with validation/v12_lroc.rule_states' per-sample verdicts. Cases: the synthetic V-14 horizon (frequent crossings)
inside the LROC year at three sites, and the 21 December 2010 total lunar eclipse (in the LROC year) every minute with
a flat -10 deg horizon, where only Earth can hide the Sun.
"""
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "backend"))
from lunaops.engine.ephem import Site  # noqa: E402
from lunaops.engine.events import EventConfig, EventDetector, build_intervals  # noqa: E402
from lunaops.engine.visibility import HorizonProfile  # noqa: E402
from lunaops.testing import v14_horizon  # noqa: E402
from validation import v12_lroc as V  # noqa: E402
from validation.v09_v10_avgvisib import track  # noqa: E402


def per_sample(site, hp, trk):
    return V.rule_states(site, hp, trk)


def detector(site, hp, ets):
    det = EventDetector(site, hp, EventConfig())
    e0, e1 = float(ets[0]) - 60.0, float(ets[-1]) + 60.0
    run = det.run(e0, e1)
    ivs = build_intervals(det, e0, e1, run["events"], run["samples"])
    out = {}
    for rule in V.RULES:
        iv = ivs[f"sun_{rule}"]
        starts = np.array([x["start_et"] for x in iv])
        out[rule] = [iv[np.searchsorted(starts, t, side="right") - 1]["state"] for t in ets]
    return out, sum(len(ivs[f"sun_{r}"]) for r in V.RULES)


cases = [((-89.5, 0.0), "2010-06-01T00:00:00Z", 29.530589, 3600.0, "v14"),
         ((-88.6, 120.0), "2010-09-01T00:00:00Z", 29.530589, 3600.0, "v14"),
         ((-88.2, 250.0), "2010-03-01T00:00:00Z", 10.0, 600.0, "v14"),
         ((-89.0, 0.0), "2010-12-21T05:00:00Z", 8 / 24, 60.0, "flat-10"),
         ((-88.5, 330.0), "2010-12-21T05:00:00Z", 8 / 24, 60.0, "flat-10")]
total = mism = 0
for (lat, lon), start, days, step, hz in cases:
    site = Site(lat, lon, 0.0, 0.0)
    trk = track(start, days / 365.25, step)
    hp = v14_horizon(site, trk["ets"][0], days + 0.1) if hz == "v14" else HorizonProfile(np.full(3600, -10.0), np.zeros(3600, bool))
    t = time.time()
    vis, stats = per_sample(site, hp, trk)
    tv = time.time() - t
    t = time.time()
    st, nint = detector(site, hp, trk["ets"])
    td = time.time() - t
    parts = []
    for rule in V.RULES:
        m = sum(1 for a, b in zip(st[rule], vis[rule]) if a is None or bool(a) != bool(b))
        mism += m
        total += vis[rule].size
        parts.append(f"{rule} visible {int(vis[rule].sum()):5d} mismatches {m}")
    print(f"{lat:6.1f} {lon:6.1f} {hz:8s} {start[:10]} {days:8.4f} d every {step:5.0f} s: {trk['ets'].size:5d} epochs, "
          f"detector intervals {nint:4d}, exact {stats['exact_samples']:4d}; " + "; ".join(parts) +
          f"; vectorised {tv:.2f} s, detector {td:.1f} s", flush=True)
print(f"TOTAL: {total} epoch-rule pairs, {mism} mismatches")
