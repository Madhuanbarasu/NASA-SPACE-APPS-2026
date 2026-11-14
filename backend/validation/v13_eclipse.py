"""V-13: Earth's occultation of the Sun at nearside sites during catalogued lunar eclipses.

    python -m validation.v13_eclipse --reference validation/reference/gsfc_lunar_eclipses_2025_2026.json --out v13.json
    python -m validation.v13_eclipse --lat 0 --lon 0 --p1 <UTC> --u1 <UTC> --u4 <UTC> --p4 <UTC> --out v13.json

Take P1/U1/U4/P4 from the NASA GSFC lunar eclipse catalogue (never from memory). The reference file holds the
GSFC contacts with their provenance; its transcription is checked against the figures' stated durations and
GSFC's minute-rounded text pages before anything runs.

The engine's own adaptive event detector finds the eclipse events (terrain is set far below the Sun so only
Earth matters): ecl_contact (Earth's limb touches the Sun's limb: partial occultation begins or ends) and
ecl_total (the Sun disappears or reappears behind Earth). Pass criterion (Section 10.1): partial occultation
lies inside [P1, P4]; any total occultation lies inside [U1, U4] (both with 1 s slack, as before).

Why containment: P1/P4 and U1/U4 are when the *Moon's limb* touches the penumbra/umbra, so the interval in which
any single site is in the penumbra (umbra) lies inside them. GSFC enlarges Earth's shadow for the atmosphere
(Danjon's rule) while LUNA-OPS uses the solid Earth; an enlarged shadow only widens [P1, P4] and [U1, U4], so
the containment still has to hold. The margins are reported, but they are not a timing comparison, and the
reference contacts carry +-0.5 s rounding.

Reference mode converts each GSFC UT contact to TD with that eclipse's own Delta T (TD - UT of its greatest
eclipse, as printed by GSFC), not with today's leap-second UTC.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lunaops.engine.ephem import Site  # noqa: E402
from lunaops.engine.kernels import load  # noqa: E402
from lunaops.engine.events import EventConfig, EventDetector  # noqa: E402
from lunaops.engine.timeutil import parse_utc, to_utc  # noqa: E402
from lunaops.engine.visibility import HorizonProfile  # noqa: E402

SLACK_S = 1.0
# nearside sites: the centre used since the first version, and four sites 45 deg from it
DEFAULT_SITES = [(0.0, 0.0), (45.0, 0.0), (-45.0, 0.0), (0.0, 45.0), (0.0, -45.0)]


def _sec(hms: str) -> int:
    h, m, s = (int(x) for x in re.findall(r"\d+", hms))
    return 3600 * h + 60 * m + s


def _tod(ts: str) -> float:
    """Seconds of day of 'YYYY-MM-DD HH:MM:SS[.f]'."""
    hh, mm, ss = ts.split()[1].split(":")
    return 3600 * int(hh) + 60 * int(mm) + float(ss)


def check_reference(ecl: dict) -> list[str]:
    """Consistency of a transcribed GSFC entry: contact differences equal the stated durations (+-1 s for the
    rounding of two contacts), every contact rounds to the text page's minute, and the contacts are ordered."""
    c, d, problems = ecl["contacts_ut"], ecl["durations_stated"], []
    t = {k: _tod(v) for k, v in c.items()}
    pairs = {"penumbral": ("P1", "P4"), "umbral": ("U1", "U4"), "total": ("U2", "U3")}
    for name, (a, b) in pairs.items():
        if name in d:
            got = t[b] - t[a]
            if abs(got - _sec(d[name])) > 1.0:
                problems.append(f"{ecl['id']}: {b}-{a} = {got:.0f} s but the figure states {name} {d[name]}")
    for k, hm in ecl.get("text_page_minutes_ut", {}).items():
        h, m = (int(x) for x in hm.split(":"))
        rounded = int((t[k] + 30) // 60) * 60
        if rounded % 86400 != (3600 * h + 60 * m) % 86400:
            problems.append(f"{ecl['id']}: {k} {c[k]} does not round to the text page's {hm}")
    order = [k for k in ("P1", "U1", "U2", "U3", "U4", "P4") if k in t]
    if any(t[a] >= t[b] for a, b in zip(order, order[1:])):
        problems.append(f"{ecl['id']}: contacts are not in order")
    return problems


def contacts_et(ecl: dict) -> tuple[dict, float]:
    """GSFC UT contacts -> ET, via TD = UT + Delta T of this eclipse (from its greatest-eclipse TD and UT)."""
    import spiceypy as sp
    dt = _tod(ecl["greatest_td"]) - _tod(ecl["greatest_ut"])
    return {k: float(sp.str2et(v + " TDT")) + dt for k, v in ecl["contacts_ut"].items()}, dt


def evaluate(lat: float, lon: float, c: dict) -> dict:
    """Run the detector around one eclipse at one site and apply the Section 10.1 criterion."""
    hp = HorizonProfile(np.full(3600, -30.0), np.zeros(3600, bool))
    det = EventDetector(Site(lat, lon, 0.0, 0.0), hp, EventConfig())
    run = det.run(c["P1"] - 7200.0, c["P4"] + 7200.0)
    part = [e["et"] for e in run["events"] if e["function"] == "ecl_contact"]
    tot = [e["et"] for e in run["events"] if e["function"] == "ecl_total"]
    ok = len(part) >= 2 and part[0] >= c["P1"] - SLACK_S and part[-1] <= c["P4"] + SLACK_S
    if tot:
        ok = ok and "U1" in c and "U4" in c and tot[0] >= c["U1"] - SLACK_S and tot[-1] <= c["U4"] + SLACK_S
    res = {"lat": lat, "lon": lon, "passed": bool(ok),
           "partial_utc": [to_utc(t, 1) for t in part], "total_utc": [to_utc(t, 1) for t in tot],
           "estimate_failures": len([f for f in det.log.estimate_failures if f["function"].startswith("ecl")])}
    if len(part) >= 2:
        res["margin_partial_start_after_P1_s"] = part[0] - c["P1"]
        res["margin_partial_end_before_P4_s"] = c["P4"] - part[-1]
    if tot and "U1" in c and "U4" in c:
        res["margin_total_start_after_U1_s"] = tot[0] - c["U1"]
        res["margin_total_end_before_U4_s"] = c["U4"] - tot[-1]
    if tot and "U2" in c and "U3" in c:          # informative only: not part of the criterion
        res["info_total_start_minus_U2_s"] = tot[0] - c["U2"]
        res["info_U3_minus_total_end_s"] = c["U3"] - tot[-1]
    return res


def main():
    ap = argparse.ArgumentParser()
    for k in ("p1", "u1", "u4", "p4"):
        ap.add_argument(f"--{k}", help="UTC contact (single-eclipse mode)")
    ap.add_argument("--reference", help="JSON file of GSFC contacts (reference mode)")
    ap.add_argument("--lat", type=float, default=None)
    ap.add_argument("--lon", type=float, default=None)
    ap.add_argument("--out", default="v13.json")
    a = ap.parse_args()
    load()                                     # kernels first: the reference times are converted with SPICE
    if a.reference:
        ref = json.loads(Path(a.reference).read_text())
        problems = [p for e in ref["eclipses"] for p in check_reference(e)]
        if problems:
            sys.exit("Reference transcription is inconsistent: " + "; ".join(problems))
        sites = [(a.lat, a.lon)] if a.lat is not None else DEFAULT_SITES
        results = []
        for ecl in ref["eclipses"]:
            c, dt = contacts_et(ecl)
            for lat, lon in sites:
                results.append({"eclipse": ecl["id"], "type": ecl["type"], "delta_t_s": round(dt, 1),
                                **evaluate(lat, lon, c)})
        ok = all(r["passed"] for r in results)
        failed = [f"{r['eclipse']} at ({r['lat']}, {r['lon']})" for r in results if not r["passed"]]
        mins = {k: min(r[k] for r in results if k in r) for k in
                ("margin_partial_start_after_P1_s", "margin_partial_end_before_P4_s",
                 "margin_total_start_after_U1_s", "margin_total_end_before_U4_s")}
        detail = (f"{len(ref['eclipses'])} GSFC eclipses x {len(sites)} nearside sites: "
                  f"{sum(r['passed'] for r in results)}/{len(results)} pass; smallest margins (s): "
                  + ", ".join(f"{k[len('margin_'):-len('_s')]} {v:.1f}" for k, v in mins.items())
                  + (f"; failed: {failed}" if failed else ""))
        out = {"tests": {"V-13": {"status": "passed" if ok else "failed", "detail": detail}},
               "criterion": f"partial occultation inside [P1, P4], total inside [U1, U4], slack {SLACK_S} s "
                            "(Section 10.1)",
               "reference": {k: ref[k] for k in ("source", "time_scale_note")}, "reference_file": a.reference,
               "results": results}
    else:
        if not (a.p1 and a.p4):
            sys.exit("give --reference, or --p1 and --p4 (UTC) for one eclipse")
        c = {"P1": parse_utc(a.p1), "P4": parse_utc(a.p4)}
        if a.u1 and a.u4:
            c.update(U1=parse_utc(a.u1), U4=parse_utc(a.u4))
        r = evaluate(a.lat or 0.0, a.lon or 0.0, c)
        out = {"tests": {"V-13": {"status": "passed" if r["passed"] else "failed",
                                  "detail": f"partial {r['partial_utc']}, total {r['total_utc']}"}},
               "results": [r]}
    from validation.common import run_meta
    out["meta"] = run_meta("v13_eclipse")
    Path(a.out).write_text(json.dumps(out, indent=2))
    print(json.dumps(out["tests"], indent=2))


if __name__ == "__main__":
    main()
