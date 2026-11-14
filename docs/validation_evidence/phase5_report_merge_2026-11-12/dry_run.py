"""Phase 5 U-04/U-06 report merge: no-write pre-merge dry run (validation.common.merge_external in memory, exactly as
run_validation merges after its pytest step). Run from backend/. Writes only dry_run.json next to this file.

Input set = the eight files of the Phase 4 final merge, with the two Phase 4 frontend files replaced by the refreshed
Phase 5 files (approved by the project owner on 2026-11-12). Checks:
  * every input's SHA-256 equals its recorded value (Phase 4 final merge dry_run.json for the six science files,
    phase5_final_2026-11-12/SHA256SUMS for the two Phase 5 files);
  * every file passes the merge guard (zero rejections) with the current fingerprints;
  * the projected test table equals the live report in every entry except U-04 and U-06, whose status stays "passed"
    and whose detail and run_utc become those of the Phase 5 files."""
import copy, hashlib, json, sys
from pathlib import Path
BACKEND = Path.cwd(); REPO = BACKEND.parent; HERE = Path(__file__).resolve().parent
EV = REPO / "docs" / "validation_evidence"
sys.path.insert(0, str(BACKEND))
import validation  # noqa: F401
from validation.common import merge_external, run_meta, OWNERS

SCIENCE = ["v09_v10_final_2026-11-10/v09_v10.json", "v11_final_2026-11-10/v11.json", "v12_final_2026-11-10/v12.json",
           "refresh_v04_v05_v13_v14_2026-11-11/v04_horizons/horizons.json",
           "refresh_v04_v05_v13_v14_2026-11-11/v13_eclipse/v13.json", "refresh_v04_v05_v13_v14_2026-11-11/v14_month/v14.json"]
FRONTEND = ["phase5_final_2026-11-12/frontend_u04_phase5.json", "phase5_final_2026-11-12/frontend_u06_phase5.json"]
FILES = SCIENCE + FRONTEND
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()

p4 = {r["file"]: r["sha256"] for r in json.loads((EV / "phase4_final_merge_2026-11-12/dry_run.json").read_text())["files"]}
sums = {}
for ln in (EV / "phase5_final_2026-11-12/SHA256SUMS").read_text().splitlines():
    h, f = ln.split(maxsplit=1)
    sums["phase5_final_2026-11-12/" + f.lstrip("*").removeprefix("./")] = h
expected = {f: p4.get(f) for f in SCIENCE} | {f: sums.get(f) for f in FRONTEND}

now = run_meta("run_validation")
rp = BACKEND / "validation/report.json"
rep = json.loads(rp.read_text())
t = copy.deepcopy(rep["tests"])
for tid, v in t.items():
    if v.get("source") == "external":
        t[tid] = {"status": v.get("automated_status") or "not run", "detail": None}
rows = []
for f in FILES:
    p = EV / f; d = json.loads(p.read_text(encoding="utf-8")); m = d["meta"]
    h = sha(p)
    fp_ok = (m["code_fingerprint"] == now["code_fingerprint"] and m["suite_fingerprint"] == now["suite_fingerprint"]
             and m["kernel_profile"] == now["kernel_profile"] and sorted(m["kernels"]) == sorted(now["kernels"]))
    rej = merge_external(t, d, now)
    rows.append({"file": f, "sha256": h, "sha256_expected": expected[f], "sha256_ok": h == expected[f], "script": m["script"],
                 "tests": {k: v["status"] for k, v in d["tests"].items()}, "owned": list(OWNERS[m["script"]]),
                 "fingerprints_match": fp_ok, "rejected_reasons": rej})
    print(f"{f.split('/')[-1]:26s} sha_ok={h == expected[f]} script={m['script']:18s} fp_match={fp_ok} tests={ {k: v['status'] for k, v in d['tests'].items()} } rejected={rej}")

# projected table vs live report
diff = {}
for tid in sorted(set(t) | set(rep["tests"])):
    a, b = rep["tests"].get(tid), t.get(tid)
    if a != b:
        diff[tid] = sorted(k for k in set(a or {}) | set(b or {}) if (a or {}).get(k) != (b or {}).get(k))
only_frontend = set(diff) <= {"U-04", "U-06"}
fe = {tid: {"status": t[tid]["status"], "detail_is_phase5": t[tid]["detail"] == json.loads((EV / f).read_text(encoding="utf-8"))["tests"][tid]["detail"]}
      for tid, f in (("U-04", FRONTEND[0]), ("U-06", FRONTEND[1]))}
ok = all(r["sha256_ok"] and r["fingerprints_match"] and not r["rejected_reasons"] for r in rows) and only_frontend \
    and all(v["status"] == "passed" and v["detail_is_phase5"] for v in fe.values())
print("projected differences vs live report:", diff)
print("U-04/U-06 projected:", fe)
print("DRY RUN OK: zero rejections, hashes verified, only U-04/U-06 detail and run_utc change" if ok else "DRY RUN NOT OK")
(HERE / "dry_run.json").write_text(json.dumps({"note": "no-write dry run; report.json only read", "ok": ok,
    "now": {k: now[k] for k in ("code_fingerprint", "suite_fingerprint", "kernel_profile", "terrain_acceptance_digest", "run_utc")},
    "report_sha256_before": sha(rp), "files": rows, "projected_differences_vs_live": diff, "frontend_projection": fe}, indent=2))
sys.exit(0 if ok else 1)
