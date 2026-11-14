"""A12: sensitivity of the V-12 rule fractions to the uniform time step (600 s in the run).

    LUNAOPS_DEM_FALLBACK_DIRS=<terrain> python -I step_sensitivity.py <v12.json> <out.json> [n]

Recomputes the first n scored points (file order) at 120 s and reports the differences in percentage points for the
any, centre and full rules.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "backend"))
from lunaops.engine.timeutil import parse_utc  # noqa: E402
from validation import v12_lroc as V  # noqa: E402
from validation.v09_v10_avgvisib import track  # noqa: E402

res = json.load(open(sys.argv[1]))
n = int(sys.argv[3]) if len(sys.argv) > 3 else 20
days = (parse_utc(V.PERIOD[1]) - parse_utc(V.PERIOD[0])) / 86400.0
fine = track(V.PERIOD[0], days / 365.25, 120.0)
pts = [p for p in res["points"] if p.get("outcome") == "scored"][:n]
d = {r: [] for r in V.RULES}
for p in pts:
    q = V.evaluate_point(p["lat"], p["lon"], fine)
    for r in V.RULES:
        d[r].append(q[r] - p[r])
out = {"coarse_step_s": res["method"]["step_s"], "fine_step_s": 120.0, "points": len(pts),
       "max_abs_pp": {r: float(np.max(np.abs(d[r]))) for r in V.RULES},
       "rms_pp": {r: float(np.sqrt(np.mean(np.square(d[r])))) for r in V.RULES}}
print(json.dumps(out, indent=1))
json.dump(out, open(sys.argv[2], "w"), indent=1)
