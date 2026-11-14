"""Phase 7: regenerate backend/validation/report.json with validation.run_validation UNCHANGED, reusing the JUnit
result of the Phase 7 full pytest run instead of running the suite a second time (owner instruction: reuse results,
do not rerun successful tests).

What it does
  * checks that the live code and suite fingerprints equal the expected ones (the fingerprints the pytest run and every
    merged external result were produced under) and refuses to run otherwise;
  * replaces run_validation's pytest subprocess call with: copy the recorded JUnit XML into the temporary file
    run_validation reads, and return the recorded pytest exit code. Everything else (test-ID parsing, merge guard
    merge_external, kernels, fingerprints, label digest, report writing) is run_validation's own code.
Difference from a plain run_validation: the reused run covered `backend/` (tests/ plus the lunaops_comms, lunaops_landing
and lunaops_tiles package tests), a superset of run_validation's `tests`; extra cases have no blueprint ID and are
recorded as "other:<name>", and any failure among them would make pytest_exit_code non-zero (stricter, not looser).
Usage (from backend/):
  python <this> --junit <xml> --exit-code <n> --expect-code <hex> --expect-suite <hex> --merge <json> [--merge ...]
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

BACKEND = Path.cwd()
sys.path.insert(0, str(BACKEND))


def take(flag: str) -> str:
    i = sys.argv.index(flag)
    v = sys.argv[i + 1]
    del sys.argv[i:i + 2]
    return v


junit = Path(take("--junit")).resolve()
rc = int(take("--exit-code"))
exp_code, exp_suite = take("--expect-code"), take("--expect-suite")

from lunaops.fingerprint import code_fingerprint, suite_fingerprint  # noqa: E402

cf, sf = code_fingerprint(), suite_fingerprint()
if (cf, sf) != (exp_code, exp_suite):
    sys.exit(f"fingerprint mismatch: live {cf} / {sf}, expected {exp_code} / {exp_suite}; nothing written")
print("fingerprints verified:", cf, sf)

import validation.run_validation as RV  # noqa: E402


def fake_run(cmd, cwd=None, **kw):
    assert cmd[1:3] == ["-m", "pytest"], cmd
    xml = next(a for a in cmd if a.startswith("--junitxml="))[len("--junitxml="):]
    shutil.copyfile(junit, xml)
    print(f"reused JUnit {junit} (pytest exit code {rc}) instead of: {' '.join(map(str, cmd))}")
    return subprocess.CompletedProcess(cmd, rc)


RV.subprocess.run = fake_run
sys.argv = [sys.argv[0]] + sys.argv[1:]
RV.main()
