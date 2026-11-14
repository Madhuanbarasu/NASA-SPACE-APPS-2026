"""Phase 4 closure: prepare the eligible merge inputs and an in-memory merge preview. Writes nothing in backend/.

    cd backend && .venv/Scripts/python.exe ../docs/validation_evidence/phase4_closure_2026-11-11/scripts/prepare_merge.py

1. Derives merge_inputs/horizons_v04_only.json from the refreshed horizons.json by removing the V-05 entry from
   "tests" (V-05's proposed 1.0 s threshold is not approved, so V-05 must stay "not run"). Every other key,
   including "meta" and the V-05 measurements under "v05", is copied unchanged; "derived_from" records the
   source file and its SHA-256. horizons_compare owns V-04 and V-05, so a file reporting V-04 alone is valid
   for the merge guard.
2. Runs validation.common.merge_external IN MEMORY for every eligible file against a copy of the live report's
   tests, exactly as run_validation would after its pytest step, and writes merge_preview.json: per-file
   rejections and per-test status before/after. backend/validation/report.json is only read.

This is not run_validation: it runs no pytest and produces no report. The official merge is blocked
(see ../README.md, "Validation report").
"""
from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

BACKEND = Path.cwd()
REPO = BACKEND.parent
HERE = Path(__file__).resolve().parents[1]
EV = REPO / "docs" / "validation_evidence"
sys.path.insert(0, str(BACKEND))

import validation  # noqa: E402,F401  (kernel-set selection, as every validation script)
from validation.common import merge_external, run_meta  # noqa: E402

REFRESH = EV / "refresh_v04_v05_v13_v14_2026-11-11"
ELIGIBLE = [  # (path, why eligible)
    (EV / "v09_v10_final_2026-11-10" / "v09_v10.json", "already merged; must be re-merged by any new run_validation (status stays 'not run')"),
    (EV / "v11_final_2026-11-10" / "v11.json", "already merged; must be re-merged by any new run_validation"),
    (EV / "v12_final_2026-11-10" / "v12.json", "already merged; must be re-merged by any new run_validation"),
    (HERE / "merge_inputs" / "horizons_v04_only.json", "V-04 PASS (refresh 2026-11-11); V-05 removed"),
    (REFRESH / "v13_eclipse" / "v13.json", "V-13 PASS (refresh 2026-11-11)"),
    (REFRESH / "v14_month" / "v14.json", "V-14 full-form PASS (refresh 2026-11-11)"),
]
NOT_ELIGIBLE = {
    REFRESH / "v04_horizons" / "horizons.json": "carries V-05 'passed' under the unapproved 1.0 s threshold",
    "U-04": "no frontend_u04 result file exists; writing one (scoped PASS -> 'passed') is an acceptance decision not taken",
    "U-06": "no approved criterion; audit status BLOCKED (provisional measurements)",
}


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> None:
    report_path = BACKEND / "validation" / "report.json"
    report_sha_before = sha(report_path)
    src = REFRESH / "v04_horizons" / "horizons.json"
    h = json.loads(src.read_text())
    assert set(h["tests"]) == {"V-04", "V-05"} and h["tests"]["V-04"]["status"] == "passed"
    derived = copy.deepcopy(h)
    derived["tests"] = {"V-04": h["tests"]["V-04"]}
    derived["derived_from"] = {
        "file": "docs/validation_evidence/refresh_v04_v05_v13_v14_2026-11-11/v04_horizons/horizons.json",
        "sha256": sha(src),
        "change": "tests.V-05 removed (threshold not approved); nothing else changed",
        "by": "docs/validation_evidence/phase4_closure_2026-11-11/scripts/prepare_merge.py"}
    out = HERE / "merge_inputs" / "horizons_v04_only.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(derived, indent=2))

    now = run_meta("run_validation")
    live = json.loads(report_path.read_text())
    tests = copy.deepcopy(live["tests"])
    # what run_validation's merge starts from: automated statuses only (external entries are rebuilt by re-merging)
    for tid, v in tests.items():
        if v.get("source") == "external":
            tests[tid] = {"status": v.get("automated_status") or "not run", "detail": None}
    files = []
    for p, why in ELIGIBLE:
        rej = merge_external(tests, json.loads(p.read_text()), now)
        files.append({"file": p.relative_to(REPO).as_posix(), "sha256": sha(p), "why_eligible": why,
                      "rejected_reasons": rej, "merged": not rej})
    changed = {tid: {"live_report": live["tests"][tid]["status"], "after_eligible_merge": tests[tid]["status"]}
               for tid in tests if tid.startswith(("V-", "U-"))
               and (tests[tid]["status"] != live["tests"][tid]["status"] or tid in ("V-04", "V-05", "V-13", "V-14", "U-04", "U-06"))}
    preview = {
        "note": "IN-MEMORY PREVIEW ONLY. Not a validation report: no pytest was run, nothing was written to "
                "backend/validation/report.json. It shows what run_validation --merge would record for the eligible "
                "files, given the automated statuses in the live report (same code and suite fingerprints).",
        "now": {k: now[k] for k in ("code_fingerprint", "suite_fingerprint", "kernel_profile",
                                    "terrain_acceptance_digest", "run_utc")},
        "live_report": {"sha256": report_sha_before, "run_utc": live["run_utc"],
                        "code_fingerprint": live["code_fingerprint"], "suite_fingerprint": live["suite_fingerprint"],
                        "pytest_exit_code": live["pytest_exit_code"]},
        "eligible_files": files,
        "not_eligible": {str(k.relative_to(REPO).as_posix()) if isinstance(k, Path) else k: v
                         for k, v in NOT_ELIGIBLE.items()},
        "status_changes": changed,
        "derived_v04_only": {"file": out.relative_to(REPO).as_posix(), "sha256": sha(out)}}
    (HERE / "merge_preview.json").write_text(json.dumps(preview, indent=2))
    assert sha(report_path) == report_sha_before, "report.json changed"
    print(json.dumps({"files": [(f["file"].split("/")[-1], f["merged"], f["rejected_reasons"]) for f in files],
                      "status_changes": changed}, indent=1))


if __name__ == "__main__":
    main()
