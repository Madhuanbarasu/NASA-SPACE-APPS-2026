"""Phase 4 final documentation consistency checks (read-only; no pytest, no measurement). Run from backend/."""
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

BACKEND = Path.cwd()
REPO = BACKEND.parent
sys.path.insert(0, str(BACKEND))
import validation  # noqa: E402,F401
from lunaops import ALGORITHM_VERSION  # noqa: E402
from lunaops.engine.provenance import GLOBAL_TESTS, QUANTITY_TESTS  # noqa: E402
from validation.common import run_meta  # noqa: E402

EV = "docs/validation_evidence/"
DOCS = ["README.md", "docs/TRACEABILITY.md", "docs/AUDIT_2026-11.md", EV + "README.md",
        EV + "phase4_closure_2026-11-11/README.md", EV + "phase4_final_merge_2026-11-12/README.md"]
txt = {d: (REPO / d).read_text(encoding="utf-8") for d in DOCS}
res = []


def check(name, ok, detail=""):
    res.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""))


L99 = ("Production kernels alone do not make results Validated: V-04, V-05, V-09 to V-13, U-04 and U-06 must also pass "
       "(see Validation).")
check("README line 99 is the protected sentence", txt["README.md"].splitlines()[98] == L99)
blk = txt["README.md"].split("<!-- validated-requirements:start -->")[1].split("<!-- validated-requirements:end -->")[0]
rows = {}
for line in blk.strip().splitlines():
    m = re.match(r"- (`(\w+)`|every quantity): (.+)$", line.strip())
    rows[m.group(2) or "*"] = [x.strip() for x in m.group(3).split(",")]
check("README validated-requirements block = provenance", rows.pop("*") == GLOBAL_TESTS and rows == QUANTITY_TESTS)
for t in ("V-09", "V-10", "V-11", "V-12", "V-13"):
    row = next(ln for ln in txt["docs/TRACEABILITY.md"].splitlines() if ln.startswith(f"| {t} |"))
    listed = {q.strip() for q in row.rstrip(" |").split("|")[-1].split(",")}
    check(f"TRACEABILITY {t} gate column = provenance", listed == {q for q, r in QUANTITY_TESTS.items() if t in r})

rb = (BACKEND / "validation/report.json").read_bytes()
rep = json.loads(rb)
sha = hashlib.sha256(rb).hexdigest()
check("report.json SHA-256 = 2279606c…d077d376", sha == "2279606ceab9354b8616ba9216e12e89e399f34cfc3cbfcbd7502d12d077d376", sha)
check("report.json == phase4_final_merge/report_after.json", rb == (REPO / EV / "phase4_final_merge_2026-11-12/report_after.json").read_bytes())
cnt = {}
for v in rep["tests"].values():
    cnt[v["status"]] = cnt.get(v["status"], 0) + 1
check("report entries 420 passed / 2 not run / 2 skipped", cnt == {"passed": 420, "not run": 2, "skipped": 2}, cnt)
exp = {k: "passed" for k in ("V-04", "V-05", "V-11", "V-12", "V-13", "V-14", "U-04", "U-06")} | {"V-09": "not run", "V-10": "not run"}
check("report statuses as documented", all(rep["tests"][k]["status"] == v for k, v in exp.items()))
log = (REPO / EV / "phase4_final_merge_2026-11-12/run_validation.log").read_text(encoding="utf-8")
check("merge log: 438 passed, 2 skipped, exit 0, nothing rejected",
      "438 passed, 2 skipped" in log and "# exit 0;" in log and " failed" not in log and "NOT merged" not in log)
now = run_meta("doc_check")
check("code fingerprint 5bf9753f…", now["code_fingerprint"].startswith("5bf9753f"))
check("suite fingerprint 1632af16…", now["suite_fingerprint"].startswith("1632af16"))
check("terrain acceptance digest e48eb8ed…", now["terrain_acceptance_digest"].startswith("e48eb8ed"))
check("report fingerprints = current", rep["code_fingerprint"] == now["code_fingerprint"] and rep["suite_fingerprint"] == now["suite_fingerprint"])
check("algorithm 1.5.0", ALGORITHM_VERSION == "1.5.0")
ta = hashlib.sha256((BACKEND / "validation/reference/terrain_acceptance.json").read_bytes()).hexdigest()
check("terrain_acceptance.json unchanged", ta.startswith("c0465069"), ta)

STALE = ["not yet merged into the official report", "until a separately approved merge", "until the pending merge",
         "\"not run\" in the official report until merged", "Not yet in the official report:", "result files merge-ready, not merged",
         "Current official report; V-04, V-05, V-13"]
for d in DOCS[:4]:
    hits = [s for s in STALE if s in txt[d]]
    check(f"{d}: no stale pre-merge statements", not hits, "; ".join(hits))
for d in DOCS:
    check(f"{d}: mentions final report 2279606c", "2279606c" in txt[d])
    check(f"{d}: records verdict COMPLETE WITH APPROVED DEFERRALS", "COMPLETE WITH APPROVED DEFERRALS" in txt[d])
    bad = re.findall(r"(?i)all (?:product |scientific )?labels (?:are |now )?validated", txt[d])
    check(f"{d}: does not claim all labels Validated", not bad, bad)
for d in ("README.md", "docs/TRACEABILITY.md", "docs/AUDIT_2026-11.md", EV + "phase4_final_merge_2026-11-12/README.md"):
    check(f"{d}: states disk/events/power stay Pending", re.search(r"`disk_visibility`, `events` and `power_indicator` (stay|remain)", txt[d]) is not None)

missing = set()
for d in DOCS:
    for m in re.findall(r"docs/validation_evidence/([A-Za-z0-9_.\-]+)/", txt[d]):
        if not (REPO / EV / m).is_dir():
            missing.add(m)
    if d.startswith(EV):
        base = (REPO / d).parent
        for m in re.findall(r"`(\.\./[A-Za-z0-9_.\-/]+?)`", txt[d]):
            if not (base / m.rstrip("/")).exists():
                missing.add(f"{d}: {m}")
check("every referenced evidence path exists", not missing, ", ".join(sorted(missing)))
for f in ("refresh_v04_v05_v13_v14_2026-11-11", "phase4_closure_2026-11-11", "phase4_merge_2026-11-11",
          "d1_v05_decision_2026-11-11", "phase4_remaining_decisions_2026-11-11", "phase4_final_merge_2026-11-12"):
    r = subprocess.run(["sha256sum", "-c", "--quiet", "SHA256SUMS"], cwd=REPO / EV / f, capture_output=True, text=True)
    check(f"{f}/SHA256SUMS verifies", r.returncode == 0, (r.stdout + r.stderr).strip()[:200])
print("ALL OK" if all(res) else f"{res.count(False)} FAILED", f"({len(res)} checks)")
sys.exit(0 if all(res) else 1)
