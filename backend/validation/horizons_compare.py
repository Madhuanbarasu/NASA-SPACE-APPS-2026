"""V-04 / V-05: controlled comparison with JPL Horizons (blueprint Q7, VT-2 to VT-5).

    cd backend && python -m validation.horizons_compare --out horizons.json [--raw-dir horizons_raw]
    python -m validation.run_validation --merge horizons.json

Procedure (Section 11, Q7):
 1. identical site coordinates (Horizons: planetodetic on its lunar reference body, MEAN_ME frame);
 2. read the reference radii from the Horizons header and convert height (VT-2): the script checks that
    Horizons uses the 1737.4 km sphere, LUNA-OPS's reference, so altitude 0 km is the same height in both
    (it stops otherwise);
 3. request apparent azimuth/elevation (quantity 4), airless, TT time tags, extra precision;
 4. compute LUNA-OPS values with CN+S in the pinned body-fixed frame;
 5. record Horizons' ephemeris and pole lines from the header;
 6. compare. Residuals are attributed only once steps 1-5 match.
Needs network access to ssd.jpl.nasa.gov. Default test sites follow Section 10.3 (no terrain is used, so DEM
coverage does not limit them). Every Horizons response is saved verbatim (with its SHA-256) for provenance.

V-04 (epoch-by-epoch direction): hourly Sun and Earth apparent az/el over the window at every site;
pass if max |dAz cos El| <= 0.01 deg and max |dEl| <= 0.01 deg.

V-05 (event timing, its own measurement and status, independent of V-04's): the times at which the Sun's and
Earth's centres cross an ideal flat 0 deg horizon.
  * Reference: Horizons alone. Sign changes of the hourly elevations bracket each crossing; Horizons is then
    queried at 1-minute steps over the hour and at 1-second steps over the minute, and the crossing time is
    interpolated linearly between the two 1-second samples that bracket it.
  * LUNA-OPS: the engine's adaptive event detector (engine.events.EventDetector) on a flat 0 deg horizon,
    functions sun_c / earth_c, over the same window.
  * Matching: same body and direction within 600 s. A detector event without a reference crossing is checked
    against Horizons at 1-minute steps over +-30 min (then refined as above), so a double crossing inside one
    hour is not reported as spurious.
  * Pass: at least one reference crossing, no missed or spurious event, every |t_LUNA - t_Horizons| <= 1.0 s.
    The 1.0 s threshold is the project's event-timing tolerance (the detector's bisection tolerance, used by
    V-14 and the Phase 2 golden test); the blueprint's own V-05 criterion text was not available when this was
    written and should be confirmed. No events at all gives "not run", never "passed".
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lunaops.engine.ephem import Site, sample_target  # noqa: E402
from lunaops.engine.kernels import load  # noqa: E402

API = "https://ssd.jpl.nasa.gov/api/horizons.api"
SITES = [  # (label, lat, lon) - south polar, north polar, nearside equatorial, limb, farside (Sun only)
    ("south-polar A", -89.5, 0.0), ("south-polar B", -86.0, 210.0), ("north-polar", 87.0, 30.0),
    ("nearside equatorial", 0.0, 0.0), ("limb", 0.0, 90.0), ("farside", 0.0, 180.0)]
TARGETS = (("10", "sun"), ("399", "earth"))
V04_TOL_DEG = 0.01
V05_TOL_S = 1.0
V05_MATCH_S = 600.0
MOON_R_KM = 1737.4


class Horizons:
    """Horizons API client that saves every response verbatim and records its SHA-256."""

    def __init__(self, raw_dir: Path | None, pause_s: float = 0.5):
        self.raw_dir = raw_dir
        self.pause_s = pause_s
        self.files: list[dict] = []
        if raw_dir:
            raw_dir.mkdir(parents=True, exist_ok=True)

    def table(self, tag: str, target: str, lat: float, lon: float, start: str, stop: str, step: str,
              seconds: bool = False) -> tuple[str, list]:
        q = {"format": "json", "COMMAND": f"'{target}'", "CENTER": "'coord@301'", "COORD_TYPE": "'GEODETIC'",
             "SITE_COORD": f"'{lon:.6f},{lat:.6f},0.000000'", "MAKE_EPHEM": "'YES'", "EPHEM_TYPE": "'OBSERVER'",
             "START_TIME": f"'{start}'", "STOP_TIME": f"'{stop}'", "STEP_SIZE": f"'{step}'", "QUANTITIES": "'4'",
             "APPARENT": "'AIRLESS'", "TIME_TYPE": "'TT'", "ANG_FORMAT": "'DEG'", "EXTRA_PREC": "'YES'",
             "CSV_FORMAT": "'YES'"}
        if seconds:
            q["TIME_DIGITS"] = "'FRACSEC'"
        url = API + "?" + urllib.parse.urlencode(q)
        raw = None
        for attempt in range(4):
            try:
                with urllib.request.urlopen(url, timeout=120) as r:
                    raw = r.read()
                break
            except Exception:  # noqa: BLE001 - network: retry with backoff, then give up loudly
                if attempt == 3:
                    raise
                time.sleep(2 ** (attempt + 1))
        time.sleep(self.pause_s)
        doc = json.loads(raw.decode())
        if "result" not in doc:
            raise RuntimeError(f"Horizons returned no result for {tag}: {doc.get('error') or doc}")
        if self.raw_dir:
            name = re.sub(r"[^A-Za-z0-9_.-]+", "_", tag) + ".json"
            (self.raw_dir / name).write_bytes(raw)
            self.files.append({"file": name, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
                               "query": {k: v for k, v in q.items() if k != "format"}})
        text = doc["result"]
        return text, parse_rows(text)


def parse_rows(text: str) -> list[tuple[str, float, float]]:
    """(TT calendar tag, azimuth deg, elevation deg) rows of a CSV quantity-4 table; NaN where blank."""
    if "$$SOE" not in text:
        raise RuntimeError("Horizons response has no $$SOE table: " + text[-500:])
    body = text.split("$$SOE")[1].split("$$EOE")[0]
    rows = []
    for ln in body.strip().splitlines():
        parts = [p.strip() for p in ln.split(",")]
        az = float(parts[-3]) if parts[-3] else math.nan
        el = float(parts[-2]) if parts[-2] else math.nan
        rows.append((parts[0], az, el))
    return rows


def header_facts(text: str) -> dict:
    facts = {}
    for key, pat in {"ephemeris_source": r"Center body name:[^\n]*\{source:\s*([^}]+)\}",
                     "target_line": r"(Target body name:[^\n]+)",
                     "center_pole_equ": r"Center pole/equ\s*:\s*([^\n{]+)",
                     "center_radii": r"Center radii\s*:\s*([^\n{]+)",
                     "center_geodetic": r"Center geodetic\s*:\s*([^\n{]+)",
                     "light_bending": r"Rel\. light bend\s*:\s*([^\n]+)",
                     "refraction": r"Atmos refraction:\s*([^\n]+)",
                     "time_type": r"Start time\s*:[^\n]*\b(TT|TDB|UT)\b"}.items():
        m = re.search(pat, text)
        facts[key] = m.group(1).strip() if m else None
    return facts


def tt_tag_to_et(tag: str) -> float:
    """Horizons TT calendar tag ('2026-Nov-14 00:00' or with seconds) -> SPICE ET (TDB seconds past J2000)."""
    import spiceypy as sp
    return float(sp.str2et(tag.strip().replace("A.D. ", "") + " TDT"))


def et_to_tt_tag(et: float) -> str:
    """SPICE ET -> a TT calendar string Horizons accepts (seconds to 1e-3 s)."""
    import spiceypy as sp
    tdt = float(sp.unitim(et, "TDB", "TDT"))
    j2000_tt = 2451545.0
    jd = j2000_tt + tdt / 86400.0
    return f"JD {jd:.9f}"


def sign_crossings(ets, els, h0: float = 0.0) -> list[tuple[float, float, int]]:
    """Brackets (et_a, et_b, direction) where el - h0 changes sign between consecutive finite samples."""
    out = []
    for a, b, ea, eb in zip(ets[:-1], ets[1:], els[:-1], els[1:]):
        if not (math.isfinite(ea) and math.isfinite(eb)):
            continue
        if (ea - h0 > 0) != (eb - h0 > 0):
            out.append((a, b, +1 if eb > ea else -1))
    return out


def interpolate_crossing(ta: float, tb: float, ea: float, eb: float, h0: float = 0.0) -> float:
    return ta + (h0 - ea) * (tb - ta) / (eb - ea)


def match_events(ref: list[dict], got: list[dict], window_s: float = V05_MATCH_S) -> tuple[list, list, list]:
    """Pair reference crossings with detector events (same body and direction, nearest within window_s).
    Returns (pairs, missed reference crossings, unmatched detector events)."""
    used, pairs, missed = set(), [], []
    for r in ref:
        cands = [(abs(g["et"] - r["et"]), j) for j, g in enumerate(got)
                 if j not in used and g["body"] == r["body"] and g["direction"] == r["direction"]]
        cands = [c for c in cands if c[0] <= window_s]
        if not cands:
            missed.append(r)
            continue
        _, j = min(cands)
        used.add(j)
        pairs.append((r, got[j]))
    spurious = [g for j, g in enumerate(got) if j not in used]
    return pairs, missed, spurious


def v05_status(pairs: list, missed: list, spurious: list, tol_s: float = V05_TOL_S) -> tuple[str, str]:
    """V-05 verdict from its own event comparison (never from V-04)."""
    n = len(pairs) + len(missed)
    if n == 0 and not spurious:
        return "not run", "no Sun or Earth centre crossing of the 0 deg horizon in the window; nothing to compare"
    dts = [g["et"] - r["et"] for r, g in pairs]
    worst = max((abs(d) for d in dts), default=float("nan"))
    ok = not missed and not spurious and all(abs(d) <= tol_s for d in dts)
    detail = (f"{len(pairs)} matched centre crossings, {len(missed)} missed, {len(spurious)} spurious; "
              f"max |t_LUNA - t_Horizons| {worst:.3f} s (tolerance {tol_s} s)")
    return ("passed" if ok else "failed"), detail


def refine_crossing(hz: Horizons, target: str, body: str, lat: float, lon: float, ta: float, tb: float,
                    label: str) -> dict | None:
    """Refine a bracket [ta, tb] (ET) to a Horizons crossing time: 1-minute steps, then 1-second steps."""
    span_min = max(1, int(round((tb - ta) / 60.0)))
    _, rows = hz.table(f"v05_{label}_{body}_{ta:.0f}_min", target, lat, lon, et_to_tt_tag(ta), et_to_tt_tag(tb),
                       str(span_min), seconds=True)
    ets = [tt_tag_to_et(r[0]) for r in rows]
    br = sign_crossings(ets, [r[2] for r in rows])
    if not br:
        return None
    a, b, direction = br[0]
    _, rows = hz.table(f"v05_{label}_{body}_{a:.0f}_sec", target, lat, lon, et_to_tt_tag(a), et_to_tt_tag(b),
                       str(max(1, int(round(b - a)))), seconds=True)
    ets = [tt_tag_to_et(r[0]) for r in rows]
    els = [r[2] for r in rows]
    for (sa, sb, d) in sign_crossings(ets, els):
        i = ets.index(sa)
        t = interpolate_crossing(sa, sb, els[i], els[i + 1])
        return {"body": body, "direction": d, "et": t, "bracket_s": sb - sa, "site": label}
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2026-11-14 00:00")
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--out", default="horizons.json")
    ap.add_argument("--raw-dir", default=None, help="folder for the verbatim Horizons responses "
                                                    "(default: <out stem>_raw next to --out)")
    args = ap.parse_args()
    import spiceypy as sp
    from datetime import datetime, timedelta

    from lunaops.engine.events import EventConfig, EventDetector
    from lunaops.engine.visibility import HorizonProfile

    ks = load()
    out_path = Path(args.out)
    raw_dir = Path(args.raw_dir) if args.raw_dir else out_path.with_name(out_path.stem + "_raw")
    hz = Horizons(raw_dir)
    stop = (datetime.fromisoformat(args.start) + timedelta(days=args.days)).strftime("%Y-%m-%d %H:%M")
    flat = HorizonProfile(np.zeros(3600), np.zeros(3600, dtype=bool))
    v04_runs, facts_all, v05_events, v05_missed, v05_spurious, residual_rows = [], [], [], [], [], []
    worst_az = worst_el = 0.0
    for label, lat, lon in SITES:
        site = Site(lat, lon, 0.0, 0.0)
        et0, et1 = tt_tag_to_et(args.start), tt_tag_to_et(stop)
        det = EventDetector(site, flat, EventConfig())
        run = det.run(et0, et1)
        for target, body in TARGETS:
            if label == "farside" and body == "earth":
                continue
            text, rows = hz.table(f"v04_{label}_{body}_hourly", target, lat, lon, args.start, stop, "1h")
            facts = header_facts(text)
            facts_all.append({"site": label, "target": body, **facts})
            radii = [float(x) for x in re.findall(r"[\d.]+", facts.get("center_radii") or "")[:3]]
            if len(radii) != 3 or any(abs(r - MOON_R_KM) > 1e-9 for r in radii):
                sys.exit(f"Horizons reference radii {facts.get('center_radii')!r} differ from {MOON_R_KM} km: "
                         "convert the site height (VT-2) before comparing")
            ets = [tt_tag_to_et(r[0]) for r in rows]
            s = sample_target(site, body, ets)
            r_az = r_el = 0.0
            for (tag, haz, hel), et, az, el in zip(rows, ets, s.az, s.el):
                if not (math.isfinite(haz) and math.isfinite(hel)):
                    continue
                daz = ((az - haz + 180) % 360 - 180) * math.cos(math.radians(el))
                residual_rows.append((label, body, tag, et, haz, hel, float(az), float(el), daz, el - hel))
                r_az, r_el = max(r_az, abs(daz)), max(r_el, abs(el - hel))
            worst_az, worst_el = max(worst_az, r_az), max(worst_el, r_el)
            v04_runs.append({"site": label, "target": body, "n": len(rows), "max_abs_daz_cos_el_deg": r_az,
                             "max_abs_del_deg": r_el})
            # V-05: reference crossings from Horizons, detector events from the engine
            ref = []
            for ta, tb, _ in sign_crossings(ets, [r[2] for r in rows]):
                c = refine_crossing(hz, target, body, lat, lon, ta, tb, label)
                if c:
                    ref.append(c)
            got = [{"body": body, "direction": e["direction"], "et": e["et"], "site": label}
                   for e in run["events"] if e["function"] == f"{body}_c"]
            pairs, missed, spurious = match_events(ref, got)
            confirmed = []
            for g in spurious:      # a double crossing inside one hour: look again around the detector event
                _, rr = hz.table(f"v05_{label}_{body}_{g['et']:.0f}_confirm", target, lat, lon,
                                 et_to_tt_tag(g["et"] - 1800.0), et_to_tt_tag(g["et"] + 1800.0), "60", seconds=True)
                e2 = [tt_tag_to_et(r[0]) for r in rr]
                for ta, tb, d in sign_crossings(e2, [r[2] for r in rr]):
                    c = refine_crossing(hz, target, body, lat, lon, ta, tb, label)
                    if c and all(abs(c["et"] - x["et"]) > 1.0 for x in ref + confirmed):
                        confirmed.append(c)
            if confirmed:
                pairs, missed, spurious = match_events(ref + confirmed, got)
            for r, g in pairs:
                v05_events.append({"site": label, "body": body, "direction": r["direction"],
                                   "t_horizons_utc": sp.et2utc(r["et"], "ISOC", 3), "et_horizons": r["et"],
                                   "et_luna": g["et"], "dt_s": g["et"] - r["et"], "ref_bracket_s": r["bracket_s"]})
            v05_missed += [{**m, "utc": sp.et2utc(m["et"], "ISOC", 3)} for m in missed]
            v05_spurious += [{**g, "utc": sp.et2utc(g["et"], "ISOC", 3)} for g in spurious]
    passed = worst_az <= V04_TOL_DEG and worst_el <= V04_TOL_DEG
    pairs_all = [({"et": e["et_horizons"]}, {"et": e["et_luna"]}) for e in v05_events]
    st5, det5 = v05_status(pairs_all, v05_missed, v05_spurious)
    out = {"tests": {"V-04": {"status": "passed" if passed else "failed",
                              "detail": f"max |dAz cos El| {worst_az:.3e} deg, max |dEl| {worst_el:.3e} deg "
                                        f"(tolerance {V04_TOL_DEG} deg); {sum(r['n'] for r in v04_runs)} epochs; "
                                        f"kernel profile {ks.profile}"},
                     "V-05": {"status": st5, "detail": det5 + f"; kernel profile {ks.profile}"}},
           "window": {"start_tt": args.start, "stop_tt": stop},
           "v04": {"criterion": f"max |dAz cos El| and max |dEl| <= {V04_TOL_DEG} deg", "runs": v04_runs},
           "v05": {"criterion": f"no missed or spurious centre crossing of the 0 deg horizon, every |dt| <= "
                                f"{V05_TOL_S} s; criterion = project event-timing tolerance (blueprint text "
                                f"unavailable, to be confirmed)",
                   "events": v05_events, "missed": v05_missed, "spurious": v05_spurious},
           "horizons_header_facts": facts_all, "horizons_responses": hz.files, "raw_dir": str(raw_dir)}
    from validation.common import run_meta
    out["meta"] = run_meta("horizons_compare")
    out_path.write_text(json.dumps(out, indent=2))
    with open(out_path.with_name(out_path.stem + "_v04_residuals.csv"), "w") as f:
        f.write("site,target,tt_tag,et,horizons_az_deg,horizons_el_deg,luna_az_deg,luna_el_deg,daz_cos_el_deg,del_deg\n")
        for r in residual_rows:
            f.write(",".join(str(x) for x in r) + "\n")
    print(json.dumps(out["tests"], indent=2))


if __name__ == "__main__":
    main()
