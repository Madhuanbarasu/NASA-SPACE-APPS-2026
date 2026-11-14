"""Phase 5 final U-06 re-measurement: evaluate the final production build against the approved D3 criteria
(docs/validation_evidence/phase4_remaining_decisions_2026-11-11/DECISIONS_RECORDED.md, "D3: U-06 performance, scoped
acceptance") and compare with the accepted 2026-11-11 measurements (u06_2026-11-11/raw/perf-variant-noprefetch-*.json,
the final U-06 build). Read-only over the raw files; run from the repository root. Writes u06_perf/summary.json.

D3 criteria, applied exactly as recorded:
  * LCP (lab, every run) <= 2.5 s                  -> worst cold or warm LCP per profile
  * CLS (every run) <= 0.1                          -> worst per profile
  * browser-measured interaction response p95 <= 200 ms -> Event Timing over the 20 keyboard time-cursor steps
    (native and 4x CPU; the network profile has no interaction workflow, as in D3). The browser records an event only
    when it lasts >= 16 ms (durationThreshold), so keystrokes missing from the record were faster than 16 ms; the p95
    over the recorded events is therefore an upper bound for the p95 over all 20. (The first version of this script
    required all 20 to be recorded and wrongly reported the native run as not met: logs/13_u06_evaluate_first_rule.log.)
  * memory: no progressive leak over repeated remount cycles -> D3 gives no number. Rule used here (stated, not
    approved): growth over 5 cycles with forced GC no larger than the accepted baseline's (+0.3 MB, +5 nodes,
    +5 listeners) plus a margin of 1 MB heap, 50 nodes and 10 listeners, and no new console warnings
  * TBT: recorded for information only, not a gate
Phase 5 supplement (beyond the D3 scope, reported separately): Mission tab, 3D globe and local terrain timings, Event
Timing on globe and terrain keyboard steps (only events >= 16 ms are recorded by the browser, so these p95 values are
upper bounds), and globe / terrain remount cycles under the same memory rule.
Usage: python u06_evaluate.py [final|repeat]  (the run label in u06_perf/raw/perf-<label>-<profile>.json)"""
import json
import sys

E = "docs/validation_evidence/"
F = E + "phase5_final_2026-11-12/u06_perf/"
B = E + "u06_2026-11-11/raw/perf-variant-noprefetch-{}.json"
PROFILES = ["native", "cpu4x", "cpu4x-net10mbps"]
LCP_MS, CLS_MAX, INP_MS = 2500, 0.1, 200
MARGIN = {"heapGrowthMB": 1.0, "nodeGrowth": 50, "listenerGrowth": 10}


def load(p):
    return json.load(open(p, encoding="utf-8"))


def worst(r, key):
    runs = r["coldLoad"]["runs"] + r["warmLoad"]["runs"]
    vals = [x[key] for x in runs if x.get(key) is not None]
    return (max(vals) if vals else None), len(runs)


def med(r, part, key):
    m = r[part].get("median") or {}
    return m.get(key)


def leak_ok(m, base):
    if not m:
        return None, "not measured"
    lim = {k: max(base.get(k, 0), 0) + MARGIN[k] for k in MARGIN}
    ok = all(m[k] <= lim[k] for k in MARGIN) and not m.get("newConsoleWarnings")
    return ok, {k: (m[k], lim[k]) for k in MARGIN} | {"newConsoleWarnings": len(m.get("newConsoleWarnings") or [])}


SET = sys.argv[1] if len(sys.argv) > 1 else "final"
PROFILES = [p for p in PROFILES if __import__("os").path.exists(F + f"raw/perf-{SET}-{p}.json")]
ok = True
out = {"run_set": SET, "profiles_measured": PROFILES, "criteria": {"lcp_ms": LCP_MS, "cls": CLS_MAX, "interaction_p95_ms": INP_MS, "memory_rule": "growth <= accepted baseline + margin " + json.dumps(MARGIN) + ", no new console warnings", "tbt": "information only"},
       "profiles": {}, "phase5_supplement": {}}
