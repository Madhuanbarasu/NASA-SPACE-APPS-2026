"""D1 reconciliation: read-only analysis of the EXISTING V-05 raw evidence (no network, no new measurement).
Run from backend/:  .venv/Scripts/python.exe ../docs/validation_evidence/d1_v05_decision_2026-11-11/reconcile_analysis.py

For each of the 18 matched events it re-reads the stored Horizons tables (horizons_raw/) and computes:
  * t_sec : the crossing interpolated from the 1-second table (as recorded by horizons_compare, re-derived here);
  * t_min : the crossing linearly interpolated from the stored 1-minute table of the same hour;
then reports t_LUNA - t_sec, t_LUNA - t_min and t_min - t_sec. It also lists every RTS-related header line,
to show whether Horizons' own rise/transit/set (RTS) mode was ever queried. Nothing is written except stdout.
"""
import json, re, sys
from pathlib import Path
sys.path.insert(0, ".")
from lunaops.engine.kernels import load
from validation.horizons_compare import parse_rows, tt_tag_to_et, sign_crossings, interpolate_crossing

load()
R = Path("../docs/validation_evidence/refresh_v04_v05_v13_v14_2026-11-11/v04_horizons")
h = json.loads((R / "horizons.json").read_text())
files = {f["file"]: f for f in h["horizons_responses"]}

def crossings(fname):
    rows = parse_rows(json.loads((R / "horizons_raw" / fname).read_text())["result"])
    ets = [tt_tag_to_et(r[0]) for r in rows]; els = [r[2] for r in rows]
    out = []
    for a, b, d in sign_crossings(ets, els):
        i = ets.index(a)
        out.append((interpolate_crossing(a, b, els[i], els[i + 1]), d, b - a))
    return out

rts_lines = set()
for f in files:
    txt = json.loads((R / "horizons_raw" / f).read_text())["result"]
    for ln in txt.splitlines():
        if re.search(r"RTS|rise|R_T_S", ln, re.I):
            rts_lines.add(ln.strip()[:100])
    q = files[f]["query"]
    if any("RTS" in k.upper() for k in q):
        rts_lines.add("QUERY PARAM: " + str(q))
marker_rows = 0
for f in files:
    body = json.loads((R / "horizons_raw" / f).read_text())["result"].split("$$SOE")[1].split("$$EOE")[0]
    marker_rows += sum(1 for ln in body.strip().splitlines() if re.match(r"^[^,]+,[^,]*,\s*[rst]\s*,", ln))
print(f"table rows carrying a Horizons RTS marker (r/s/t) in the 3rd column, all 47 responses: {marker_rows}")
print("RTS-related header lines / query parameters across all 47 responses:")
for l in sorted(rts_lines): print("   ", l)

rows = []
for e in h["v05"]["events"]:
    lab = e["site"].replace(" ", "_")
    best = {}
    for kind in ("min", "sec"):
        for f in files:
            if f.startswith(f"v05_{lab}_{e['body']}_") and f.endswith(f"_{kind}.json"):
                for t, d, step in crossings(f):
                    if d == e["direction"] and abs(t - e["et_horizons"]) < 3600 and \
                            (kind not in best or abs(t - e["et_horizons"]) < abs(best[kind][0] - e["et_horizons"])):
                        best[kind] = (t, step, f)
    tmin, smin, fmin = best["min"]; tsec, ssec, fsec = best["sec"]
    rows.append((e["site"], e["body"], e["direction"], e["et_luna"] - tsec, e["et_luna"] - tmin, tmin - tsec,
                 tsec - e["et_horizons"], smin, ssec))
print("\nsite                 body  event  LUNA-t_sec   LUNA-t_min   t_min-t_sec  (t_sec re-derived - recorded)  min step / sec step")
for r in rows:
    print(f"{r[0]:20s} {r[1]:5s} {'rise' if r[2] == 1 else 'set ':5s} {r[3]:+11.4f}s {r[4]:+11.4f}s {r[5]:+11.4f}s   {r[6]:+.1e}s   {r[7]:.0f} s / {r[8]:.0f} s")
m = lambda k: max(abs(r[k]) for r in rows)
print(f"\nn = {len(rows)} matched events (missed {len(h['v05']['missed'])}, spurious {len(h['v05']['spurious'])})")
print(f"max |t_LUNA - t_sec| (Horizons 1-s crossing)          = {m(3):.5f} s")
print(f"max |t_LUNA - t_min| (interpolated 1-minute table)    = {m(4):.5f} s")
print(f"max |t_min - t_sec|  (1-minute interpolation error)   = {m(5):.5f} s")
print(f"max |re-derived t_sec - recorded et_horizons|         = {m(6):.1e} s")
for lim in (1.0, 10.0, 120.0):
    print(f"within {lim:>5} s: vs 1-s crossing {sum(abs(r[3]) <= lim for r in rows)}/18, vs 1-minute interpolation {sum(abs(r[4]) <= lim for r in rows)}/18")
