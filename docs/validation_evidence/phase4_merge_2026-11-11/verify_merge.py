"""Verify the Phase 4 validation merge (read-only; writes only verification.json next to this file).

    cd backend && .venv/Scripts/python.exe ../docs/validation_evidence/phase4_merge_2026-11-11/verify_merge.py

Checks the new backend/validation/report.json against the expectations approved for the six-file merge, compares
it with report_before.json, and computes the labels with the engine's own rule (provenance.compute_labels).
Exit code 0 only if every check holds.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

BACKEND = Path.cwd()
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND))

import validation  # noqa: E402,F401  (kernel-set selection)
from validation.common import run_meta  # noqa: E402

EXPECT = {  # test ID -> (status, external source script or None for automated only)
    "V-04": ("passed", "horizons_compare"), "V-05": ("not run", None),
    "V-09": ("not run", "v09_v10_avgvisib"), "V-10": ("not run", "v09_v10_avgvisib"),
    "V-11": ("passed", "v11_psr"), "V-12": ("passed", "v12_lroc"),
    "V-13": ("passed", "v13_eclipse"), "V-14": ("passed", "v14_month"),
    "U-04": ("not run", None), "U-06": ("not run", None)}
MUST_NOT_PASS = ("V-05", "V-09", "V-10", "U-04", "U-06")
BEFORE_SHA = "00d2cda1bf3fe38fe98cc8a76e92acabdf9cb771ab900119750203586b15c239"


def main() -> int:
    from lunaops import ALGORITHM_VERSION
    from lunaops.engine.provenance import compute_labels, label_blockers, label_rules_digest

    rp = BACKEND / "validation" / "report.json"
    rep_bytes = rp.read_bytes()
    rep = json.loads(rep_bytes)
    before = json.loads((HERE / "report_before.json").read_text())
    now = run_meta("run_validation")
    checks = []

    def check(name, ok, detail=""):
        checks.append({"check": name, "ok": bool(ok), "detail": detail})

    check("report_before.json SHA-256 is the original", hashlib.sha256((HERE / "report_before.json").read_bytes())
          .hexdigest() == BEFORE_SHA, BEFORE_SHA)
    check("report.json was rewritten by this run", hashlib.sha256(rep_bytes).hexdigest() != BEFORE_SHA,
          hashlib.sha256(rep_bytes).hexdigest())
    check("pytest exit code 0", rep.get("pytest_exit_code") == 0, str(rep.get("pytest_exit_code")))
    check("zero rejected merges", rep.get("rejected_merges") == {}, json.dumps(rep.get("rejected_merges")))
    check("code fingerprint = current build", rep.get("code_fingerprint") == now["code_fingerprint"],
          rep.get("code_fingerprint"))
    check("suite fingerprint = current build", rep.get("suite_fingerprint") == now["suite_fingerprint"],
          rep.get("suite_fingerprint"))
    check("kernel profile production", rep.get("kernel_profile") == "production", rep.get("kernel_profile"))
    check("kernel SHA-256 = loaded kernels",
          sorted(k["sha256"] for k in rep.get("kernels", [])) == sorted(now["kernels"]), f"{len(rep.get('kernels', []))} files")
    check("label rules digest = current", rep.get("label_rules_digest") == label_rules_digest(), rep.get("label_rules_digest"))
    check("terrain products recorded", bool(rep.get("terrain_products")), f"{len(rep.get('terrain_products') or [])} products")
    check("terrain products unchanged vs before", rep.get("terrain_products") == before.get("terrain_products"))
    check("terrain acceptance digest (current) unchanged", now["terrain_acceptance_digest"] ==
          "e48eb8ed0ca2003c2769c60932323dbce34385e4eac2a675f076e13bbd943dce", now["terrain_acceptance_digest"])
    check("algorithm version 1.5.0", ALGORITHM_VERSION == "1.5.0", ALGORITHM_VERSION)
    check("no report-level label blockers", label_blockers(rep) == [], json.dumps(label_blockers(rep)))
    t = rep["tests"]
    for tid, (st, script) in EXPECT.items():
        got = t.get(tid, {})
        ok = got.get("status") == st and (script is None or (got.get("source") == "external" and got.get("script") == script))
        check(f"{tid} = {st}" + (f" (external, {script})" if script else ""), ok,
              f"status={got.get('status')} source={got.get('source')} script={got.get('script')} "
              f"external={got.get('external_status')} automated={got.get('automated_status')}")
    for tid in MUST_NOT_PASS:
        check(f"{tid} not marked passed", t.get(tid, {}).get("status") != "passed", t.get(tid, {}).get("status"))
    failed = {k: v for k, v in t.items() if v.get("status") == "failed"}
    check("no failed entries (blueprint or other)", not failed, json.dumps(list(failed)))
    # every automated (non-external) blueprint status equals the previous report's
    changed = {k: (before["tests"].get(k, {}).get("status"), v.get("status")) for k, v in t.items()
               if k[:2] in ("V-", "U-") and v.get("source") != "external"
               and before["tests"].get(k, {}).get("status") != v.get("status")}
    check("automated blueprint statuses unchanged vs before", not changed, json.dumps(changed))
    counts = {}
    for v in t.values():
        counts[v["status"]] = counts.get(v["status"], 0) + 1
    diff = {k: {"before": before["tests"].get(k, {}).get("status"), "after": t[k]["status"]}
            for k in t if k[:2] in ("V-", "U-")}
    labels = compute_labels(t, label_blockers(rep), synthetic=False)
    check("every quantity label stays 'Pending validation'",
          all(v["validation"] == "Pending validation" for v in labels.values()),
          json.dumps({q: v["validation"] for q, v in labels.items()}))
    out = {"all_ok": all(c["ok"] for c in checks), "checks": checks, "status_counts": counts,
           "blueprint_status_before_after": diff,
           "labels": {q: {"validation": v["validation"], "reasons": v["reasons"]} for q, v in labels.items()},
           "report": {"sha256": hashlib.sha256(rep_bytes).hexdigest(), "run_utc": rep.get("run_utc")},
           "verified_utc": now["run_utc"]}
    (HERE / "verification.json").write_text(json.dumps(out, indent=2))
    for c in checks:
        print(("PASS " if c["ok"] else "FAIL ") + c["check"] + (f"  [{c['detail']}]" if c["detail"] else ""))
    print("status counts:", counts)
    print("ALL CHECKS OK" if out["all_ok"] else "SOME CHECKS FAILED")
    return 0 if out["all_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
