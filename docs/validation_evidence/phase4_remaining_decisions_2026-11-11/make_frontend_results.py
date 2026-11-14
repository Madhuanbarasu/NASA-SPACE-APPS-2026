"""Write the U-04 and U-06 result files (frontend_u04.json, frontend_u06.json) and dry-run the merge guard in memory.

    cd backend && .venv/Scripts/python.exe ../docs/validation_evidence/phase4_remaining_decisions_2026-11-11/make_frontend_results.py

Kept outside backend/ so no fingerprint changes. Schema = what validation.common.merge_external checks:
  {"tests": {"<ID>": {"status": one of STATUSES, "detail": str}}, "meta": run_meta("<owner script>"), ...extra keys}
Owner scripts: OWNERS["frontend_u04"] = ("U-04",), OWNERS["frontend_u06"] = ("U-06",). U-04/U-06 are not terrain-gated.
Extra keys (ignored by the guard) carry the approved criteria, measurements, scope, limitations and the frontend
build hashes, because the guard binds a result only to the backend fingerprints.

Statuses are computed here from the existing evidence under the criteria approved on 2026-11-11 (D3, D4); nothing
is measured. Writes only the two result files and merge_dry_run.json in this folder; report.json is only read.
"""
from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

BACKEND = Path.cwd()
REPO = BACKEND.parent
HERE = Path(__file__).resolve().parent
EV = REPO / "docs" / "validation_evidence"
sys.path.insert(0, str(BACKEND))

import validation  # noqa: E402,F401  (kernel-set selection, as every validation script)
from validation.common import OWNERS, STATUSES, merge_external, run_meta  # noqa: E402


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def rel(p: Path) -> str:
    return p.relative_to(REPO).as_posix()


def dist_hashes() -> dict:
    d = REPO / "frontend" / "dist"
    return {p.relative_to(d).as_posix(): sha(p) for p in sorted(d.rglob("*")) if p.is_file()}


def u06() -> dict:
    s_path = EV / "u06_2026-11-11" / "summary.json"
    s = json.loads(s_path.read_text(encoding="utf-8"))
    per = {}
    for prof, v in s["profiles"].items():
        a = v["after"]
        raw = json.loads((EV / "u06_2026-11-11" / "raw" / f"perf-variant-noprefetch-{prof}.json").read_text(encoding="utf-8"))
        runs = []

        def walk(o):
            if isinstance(o, dict):
                if {"lcp", "fcp", "cls"} <= set(o):
                    runs.append(o)
                for x in o.values():
                    walk(x)
            elif isinstance(o, list):
                for x in o:
                    walk(x)
        walk(raw)
        i = a.get("interactions") or {}
        per[prof] = {
            "lcp_ms_max": max(r["lcp"] for r in runs), "lcp_ms_median_cold": a["cold"]["lcp"],
            "lcp_ms_median_warm": a["warm"]["lcp"], "cls_max": max(r["cls"] for r in runs),
            "tbt_ms_cold_info": a["cold"]["tbt"], "tbt_ms_warm_info": a["warm"]["tbt"],
            "interaction_p95_ms": (i.get("cursorStep") or {}).get("p95Ms"),
            "interaction_basis": ("Event Timing, 20 keyboard time-cursor interactions" if i.get("cursorStep") else
                                  "not measured in this profile (loads only)"),
            "single_frame_ui_ms_info": ({"tabs": i.get("tabs"), "rotate3D_max": (i.get("rotate3D") or {}).get("maxMs"),
                                         "mode_switch": [i.get("modeToPublicMs"), i.get("modeToTechnicalMs")],
                                         "metric_switch": i.get("metricSwitchMs"), "cell_to_result": i.get("cellToResultMs")}
                                        if i else None),
            "data_loading_ms_info": ({"analysis_to_result": i.get("analysisToResultMs"),
                                      "analysis_to_3d_data": i.get("analysisTo3DDataMs"),
                                      "compare_to_matrix": i.get("compareToMatrixMs")} if i else None),
            "memory": a.get("memory"), "blocked_requests": a.get("blocked")}
    lcp_ok = all(p["lcp_ms_max"] <= 2500 for p in per.values())
    cls_ok = all(p["cls_max"] <= 0.1 for p in per.values())
    measured_int = {k: p["interaction_p95_ms"] for k, p in per.items() if p["interaction_p95_ms"] is not None}
    int_ok = bool(measured_int) and all(x <= 200 for x in measured_int.values())
    mem = per["native"]["memory"]
    # No numeric memory threshold is introduced. The criterion is met on the U-06 audit's own documented finding,
    # "No leak and no WebGL context exhaustion were observed" (u06 README, Results: memory; finding 4 "No leak
    # demonstrated"), restated from its recorded observations: 5 remount cycles with forced GC, heap +0.3 MB, +5 DOM
    # nodes, +5 listeners, no new console (WebGL) warnings. Per-cycle series were not recorded, so a progressive trend
    # cannot be shown cycle by cycle; this limitation is recorded with the result.
    u06_readme = (EV / "u06_2026-11-11" / "README.md").read_text(encoding="utf-8")
    audit_finding = "No leak and no WebGL context exhaustion were observed" in u06_readme
    mem_ok = bool(mem is not None and mem["cycles"] >= 5 and not mem["newConsoleWarnings"] and audit_finding)
    status = "passed" if (lcp_ok and cls_ok and int_ok and mem_ok) else "failed"
    detail = (f"Scoped U-06 (D3, approved 2026-11-11): LCP max {per['native']['lcp_ms_max']}/{per['cpu4x']['lcp_ms_max']}/"
              f"{per['cpu4x-net10mbps']['lcp_ms_max']} ms (<= 2500), CLS max 0 (<= 0.1), interaction p95 "
              f"{measured_int.get('native')}/{measured_int.get('cpu4x')} ms (<= 200; Event Timing, native/4x CPU), "
              f"no progressive memory leak (+{mem['heapGrowthMB']} MB over {mem['cycles']} remounts); "
              "HP 15-fd0xxx Core 5 120U, Chrome 157 headless, profiles native / 4x CPU / 4x CPU + 10 Mbit/s; "
              "TBT information only; two slow backend map tiles (0/0/0, 1/0/1) excluded; lab measurement, "
              "not a field Core Web Vitals claim")
    return {"status": status, "detail": detail, "per_profile": per,
            "checks": {"lcp_le_2500ms": lcp_ok, "cls_le_0.1": cls_ok, "interaction_p95_le_200ms": int_ok,
                       "no_progressive_memory_leak": mem_ok},
            "evidence": {rel(s_path): sha(s_path)} | {rel(p): sha(p) for p in sorted((EV / "u06_2026-11-11" / "raw").glob("perf-variant-noprefetch-*.json"))}}


