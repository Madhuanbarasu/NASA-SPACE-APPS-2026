"""Read-only D1 analysis of the existing V-05 evidence (no new measurement, no network). Run from backend/.
Rates are per site and body, taken from that pair's stored 1-s Horizons refinement table; the geometric bound uses
the largest hourly V-04 elevation residual of that site and body over the whole month (conservative)."""
import csv, json, math, statistics, sys
from pathlib import Path
sys.path.insert(0, ".")
from validation.horizons_compare import parse_rows, V05_TOL_S, V05_MATCH_S
from lunaops import settings
R = Path("../docs/validation_evidence/refresh_v04_v05_v13_v14_2026-11-11")
h = json.loads((R / "v04_horizons/horizons.json").read_text())
r = json.loads((R / "v05_riseset/v05_report.json").read_text())
ev = h["v05"]["events"]
print("matched", len(ev), "missed", len(h["v05"]["missed"]), "spurious", len(h["v05"]["spurious"]))
print("max|dt| from horizons.json", max(abs(e["dt_s"]) for e in ev), "| v05_report", r["summary"]["max_abs_dt_s"])
print("V05_TOL_S", V05_TOL_S, "MATCH", V05_MATCH_S, "EVENT_TOL_S", settings.EVENT_TOL_S, "floor", settings.EVENT_STEP_FLOOR_S, "cap", settings.EVENT_STEP_CAP_S)
# V-04 residual maxima per site/body (hourly, existing CSV)
mx = {}
for row in csv.DictReader(open(R / "v04_horizons/horizons_v04_residuals.csv")):
    k = (row["site"], row["target"]); mx[k] = max(mx.get(k, 0.0), abs(float(row["del_deg"])))
# elevation rate at each crossing from the stored 1-s Horizons table
sec = {f["file"]: f for f in r["horizons_responses_by_stage"]["second_refine"]}
out = []
for e in ev:
    lab = e["site"].replace(" ", "_")
    cands = [f for f in sec if f.startswith(f"v05_{lab}_{e['body']}_")]
    best = None
    for f in cands:
        rows = parse_rows(json.loads((R / "v04_horizons/horizons_raw" / f).read_text())["result"])
        els = [x[2] for x in rows]
        for a, b in zip(els[:-1], els[1:]):
            if (a > 0) != (b > 0):
                best = abs(b - a)  # deg per 1 s
        if best: 
            # check this file is the one for this event: crossing time near
            pass
    rate = best
    geo_s = mx[(e["site"], e["body"])] / rate if rate else float("nan")
    ref_s = 1e-9 / rate if rate else float("nan")     # Horizons prints elevation to 1e-9 deg
    out.append((e["site"], e["body"], e["direction"], e["dt_s"], rate, geo_s, ref_s))
for o in out:
    print(f"{o[0]:20s} {o[1]:5s} {'rise' if o[2]==1 else 'set ':4s} dt={o[3]:+.4f}s  rate={o[4]:.3e} deg/s  geom<= {o[5]:.2e}s  ref_print<= {o[6]:.1e}s")
sun = [o[3] for o in out if o[1] == "sun"]; earth = [o[3] for o in out if o[1] == "earth"]
print("sun n", len(sun), "min", min(sun), "max", max(sun), "mean", statistics.fmean(sun), "all positive", all(x > 0 for x in sun))
print("earth n", len(earth), "min", min(earth), "max", max(earth), "mean", statistics.fmean(earth))
print("max geometric timing bound", max(o[5] for o in out), "max reference print bound", max(o[6] for o in out))
print("P(all", len(sun), "sun dt > 0 | symmetric error) =", 0.5 ** len(sun))
