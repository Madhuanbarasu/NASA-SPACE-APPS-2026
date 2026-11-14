"""A10: sensitivity of the 18.6-year averages to the (undocumented) start epoch.

    LUNAOPS_DEM_FALLBACK_DIRS=<terrain> python -I epoch_sensitivity.py <v09_v10.json> <out.json> [n_per_test]

For the first n scored points of each test (in file order), recompute the average visibility with the span starting
at 2009-07-13 (the labels' LOLA data START_TIME) instead of 2026-01-01, and report the differences in percentage
points. Both spans are full 18.6-year nutation cycles; no sunlight criterion is evaluated here.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "backend"))
from validation import v09_v10_avgvisib as V  # noqa: E402

res = json.load(open(sys.argv[1]))
n = int(sys.argv[3]) if len(sys.argv) > 3 else 20
alt = V.track("2009-07-13T00:00:00Z", V.YEARS)
out = {"alternative_start": "2009-07-13T00:00:00Z", "default_start": res["assumptions"]["start_utc"], "tests": {}}
for tid, r in res["results"].items():
    pts = [p for p in r["points"] if p.get("outcome") == "scored"][:n]
    d = []
    for p in pts:
        q = V.evaluate_point(p["lat"], p["lon"], r["target"], alt, res["assumptions"]["observer_height_m"])
        if q.get("outcome") == "scored":
            d.append(100.0 * (q["computed"] - p["computed"]))
    d = np.array(d)
    out["tests"][tid] = {"points": int(d.size), "max_abs_pp": float(np.max(np.abs(d))), "rms_pp": float(np.sqrt(np.mean(d * d))),
                         "mean_pp": float(np.mean(d)), "differences_pp": [round(float(x), 4) for x in d]}
    print(tid, {k: v for k, v in out["tests"][tid].items() if k != "differences_pp"}, flush=True)
json.dump(out, open(sys.argv[2], "w"), indent=1)