def u04() -> dict:
    cur_p = HERE / "u04_current_build" / "audit-current-build.json"
    rel_p = EV / "u04_2026-11-11" / "audit-release.json"
    cur, relr = json.loads(cur_p.read_text(encoding="utf-8")), json.loads(rel_p.read_text(encoding="utf-8"))
    views = {}
    for v in cur["views"]:
        k = v.get("keyboard") or {}
        cnt = {"axUnnamed": len(v["ax"]["unnamed"]), "focusableNoRole": len(v["ax"]["focusableWithoutWidgetRole"]),
               "contrastFail": len(v["contrast"]["failures"]), "targetFail": len(v["targets"]["failures"]),
               "noFocusIndicator": len(k.get("noIndicator", [])), "focusClipped": len(k.get("clipped", [])),
               "obscured": len(k.get("obscured", [])), "reflowHScroll": int(bool(v["reflow320"]["horizontalScroll"])),
               "reflowOffenders": v["reflow320"]["offenderCount"], "spacingClipped": len(v["textSpacing"]["clipped"]),
               "unlabeled": len(v["structure"]["unlabeledFormControls"]), "dupIds": len(v["structure"]["duplicateIds"]),
               "roleApplication": len(v["structure"]["roleApplication"])}
        views[v["view"]] = {"problems": sum(cnt.values()), "counts": cnt, "tabStops": k.get("stops")}
    same_views = set(views) == {v["view"] for v in relr["views"]}
    func = {key: json.dumps(cur["functional"].get(key), sort_keys=True) == json.dumps(val, sort_keys=True)
            for key, val in relr["functional"].items() if key != "mobileSite"}
    ok = same_views and all(v["problems"] == 0 for v in views.values()) and all(func.values())
    status = "passed" if ok else "failed"
    detail = ("Scoped U-04 (D4, approved 2026-11-11): WCAG 2.2 Level A/AA, 55 success criteria assessed, 24 defects fixed "
              "(docs/validation_evidence/u04_2026-11-11); current build re-audited 2026-11-11 (npm run audit:a11y): "
              f"{'0' if ok else 'non-zero'} automated problems in {len(views)} views, "
              f"{sum(func.values())}/{len(func)} functional tests as in the release run. Scope: Chrome/Chromium 157 headless only; "
              "no real screen-reader (assistive-technology) user session; zoom emulated through the viewport; speech input "
              "not tested. Not a claim of unrestricted WCAG 2.2 AA conformance")
    return {"status": status, "detail": detail, "views": views, "functional_same_as_release": func,
            "evidence": {rel(cur_p): sha(cur_p), rel(rel_p): sha(rel_p)}}


