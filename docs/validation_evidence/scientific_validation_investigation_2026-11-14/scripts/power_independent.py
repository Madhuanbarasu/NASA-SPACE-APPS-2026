"""Estimated power indicator (engine.power) and, separately, the Communication RF link budget (lunaops_comms.linkbudget):
independent recomputation with formulas written here from their published definitions.

Power indicator (dimensionless, not electrical output):
  P_rel(t) = f_sun(t) * (1 au / r_sun(t))^2 * k(t);  k = cos(el) (vertical, tracking the Sun in azimuth),
  max(0, sin el) (horizontal), cos(el) max(0, cos(az - az_panel)) (vertical, fixed azimuth); 1 au = 149 597 870.7 km.
  Window metrics: trapezoid over grid intervals whose two ends are known; mean = integral / known time;
  equivalent full-Sun hours = integral / 3600 s; coverage = known time / span.
Checked on cached results (read only): every series value and every metric, for the three panel models, plus edge
cases of the engine functions. RF: one hand-worked chain (constants CODATA k, exact c) against the comms evaluator.
Usage: python power_independent.py <out json>
"""
import json, math, os, sqlite3, sys
sys.path.insert(0, r"E:\LUNA-OPS\backend")
import numpy as np

from lunaops.engine.power import p_rel, window_metrics

AU = 149_597_870.7
CACHE = r"E:\LUNA-OPS\data\cache"


def k_indep(model, az, el, paz):
    e = np.radians(el)
    if model == "vertical_tracking":
        return np.cos(e)
    if model == "horizontal":
        return np.clip(np.sin(e), 0, None)
    return np.cos(e) * np.clip(np.cos(np.radians(az - paz)), 0, None)


def metrics_indep(t, v):
    t = np.asarray(t, float); v = np.asarray(v, float)
    integ = known = 0.0
    for i in range(t.size - 1):
        if np.isfinite(v[i]) and np.isfinite(v[i + 1]):
            integ += 0.5 * (v[i] + v[i + 1]) * (t[i + 1] - t[i]); known += t[i + 1] - t[i]
    span = t[-1] - t[0]
    return {"mean": integ / known if known else None, "equivalent_full_sun_h": integ / 3600.0 if known else None,
            "coverage": known / span, "unknown_hours": (span - known) / 3600.0}


con = sqlite3.connect(f"file:{CACHE}/cache.sqlite?mode=ro", uri=True)
rows = []
worst = {"series": 0.0, "mean": 0.0, "efsh_h": 0.0, "coverage": 0.0}
for rid, p in con.execute("select id, path from results order by created"):
    fp = os.path.join(CACHE, os.path.basename(p))
    if not os.path.exists(fp):
        continue
    r = json.load(open(fp))
    s = r["series"]; sun = s["sun"]
    t = np.asarray(s["et"], float) - r["window"]["start_et"]
    f = np.array([np.nan if x is None else x for x in sun["f"]], float)
    paz = float(r["provenance"]["parameters"].get("panel_az_deg", 0.0)) if isinstance(r["provenance"].get("parameters"), dict) else 0.0
    for model in ("vertical_tracking", "horizontal", "fixed_vertical"):
        ref = f * (AU / np.asarray(sun["dist_km"], float)) ** 2 * k_indep(model, np.asarray(sun["az"], float), np.asarray(sun["el"], float), paz)
        st = np.array([np.nan if x is None else x for x in s["power"][model]["series"]], float)
        both = np.isfinite(ref) & np.isfinite(st)
        nan_agree = bool(np.array_equal(np.isfinite(ref), np.isfinite(st)))
        ds = float(np.max(np.abs(ref[both] - st[both]))) if both.any() else 0.0
        m_eng = r["summary"]["power"][model]; m_ind = metrics_indep(t, ref)
        dm = abs((m_eng["mean"] or 0) - (m_ind["mean"] or 0)); de = abs((m_eng["equivalent_full_sun_h"] or 0) - (m_ind["equivalent_full_sun_h"] or 0))
        dc = abs(m_eng["coverage"] - m_ind["coverage"])
        worst["series"] = max(worst["series"], ds); worst["mean"] = max(worst["mean"], dm)
        worst["efsh_h"] = max(worst["efsh_h"], de); worst["coverage"] = max(worst["coverage"], dc)
        rows.append({"result": rid, "lat": r["site"]["lat"], "lon": r["site"]["lon"], "model": model, "samples": int(t.size),
                     "series_max_abs_diff": ds, "unknown_samples_agree": nan_agree, "engine": m_eng, "independent": m_ind,
                     "mean_abs_diff": dm, "efsh_abs_diff_h": de, "coverage_abs_diff": dc})
print(f"power: {len(rows)} (result, panel model) pairs from {len(rows) // 3} cached results")
print(f"  worst |series diff| {worst['series']:.2e} (series stored rounded to 5 decimals) | worst |mean diff| {worst['mean']:.2e} | "
      f"worst |equivalent full-Sun hours diff| {worst['efsh_h']:.2e} h | worst |coverage diff| {worst['coverage']:.2e}")
print(f"  unknown (NaN) samples placed identically in every pair: {all(x['unknown_samples_agree'] for x in rows)}")
print(f"  results with unknown time: {sorted({x['result'] for x in rows if x['engine']['coverage'] < 1})}")

# edge cases of the engine functions (expected values from the definitions)
edge = []
def chk(name, got, exp, tol=1e-12):
    ok = (got is None and exp is None) or (isinstance(exp, float) and math.isnan(exp) and isinstance(got, float) and math.isnan(got)) \
         or (got is not None and exp is not None and abs(got - exp) <= tol)
    edge.append({"case": name, "engine": got, "expected": exp, "ok": bool(ok)}); return ok
