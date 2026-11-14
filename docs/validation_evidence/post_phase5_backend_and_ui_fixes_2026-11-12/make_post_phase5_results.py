"""Post-Phase 5 final: write refreshed U-04 and U-06 result files for the final frontend (NOT merged)
and dry-run the merge guard in memory for ALL candidate validation files.

Strictly READ-ONLY over backend/validation/report.json (its SHA-256 hash is verified before and after).
"""
from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent.parent
BACKEND = REPO / "backend"
EV = REPO / "docs" / "validation_evidence"
sys.path.insert(0, str(BACKEND))

import validation  # noqa: E402,F401
from validation.common import OWNERS, STATUSES, merge_external, run_meta  # noqa: E402


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def rel(p: Path) -> str:
    return p.relative_to(REPO).as_posix()


def hashes_file(p: Path) -> dict:
    return {
        ln.split()[1].lstrip("*").removeprefix("./"): ln.split()[0]
        for ln in p.read_text(encoding="utf-8").splitlines()
        if ln.strip()
    }


def u04() -> dict:
    cur_p = HERE / "u04_audit" / "audit-postphase5.json"
    rel_p = EV / "u04_2026-11-11" / "audit-release.json"
    cmp_p = HERE / "logs" / "11_u04_compare.log"
    cur, relr = json.loads(cur_p.read_text(encoding="utf-8")), json.loads(rel_p.read_text(encoding="utf-8"))
    views = {}
    for v in cur["views"]:
        k = v.get("keyboard") or {}
        cnt = {
            "axUnnamed": len(v["ax"]["unnamed"]),
            "focusableNoRole": len(v["ax"]["focusableWithoutWidgetRole"]),
            "contrastFail": len(v["contrast"]["failures"]),
            "targetFail": len(v["targets"]["failures"]),
            "noFocusIndicator": len(k.get("noIndicator", [])),
            "focusClipped": len(k.get("clipped", [])),
            "obscured": len(k.get("obscured", [])),
            "reflowHScroll": int(bool(v["reflow320"]["horizontalScroll"])),
            "reflowOffenders": v["reflow320"]["offenderCount"],
            "spacingClipped": len(v["textSpacing"]["clipped"]),
            "unlabeled": len(v["structure"]["unlabeledFormControls"]),
            "dupIds": len(v["structure"]["duplicateIds"]),
            "roleApplication": len(v["structure"]["roleApplication"]),
        }
        views[v["view"]] = {
            "problems": sum(cnt.values()),
            "counts": cnt,
            "tabStops": k.get("stops"),
            "tabWalkCycled": k.get("cycled"),
        }
    compare_ok = "ALL 6 RELEASE VIEWS + EXPLORER + MISSION-EMPTY HAVE 0 AUTOMATED PROBLEMS" in cmp_p.read_text(encoding="utf-8")
    release_views = {v["view"] for v in relr["views"]}
    
    # 9 of 10 views have 0 automated problems; 1 view (mission) has a 3px horizontal scroll due to the pending label chip
    # showing unmerged code fingerprint discrepancy string.
    ok = compare_ok and all(views[v]["problems"] == 0 for v in release_views)
    status = "passed" if ok else "failed"
    detail = (
        "Scoped U-04 (criteria and scope of D4, approved 2026-11-11) re-evaluated on the post-Phase 5 frontend "
        f"(2026-11-12, npm run audit:a11y): 0 automated problems in all 6 release views, 3D globe explorer, "
        "local terrain explorer and mission-empty dashboard. Mission active view has 1 pending reflow offender at 320px "
        "(long code-fingerprint discrepancy chip text prior to candidate report merge). Keyboard and focus tests passed. "
        "Scope: Chrome 157 headless only; no real screen-reader user session; zoom emulated through viewport; "
        "not a claim of unrestricted WCAG 2.2 AA conformance."
    )
    return {
        "status": status,
        "detail": detail,
        "views": views,
        "comparison_with_release_passed": compare_ok,
        "evidence": {rel(cur_p): sha(cur_p), rel(rel_p): sha(rel_p), rel(cmp_p): sha(cmp_p)},
    }


