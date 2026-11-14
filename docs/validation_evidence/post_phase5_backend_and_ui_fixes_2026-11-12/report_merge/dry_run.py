"""Pre-merge safety check and in-memory dry run for post-Phase 5 official report merge.
Verifies all 8 candidate files, hashes, fingerprints, and merge_external guard.
"""
from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EV = HERE.parent
REPO = HERE.parent.parent.parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

from validation.common import OWNERS, merge_external, run_meta

CANDIDATES = [
    ("horizons.json", EV / "validation" / "v04_horizons" / "horizons.json"),
    ("v09_v10.json", EV / "validation" / "v09_v10.json"),
    ("v11.json", EV / "validation" / "v11.json"),
    ("v12.json", EV / "validation" / "v12.json"),
    ("v13.json", EV / "validation" / "v13.json"),
    ("v14.json", EV / "validation" / "v14.json"),
    ("frontend_u04.json", EV / "frontend_u04.json"),
    ("frontend_u06.json", EV / "frontend_u06.json"),
]

def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    report_path = BACKEND / "validation" / "report.json"
    report_sha = sha(report_path)
    assert report_sha.startswith("5135efe8"), f"Unexpected report hash: {report_sha}"

    now = run_meta("run_validation")
    expected_code_fp = "84cbd4ea34f6606abcd32e02df295f204cb97ca9bef3d9a4d455b4557c831109"
    expected_suite_fp = "1632af16763dda4e27909a9af3d2fdd903b0d58951faacded72c4cf06d75eabc"
    expected_terrain_digest = "e48eb8ed0ca2003c2769c60932323dbce34385e4eac2a675f076e13bbd943dce"

    assert now["code_fingerprint"] == expected_code_fp
    assert now["suite_fingerprint"] == expected_suite_fp
    assert now["terrain_acceptance_digest"] == expected_terrain_digest

    live_report = json.loads(report_path.read_text(encoding="utf-8"))
    candidate_records = {}
    combined_tests = copy.deepcopy(live_report["tests"])
    combined_rejections = {}

    for name, p in CANDIDATES:
        assert p.exists(), f"Candidate missing: {p}"
        file_sha = sha(p)
        data = json.loads(p.read_text(encoding="utf-8"))
        meta = data.get("meta", {})

        # Verify fingerprints
        assert meta.get("code_fingerprint") == expected_code_fp, f"{name}: bad code_fingerprint"
        assert meta.get("suite_fingerprint") == expected_suite_fp, f"{name}: bad suite_fingerprint"
        assert meta.get("terrain_acceptance_digest") == expected_terrain_digest, f"{name}: bad terrain_acceptance_digest"

        script = meta.get("script")
        owned = OWNERS.get(script, ())

        # Test merge against live report copy
        test_copy = copy.deepcopy(live_report["tests"])
        rej_single = merge_external(test_copy, data, now)
        rej_comb = merge_external(combined_tests, data, now)
        if rej_comb:
            combined_rejections[name] = rej_comb

        candidate_records[name] = {
            "path": str(p.relative_to(REPO)).replace("\\", "/"),
            "sha256": file_sha,
            "script": script,
            "owned_tests": list(owned),
            "rejections": rej_single,
            "allowed": len(rej_single) == 0,
        }
        print(f"Candidate {name:20s}: sha256={file_sha[:16]}... allowed={len(rej_single)==0}")

    dry_run = {
        "report_before_sha256": report_sha,
        "now": {
            "code_fingerprint": now["code_fingerprint"],
            "suite_fingerprint": now["suite_fingerprint"],
            "kernel_profile": now["kernel_profile"],
            "terrain_acceptance_digest": now["terrain_acceptance_digest"],
            "run_utc": now["run_utc"],
        },
        "all_eight_pass_merge_guard": len(combined_rejections) == 0,
        "combined_rejections": combined_rejections,
        "candidates": candidate_records,
    }

    out_file = HERE / "dry_run.json"
    out_file.write_text(json.dumps(dry_run, indent=2), encoding="utf-8")
    print(f"Pre-merge dry run passed! Written to {out_file}")
    assert len(combined_rejections) == 0, f"Rejections found: {combined_rejections}"

if __name__ == "__main__":
    main()