chk("f = 0 -> 0", float(p_rel(0.0, AU, 0, 10, "vertical_tracking")), 0.0)
chk("f unknown (NaN) stays unknown", float(p_rel(np.nan, AU, 0, 10, "vertical_tracking")), float("nan"))
chk("full disk at 1 au, el 0, vertical tracking -> 1", float(p_rel(1.0, AU, 0, 0, "vertical_tracking")), 1.0)
chk("distance 0.983 au (perihelion) scales by (1/0.983)^2", float(p_rel(1.0, 0.983 * AU, 0, 0, "vertical_tracking")), 1 / 0.983 ** 2, 1e-12)
chk("horizontal panel, Sun below 0 deg -> 0", float(p_rel(1.0, AU, 0, -1.0, "horizontal")), 0.0)
chk("horizontal panel, Sun at 1.5 deg -> sin(1.5 deg)", float(p_rel(1.0, AU, 0, 1.5, "horizontal")), math.sin(math.radians(1.5)), 1e-15)
chk("fixed vertical, Sun behind the panel (180 deg) -> 0", float(p_rel(1.0, AU, 180, 1, "fixed_vertical", 0.0)), 0.0)
chk("fixed vertical, Sun 60 deg off normal at el 0 -> 0.5", float(p_rel(1.0, AU, 60, 0, "fixed_vertical", 0.0)), 0.5, 1e-12)
chk("vertical tracking at el 89 deg -> cos 89 deg", float(p_rel(1.0, AU, 0, 89.0, "vertical_tracking")), math.cos(math.radians(89)), 1e-15)
wm = window_metrics(np.array([0.0, 3600.0, 7200.0]), np.array([np.nan, np.nan, np.nan]))
chk("all samples unknown -> mean None", wm["mean"], None); chk("all samples unknown -> coverage 0", float(wm["coverage"]), 0.0)
wm = window_metrics(np.array([0.0, 3600.0, 7200.0, 10800.0]), np.array([1.0, np.nan, 1.0, 1.0]))
chk("a known sample between unknown ones adds no time (coverage 1/3)", float(wm["coverage"]), 1 / 3, 1e-12)
chk("... and the bound is flagged (lower_bound True)", float(wm["lower_bound"]), 1.0)
try:
    p_rel(1.0, AU, 0, 0, "solar_array_5kW"); chk("unknown panel model is refused", "accepted", "refused")
except ValueError:
    edge.append({"case": "unknown panel model is refused", "ok": True})
print(f"edge cases: {sum(e['ok'] for e in edge)}/{len(edge)} as defined")
for e in edge:
    if not e["ok"]:
        print("  NOT AS DEFINED:", e)
print("  note: p_rel does not clamp f; f comes from the disk computation (0..1, or NaN), never from user input")

# RF link budget (Communication tab), one hand-worked case: Pt 20 W, Gt 20 dBi, Ltx 1 dB, Gr 60 dBi, Lrx 1 dB,
# Lother 3 dB, Ts 50 K, f 8.45 GHz, Rb 1 Mbit/s, Eb/N0 req 2.5 dB, B 2 MHz, R = 384 400 km
from lunaops_comms.linkbudget import evaluate
inp = {"pt_w": 20.0, "gt_dbi": 20.0, "ltx_db": 1.0, "gr_dbi": 60.0, "lrx_db": 1.0, "lother_db": 3.0, "ts_k": 50.0,
       "freq_hz": 8.45e9, "rb_bps": 1e6, "ebn0_req_db": 2.5, "bandwidth_hz": 2e6}
R = 384_400e3; lam = 299_792_458.0 / 8.45e9; kB = 1.380649e-23
hand = {"fspl_db": 20 * math.log10(4 * math.pi * R / lam), "eirp_dbw": 10 * math.log10(20.0) + 20 - 1}
hand["pr_dbw"] = hand["eirp_dbw"] - hand["fspl_db"] - 3 + 60 - 1
hand["cn0_dbhz"] = hand["pr_dbw"] - 10 * math.log10(kB) - 10 * math.log10(50.0)
hand["ebn0_db"] = hand["cn0_dbhz"] - 60.0
hand["margin_db"] = hand["ebn0_db"] - 2.5
hand_cn = hand["cn0_dbhz"] - 10 * math.log10(2e6)
ev = evaluate(inp, 384_400.0)
rf = {k: {"engine": ev["values"][k], "hand": v, "diff": abs(ev["values"][k] - v)} for k, v in hand.items()}
rf["cn_db"] = {"engine": ev["cn_db"], "hand": hand_cn, "diff": abs(ev["cn_db"] - hand_cn)}
print("RF link budget, hand-worked case:", {k: round(v["hand"], 4) for k, v in rf.items()}, "| max diff", max(v["diff"] for v in rf.values()))
miss = evaluate({k: v for k, v in inp.items() if k != "ts_k"}, 384_400.0)
print("RF with the noise temperature missing: complete =", miss["complete"], "| stages not evaluated:",
      [s["key"] for s in miss["stages"] if not s["evaluated"]])
zero = evaluate({**inp, "rb_bps": 0.0}, 384_400.0)
print("RF with data rate 0: complete =", zero["complete"], "| invalid:", list(zero["problems"]))
json.dump({"power_rows": rows, "worst": worst, "edge_cases": edge, "rf_hand_case": rf,
           "rf_missing_ts": {"complete": miss["complete"]}, "rf_zero_rb": {"complete": zero["complete"], "problems": zero["problems"]}},
          open(sys.argv[1], "w"), indent=1, default=lambda o: None if o is None else float(o))
