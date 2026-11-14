"""Fingerprint snapshot for the V-04/V-05/V-13/V-14 refresh (read-only; writes only the --out file).

    cd backend && .venv/Scripts/python.exe ../docs/validation_evidence/refresh_v04_v05_v13_v14_2026-11-11/scripts/snapshot.py --out <file>

Records the code/suite fingerprints, kernel set, terrain acceptance digest, algorithm version, library
versions, SHA-256 of the validation scripts, reference files and the live report, and the metadata of the
previous V-04/V-05/V-13/V-14 evidence so staleness is shown, not asserted.
Kept outside backend/ so it does not change the suite fingerprint.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from pathlib import Path

BACKEND = Path.cwd()
REPO = BACKEND.parent
sys.path.insert(0, str(BACKEND))

import validation  # noqa: E402,F401  (selects the kernel set exactly as the validation scripts do)


def sha(p: Path) -> str | None:
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    import numpy
    import spiceypy

    from lunaops import ALGORITHM_VERSION
    from validation.common import run_meta

    meta = run_meta("snapshot")
    files = ["backend/validation/horizons_compare.py", "backend/validation/v13_eclipse.py",
             "backend/validation/v14_month.py", "backend/validation/common.py",
             "backend/validation/run_validation.py", "backend/validation/terrain_gate.py",
             "backend/validation/reference/gsfc_lunar_eclipses_2025_2026.json",
             "backend/validation/reference/terrain_acceptance.json", "backend/validation/report.json",
             "backend/lunaops/engine/events.py", "backend/lunaops/engine/ephem.py", "backend/lunaops/testing.py",
             "backend/lunaops/settings.py", "data/kernels/lock.json"]
    prev = {}
    for name, rel in {"V-04/V-05 (A8/A9)": "docs/validation_evidence/horizons_v04_v05_2026-11-09/horizons.json",
                      "V-13 (A13)": "docs/validation_evidence/v13_gsfc_2026-11-09/v13.json",
                      "V-14 (A14)": "docs/validation_evidence/v14_month_a14_2026-11-10/v14.json",
                      "V-04/V-05 re-run in A14": "docs/validation_evidence/v14_month_a14_2026-11-10/report/horizons.json",
                      "V-13 re-run in A14": "docs/validation_evidence/v14_month_a14_2026-11-10/report/v13.json"}.items():
        p = REPO / rel
        if not p.exists():
            prev[name] = {"file": rel, "present": False}
            continue
        m = json.loads(p.read_text()).get("meta", {})
        prev[name] = {"file": rel, "run_utc": m.get("run_utc"), "code_fingerprint": m.get("code_fingerprint"),
                      "suite_fingerprint": m.get("suite_fingerprint"),
                      "terrain_acceptance_digest": m.get("terrain_acceptance_digest"),
                      "stale_code": m.get("code_fingerprint") != meta["code_fingerprint"],
                      "stale_suite": m.get("suite_fingerprint") != meta["suite_fingerprint"],
                      "tests": {k: v.get("status") for k, v in json.loads(p.read_text()).get("tests", {}).items()}}
    rep = json.loads((BACKEND / "validation" / "report.json").read_text())
    out = {"meta": meta, "algorithm_version": ALGORITHM_VERSION,
           "python": sys.version, "platform": platform.platform(), "spiceypy": spiceypy.__version__,
           "cspice": spiceypy.tkvrsn("TOOLKIT"), "numpy": numpy.__version__,
           "sha256": {f: sha(REPO / f) for f in files},
           "live_report": {"run_utc": rep.get("run_utc"), "code_fingerprint": rep.get("code_fingerprint"),
                           "suite_fingerprint": rep.get("suite_fingerprint"),
                           "matches_current_code": rep.get("code_fingerprint") == meta["code_fingerprint"],
                           "matches_current_suite": rep.get("suite_fingerprint") == meta["suite_fingerprint"],
                           "tests": {k: rep["tests"][k] for k in ("V-04", "V-05", "V-13", "V-14")}},
           "previous_evidence": prev}
    Path(a.out).write_text(json.dumps(out, indent=2))
    print(json.dumps({k: out[k] for k in ("algorithm_version", "live_report")}, indent=1))
    print(json.dumps({k: (v.get("stale_code"), v.get("stale_suite")) for k, v in prev.items()}, indent=1))


if __name__ == "__main__":
    main()
