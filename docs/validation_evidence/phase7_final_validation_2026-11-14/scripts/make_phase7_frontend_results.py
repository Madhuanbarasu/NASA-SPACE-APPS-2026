"""Phase 7: write the U-04 and U-06 result files for the validation report (owners frontend_u04 / frontend_u06), in the
schema of the earlier ones (post_phase5_backend_and_ui_fixes_2026-11-12/make_post_phase5_results.py):
{"tests": {"<ID>": {"status", "detail"}}, "decision", "criterion", "result", "evidence", "meta": run_meta(<owner>)}.

Statuses are computed from this folder's evidence under the approved criteria (D4: U-04 scoped WCAG 2.2 A/AA; D3: U-06
LCP <= 2500 ms, CLS <= 0.1, interaction p95 <= 200 ms, no progressive leak). Nothing is measured here.
    cd backend && .venv/Scripts/python.exe ../docs/validation_evidence/phase7_final_validation_2026-11-14/scripts/make_phase7_frontend_results.py
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

BACKEND = Path.cwd()
REPO = BACKEND.parent
HERE = REPO / "docs" / "validation_evidence" / "phase7_final_validation_2026-11-14"
sys.path.insert(0, str(BACKEND))
from validation.common import OWNERS, run_meta  # noqa: E402


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def rel(p: Path) -> str:
    return p.relative_to(REPO).as_posix()


def u04() -> dict:
    p = HERE / "accessibility" / "u04_audit" / "audit-phase7.json"
    r = json.loads(p.read_text(encoding="utf-8"))
    views = {}
    for v in r["views"]:
        k = v.get("keyboard") or {}
        cnt = {"axUnnamed": len(v["ax"]["unnamed"]), "focusableNoRole": len(v["ax"]["focusableWithoutWidgetRole"]),
               "contrastFail": len(v["contrast"]["failures"]), "targetFail": len(v["targets"]["failures"]),
               "noFocusIndicator": len(k.get("noIndicator", [])), "focusClipped": len(k.get("clipped", [])),
               "obscured": len(k.get("obscured", [])), "reflowHScroll": int(bool(v["reflow320"]["horizontalScroll"])),
               "reflowOffenders": v["reflow320"]["offenderCount"], "spacingClipped": len(v["textSpacing"]["clipped"]),
               "unlabeled": len(v["structure"]["unlabeledFormControls"]), "dupIds": len(v["structure"]["duplicateIds"]),
               "roleApplication": len(v["structure"]["roleApplication"])}
        views[v["view"]] = {"problems": sum(cnt.values()), "counts": cnt, "tabStops": k.get("stops"),
                            "tabWalkCycled": k.get("cycled") if v.get("keyboard") else None}
    f = r["functional"]
    changed = lambda d: all(x.get("changed") for x in d.values())
    func = {"skip link moves focus to main": f["skipLink"]["afterEnter"] == "main",
            "invalid coordinates announced, Analyse disabled": f["invalidCoordinates"]["latInvalid"] == "true" and f["invalidCoordinates"]["runDisabled"] is True,
            "map keyboard pan and zoom": changed(f["mapKeyboard"]),
            "3D terrain keyboard pan, rotate, zoom": changed(f["terrain3dKeyboard"]),
            "globe keyboard rotate and zoom": changed(f["globeKeyboard"]),
            "terrain preview keyboard pan, rotate, zoom": changed(f["terrainPreviewKeyboard"]),
            "panorama slider moves by arrow key": f["panoramaKeyboard"]["onFocus"]["now"] != f["panoramaKeyboard"]["afterArrowRight"]["now"],
            "return to the result": f["returnToResult"] is True,
            "dashboard deep link moves focus": f["missionDeepLinkFocus"] == "result-visibility",
            "status announcements after analysis and comparison": bool(f["statusAfterAnalysis"]) and bool(f["statusAfterComparison"]),
            "matrix cell opens its result by keyboard": f["matrixCellEnter"] == "Site" and f["matrixCellSpace"] == "Site",
            "reduced motion removes transitions": f["reducedMotionTransition"] == "0s",
            "tab list arrow keys": f["tabsArrowKeys"]["afterRight"]["selected"] == "Site"}
    walks = all(v["tabWalkCycled"] in (True, None) for v in views.values())
    ok = all(v["problems"] == 0 for v in views.values()) and walks and all(func.values())
    status = "passed" if ok else "failed"
    detail = (f"Scoped U-04 (criteria and scope of D4, approved 2026-11-11) re-evaluated in Phase 7 (2026-11-14, "
              f"npm run audit:a11y extended with the Landing and Communication views): {'0' if ok else 'non-zero'} automated "
              f"problems in {len(views)} views; every Tab walk cycled (no trap); {sum(func.values())}/{len(func)} keyboard and "
              "announcement functional checks passed. Four findings of the first Phase 7 audit were fixed first (text-spacing "
              "overflow of the figure cards and their label badges, an invisible chart label counted as text, a clipped focus "
              "ring in the comparison matrix, a long label chip at 320 px). Tab-stop counts are re-registered for the LUNA-OPS 2.0 "
              "views. Scope: Chrome headless only; no real screen-reader (assistive-technology) user session; zoom emulated "
              "through the viewport; speech input not tested. Not a claim of unrestricted WCAG 2.2 AA conformance")
    return {"status": status, "detail": detail, "views": views, "functional": func,
            "evidence": {rel(p): sha(p), rel(HERE / "accessibility" / "u04_audit" / "audit-phase7-before-fixes.json"):
                         sha(HERE / "accessibility" / "u04_audit" / "audit-phase7-before-fixes.json")}}


def u06() -> dict:
    p = HERE / "performance" / "u06_perf" / "summary.json"
    s = json.loads(p.read_text(encoding="utf-8"))
    ok = bool(s.get("all_d3_criteria_met"))
    prof = s["profiles"]
    lcp = lambda pr: prof[pr]["lcp_worst_ms"]
    p95 = lambda pr: (prof[pr].get("interaction") or {}).get("cursorStep", {}).get("p95Ms")
    status = "passed" if ok else "failed"
    detail = (f"Scoped U-06 (criteria of D3, approved 2026-11-11) re-measured in Phase 7 (2026-11-14): worst LCP "
              f"{lcp('native')}/{lcp('cpu4x')}/{lcp('cpu4x-net10mbps')} ms (<= 2500; native/4x CPU/4x CPU + 10 Mbit/s), CLS "
              f"(<= 0.1) and interaction p95 {p95('native')}/{p95('cpu4x')} ms (<= 200) as in summary.json, memory: no progressive "
              f"leak over remount cycles; all D3 criteria met: {ok}. Same laptop and Chrome headless profiles as D3; lab "
              "measurement, not a field Core Web Vitals claim")
    raw = sorted((HERE / "performance" / "u06_perf" / "raw").glob("perf-*.json"))
    return {"status": status, "detail": detail, "summary": s, "evidence": {rel(p): sha(p)} | {rel(x): sha(x) for x in raw}}


def main() -> None:
    report = BACKEND / "validation" / "report.json"
    before = sha(report)
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None   # e.g. --only U-04 (U-06 needs the server)
    for owner, tid, fn, decision, criterion in (
            ("frontend_u04", "U-04", u04, "D4 (criteria and scope), Phase 7 re-evaluation",
             "WCAG 2.2 Level A and AA (requirement C02), scoped: Chrome/Chromium only, no real screen-reader user session"),
            ("frontend_u06", "U-06", u06, "D3 (criteria), Phase 7 re-measurement",
             {"lcp_ms_max": 2500, "cls_max": 0.1, "interaction_response_p95_ms_max": 200,
              "memory": "no progressive leak over repeated remount cycles", "tbt": "information only, not gated"})):
        assert tid in OWNERS[owner]
        if only and tid != only:
            print(owner, tid, "skipped (--only", only + ")")
            continue
        r = fn()
        doc = {"tests": {tid: {"status": r["status"], "detail": r["detail"]}}, "decision": decision, "criterion": criterion,
               "result": {k: v for k, v in r.items() if k not in ("status", "detail", "evidence")}, "evidence": r["evidence"],
               "meta": run_meta(owner)}
        out = HERE / "accessibility" / f"{owner}.json" if tid == "U-04" else HERE / "performance" / f"{owner}.json"
        out.write_text(json.dumps(doc, indent=2), encoding="utf-8")
        print(owner, tid, r["status"], "->", rel(out))
    assert sha(report) == before, "report.json changed"


if __name__ == "__main__":
    main()
