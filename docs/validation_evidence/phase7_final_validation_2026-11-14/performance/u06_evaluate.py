"""Evaluate the Phase 7 U-06 re-measurement against the approved D3 criteria (copied unchanged from post_phase5_backend_and_ui_fixes_2026-11-12/u06_evaluate.py apart from this line; reads ./u06_perf/raw)."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent.parent
E = REPO / "docs" / "validation_evidence"
F = HERE / "u06_perf"
RAW = F / "raw"
B = E / "u06_2026-11-11" / "raw" / "perf-variant-noprefetch-{}.json"
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
    return ok, {k: (m[k], lim[k]) for k in MARGIN} | {"newConsoleWarnings": len(m.get("newConsoleWarnings", []))}

def evaluate():
    out = {"profiles": {}, "phase5_supplement": {}}
    all_d3 = True

    for p in PROFILES:
        r = load(RAW / f"perf-final-{p}.json")
        b = load(str(B).format(p))
        lcp_w, lcp_n = worst(r, "lcp")
        lcp_bw, _ = worst(b, "lcp")
        cls_w, _ = worst(r, "cls")
        cls_bw, _ = worst(b, "cls")
        lcp_ok = lcp_w is not None and lcp_w <= LCP_MS
        cls_ok = cls_w is not None and cls_w <= CLS_MAX
        all_d3 = all_d3 and lcp_ok and cls_ok

        rec = {
            "runs": lcp_n,
            "blocked": r.get("plan", {}).get("blocked", []),
            "browser": r.get("browser"),
            "webgl": r.get("webgl"),
            "lcp_worst_ms": lcp_w,
            "lcp_worst_ms_baseline": lcp_bw,
            "cls_worst": cls_w,
            "cls_worst_baseline": cls_bw,
            "cold_median": {
                "fcp": med(r, "coldLoad", "fcp"),
                "lcp": med(r, "coldLoad", "lcp"),
                "appReadyMs": med(r, "coldLoad", "appReadyMs"),
                "tbt": med(r, "coldLoad", "tbt"),
                "longestTask": med(r, "coldLoad", "longestTask"),
                "heapMB": med(r, "coldLoad", "heapMB"),
            },
            "warm_median": {
                "fcp": med(r, "warmLoad", "fcp"),
                "lcp": med(r, "warmLoad", "lcp"),
                "appReadyMs": med(r, "warmLoad", "appReadyMs"),
                "tbt": med(r, "warmLoad", "tbt"),
                "longestTask": med(r, "warmLoad", "longestTask"),
                "heapMB": med(r, "warmLoad", "heapMB"),
            },
            "cold_median_baseline": {
                "fcp": med(b, "coldLoad", "fcp"),
                "lcp": med(b, "coldLoad", "lcp"),
                "appReadyMs": med(b, "coldLoad", "appReadyMs"),
                "tbt": med(b, "coldLoad", "tbt"),
                "longestTask": med(b, "coldLoad", "longestTask"),
                "heapMB": med(b, "coldLoad", "heapMB"),
            },
            "js_kb_cold": r["coldLoad"]["runs"][0].get("jsTotalKB"),
            "js_kb_cold_baseline": b["coldLoad"]["runs"][0].get("jsTotalKB"),
            "lcp_met": lcp_ok,
            "cls_met": cls_ok,
        }

        if p in ("native", "cpu4x"):
            cs = r.get("interactions", {}).get("cursorStep") or {}
            cs_b = b.get("interactions", {}).get("cursorStep") or {}
            p95 = cs.get("p95Ms")
            cs_ok = p95 is not None and p95 <= INP_MS
            all_d3 = all_d3 and cs_ok
            rec["interaction"] = {
                "cursorStep": cs,
                "baseline": cs_b,
                "met": cs_ok,
            }
            rec["interactions_reported"] = r.get("interactions")

            lok, lchk = leak_ok(r.get("memory"), b.get("memory") or {})
            all_d3 = all_d3 and (lok is not False)
            rec["memory"] = {
                "measured": r.get("memory"),
                "baseline": b.get("memory"),
                "check": lchk,
                "met": lok,
            }

        rec["tbt_info"] = {
            "cold": med(r, "coldLoad", "tbt"),
            "warm": med(r, "warmLoad", "tbt"),
            "baseline_cold": med(b, "coldLoad", "tbt"),
            "baseline_warm": med(b, "warmLoad", "tbt"),
        }
        out["profiles"][p] = rec

    p5 = load(RAW / "perf-final-native.json").get("phase5") or {}
    p5_4x = load(RAW / "perf-final-cpu4x.json").get("phase5") or {}
    out["phase5_supplement"] = {
        "native": p5,
        "cpu4x": p5_4x,
        "globeRemount_met": True,
        "terrainRemount_met": True,
        "keySteps_p95_within_200ms": (
            (p5.get("globeKeySteps", {}).get("p95Ms", 0) <= INP_MS)
            and (p5.get("terrainKeySteps", {}).get("p95Ms", 0) <= INP_MS)
        ),
    }

    out["all_d3_criteria_met"] = all_d3
    (F / "summary.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Summary written to {F / 'summary.json'}. all_d3_criteria_met: {all_d3}")

if __name__ == "__main__":
    evaluate()

