"""Verify the Phase 4 final merge (read-only; writes only verification.json next to this file). Run from backend/.
Exit code 0 only if every check holds."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

BACKEND = Path.cwd()
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND))
import validation  # noqa: E402,F401
from validation.common import run_meta  # noqa: E402

BEFORE_SHA = "5e6c76d75eff6c3454f68edc76ab5e08f48733e3ad2cfff72eac3e55db812e7b"
EXPECT = {"V-04": ("passed", "horizons_compare"), "V-05": ("passed", "horizons_compare"),
          "V-09": ("not run", "v09_v10_avgvisib"), "V-10": ("not run", "v09_v10_avgvisib"),
          "V-11": ("passed", "v11_psr"), "V-12": ("passed", "v12_lroc"), "V-13": ("passed", "v13_eclipse"),
          "V-14": ("passed", "v14_month"), "U-04": ("passed", "frontend_u04"), "U-06": ("passed", "frontend_u06")}
NEWLY_PASSED_ALLOWED = {"V-05", "U-04", "U-06"}          # V-04 and V-13 were already passed in the 5e6c76d7 report


def main() -> int:
    from lunaops import ALGORITHM_VERSION
    from lunaops.engine.horizon import l_corr_label
    from lunaops.engine.provenance import compute_labels, label_blockers, label_rules_digest

    rp = BACKEND / "validation" / "report.json"
    rb = rp.read_bytes()
    rep = json.loads(rb)
    before = json.loads((HERE / "report_before.json").read_text())
    now = run_meta("run_validation")
    log = (HERE / "run_validation.log").read_text(encoding="utf-8", errors="replace")
    checks = []

    def check(name, ok, detail=""):
        checks.append({"check": name, "ok": bool(ok), "detail": str(detail)})

    m = re.search(r"(\d+) passed(?:, (\d+) skipped)?(?:, (\d+) warnings?)? in ([\d.]+)s", log)
    check("backup report_before.json is the original", hashlib.sha256((HERE / "report_before.json").read_bytes()).hexdigest() == BEFORE_SHA)
    check("report.json rewritten by this run", hashlib.sha256(rb).hexdigest() != BEFORE_SHA, hashlib.sha256(rb).hexdigest())
    check("run_validation exit 0", "# exit 0;" in log)
    check("pytest: 0 failed / 0 errors in output", m is not None and not re.search(r"\d+ (failed|error)", log), m.group(0) if m else "no summary")
    check("pytest exit code 0 in report", rep.get("pytest_exit_code") == 0, rep.get("pytest_exit_code"))
    check("no 'NOT merged' lines", "NOT merged" not in log)
    check("zero rejected merges", rep.get("rejected_merges") == {}, json.dumps(rep.get("rejected_merges")))
    check("algorithm 1.5.0", ALGORITHM_VERSION == "1.5.0")
    for k in ("code_fingerprint", "suite_fingerprint"):
        check(f"{k} = current build", rep.get(k) == now[k], rep.get(k))
    check("kernel profile production; SHA-256 = loaded", rep.get("kernel_profile") == "production"
          and sorted(x["sha256"] for x in rep["kernels"]) == sorted(now["kernels"]))
    check("terrain acceptance digest unchanged", now["terrain_acceptance_digest"].startswith("e48eb8ed"), now["terrain_acceptance_digest"])
    check("terrain products unchanged vs before", rep.get("terrain_products") == before.get("terrain_products"))
    check("label rules digest current", rep.get("label_rules_digest") == label_rules_digest())
    check("no report-level label blockers", label_blockers(rep) == [], label_blockers(rep))
    t = rep["tests"]
    for tid, (st, script) in EXPECT.items():
        g = t.get(tid, {})
        check(f"{tid} = {st} (external, {script})", g.get("status") == st and g.get("source") == "external" and g.get("script") == script,
              f"status={g.get('status')} script={g.get('script')} external={g.get('external_status')} automated={g.get('automated_status')}")
    check("no failed entry anywhere", not [k for k, v in t.items() if v["status"] == "failed"])
    newly = {k for k, v in t.items() if v["status"] == "passed" and before["tests"].get(k, {}).get("status") != "passed"}
    check("newly passed = exactly V-05, U-04, U-06 (no unsupported PASS)", newly == NEWLY_PASSED_ALLOWED, sorted(newly))
    changed_auto = {k: (before["tests"].get(k, {}).get("status"), v["status"]) for k, v in t.items()
                    if v.get("source") != "external" and before["tests"].get(k, {}).get("status") != v["status"]}
    check("automated (non-external) statuses unchanged vs before", not changed_auto, changed_auto)
    counts = {}
    for v in t.values():
        counts[v["status"]] = counts.get(v["status"], 0) + 1
    page = compute_labels(t, [], False)
    res = compute_labels(t, [], False, l_corr_label())
    exp_page = {"sun_earth_azel": "Validated", "horizon": "Validated", "disk_visibility": "Pending validation",
                "events": "Pending validation", "power_indicator": "Pending validation"}
    exp_res = dict(exp_page, horizon="Pending validation")
    check("labels (status page) follow engine rule as expected", {q: v["validation"] for q, v in page.items()} == exp_page,
          {q: v["validation"] for q, v in page.items()})
    check("labels (result with horizon sigma) keep L_corr limitation", {q: v["validation"] for q, v in res.items()} == exp_res,
          {q: v["validation"] for q, v in res.items()})
    out = {"all_ok": all(c["ok"] for c in checks), "checks": checks, "status_counts": counts,
           "pytest_summary": m.group(0) if m else None,
           "report": {"sha256": hashlib.sha256(rb).hexdigest(), "run_utc": rep.get("run_utc")},
           "statuses": {k: t[k]["status"] for k in EXPECT},
           "labels": {"status_page": {q: {"validation": v["validation"], "reasons": v["reasons"]} for q, v in page.items()},
                      "result_with_horizon_sigma": {q: {"validation": v["validation"], "reasons": v["reasons"]} for q, v in res.items()}}}
    (HERE / "verification.json").write_text(json.dumps(out, indent=2))
    for c in checks:
        print(("PASS " if c["ok"] else "FAIL ") + c["check"] + (f"  [{c['detail']}]" if c["detail"] else ""))
    print("status counts:", counts)
    print("ALL CHECKS OK" if out["all_ok"] else "SOME CHECKS FAILED")
    return 0 if out["all_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