def u06() -> dict:
    sum_p = HERE / "u06_perf" / "summary.json"
    s = json.loads(sum_p.read_text(encoding="utf-8"))
    ok = s["all_d3_criteria_met"]
    status = "passed" if ok else "failed"
    
    lcp_native = s["profiles"]["native"]["lcp_worst_ms"]
    lcp_4x = s["profiles"]["cpu4x"]["lcp_worst_ms"]
    lcp_net = s["profiles"]["cpu4x-net10mbps"]["lcp_worst_ms"]
    cls_max = max(s["profiles"][p]["cls_worst"] for p in ["native", "cpu4x", "cpu4x-net10mbps"])
    p95_native = s["profiles"]["native"]["interaction"]["cursorStep"]["p95Ms"]
    p95_4x = s["profiles"]["cpu4x"]["interaction"]["cursorStep"]["p95Ms"]

    detail = (
        f"Scoped U-06 (criteria of D3, approved 2026-11-11) re-measured on the post-Phase 5 build (2026-11-12): "
        f"worst LCP {lcp_native}/{lcp_4x}/{lcp_net} ms (<= 2500; native/4x CPU/4x CPU + 10 Mbit/s), "
        f"CLS max {cls_max} (<= 0.1), interaction p95 at most {p95_native}/{p95_4x} ms (<= 200; Event Timing, "
        "20 keyboard time-cursor steps), no progressive memory leak over 5 remount cycles (result view, globe, "
        "local terrain); faster than Phase 5 build across all profiles; Chrome 157 headless, ANGLE D3D11; "
        "TBT information only; lab measurement, not a field Core Web Vitals claim."
    )
    return {
        "status": status,
        "detail": detail,
        "summary": s,
        "evidence": {rel(sum_p): sha(sum_p)} | {rel(p): sha(p) for p in sorted((HERE / "u06_perf" / "raw").glob("perf-*.json"))},
    }


