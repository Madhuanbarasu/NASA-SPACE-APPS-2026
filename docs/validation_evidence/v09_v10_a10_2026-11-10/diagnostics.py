"""A10 diagnostics of a preliminary V-09/V-10 run (no criterion is evaluated).

    LUNAOPS_DEM_FALLBACK_DIRS=<terrain> python -I diagnostics.py <v09_v10.json> <out.json>

1. Inconclusive points: why their horizons are incomplete. For each incomplete bin, the engine's stop step gives the
   distance at which the ray broke: at the end of the last window (the 80 m level's 250 km) or earlier (left the
   registered data or met nodata).
2. Scored points with |computed - reference| > 5 pp: the same average recomputed at observer heights 2 m and 10 m
   (the AVGVISIB observer height is not documented; 0 m is assumed), to show how strongly that assumption could move
   them.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "backend"))
from lunaops.engine.dem import load_pyramid, site_height_window  # noqa: E402
from lunaops.engine.horizon import build_steps, compute_horizon  # noqa: E402
from validation import v09_v10_avgvisib as V  # noqa: E402

res = json.load(open(sys.argv[1]))
trk = V.track(res["assumptions"]["start_utc"], res["assumptions"]["years"])
out = {}
for tid, r in res["results"].items():
    pts = r["points"]
    inc = [p for p in pts if p.get("outcome") != "scored"]
    causes = {"window_end_only": 0, "data_edge_or_nodata": 0, "no_terrain": 0}
    inc_rows = []
    for p in inc:
        if "no terrain" in p.get("reason", ""):
            causes["no_terrain"] += 1
            continue
        pyr = load_pyramid(p["lat"], p["lon"])
        hz = compute_horizon(p["lat"], p["lon"], 0.0, pyramid=pyr)
        _g, wi = site_height_window(pyr, p["lat"], p["lon"])
        d, _ = build_steps(pyr, 0.5 * pyr[wi].pixel_m)
        k = np.nonzero(hz.incomplete)[0]
        brk = d[np.minimum(hz.stop_step[k], d.size - 1)]
        at_end = brk >= d[-1] - 1.0
        causes["window_end_only" if at_end.all() else "data_edge_or_nodata"] += 1
        inc_rows.append({"lat": p["lat"], "lon": p["lon"], "stratum": p["stratum"], "reference": p["reference"],
                         "incomplete_bins": int(k.size), "window_end_bins": int(at_end.sum()),
                         "min_horizon_in_incomplete_deg": float(hz.h_deg[k].min())})
    big = [p for p in pts if p.get("outcome") == "scored" and abs(p["computed"] - p["reference"]) > 0.05]
    hrows = []
    for p in big:
        row = {"lat": p["lat"], "lon": p["lon"], "stratum": p["stratum"], "reference": p["reference"],
               "computed_0m": p["computed"], "reference_3x3": [p["reference_3x3_min"], p["reference_3x3_max"]]}
        for h in (2.0, 10.0):
            q = V.evaluate_point(p["lat"], p["lon"], r["target"], trk, h)
            row[f"computed_{h:g}m"] = q.get("computed")
        hrows.append(row)
        print(tid, json.dumps(row), flush=True)
    out[tid] = {"inconclusive": len(inc), "inconclusive_causes": causes,
                "inconclusive_by_stratum": {j: sum(1 for p in inc if p["stratum"] == j) for j in range(5)},
                "inconclusive_points": inc_rows, "large_difference_points": hrows}
    print(tid, causes, flush=True)
json.dump(out, open(sys.argv[2], "w"), indent=1)
