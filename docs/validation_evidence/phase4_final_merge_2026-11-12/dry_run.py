"""Phase 4 final merge: no-write pre-merge dry run of the eight approved files (validation.common.merge_external in
memory, as run_validation merges after its pytest step). Run from backend/. Writes only dry_run.json next to this file."""
import copy, hashlib, json, sys
from pathlib import Path
BACKEND = Path.cwd(); REPO = BACKEND.parent; HERE = Path(__file__).resolve().parent
EV = REPO / "docs" / "validation_evidence"
sys.path.insert(0, str(BACKEND))
import validation  # noqa: F401
from validation.common import merge_external, run_meta, OWNERS
FILES = ["v09_v10_final_2026-11-10/v09_v10.json", "v11_final_2026-11-10/v11.json", "v12_final_2026-11-10/v12.json",
         "refresh_v04_v05_v13_v14_2026-11-11/v04_horizons/horizons.json",
         "refresh_v04_v05_v13_v14_2026-11-11/v13_eclipse/v13.json", "refresh_v04_v05_v13_v14_2026-11-11/v14_month/v14.json",
         "phase4_remaining_decisions_2026-11-11/frontend_u04.json", "phase4_remaining_decisions_2026-11-11/frontend_u06.json"]
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
now = run_meta("run_validation")
rep = json.loads((BACKEND / "validation/report.json").read_text())
t = copy.deepcopy(rep["tests"])
for tid, v in t.items():
    if v.get("source") == "external":
        t[tid] = {"status": v.get("automated_status") or "not run", "detail": None}
rows = []
for f in FILES:
    p = EV / f; d = json.loads(p.read_text(encoding="utf-8")); m = d["meta"]
    fp_ok = (m["code_fingerprint"] == now["code_fingerprint"] and m["suite_fingerprint"] == now["suite_fingerprint"]
             and m["kernel_profile"] == now["kernel_profile"] and sorted(m["kernels"]) == sorted(now["kernels"]))
    rej = merge_external(t, d, now)
    rows.append({"file": f, "sha256": sha(p), "script": m["script"], "tests": {k: v["status"] for k, v in d["tests"].items()},
                 "owned": list(OWNERS[m["script"]]), "fingerprints_match": fp_ok, "rejected_reasons": rej})
    print(f"{f.split('/')[-1]:24s} script={m['script']:18s} fp_match={fp_ok} tests={ {k: v['status'] for k, v in d['tests'].items()} } rejected={rej}")
ids = ("V-04", "V-05", "V-09", "V-10", "V-11", "V-12", "V-13", "V-14", "U-04", "U-06")
st = {k: t[k]["status"] for k in ids}
print("projected:", st)
print("ZERO REJECTIONS" if all(not r["rejected_reasons"] for r in rows) else "REJECTIONS PRESENT")
(HERE / "dry_run.json").write_text(json.dumps({"note": "no-write dry run; report.json only read", "now": {k: now[k] for k in (
    "code_fingerprint", "suite_fingerprint", "kernel_profile", "terrain_acceptance_digest", "run_utc")},
    "report_sha256_before": sha(BACKEND / "validation/report.json"), "files": rows, "projected_statuses": st}, indent=2))