base_mem = load(B.format("native")).get("memory") or {}
print(f"U-06 (D3 criteria) on the final Phase 5 build, run set '{SET}'; baseline = accepted 2026-11-11 final U-06 build")
for p in PROFILES:
    r, b = load(F + f"raw/perf-{SET}-{p}.json"), load(B.format(p))
    if not r.get("complete"):
        ok = False; print(f"{p}: RUN INCOMPLETE: {r.get('error', '')[:200]}"); continue
    lcp, n = worst(r, "lcp"); cls, _ = worst(r, "cls")
    blcp, _ = worst(b, "lcp"); bcls, _ = worst(b, "cls")
    e = {"runs": n, "blocked": r["plan"]["blockedUrls"], "browser": r["browser"], "webgl": r.get("webgl"),
         "lcp_worst_ms": lcp, "lcp_worst_ms_baseline": blcp, "cls_worst": cls, "cls_worst_baseline": bcls,
         "cold_median": {k: med(r, "coldLoad", k) for k in ["fcp", "lcp", "appReadyMs", "tbt", "longestTask", "heapMB"]},
         "warm_median": {k: med(r, "warmLoad", k) for k in ["fcp", "lcp", "appReadyMs", "tbt", "longestTask", "heapMB"]},
         "cold_median_baseline": {k: med(b, "coldLoad", k) for k in ["fcp", "lcp", "appReadyMs", "tbt", "longestTask", "heapMB"]},
         "js_kb_cold": r["coldLoad"]["runs"][0]["transfer"]["jsKB"], "js_kb_cold_baseline": b["coldLoad"]["runs"][0]["transfer"]["jsKB"]}
    lcp_ok, cls_ok = lcp is not None and lcp <= LCP_MS, cls is not None and cls <= CLS_MAX
    e["lcp_met"], e["cls_met"] = lcp_ok, cls_ok
    ok &= lcp_ok and cls_ok
    line = f"{p:16s} LCP worst {lcp} ms (baseline {blcp}) {'met' if lcp_ok else 'NOT MET'} | CLS worst {cls} (baseline {bcls}) {'met' if cls_ok else 'NOT MET'}"
    if r.get("interactions"):
        cs, bcs = r["interactions"]["cursorStep"], (b.get("interactions") or {}).get("cursorStep", {})
        inp_ok = cs["p95Ms"] is not None and cs["p95Ms"] <= INP_MS and 1 <= cs["interactions"] <= 20
        e["interaction"] = {"cursorStep": cs, "baseline": bcs, "met": inp_ok}
        e["interactions_reported"] = {k: v for k, v in r["interactions"].items() if k not in ("cursorStep",)}
        ok &= inp_ok
        line += f" | p95 {cs['p95Ms']} ms over {cs['interactions']} recorded of 20 (baseline {bcs.get('p95Ms')}) {'met' if inp_ok else 'NOT MET'}"
    else:
        e["interaction"] = "not measured (no workflow in this profile, as in D3)"
        line += " | interaction: not measured (as in D3)"
    if r.get("memory"):
        mok, md = leak_ok(r["memory"], base_mem)
        e["memory"] = {"measured": r["memory"], "baseline": base_mem, "check": md, "met": mok}
        ok &= bool(mok)
        line += f" | memory {'met' if mok else 'NOT MET'} {md}"
    e["tbt_info"] = {"cold": med(r, "coldLoad", "tbt"), "warm": med(r, "warmLoad", "tbt"), "baseline_cold": med(b, "coldLoad", "tbt"), "baseline_warm": med(b, "warmLoad", "tbt")}
    line += f" | TBT cold/warm {e['tbt_info']['cold']}/{e['tbt_info']['warm']} ms (info; baseline {e['tbt_info']['baseline_cold']}/{e['tbt_info']['baseline_warm']})"
    out["profiles"][p] = e
    print(line)
    if r.get("phase5"):
        s = r["phase5"]
        g, t = s["globeRemount"], s["terrainRemount"]
        gok, gd = leak_ok(g, base_mem); tok, td = leak_ok(t, base_mem)
        sup = {k: s[k] for k in ["tabToMissionMs", "tabMissionToSiteMs", "globeToCanvasMs", "globeToImageryMs", "globeImageryKB", "terrainToCanvasMs", "terrainToDataMs"]}
        sup.update({"globeKeySteps": s["globeKeySteps"], "terrainKeySteps": s["terrainKeySteps"], "globeRemount": g, "terrainRemount": t,
                    "globeRemount_rule": gd, "terrainRemount_rule": td, "globeRemount_met": gok, "terrainRemount_met": tok,
                    "keySteps_p95_within_200ms": all(x["p95Ms"] is None or x["p95Ms"] <= INP_MS for x in (s["globeKeySteps"], s["terrainKeySteps"]))})
        out["phase5_supplement"][p] = sup
        print(f"   Phase 5 supplement: Mission tab {sup['tabToMissionMs']} ms; globe canvas {sup['globeToCanvasMs']} ms, imagery {sup['globeToImageryMs']} ms ({sup['globeImageryKB']} KB);"
              f" terrain canvas {sup['terrainToCanvasMs']} ms, data {sup['terrainToDataMs']} ms; key p95 globe {s['globeKeySteps']['p95Ms']} / terrain {s['terrainKeySteps']['p95Ms']} ms"
              f" (n = {s['globeKeySteps']['interactions']}/{s['terrainKeySteps']['interactions']} events >= 16 ms);"
              f" remount globe {'ok' if gok else 'GROWTH'} {gd}, terrain {'ok' if tok else 'GROWTH'} {td}")
out["all_d3_criteria_met"] = bool(ok)
json.dump(out, open(F + f"summary-{SET}.json", "w", encoding="utf-8"), indent=1)
print("U-06 D3 CRITERIA MET IN EVERY MEASURED PROFILE (scoped; not a field Core Web Vitals claim)" if ok else "U-06 D3 CRITERIA NOT MET (see above)")
sys.exit(0 if ok else 1)
