"""A10: the vectorised V-09/V-10 verdicts against the engine's own event detector, on shorter periods.

    python -I crosscheck_detector.py > crosscheck_detector.txt

For each case the detector runs over the period and its "sun_any" / "earth_any" intervals are looked up at every
sampled epoch; the vectorised method (validation/v09_v10_avgvisib.visible_any) is evaluated at the same epochs.
Cases: the synthetic V-14 horizon (frequent crossings) for one synodic month hourly at two sites and 10 days every
10 minutes at a third; and the 3 March 2026 total lunar eclipse every minute with a flat -10 deg horizon at three
sites (only Earth can hide the Sun there).
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
from validation import v09_v10_avgvisib as V  # noqa: E402


def detector_states(site, hp, target, ets):
    det = EventDetector(site, hp, EventConfig())
    e0, e1 = float(ets[0]) - 60.0, float(ets[-1]) + 60.0
    run = det.run(e0, e1)
    ivs = build_intervals(det, e0, e1, run["events"], run["samples"])[f"{target}_any"]
    starts = np.array([iv["start_et"] for iv in ivs])
    return [ivs[np.searchsorted(starts, t, side="right") - 1]["state"] for t in ets], len(ivs)


cases = [((-89.5, 0.0), "2026-11-14T00:00:00Z", 29.530589, 3600.0, "v14"),
         ((-88.0, 120.0), "2026-11-14T00:00:00Z", 29.530589, 3600.0, "v14"),
         ((-86.5, 250.0), "2026-11-14T00:00:00Z", 10.0, 600.0, "v14"),
         ((-89.0, 0.0), "2026-03-03T08:00:00Z", 8 / 24, 60.0, "flat-10"),
         ((-87.0, 20.0), "2026-03-03T08:00:00Z", 8 / 24, 60.0, "flat-10"),
         ((-85.5, 340.0), "2026-03-03T08:00:00Z", 8 / 24, 60.0, "flat-10")]
total = mism_total = 0
for (lat, lon), start, days, step, hz in cases:
    site = Site(lat, lon, 0.0, 0.0)
    trk = V.track(start, days / 365.25, step)
    hp = v14_horizon(site, trk["ets"][0], days + 0.1) if hz == "v14" else HorizonProfile(np.full(3600, -10.0), np.zeros(3600, bool))
    for tg in (("sun", "earth") if hz == "v14" else ("sun",)):
        t = time.time()
        vis, stats = V.visible_any(site, hp, tg, trk)
        tv = time.time() - t
        t = time.time()
        st, nint = detector_states(site, hp, tg, trk["ets"])
        td = time.time() - t
        mism = sum(1 for a, b in zip(st, vis) if a is None or bool(a) != bool(b))
        total += vis.size
        mism_total += mism
        extra = f", hidden by Earth {stats['hidden_by_earth_hours']}" if tg == "sun" else ""
        print(f"{lat:6.1f} {lon:6.1f} {hz:8s} {start[:10]} {days:9.4f} d every {step:5.0f} s {tg:5s}: {vis.size:5d} epochs, "
              f"detector intervals {nint:4d}, visible {int(vis.sum()):5d}, exact {stats['exact_hours']:4d}{extra}, "
              f"mismatches {mism}; vectorised {tv:.2f} s, detector {td:.1f} s", flush=True)
print(f"TOTAL: {total} epochs, {mism_total} mismatches")
