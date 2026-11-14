"""Run the automated validation suite and archive backend/validation/report.json.

    cd backend && python -m validation.run_validation

Test names map to blueprint IDs (test_V02a_... -> V-02a). The report records the
code version and kernel profile; results are labelled Validated only when the
report shows passing tests for the same code version and the production kernels.
Tests that need external services (V-04, V-05 Horizons; V-09 to V-13 PGDA/LROC/
eclipse references) are run by their own scripts in this folder and merged in
with --merge <file>.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parent


# the kernel set is selected in validation/__init__.py (production if installed, else demo)

ALL_IDS = ["V-01", "V-02a", "V-02b", "V-02c", "V-02d", "V-02e", "V-03", "V-04", "V-05", "V-06", "V-07", "V-08",
           "V-08b", "V-09", "V-10", "V-11", "V-12", "V-13", "V-14", "U-01", "U-02", "U-03", "U-04", "U-05", "U-06", "U-07"]


def test_id(name: str) -> str | None:
    m = re.match(r"test_([VU])(\d\d)([a-f]?)", name)
    if not m:
        return None
    return f"{m.group(1)}-{m.group(2)}{m.group(3)}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--merge", action="append", default=[], help="JSON results from external validation scripts")
    args = ap.parse_args()
    xml = Path(tempfile.mkstemp(suffix=".xml")[1])
    proc = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests", f"--junitxml={xml}"],
                          cwd=BACKEND)
    tests: dict[str, dict] = {i: {"status": "not run", "detail": None} for i in ALL_IDS}
    if not xml.exists() or xml.stat().st_size == 0:
        sys.exit("pytest produced no JUnit report; nothing was recorded")
    seen: dict[str, list] = {}
    for case in ET.parse(xml).getroot().iter("testcase"):
        tid = test_id(case.get("name", ""))
        if not tid:
            # tests without a blueprint ID (label integrity, merge guard, terrain registry) still gate the
            # report through pytest_exit_code; record them so a failure is visible
            tid = "other:" + case.get("name", "?")
        st, detail = "passed", None
        for child in case:
            if child.tag in ("failure", "error"):
                st, detail = "failed", (child.get("message") or "")[:300]
            elif child.tag == "skipped":
                st, detail = "skipped", (child.get("message") or "")[:300]
        seen.setdefault(tid, []).append((st, detail))
    for tid, results in seen.items():
        sts = [r[0] for r in results]
        if "failed" in sts:
            tests[tid] = {"status": "failed", "detail": next(d for s_, d in results if s_ == "failed")}
        elif "passed" in sts:
            tests[tid] = {"status": "passed", "detail": f"{sts.count('passed')} case(s)"}
        else:
            tests[tid] = {"status": "skipped", "detail": results[0][1]}
    sys.path.insert(0, str(BACKEND))
    from validation.common import merge_external, run_meta
    from lunaops.engine.kernels import load
    from lunaops.engine.provenance import code_version, label_rules_digest, terrain_products_record
    now = run_meta("run_validation")
    rejected = {}
    for m in args.merge:
        why = merge_external(tests, json.loads(Path(m).read_text()), now)
        if why:
            rejected[m] = why
            print(f"NOT merged {m}: " + "; ".join(why))
    ks = load()
    report = {"run_utc": now["run_utc"], "code_version": code_version(), "code_fingerprint": now["code_fingerprint"],
              "suite_fingerprint": now["suite_fingerprint"], "kernel_profile": ks.profile,
              "kernels": [{"name": f["name"], "sha256": f["sha256"]} for f in ks.files],
              "pytest_exit_code": proc.returncode, "tests": tests, "rejected_merges": rejected,
              # terrain the report covers: a result's terrain-dependent labels can be Validated only for these
              "terrain_products": terrain_products_record(), "label_rules_digest": label_rules_digest(),
              "note": "U-04 (accessibility) and U-06 (performance) are run with frontend/scripts and recorded here via --merge."}
    (HERE / "report.json").write_text(json.dumps(report, indent=2))
    counts = {}
    for v in tests.values():
        counts[v["status"]] = counts.get(v["status"], 0) + 1
    print("Validation report written:", HERE / "report.json", counts)


if __name__ == "__main__":
    main()
