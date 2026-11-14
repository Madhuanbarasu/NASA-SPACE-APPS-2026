"""V-09 / V-10: independent recomputation of the benchmark statistics and residual analysis from the per-point output
of the existing run (backend_tiles_and_ui_fixes_2026-11-12/validation/v09_v10.json, engine 84cbd4ea..., 2026-11-12).
Read only. Recomputes RMSE / bias / max with numpy (not the validation script's own code) and breaks the residuals down.
Usage: python avgvisib_residuals.py <v09_v10.json> <out dir>
"""
import csv, json, math, sys
from pathlib import Path
import numpy as np

src, out = Path(sys.argv[1]), Path(sys.argv[2])
R = json.loads(src.read_text())
print("source:", src.name, "| engine", R["meta"]["code_fingerprint"][:8], "| run", R["meta"]["run_utc"])
print("assumptions:", json.dumps(R["assumptions"]))
for test, sub in (("V-09", "V09_illumination"), ("V-10", "V10_earth_visibility")):
    pts = [p for p in R["results"][test]["points"] if p["outcome"] == "scored"]
    ref = np.array([p["reference"] for p in pts]); com = np.array([p["computed"] for p in pts])
    d = (com - ref) * 100
    lo = np.array([p["reference_3x3_min"] for p in pts]); hi = np.array([p["reference_3x3_max"] for p in pts])
    rough = (hi - lo) * 100
    inside = (com >= lo - 1e-12) & (com <= hi + 1e-12)
    # nearest in-range reference value: 0 if computed lies within the reference's own 3x3 (+-60 m) range
    dn = np.where(inside, 0.0, np.where(com < lo, com - lo, com - hi)) * 100
    lat = np.array([p["lat"] for p in pts]); gh = np.array([p["ground_h_m"] for p in pts]); st = np.array([p["stratum"] for p in pts])
    print(f"\n== {test}: {len(pts)} scored ==")
    print(f"RMSE {math.sqrt((d**2).mean()):.2f} pp | bias {d.mean():.2f} pp | max |d| {np.abs(d).max():.2f} pp | median d {np.median(d):.2f} | "
          f"MAE {np.abs(d).mean():.2f} | points |d|>5 pp: {(np.abs(d) > 5).sum()} | |d|>10: {(np.abs(d) > 10).sum()}")
    print(f"computed inside the reference's own 3x3 (+-60 m) range: {inside.sum()}/{len(pts)}; residual to that range: "
          f"RMSE {math.sqrt((dn**2).mean()):.2f} pp, bias {dn.mean():.2f} pp, max {np.abs(dn).max():.2f}")
    print(f"reference 3x3 range: median {np.median(rough):.2f} pp, 90th pct {np.percentile(rough, 90):.2f} pp")
    print("stratum | n | RMSE | bias | median 3x3 range | inside 3x3")
    for s in sorted(set(st)):
        m = st == s
        print(f"  {s} [{0.2*s:.1f},{0.2*s+0.2:.1f}] | {m.sum()} | {math.sqrt((d[m]**2).mean()):.2f} | {d[m].mean():+.2f} | {np.median(rough[m]):.1f} | {inside[m].sum()}/{m.sum()}")
    # share of the total squared error carried by the worst points
    order = np.argsort(-np.abs(d)); cum = np.cumsum(d[order] ** 2) / (d ** 2).sum()
    print(f"share of squared error in the worst 10 points: {cum[9]*100:.1f} %, worst 20: {cum[19]*100:.1f} %")
    for k in (10, 20):
        keep = np.ones(len(d), bool); keep[order[:k]] = False
        print(f"  without the worst {k}: RMSE {math.sqrt((d[keep]**2).mean()):.2f}, bias {d[keep].mean():+.2f}")
    # correlations (Spearman via ranks) of the residual with candidate drivers
    def sp(a, b):
        ra, rb = np.argsort(np.argsort(a)), np.argsort(np.argsort(b)); return float(np.corrcoef(ra, rb)[0, 1])
    print(f"Spearman(d, reference) {sp(d, ref):+.2f} | (|d|, 3x3 range) {sp(np.abs(d), rough):+.2f} | (d, latitude) {sp(d, lat):+.2f} | (d, ground height) {sp(d, gh):+.2f}")
    print(f"sign of d among |d|>5 pp: negative {(d[np.abs(d) > 5] < 0).sum()}, positive {(d[np.abs(d) > 5] > 0).sum()}")
    print("worst 12:  lat  lon  ref  computed  d_pp  3x3[min,max]  ground_h")
    for i in order[:12]:
        p = pts[i]; print(f"  {p['lat']:.4f} {p['lon']:.4f} {p['reference']*100:.2f} {p['computed']*100:.2f} {d[i]:+.2f}  [{p['reference_3x3_min']*100:.1f},{p['reference_3x3_max']*100:.1f}]  {p['ground_h_m']:.0f}")
    with open(out / sub / "per_point_residuals.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["stratum", "row", "col", "lat", "lon", "x_m", "y_m", "ground_h_m", "reference_pct", "computed_pct",
                                       "residual_pp", "reference_3x3_min_pct", "reference_3x3_max_pct", "computed_inside_3x3", "residual_to_3x3_range_pp"])
        for p, di, ins, dni in zip(pts, d, inside, dn):
            w.writerow([p["stratum"], p["row"], p["col"], f"{p['lat']:.6f}", f"{p['lon']:.6f}", p["x_m"], p["y_m"], f"{p['ground_h_m']:.1f}",
                        f"{p['reference']*100:.3f}", f"{p['computed']*100:.3f}", f"{di:.3f}", f"{p['reference_3x3_min']*100:.3f}",
                        f"{p['reference_3x3_max']*100:.3f}", int(ins), f"{dni:.3f}"])
