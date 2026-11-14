"""Post-merge verification for post-Phase 5 official report merge.
Verifies all 8 merged external results, fingerprints, report schema, and preservation of unrelated entries.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EV = HERE.parent
REPO = HERE.parent.parent.parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

from validation.common import OWNERS, run_meta

BEFORE_SHA = "5135efe88e5feb0fd36e0230ecba9f2d2b99322a70e1e69e822e13def69df53f"
EXPECT_STATUS = {
    "V-04": ("passed", "horizons_compare"),
    "V-05": ("passed", "horizons_compare"),
    "V-09": ("not run", "v09_v10_avgvisib"),
    "V-10": ("not run", "v09_v10_avgvisib"),
    "V-11": ("passed", "v11_psr"),
    "V-12": ("passed", "v12_lroc"),
    "V-13": ("passed", "v13_eclipse"),
    "V-14": ("passed", "v14_month"),
    "U-04": ("passed", "frontend_u04"),
    "U-06": ("passed", "frontend_u06"),
}

def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    report_path = BACKEND / "validation" / "report.json"
    report_before_path = HERE / "report_before.json"

    assert report_before_path.exists(), "Missing report_before.json"
    assert sha(report_before_path) == BEFORE_SHA, "report_before.json hash mismatch"

    report_after_sha = sha(report_path)
    assert report_after_sha != BEFORE_SHA, "report.json was not updated!"

    rep = json.loads(report_path.read_text(encoding="utf-8"))
    rep_before = json.loads(report_before_path.read_text(encoding="utf-8"))

    now = run_meta("run_validation")

    # 1. Metadata and fingerprints
    assert rep["code_fingerprint"] == now["code_fingerprint"]
    assert rep["suite_fingerprint"] == now["suite_fingerprint"]
    assert rep["kernel_profile"] == "production"
    assert rep["pytest_exit_code"] == 0, f"pytest exit code was {rep.get('pytest_exit_code')}"
    assert rep.get("rejected_merges") == {}, f"Rejected merges: {rep.get('rejected_merges')}"

    # 2. Check merged test entries
    tests = rep["tests"]
    merged_checks = {}
    for tid, (exp_st, exp_script) in EXPECT_STATUS.items():
        val = tests.get(tid)
        assert val is not None, f"Missing test {tid}"
        assert val.get("status") == exp_st, f"{tid}: expected status {exp_st}, got {val.get('status')}"
        assert val.get("source") == "external", f"{tid}: expected source external, got {val.get('source')}"
        assert val.get("script") == exp_script, f"{tid}: expected script {exp_script}, got {val.get('script')}"
        merged_checks[tid] = {
            "status": val["status"],
            "script": val["script"],
            "detail": val.get("detail"),
            "run_utc": val.get("run_utc"),
        }

    # 3. Check preservation of unrelated entries
    unrelated_diffs = []
    for tid, val_b in rep_before["tests"].items():
        if tid in EXPECT_STATUS:
            continue
        val_a = tests.get(tid)
        if val_a != val_b:
            unrelated_diffs.append((tid, val_b, val_a))

    print(f"Unrelated tests checked: {len(rep_before['tests']) - len(EXPECT_STATUS)}")
    print(f"Unrelated tests changed: {len(unrelated_diffs)}")
    assert len(unrelated_diffs) == 0, f"Unrelated tests modified: {unrelated_diffs[:5]}"

    # Save copy of report_after.json
    (HERE / "report_after.json").write_text(json.dumps(rep, indent=2), encoding="utf-8")

    verification = {
        "report_before_sha256": BEFORE_SHA,
        "report_after_sha256": report_after_sha,
        "run_utc": rep["run_utc"],
        "code_fingerprint": rep["code_fingerprint"],
        "suite_fingerprint": rep["suite_fingerprint"],
        "pytest_exit_code": rep["pytest_exit_code"],
        "rejected_merges": rep["rejected_merges"],
        "merged_tests_verified": merged_checks,
        "unrelated_tests_identical_count": len(rep_before["tests"]) - len(EXPECT_STATUS),
        "unrelated_tests_diff_count": len(unrelated_diffs),
        "all_checks_passed": True,
    }

    ver_path = HERE / "verification.json"
    ver_path.write_text(json.dumps(verification, indent=2), encoding="utf-8")
    print(f"Verification successfully completed and written to {ver_path}")
    print(f"New Official Report SHA-256: {report_after_sha}")

if __name__ == "__main__":
    main()

