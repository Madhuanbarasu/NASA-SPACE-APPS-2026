"""Phase 7 INTERIM validation report (owner instruction 2026-11-14: full pytest suite skipped; "if the official report
generator requires the full suite, preserve that requirement and generate an interim report instead").

backend/validation/report.json is NOT written: validation.run_validation requires a complete pytest run, which was
stopped by the owner. This script builds the same report structure in the evidence folder with the project's own code:
  * every test starts as "not run" (as in run_validation); NO pytest result is recorded as passed;
  * external results are merged with validation.common.merge_external (same guard: code and suite fingerprints,
    kernels, owner script must match), so a stale or mismatched result is rejected, not used;
  * pytest_exit_code is null and pytest_status explains why, so lunaops.engine.provenance.label_blockers withholds
    every Validated label;
  * labels are computed with provenance.compute_labels from this interim report (what the application WOULD show if
    this file were installed), and separately from the official report currently installed (what it shows now).
Usage (from backend/): python <this> <partial pytest summary json> <out json> --merge <file> [--merge ...]
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

BACKEND = Path.cwd()
sys.path.insert(0, str(BACKEND))
from validation.common import merge_external, run_meta  # noqa: E402
from validation.run_validation import ALL_IDS  # noqa: E402
from lunaops.engine.kernels import load  # noqa: E402
from lunaops.engine import provenance as PV  # noqa: E402

partial = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
out = Path(sys.argv[2])
merges = [sys.argv[i + 1] for i, a in enumerate(sys.argv) if a == "--merge"]

now = run_meta("run_validation")
tests = {i: {"status": "not run", "detail": None} for i in ALL_IDS}
rejected, merged = {}, {}
for m in merges:
    doc = json.loads(Path(m).read_text(encoding="utf-8"))
    why = merge_external(tests, doc, now)
    if why:
        rejected[m] = why
    else:
        merged[m] = {"sha256": hashlib.sha256(Path(m).read_bytes()).hexdigest(), "tests": sorted(doc["tests"])}
ks = load()
report = {"INTERIM": "Interim Phase 7 report, NOT the official validation report (backend/validation/report.json is unchanged). "
                     "The full pytest suite was not completed (stopped on the owner's instruction), so no Validated label "
                     "may be derived from this file.",
          "run_utc": now["run_utc"], "code_version": PV.code_version(), "code_fingerprint": now["code_fingerprint"],
          "suite_fingerprint": now["suite_fingerprint"], "kernel_profile": ks.profile,
          "kernels": [{"name": f["name"], "sha256": f["sha256"]} for f in ks.files],
          "pytest_exit_code": None, "pytest_status": partial, "tests": tests, "merged": merged, "rejected_merges": rejected,
          "terrain_products": PV.terrain_products_record(), "label_rules_digest": PV.label_rules_digest()}

blk_interim = PV.label_blockers(report)
lab_interim = PV.compute_labels(tests, blk_interim, synthetic=False, report_products=report["terrain_products"])
official = PV.validation_report()
blk_off = PV.label_blockers(official)
lab_off = PV.compute_labels((official or {}).get("tests", {}), blk_off, synthetic=False,
                            report_products=(official or {}).get("terrain_products"))
report["label_check"] = {
    "interim_report": {"blockers": blk_interim, "labels": lab_interim},
    "official_report_installed": {"sha256": PV.report_digest(), "code_fingerprint": (official or {}).get("code_fingerprint"),
                                  "suite_fingerprint": (official or {}).get("suite_fingerprint"),
                                  "blockers": blk_off, "labels": lab_off}}
out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
counts = {}
for v in tests.values():
    counts[v["status"]] = counts.get(v["status"], 0) + 1
print("interim report:", out, counts)
print("rejected merges:", rejected or "none")
for k in ("V-04", "V-05", "V-09", "V-10", "V-11", "V-12", "V-13", "V-14", "U-04", "U-06"):
    print(f"  {k}: {tests[k]['status']}")
def validated(labs):
    return sorted(q for q, v in labs.items() if (v.get("label") if isinstance(v, dict) else v) == "Validated")
print("Validated labels from interim report:", validated(lab_interim), "| blockers:", blk_interim)
print("Validated labels from installed official report:", validated(lab_off), "| blockers:", blk_off)