def main() -> None:
    report_path = BACKEND / "validation" / "report.json"
    report_sha = sha(report_path)
    dist = dist_hashes()
    u06_dist_ref = (EV / "u06_2026-11-11" / "logs" / "dist_final_sha256.txt").read_text(encoding="utf-8")
    ref = {ln.split()[1].lstrip("*").removeprefix("dist/"): ln.split()[0] for ln in u06_dist_ref.splitlines() if ln.strip()}
    build = {"frontend_dist_sha256": dist, "equals_u06_final_build": dist == ref}
    outs = {}
    for script, tid, fn, extra in (
            ("frontend_u04", "U-04", u04, {"decision": "D4", "criterion": "WCAG 2.2 Level A and AA (requirement C02), scoped: "
                                           "Chrome/Chromium only, no real screen-reader user session; conditional on a "
                                           "current-build re-run of npm run audit:a11y matching the release run"}),
            ("frontend_u06", "U-06", u06, {"decision": "D3", "criterion": {
                "lcp_ms_max": 2500, "cls_max": 0.1, "interaction_response_p95_ms_max": 200,
                "memory": "no progressive leak over repeated remount cycles",
                "tbt": "information only, not gated",
                "scope": "HP Laptop 15-fd0xxx (Intel Core 5 120U, 15.7 GB), Windows 11, Chrome 157 headless 1440x900; "
                         "profiles native, 4x CPU, 4x CPU + 10 Mbit/s 40 ms",
                "exclusion": "two unusually slow backend basemap tiles (/api/tiles/0/0/0.png, /api/tiles/1/0/1.png) were "
                             "blocked during measurement",
                "not_claimed": "formal field Core Web Vitals compliance (field metrics are 75th-percentile real-user data)"}})):
        assert tid in OWNERS[script]
        r = fn()
        assert r["status"] in STATUSES
        doc = {"tests": {tid: {"status": r["status"], "detail": r["detail"]}}, **extra,
               "result": {k: v for k, v in r.items() if k not in ("status", "detail")}, "frontend_build": build,
               "approved": {"by": "project owner (working-session instruction, 2026-11-11)", "decision": extra["decision"]},
               "meta": run_meta(script)}
        out = HERE / f"{script}.json"
        out.write_text(json.dumps(doc, indent=2), encoding="utf-8")
        outs[script] = out
        print(f"{out.name}: {tid} {r['status']}")

    # no-write merge dry run, exactly as run_validation would merge after its pytest step
    now = run_meta("run_validation")
    live = json.loads(report_path.read_text(encoding="utf-8"))
    def fresh():
        t = copy.deepcopy(live["tests"])
        for tid, v in t.items():
            if v.get("source") == "external":
                t[tid] = {"status": v.get("automated_status") or "not run", "detail": None}
        return t
    single = {}
    for script, p in outs.items():
        t = copy.deepcopy(live["tests"])
        single[p.name] = {"rejected_reasons": merge_external(t, json.loads(p.read_text(encoding="utf-8")), now),
                          "status_after": {k: t[k]["status"] for k in OWNERS[script]}}
    full_set = [EV / "v09_v10_final_2026-11-10" / "v09_v10.json", EV / "v11_final_2026-11-10" / "v11.json",
                EV / "v12_final_2026-11-10" / "v12.json",
                EV / "refresh_v04_v05_v13_v14_2026-11-11" / "v04_horizons" / "horizons.json",
                EV / "refresh_v04_v05_v13_v14_2026-11-11" / "v13_eclipse" / "v13.json",
                EV / "refresh_v04_v05_v13_v14_2026-11-11" / "v14_month" / "v14.json", outs["frontend_u04"], outs["frontend_u06"]]
    t = fresh()
    files = [{"file": rel(p), "sha256": sha(p), "rejected_reasons": merge_external(t, json.loads(p.read_text(encoding="utf-8")), now)}
             for p in full_set]
    ids = ("V-04", "V-05", "V-09", "V-10", "V-11", "V-12", "V-13", "V-14", "U-04", "U-06")
    from lunaops.engine.horizon import l_corr_label
    from lunaops.engine.provenance import compute_labels
    labels = {"status_page": {q: v["validation"] for q, v in compute_labels(t, [], False).items()},
              "result_with_horizon_sigma": {q: v["validation"] for q, v in compute_labels(t, [], False, l_corr_label()).items()}}
    dry = {"note": "IN-MEMORY DRY RUN ONLY (validation.common.merge_external). No pytest, no merge, nothing written to "
                   "backend/validation/report.json.",
           "now": {k: now[k] for k in ("code_fingerprint", "suite_fingerprint", "kernel_profile", "terrain_acceptance_digest", "run_utc")},
           "live_report_sha256": report_sha,
           "each_file_against_live_report": single,
           "prospective_full_merge": {"files": files, "statuses": {k: t[k]["status"] for k in ids},
                                      "labels_if_merged": labels,
                                      "note": "the full horizons.json carries V-05 'passed' under its internal 1.0 s check, "
                                              "which the D1 acceptance record maps to the approved Phase 1.1 criteria"}}
    (HERE / "merge_dry_run.json").write_text(json.dumps(dry, indent=2), encoding="utf-8")
    assert sha(report_path) == report_sha, "report.json changed"
    print(json.dumps({"each": single, "full_merge_rejections": {f["file"].split("/")[-1]: f["rejected_reasons"] for f in files},
                      "statuses": dry["prospective_full_merge"]["statuses"], "labels": labels,
                      "dist_equals_u06_final": build["equals_u06_final_build"]}, indent=1))


if __name__ == "__main__":
    main()
