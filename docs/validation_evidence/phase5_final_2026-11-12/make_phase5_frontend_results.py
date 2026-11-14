"""Phase 5 final: write refreshed U-04 and U-06 result files for the final frontend (NOT merged) and dry-run the merge
guard in memory.

    cd backend && .venv/Scripts/python.exe ../docs/validation_evidence/phase5_final_2026-11-12/make_phase5_frontend_results.py

Same schema and owners as phase4_remaining_decisions_2026-11-11/make_frontend_results.py (validation.common.merge_external:
{"tests": {"<ID>": {"status", "detail"}}, "meta": run_meta("<owner>")}; OWNERS["frontend_u04"] = ("U-04",),
OWNERS["frontend_u06"] = ("U-06",)). Statuses are computed from this folder's evidence under the criteria approved on
2026-11-11 (D3, D4); nothing is measured here. Writes only frontend_u04_phase5.json, frontend_u06_phase5.json and
merge_dry_run_phase5.json in this folder. backend/validation/report.json is only read (its hash is checked before and
after). Merging these files into the official report needs the project owner's explicit approval; it is not done here.
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

import validation  # noqa: E402,F401
from validation.common import OWNERS, STATUSES, merge_external, run_meta  # noqa: E402


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def rel(p: Path) -> str:
    return p.relative_to(REPO).as_posix()


def hashes_file(p: Path) -> dict:
    return {ln.split()[1].lstrip("*").removeprefix("./"): ln.split()[0] for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()}


def u04() -> dict:
    cur_p = HERE / "u04_audit" / "audit-phase5final.json"
    rel_p = EV / "u04_2026-11-11" / "audit-release.json"
    cmp_p = HERE / "logs" / "11_u04_compare.log"
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
        views[v["view"]] = {"problems": sum(cnt.values()), "counts": cnt, "tabStops": k.get("stops"), "tabWalkCycled": k.get("cycled")}
    compare_ok = "U-04 RE-EVALUATION: NO AUTOMATED PROBLEM IN ANY VIEW" in cmp_p.read_text(encoding="utf-8")
    release_views = {v["view"] for v in relr["views"]}
    ok = release_views <= set(views) and all(v["problems"] == 0 for v in views.values()) and compare_ok
    status = "passed" if ok else "failed"
    detail = ("Scoped U-04 (criteria and scope of D4, approved 2026-11-11) re-evaluated on the final Phase 5 frontend "
              f"(2026-11-12, npm run audit:a11y): {'0' if ok else 'non-zero'} automated problems in {len(views)} views "
              "(the 6 release views plus the 3D globe, local terrain, mission dashboard and empty dashboard); release "
              "functional tests unchanged apart from documented Phase 5 additions (tab stops, panorama readout text); "
              "Phase 5 keyboard and focus tests passed (docs/validation_evidence/phase5_final_2026-11-12). Scope: Chrome 157 "
              "headless only; no real screen-reader (assistive-technology) user session; zoom emulated through the viewport; "
              "speech input not tested. Not a claim of unrestricted WCAG 2.2 AA conformance")
    return {"status": status, "detail": detail, "views": views, "comparison_with_release_passed": compare_ok,
            "evidence": {rel(cur_p): sha(cur_p), rel(rel_p): sha(rel_p), rel(cmp_p): sha(cmp_p)}}


def u06() -> dict:
    sets = {}
    for label in ("final", "repeat"):
        p = HERE / "u06_perf" / f"summary-{label}.json"
        sets[label] = (p, json.loads(p.read_text(encoding="utf-8")))
    ok = all(s["all_d3_criteria_met"] for _, s in sets.values())
    f = sets["final"][1]["profiles"]
    rp = sets["repeat"][1]["profiles"]
    lcp = lambda pr: max(x["profiles"][pr]["lcp_worst_ms"] for _, x in sets.values() if pr in x["profiles"])
    p95 = lambda pr: max(x["profiles"][pr]["interaction"]["cursorStep"]["p95Ms"] for _, x in sets.values()
                         if pr in x["profiles"] and isinstance(x["profiles"][pr].get("interaction"), dict))
    status = "passed" if ok else "failed"
    detail = (f"Scoped U-06 (criteria of D3, approved 2026-11-11) re-measured on the final Phase 5 build (2026-11-12): worst LCP "
              f"{lcp('native')}/{lcp('cpu4x')}/{lcp('cpu4x-net10mbps')} ms (<= 2500; native/4x CPU/4x CPU + 10 Mbit/s), CLS max 0 "
              f"(<= 0.1), interaction p95 at most {p95('native')}/{p95('cpu4x')} ms (<= 200; Event Timing, 20 keyboard time-cursor "
              "steps), no progressive memory leak over 5 remount cycles (result view; also globe and local terrain); two run "
              "sets (the first 4x CPU set ran under evident CPU contention and is kept); slower than the 2026-11-11 U-06 build "
              "(reported, cause not isolated); same laptop, Chrome 157 headless, profiles and tile exclusion as D3; TBT "
              "information only; lab measurement, not a field Core Web Vitals claim")
    return {"status": status, "detail": detail,
            "run_sets": {k: {"profiles": s["profiles"], "phase5_supplement": s["phase5_supplement"], "all_d3_criteria_met": s["all_d3_criteria_met"]}
                         for k, (_, s) in sets.items()},
            "evidence": {rel(p): sha(p) for p, _ in sets.values()} | {rel(p): sha(p) for p in sorted((HERE / "u06_perf" / "raw").glob("perf-*.json"))}}


def main() -> None:
    report_path = BACKEND / "validation" / "report.json"
    report_sha = sha(report_path)
    measured = hashes_file(HERE / "logs" / "dist_after_sha256.txt")
    release = hashes_file(HERE / "logs" / "dist_release_sha256.txt")
    added = sorted(set(release) - set(measured))
    build = {"measured_build_sha256": measured, "release_build_sha256": release,
             "release_equals_measured_except": added,
             "release_differs_only_by_added_text_files": all(release[k] == v for k, v in measured.items()) and set(added) <= {"OFL.txt", "THIRD_PARTY_NOTICES.txt"}}
    outs = {}
    for script, tid, fn, extra in (
            ("frontend_u04", "U-04", u04, {"decision": "D4 (criteria and scope; re-evaluation on the final Phase 5 frontend)",
                                           "criterion": "WCAG 2.2 Level A and AA (requirement C02), scoped: Chrome/Chromium only, no real screen-reader user session"}),
            ("frontend_u06", "U-06", u06, {"decision": "D3 (criteria; re-measurement on the final Phase 5 build)", "criterion": {
                "lcp_ms_max": 2500, "cls_max": 0.1, "interaction_response_p95_ms_max": 200,
                "memory": "no progressive leak over repeated remount cycles", "tbt": "information only, not gated",
                "scope": "HP Laptop 15-fd0xxx (Intel Core 5 120U, 15.7 GB), Windows 11, Chrome 157 headless 1440x900; "
                         "profiles native, 4x CPU, 4x CPU + 10 Mbit/s 40 ms",
                "exclusion": "two slow backend basemap tiles (/api/tiles/0/0/0.png, /api/tiles/1/0/1.png) blocked during measurement",
                "not_claimed": "formal field Core Web Vitals compliance"}})):
        assert tid in OWNERS[script]
        r = fn()
        assert r["status"] in STATUSES
        doc = {"tests": {tid: {"status": r["status"], "detail": r["detail"]}}, **extra,
               "result": {k: v for k, v in r.items() if k not in ("status", "detail")}, "frontend_build": build,
               "merge": "NOT MERGED. Re-registration in backend/validation/report.json needs the project owner's explicit approval.",
               "meta": run_meta(script)}
        out = HERE / f"{script}_phase5.json"
        out.write_text(json.dumps(doc, indent=2), encoding="utf-8")
        outs[script] = out
        print(f"{out.name}: {tid} {r['status']}")

    now = run_meta("run_validation")
    live = json.loads(report_path.read_text(encoding="utf-8"))
    single = {}
    for script, p in outs.items():
        t = copy.deepcopy(live["tests"])
        single[p.name] = {"rejected_reasons": merge_external(t, json.loads(p.read_text(encoding="utf-8")), now),
                          "status_after": {k: t[k]["status"] for k in OWNERS[script]},
                          "status_in_live_report": {k: live["tests"][k]["status"] for k in OWNERS[script]}}
    dry = {"note": "IN-MEMORY DRY RUN ONLY (validation.common.merge_external) of each Phase 5 result file against the live "
                   "report. No pytest, no merge, nothing written to backend/validation/report.json.",
           "now": {k: now[k] for k in ("code_fingerprint", "suite_fingerprint", "kernel_profile", "terrain_acceptance_digest", "run_utc")},
           "live_report_sha256": report_sha, "each_file_against_live_report": single}
    (HERE / "merge_dry_run_phase5.json").write_text(json.dumps(dry, indent=2), encoding="utf-8")
    assert sha(report_path) == report_sha, "report.json changed"
    print(json.dumps({"each": single, "release_differs_only_by_added_text_files": build["release_differs_only_by_added_text_files"],
                      "added": added, "report_sha256_unchanged": report_sha}, indent=1))


if __name__ == "__main__":
    main()
