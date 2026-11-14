"""Run metadata shared by every validation script, and the guard for merging their results.

External results (Horizons, PSR, eclipse, month-long V-14) carry this metadata, and
run_validation.py refuses to merge any result produced with different code, kernels or test
suite, so a report can never mix runs (blueprint C06). Each script may report only the tests it
owns, a merge can never turn a failed automated test into a pass, and only the known status
values are accepted. V-09 to V-12 may report a status other than "not run" only if the run met the
shared terrain acceptance gate under the acceptance record in force now (Phase 4 A6).
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from validation.terrain_gate import GATED_TESTS  # noqa: E402  (V-09..V-12: final status needs the terrain gate)

# "inconclusive": the test ran but its evidence cannot decide it (V-11: points whose terrain horizon is incomplete).
# It is never a pass: it keeps every dependent label Pending, exactly like "not run".
STATUSES = ("passed", "failed", "inconclusive", "skipped", "not run")
# which external script may report which test IDs
OWNERS = {
    "horizons_compare": ("V-04", "V-05"),
    "v13_eclipse": ("V-13",),
    "v11_psr": ("V-11",),
    "v14_month": ("V-14",),
    "v09_v10_avgvisib": ("V-09", "V-10"),
    "v12_lroc": ("V-12",),
    "frontend_u04": ("U-04",),
    "frontend_u06": ("U-06",),
}


def run_meta(script: str | None = None) -> dict:
    from lunaops.engine.kernels import load
    from lunaops.fingerprint import code_fingerprint, suite_fingerprint

    ks = load()
    if script is None:
        script = Path(sys.argv[0]).stem
    return {"script": script, "code_fingerprint": code_fingerprint(), "suite_fingerprint": suite_fingerprint(),
            "kernel_profile": ks.profile, "kernels": sorted(f["sha256"] for f in ks.files),
            "terrain_acceptance_digest": _acceptance_digest_or_none(),
            "run_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")}


def _acceptance_digest_or_none() -> str | None:
    from validation.terrain_gate import acceptance_digest
    try:
        return acceptance_digest()
    except (OSError, ValueError):
        return None


def combine(pytest_status: str | None, external_status: str) -> str:
    """Status after merging: a failure anywhere is a failure; an inconclusive side is never turned into a pass;
    a pass needs neither on either side."""
    sts = {pytest_status or "not run", external_status}
    if "failed" in sts:
        return "failed"
    if "inconclusive" in sts:
        return "inconclusive"
    if "passed" in sts:
        return "passed"
    if "skipped" in sts:
        return "skipped"
    return "not run"


def _terrain_gate_reasons(tid: str, status: str, meta: dict, now: dict) -> list[str]:
    """A V-09..V-12 status other than "not run" needs the terrain gate met when the result was produced, under the
    terrain acceptance in force now (validation/terrain_gate.py)."""
    gate = meta.get("terrain_gate") or {}
    why = []
    if gate.get("ok") is not True:
        why.append(f"{tid}: '{status}' was produced without the terrain acceptance gate being met")
    digest = now.get("terrain_acceptance_digest")
    if not digest or gate.get("acceptance_digest") != digest or meta.get("terrain_acceptance_digest") != digest:
        why.append(f"{tid}: produced under a different terrain acceptance record than the current one")
    return why


def merge_external(tests: dict, ext: dict, now: dict) -> list[str]:
    """Merge an external result file into tests; return the reasons it was rejected (empty if merged)."""
    meta = ext.get("meta") or {}
    reasons = []
    if meta.get("code_fingerprint") != now["code_fingerprint"]:
        reasons.append("produced by different code")
    if "suite_fingerprint" in now and meta.get("suite_fingerprint") != now["suite_fingerprint"]:
        reasons.append("produced by a different version of the tests or validation scripts")
    if meta.get("kernel_profile") != now["kernel_profile"]:
        reasons.append("produced with a different kernel profile")
    if sorted(meta.get("kernels") or []) != sorted(now["kernels"]):
        reasons.append("produced with different kernel files")
    owned = OWNERS.get(meta.get("script") or "")
    if owned is None:
        reasons.append(f"unknown producing script {meta.get('script')!r}")
    ext_tests = ext.get("tests") or {}
    for tid, val in ext_tests.items():
        if owned is not None and tid not in owned:
            reasons.append(f"{meta.get('script')} may not report {tid}")
        if not isinstance(val, dict) or val.get("status") not in STATUSES:
            reasons.append(f"{tid}: status must be one of {', '.join(STATUSES)}")
        elif tid in GATED_TESTS and val["status"] != "not run":
            reasons.extend(_terrain_gate_reasons(tid, val["status"], meta, now))
    if not ext_tests:
        reasons.append("no test results in the file")
    if reasons:
        return reasons
    for tid, val in ext_tests.items():
        prev = tests.get(tid) or {}
        prev_status = prev.get("status") if prev.get("source") != "external" else None
        status = combine(prev_status, val["status"])
        tests[tid] = {**val, "status": status, "source": "external", "script": meta.get("script"),
                      "external_status": val["status"], "automated_status": prev_status,
                      "run_utc": meta.get("run_utc")}
    return []
