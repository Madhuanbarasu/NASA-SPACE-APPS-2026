"""D2: read-only re-analysis of the final V-09/V-10 points (v09_v10_final_2026-11-10/v09_v10.json). No new measurement.
Run from the repository root: python docs/validation_evidence/phase4_remaining_decisions_2026-11-11/d2_strata.py"""
import json, math
d = json.load(open("docs/validation_evidence/v09_v10_final_2026-11-10/v09_v10.json", encoding="utf-8"))
print("criteria:", d["criteria"]); print("assumptions:", d["assumptions"])
for tid in ("V-09", "V-10"):
    r = d["results"][tid]
    print(f"\n== {tid} ({r['target']}) recorded metrics: {json.dumps(r['metrics'])[:400]}")
    pts = [p for p in r["points"] if p["outcome"] == "scored"]
    diffs = [100 * (p["computed"] - p["reference"]) for p in pts]
    rmse = math.sqrt(sum(x * x for x in diffs) / len(diffs)); bias = sum(diffs) / len(diffs)
    print(f"recomputed: n={len(pts)} RMSE={rmse:.2f} pp bias={bias:+.2f} pp max|d|={max(abs(x) for x in diffs):.2f} pp")
    for lim in (2, 5, 10, 20):
        print(f"   |d| <= {lim:>2} pp: {sum(abs(x) <= lim for x in diffs)}/{len(diffs)}")
    edges = [0, 0.2, 0.4, 0.6, 0.8, 1.0001]
    print("   stratum      n   RMSE    bias   max|d|")
    for a, b in zip(edges[:-1], edges[1:]):
        s = [100 * (p["computed"] - p["reference"]) for p in pts if a <= p["reference"] < b]
        if s:
            print(f"   [{a:.1f},{min(b,1):.1f}]  {len(s):3d} {math.sqrt(sum(x*x for x in s)/len(s)):6.2f} {sum(s)/len(s):+7.2f} {max(abs(x) for x in s):7.2f}")
    low = [100 * (p["computed"] - p["reference"]) for p in pts if p["reference"] < 0.6]
    print(f"   reference < 0.6: n={len(low)} RMSE={math.sqrt(sum(x*x for x in low)/len(low)):.2f} bias={sum(low)/len(low):+.2f}")
