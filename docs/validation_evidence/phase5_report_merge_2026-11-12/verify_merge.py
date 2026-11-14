"""Verify the Phase 5 U-04/U-06 report merge (read-only; writes only verification.json next to this file). Run from
backend/. Exit code 0 only if every check holds.

Expected: the regenerated report equals the previous one (2279606c…, kept as report_before.json) in every respect except
run_utc and the U-04 and U-06 entries, which must now carry the Phase 5 result files' detail and run_utc (status
"passed", source external, scripts frontend_u04 / frontend_u06)."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

BACKEND = Path.cwd()
HERE = Path(__file__).resolve().parent
EV = HERE.parent
sys.path.insert(0, str(BACKEND))
import validation  # noqa: E402,F401
from validation.common import run_meta  # noqa: E402

BEFORE_SHA = "2279606ceab9354b8616ba9216e12e89e399f34cfc3cbfcbd7502d12d077d376"
EXPECT = {"V-04": ("passed", "horizons_compare"), "V-05": ("passed", "horizons_compare"),
          "V-09": ("not run", "v09_v10_avgvisib"), "V-10": ("not run", "v09_v10_avgvisib"),
          "V-11": ("passed", "v11_psr"), "V-12": ("passed", "v12_lroc"), "V-13": ("passed", "v13_eclipse"),
          "V-14": ("passed", "v14_month"), "U-04": ("passed", "frontend_u04"), "U-06": ("passed", "frontend_u06")}
P5 = {"U-04": EV / "phase5_final_2026-11-12" / "frontend_u04_phase5.json", "U-06": EV / "phase5_final_2026-11-12" / "frontend_u06_phase5.json"}


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
    check("backup report_before.json is the original 2279606c…", hashlib.sha256((HERE / "report_before.json").read_bytes()).hexdigest() == BEFORE_SHA)
    check("report.json rewritten by this run", hashlib.sha256(rb).hexdigest() != BEFORE_SHA, hashlib.sha256(rb).hexdigest())
    check("run_validation exit 0", "# exit 0;" in log)
    check("pytest: 0 failed / 0 errors in output", m is not None and not re.search(r"\d+ (failed|error)", log), m.group(0) if m else "no summary")
    check("pytest: same counts as the previous merge (438 passed, 2 skipped)", m is not None and m.group(1) == "438" and m.group(2) == "2", m.group(0) if m else "")
    check("pytest exit code 0 in report", rep.get("pytest_exit_code") == 0, rep.get("pytest_exit_code"))
    check("no 'NOT merged' lines", "NOT merged" not in log)
    check("zero rejected merges", rep.get("rejected_merges") == {}, json.dumps(rep.get("rejected_merges")))
    check("algorithm 1.5.0", ALGORITHM_VERSION == "1.5.0")
    for k in ("code_fingerprint", "suite_fingerprint"):
        check(f"{k} = current build = previous report", rep.get(k) == now[k] == before.get(k), rep.get(k))
    check("kernel profile production; SHA-256 = loaded", rep.get("kernel_profile") == "production"
          and sorted(x["sha256"] for x in rep["kernels"]) == sorted(now["kernels"]))
    check("terrain acceptance digest unchanged", now["terrain_acceptance_digest"].startswith("e48eb8ed"), now["terrain_acceptance_digest"])
    top = sorted(k for k in set(rep) | set(before) if k not in ("run_utc", "tests") and rep.get(k) != before.get(k))
    check("report-level fields unchanged except run_utc (and tests)", not top, top)
    check("label rules digest current", rep.get("label_rules_digest") == label_rules_digest())
    check("no report-level label blockers", label_blockers(rep) == [], label_blockers(rep))
    t, tb = rep["tests"], before["tests"]
    check("same set of test entries", set(t) == set(tb), sorted(set(t) ^ set(tb)))
    check("every test status unchanged", all(t[k]["status"] == tb.get(k, {}).get("status") for k in t),
          {k: (tb.get(k, {}).get("status"), t[k]["status"]) for k in t if t[k]["status"] != tb.get(k, {}).get("status")})
    ext_changed = sorted(k for k, v in t.items() if (v.get("source") == "external" or tb.get(k, {}).get("source") == "external")
                         and k not in P5 and v != tb.get(k))
    check("external entries other than U-04/U-06 byte-identical to the previous report", not ext_changed, ext_changed)
    auto_detail = sorted(k for k, v in t.items() if v.get("source") != "external" and v != tb.get(k))
    check("automated entries identical to the previous report", not auto_detail, auto_detail)
    for tid, (st, script) in EXPECT.items():
        g = t.get(tid, {})
        check(f"{tid} = {st} (external, {script})", g.get("status") == st and g.get("source") == "external" and g.get("script") == script,
              f"status={g.get('status')} script={g.get('script')}")
    for tid, p in P5.items():
        d = json.loads(p.read_text(encoding="utf-8"))
        g = t[tid]
        check(f"{tid} now carries the Phase 5 result (detail and run_utc of {p.name})",
              g.get("detail") == d["tests"][tid]["detail"] and g.get("run_utc") == d["meta"]["run_utc"] and g.get("external_status") == "passed"
              and "Phase 5" in g.get("detail", ""), g.get("run_utc"))
        check(f"{tid} previous entry described the Phase 4 build", "Phase 5" not in tb[tid].get("detail", ""), tb[tid].get("run_utc"))
    counts = {}
    for v in t.values():
        counts[v["status"]] = counts.get(v["status"], 0) + 1
    counts_b = {}
    for v in tb.values():
        counts_b[v["status"]] = counts_b.get(v["status"], 0) + 1
    check("status counts unchanged (420 passed, 2 not run, 2 skipped)", counts == counts_b == {"passed": 420, "not run": 2, "skipped": 2}, counts)
    lab = lambda tests, s=None: {q: v["validation"] for q, v in (compute_labels(tests, [], False, s) if s else compute_labels(tests, [], False)).items()}
    check("labels (status page) identical to the previous report", lab(t) == lab(tb), lab(t))
    check("labels (result with horizon sigma) identical, L_corr limitation kept", lab(t, l_corr_label()) == lab(tb, l_corr_label()), lab(t, l_corr_label()))
    out = {"all_ok": all(c["ok"] for c in checks), "checks": checks, "status_counts": counts,
           "pytest_summary": m.group(0) if m else None,
           "report": {"sha256": hashlib.sha256(rb).hexdigest(), "run_utc": rep.get("run_utc"), "previous_sha256": BEFORE_SHA},
           "statuses": {k: t[k]["status"] for k in EXPECT},
           "u04_u06": {k: {kk: t[k].get(kk) for kk in ("status", "script", "run_utc", "detail")} for k in P5},
           "labels": {"status_page": lab(t), "result_with_horizon_sigma": lab(t, l_corr_label())}}
    (HERE / "verification.json").write_text(json.dumps(out, indent=2))
    for c in checks:
        print(("PASS " if c["ok"] else "FAIL ") + c["check"] + (f"  [{c['detail']}]" if c["detail"] else ""))
    print("status counts:", counts)
    print("ALL CHECKS OK" if out["all_ok"] else "SOME CHECKS FAILED")
    return 0 if out["all_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
