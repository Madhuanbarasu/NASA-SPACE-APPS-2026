"""Separate V-05 (rise/set timing) report from the horizons_compare output. Post-processing only.

    cd backend && .venv/Scripts/python.exe <this file> --horizons <horizons.json> --out-dir <v05 folder>

It recomputes nothing scientific: it re-reads the V-05 section that validation/horizons_compare.py wrote, lists
every matched crossing with its difference, records how each reference and LUNA-OPS time was searched, and
sets the formal status.

Formal status rule for this refresh (instruction of 2026-11-11): the proposed 1.0 s V-05 threshold is NOT
approved, so V-05 is never reported as PASS here.
  * FAIL        - a reference crossing is missed or a detector event is spurious (the event sets disagree).
  * PROVISIONAL - the event sets agree; the timing differences are reported against the proposed (unapproved)
                  threshold, pending formal approval of a V-05 criterion.
  * BLOCKED     - no Horizons crossings were produced (no reference to compare against).
The status that horizons_compare.py itself wrote ("passed"/"failed") is kept verbatim in the input file and
quoted here as the script's mechanical evaluation against the proposed threshold, not as the formal result.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
from pathlib import Path

BACKEND = Path.cwd()
sys.path.insert(0, str(BACKEND))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--horizons", required=True)
    ap.add_argument("--out-dir", required=True)
    a = ap.parse_args()
    src = Path(a.horizons)
    raw = src.read_bytes()
    h = json.loads(raw)
    out_dir = Path(a.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    from lunaops import settings
    from validation import horizons_compare as HC

    v05 = h["v05"]
    ev, missed, spurious = v05["events"], v05["missed"], v05["spurious"]
    dts = [e["dt_s"] for e in ev]
    absd = [abs(d) for d in dts]
    # Horizons responses used by the V-05 reference search, grouped by stage (from the response tags)
    stages = {"hourly_scan": [], "minute_refine": [], "second_refine": [], "confirm_window": []}
    for f in h["horizons_responses"]:
        name = f["file"]
        q = f["query"]
        rec = {"file": name, "sha256": f["sha256"], "step": q.get("STEP_SIZE"), "start": q.get("START_TIME"),
               "stop": q.get("STOP_TIME"), "target": q.get("COMMAND"), "site_coord": q.get("SITE_COORD")}
        if name.startswith("v04_") and name.endswith("_hourly.json"):
            stages["hourly_scan"].append(rec)
        elif name.endswith("_min.json"):
            stages["minute_refine"].append(rec)
        elif name.endswith("_sec.json"):
            stages["second_refine"].append(rec)
        elif name.endswith("_confirm.json"):
            stages["confirm_window"].append(rec)

    if not ev and not missed:
        status, why = "BLOCKED", "no Horizons centre crossing was produced; nothing to compare"
    elif missed or spurious:
        status, why = "FAIL", f"{len(missed)} reference crossing(s) missed and {len(spurious)} spurious detector event(s)"
    else:
        status, why = "PROVISIONAL", ("event sets agree (0 missed, 0 spurious); the timing differences cannot be "
                                      "judged PASS/FAIL because the proposed 1.0 s V-05 threshold is not approved")
    summary = {
        "n_matched": len(ev), "n_missed": len(missed), "n_spurious": len(spurious),
        "max_abs_dt_s": max(absd) if absd else None, "mean_dt_s": statistics.fmean(dts) if dts else None,
        "median_abs_dt_s": statistics.median(absd) if absd else None,
        "min_dt_s": min(dts) if dts else None, "max_dt_s": max(dts) if dts else None,
        "n_within_proposed_threshold": sum(1 for d in absd if d <= HC.V05_TOL_S),
        "n_within_detector_half_bracket_0p5s": sum(1 for d in absd if d <= settings.EVENT_TOL_S / 2 + 1e-9)}
    report = {
        "test": "V-05",
        "formal_status": status, "formal_status_reason": why,
        "approval": {"proposed_threshold_s": HC.V05_TOL_S, "approved": False,
                     "note": "The 1.0 s threshold (EVENT_TOL_S) was proposed in A9 because the blueprint's V-05 "
                             "criterion text was unavailable. It has not been formally approved (instruction of "
                             "2026-11-11), so V-05 is not marked PASS."},
        "script_mechanical_evaluation": {"status": h["tests"]["V-05"]["status"],
                                         "detail": h["tests"]["V-05"]["detail"],
                                         "note": "written by horizons_compare.py against the unapproved proposed "
                                                 "threshold; not the formal result"},
        "summary": summary,
        "window": h["window"],
        "sites_deg": [{"label": l, "lat": la, "lon": lo, "height_km": 0.0} for l, la, lo in HC.SITES],
        "bodies": ["sun (Horizons 10)", "earth (Horizons 399; not at the farside site)"],
        "event_definition": "centre of the Sun / Earth crosses an ideal flat 0 deg horizon (no terrain, no refraction)",
        "search_steps": {
            "reference_horizons": {
                "stage_1": "hourly Horizons elevations (the V-04 tables, STEP_SIZE=1h); a sign change brackets a crossing",
                "stage_2": "Horizons table over the bracketing hour at 1-minute steps (STEP_SIZE=60 i.e. 60 intervals)",
                "stage_3": "Horizons table over the bracketing minute at 1-second steps, TIME_DIGITS=FRACSEC",
                "interpolation": "linear between the two 1-s samples that bracket 0 deg",
                "confirmation": "an unmatched detector event triggers a +-30 min, 1-minute Horizons table and the same "
                                "refinement (double crossing inside one hour)",
                "time_scale": "TT tags from Horizons converted to ET with SPICE (TDT)"},
            "luna_ops_detector": {
                "engine": "lunaops.engine.events.EventDetector, functions sun_c / earth_c",
                "step_cap_s": settings.EVENT_STEP_CAP_S, "step_floor_s": settings.EVENT_STEP_FLOOR_S,
                "bisection_tolerance_s": settings.EVENT_TOL_S,
                "reported_time": "midpoint of the final bisection bracket, so its resolution limit is "
                                 f"+-{settings.EVENT_TOL_S / 2} s"},
            "matching": {"same_body_and_direction": True, "window_s": HC.V05_MATCH_S}},
        "events": ev, "missed": missed, "spurious": spurious,
        "horizons_responses_by_stage": stages,
        "source_file": {"path": str(src).replace("\\", "/"), "sha256": hashlib.sha256(raw).hexdigest()},
        "meta": h["meta"]}
    (out_dir / "v05_report.json").write_text(json.dumps(report, indent=2))
    with open(out_dir / "v05_events.csv", "w", newline="") as f:
        f.write("site,body,direction,t_horizons_utc,et_horizons,et_luna,dt_s,ref_bracket_s\n")
        for e in ev:
            f.write(",".join(str(e[k]) for k in ("site", "body", "direction", "t_horizons_utc", "et_horizons",
                                                 "et_luna", "dt_s", "ref_bracket_s")) + "\n")
    print(json.dumps({"formal_status": status, "reason": why, **summary}, indent=1))
    print({k: len(v) for k, v in stages.items()})


if __name__ == "__main__":
    main()