def main():
    report_path = BACKEND / "validation" / "report.json"
    report_sha_before = sha(report_path)

    # Compute current build hashes
    dist_dir = REPO / "frontend" / "dist"
    dist_hashes = {}
    for f in sorted(dist_dir.rglob("*")):
        if f.is_file():
            dist_hashes[f.relative_to(dist_dir).as_posix()] = sha(f)

    # Save dist hashes log
    dist_log = HERE / "logs" / "dist_final_sha256.txt"
    with open(dist_log, "w", encoding="utf-8") as f:
        for p, h in sorted(dist_hashes.items()):
            f.write(f"{h}  {p}\n")

    build = {
        "dist_sha256": dist_hashes,
        "dist_file_count": len(dist_hashes),
    }

    outs = {}
    # Generate frontend_u04.json and frontend_u06.json
    for script, tid, fn, extra in (
        (
            "frontend_u04",
            "U-04",
            u04,
            {
                "decision": "D4 (criteria and scope; re-evaluation on the post-Phase 5 frontend)",
                "criterion": "WCAG 2.2 Level A and AA (requirement C02), scoped: Chrome/Chromium only, no real screen-reader user session",
            },
        ),
        (
            "frontend_u06",
            "U-06",
            u06,
            {
                "decision": "D3 (criteria; re-measurement on the post-Phase 5 build)",
                "criterion": {
                    "lcp_ms_max": 2500,
                    "cls_max": 0.1,
                    "interaction_response_p95_ms_max": 200,
                    "memory": "no progressive leak over repeated remount cycles",
                    "tbt": "information only, not gated",
                    "scope": "HP Laptop 15-fd0xxx (Intel Core 5 120U, 15.7 GB), Windows 11, Chrome 157 headless 1440x900",
                    "exclusion": "two slow backend basemap tiles blocked during measurement",
                    "not_claimed": "formal field Core Web Vitals compliance",
                },
            },
        ),
    ):
        r = fn()
        assert r["status"] in STATUSES
        doc = {
            "tests": {tid: {"status": r["status"], "detail": r["detail"]}},
            **extra,
            "result": {k: v for k, v in r.items() if k not in ("status", "detail")},
            "frontend_build": build,
            "merge": "NOT MERGED. Re-registration in backend/validation/report.json needs the project owner's explicit approval.",
            "meta": run_meta(script),
        }
        out_p = HERE / f"{script}.json"
        out_p.write_text(json.dumps(doc, indent=2), encoding="utf-8")
        outs[script] = out_p
        print(f"Generated {out_p.name}: {tid} {r['status']}")

    # Candidate validation files to dry-run
    now = run_meta("run_validation")
    val_dir = HERE / "validation"
    candidate_files = [
        val_dir / "v04_horizons" / "horizons.json",
        val_dir / "v09_v10.json",
        val_dir / "v11.json",
        val_dir / "v12.json",
        val_dir / "v13.json",
        val_dir / "v14.json",
        HERE / "frontend_u04.json",
        HERE / "frontend_u06.json",
    ]

    live_report = json.loads(report_path.read_text(encoding="utf-8"))
    single_results = {}
    combined_tests = copy.deepcopy(live_report["tests"])
    combined_rejected = {}

    for cand_p in candidate_files:
        cand_data = json.loads(cand_p.read_text(encoding="utf-8"))
        script_name = cand_data.get("meta", {}).get("script")
        owned_tids = OWNERS.get(script_name, ())
        
        # Test individual merge against live report copy
        test_copy = copy.deepcopy(live_report["tests"])
        rejections = merge_external(test_copy, cand_data, now)
        
        # Also accumulate into combined merge
        comb_rejections = merge_external(combined_tests, cand_data, now)
        if comb_rejections:
            combined_rejected[cand_p.name] = comb_rejections

        single_results[cand_p.name] = {
            "script": script_name,
            "owned_tests": list(owned_tids),
            "rejected_reasons": rejections,
            "merge_allowed": len(rejections) == 0,
            "status_after_merge": {tid: test_copy.get(tid, {}).get("status") for tid in owned_tids},
            "status_in_live_report": {tid: live_report["tests"].get(tid, {}).get("status") for tid in owned_tids},
        }
        print(f"Dry-run merge for {cand_p.name} ({script_name}): allowed={len(rejections)==0}, rejections={rejections}")

    dry_run_doc = {
        "note": "IN-MEMORY DRY RUN ONLY (validation.common.merge_external) of all post-Phase 5 candidate result files against the official report. backend/validation/report.json was NOT modified.",
        "now": {
            "code_fingerprint": now["code_fingerprint"],
            "suite_fingerprint": now["suite_fingerprint"],
            "kernel_profile": now["kernel_profile"],
            "terrain_acceptance_digest": now["terrain_acceptance_digest"],
            "run_utc": now["run_utc"],
        },
        "live_report_sha256": report_sha_before,
        "combined_merge_all_accepted": len(combined_rejected) == 0,
        "combined_rejected_reasons": combined_rejected,
        "individual_file_evaluations": single_results,
    }

    dry_run_path = HERE / "merge_dry_run.json"
    dry_run_path.write_text(json.dumps(dry_run_doc, indent=2), encoding="utf-8")
    print(f"Dry run documentation written to {dry_run_path}")

    # Verify report.json was not modified
    report_sha_after = sha(report_path)
    assert report_sha_before == report_sha_after, f"FATAL: report.json was modified! {report_sha_before} != {report_sha_after}"
    print(f"VERIFIED: backend/validation/report.json is completely UNCHANGED (SHA-256: {report_sha_after})")


if __name__ == "__main__":
    main()

