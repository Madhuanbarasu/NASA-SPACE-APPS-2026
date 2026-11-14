"""Communication simulation built on a completed engine analysis result.

Direct-to-Earth (DTE) geometry is read from the result, never recomputed: Earth azimuth, elevation, distance, light
time and clearance above the terrain horizon (series on the analysis grid), the terrain horizon profile, and the
Earth-visibility intervals of the result's DTE rule (adaptive event detection, with their uncertainty flags). The
engine's validation labels are passed through verbatim.

On top of it this package adds (all labelled VALIDATION_STATUS): the RF link budget over the actual distance, the
hypothetical relay's two legs, availability timelines (geometric, RF-feasible, unknown kept apart), comparison
statistics and the store-and-forward planner.
"""
from __future__ import annotations

import hashlib
import json
import math
import threading
from collections import OrderedDict

import numpy as np

from lunaops.engine.cache import get_result
from lunaops.engine.ephem import Site
from lunaops.engine.timeutil import parse_utc, to_utc
from lunaops.engine.visibility import HorizonProfile
from lunaops.fingerprint import code_fingerprint

from . import COMMS_VERSION, VALIDATION_STATUS, comms_code_hash
from . import linkbudget as LB
from . import relay as RL
from . import windows as W
from .constants import R_MOON_KM, moon_gm

ENGINE_LABEL_KEYS = ("sun_earth_azel", "horizon", "disk_visibility", "events")
_RESULTS: "OrderedDict[str, dict]" = OrderedDict()
_RELAYS: "OrderedDict[str, dict]" = OrderedDict()
_LOCK = threading.Lock()


class CommsInputError(ValueError):
    pass


class RelayConfigError(CommsInputError):
    """The hypothetical relay cannot be simulated with the entered configuration (missing or invalid elements, step or
    grazing altitude). Reported with the relay only: direct-to-Earth, its link budget and the planner are still computed."""

    def __init__(self, problems: list[str]):
        self.problems = [p for p in problems if p] or ["The relay configuration is not valid."]
        super().__init__("; ".join(self.problems))


def _iso(et: float) -> str:
    """UTC text through the engine's SPICE time conversion (leap seconds from the loaded LSK), whole seconds."""
    return to_utc(float(et), 0)


def load_result(rid: str) -> dict | None:
    with _LOCK:
        r = _RESULTS.get(rid)
        if r is not None:
            _RESULTS.move_to_end(rid)
            return r
    r = get_result(rid)
    if r is None:
        return None
    with _LOCK:
        _RESULTS[rid] = r
        while len(_RESULTS) > 3:
            _RESULTS.popitem(last=False)
    return r


def horizon_profile(res: dict) -> HorizonProfile:
    hz = res["horizon"]
    flags = {k: hz.get(k) for k in ("near_field", "sigma_nonlinear", "discrepancy_unknown", "subbin_excess_deg", "subbin_unknown")}
    return HorizonProfile(np.asarray(hz["h_deg"], float), np.asarray(hz["incomplete"], bool),
                          None if hz.get("sigma_deg") is None else np.asarray([np.nan if v is None else v for v in hz["sigma_deg"]], float),
                          flags)


def site_of(res: dict) -> Site:
    s = res["site"]
    obs = res["provenance"]["parameters"]["observer"]["height_m"]
    return Site(float(s["lat"]), float(s["lon"]), float(s["ground_h_m"]), float(obs))


# ------------------------------------------------------------------ direct to Earth (engine values)
def direct(res: dict) -> dict:
    et0, et1 = res["window"]["start_et"], res["window"]["end_et"]
    rule = res["provenance"]["parameters"]["rules"]["dte"]
    vis = W.segments_from_intervals(res["intervals"][f"earth_{rule}"], et0, et1)
    se = res["series"]
    ets = np.asarray(se["et"], float)
    el = np.asarray([np.nan if v is None else v for v in se["earth"]["el"]], float)
    c = np.asarray([np.nan if v is None else v for v in se["earth"]["c"]], float)
    # display row: Earth centre above the local horizontal plane but below the terrain horizon (series grid)
    above_plane = W.segments_from_samples(ets, el)
    blocked = W.combine("and_not", above_plane, W.segments_from_samples(ets, c))
    return {"rule": rule, "visible": vis, "terrain_blocked": blocked, "ets": ets,
            "dist_km": np.asarray([np.nan if v is None else v for v in se["earth"]["dist_km"]], float)}


def _labels(res: dict) -> dict:
    """The analysis result's own validation labels, verbatim (a result can carry a stricter label than /api/status, e.g.
    'Pending validation' for the horizon when the result uses the uncalibrated L_corr uncertainty model)."""
    return {k: (res.get("labels", {}).get(k) or {}).get("validation") for k in ENGINE_LABEL_KEYS}


def _label_reasons(res: dict) -> dict:
    return {k: list((res.get("labels", {}).get(k) or {}).get("reasons") or []) for k in ENGINE_LABEL_KEYS}


# ------------------------------------------------------------------ RF over time
def rf_timeline(geom: list[dict], ets: np.ndarray, dist_km: np.ndarray, link: dict | None) -> tuple[list[dict] | None, dict]:
    """RF-feasible timeline = geometric timeline AND margin >= 0 (margin sampled on `ets`, boundaries interpolated).
    None when the link budget is incomplete (then nothing is called feasible or infeasible)."""
    ev = LB.evaluate(link, dist_km)
    info = {"complete": ev["complete"], "problems": ev["problems"], "basis": ev["basis"], "reference": ev["reference"],
            "stages": ev["stages"], "inputs": ev["inputs"], "notes": ev["notes"]}
    finite = np.isfinite(dist_km) & (dist_km > 0)
    if finite.any():
        dmin, dmax = float(np.nanmin(dist_km[finite])), float(np.nanmax(dist_km[finite]))
        info["at_min_distance"] = LB.breakdown(link, dmin)
        info["at_max_distance"] = LB.breakdown(link, dmax)
    if not ev["complete"]:
        return None, info
    m = np.asarray(ev["values"]["margin_db"], float)
    info["margin_db"] = {"min": float(np.nanmin(m)), "max": float(np.nanmax(m))}
    rf_ok = W.segments_from_samples(ets, m + 0.0)       # margin > 0 open; == 0 counts as closed (boundary)
    return W.combine("and", geom, rf_ok), info


def _margin_series(link, dist_km):
    ev = LB.evaluate(link, dist_km)
    return None if not ev["complete"] else np.asarray(ev["values"]["margin_db"], float)


# ------------------------------------------------------------------ relay (cached per result and orbit)
def relay_geometry(res: dict, relay_cfg: dict) -> dict:
    el, probs = RL.validate_elements(relay_cfg, parse_utc)
    probs = list(probs)
    # sampling step: 60 s when not given (a numerical sampling choice, not a hardware value); an entered 0 is an error,
    # not "not given" (it used to be replaced by 60 s silently)
    step_in, graze_in = relay_cfg.get("step_s"), relay_cfg.get("grazing_alt_km")
    step = 60.0 if step_in is None else float(step_in)
    graze = 0.0 if graze_in is None else float(graze_in)
    if not (math.isfinite(step) and RL.MIN_STEP_S <= step <= RL.MAX_STEP_S):
        probs.append(f"The relay sampling step must be between {RL.MIN_STEP_S:g} and {RL.MAX_STEP_S:g} s.")
    if not (math.isfinite(graze) and 0.0 <= graze <= 500.0):
        probs.append("The grazing altitude must be between 0 and 500 km.")
    if el is None or probs:
        raise RelayConfigError(probs)
    key = hashlib.sha256(json.dumps([res["id"], el.__dict__, step, graze], sort_keys=True, default=str).encode()).hexdigest()
    with _LOCK:
        hit = _RELAYS.get(key)
    if hit is not None:
        return hit
    et0, et1 = res["window"]["start_et"], res["window"]["end_et"]
    try:
        g = RL.simulate(el, et0, et1, step, site_of(res), horizon_profile(res), graze)
    except RL.RelayInputError as exc:
        raise RelayConfigError([str(exc)])
    g["elements"] = el
    g["step_s"] = step
    g["grazing_km"] = graze
    l1 = g["leg1"]
    g["leg1_tl"] = W.segments_from_samples(g["ets"], l1["clearance_deg"], l1["unknown"], l1["uncertain"])
    g["leg2_tl"] = W.segments_from_samples(g["ets"], g["leg2"]["clearance_deg"])
    g["both_tl"] = W.combine("and", g["leg1_tl"], g["leg2_tl"])
    with _LOCK:
        _RELAYS[key] = g
        while len(_RELAYS) > 4:
            _RELAYS.popitem(last=False)
    return g


# ------------------------------------------------------------------ store and forward
def store_and_forward(tl: list[dict] | None, volume_mbit: float | None, rate_kbps: float | None, start_et: float,
                      et1: float) -> dict:
    """Conceptual contact planning: data of `volume_mbit` ready at start_et is sent at `rate_kbps` during open segments
    of `tl` (whole contact time usable; no protocol overhead, light-time or handover modelled)."""
    if tl is None:
        return {"evaluated": False, "reason": "The chosen path has no evaluated timeline (complete its link budget or relay)."}
    if not volume_mbit or volume_mbit <= 0 or not rate_kbps or rate_kbps <= 0:
        return {"evaluated": False, "reason": "Enter a data volume and a transmission rate greater than 0."}
    if not (math.isfinite(volume_mbit) and math.isfinite(rate_kbps)) or volume_mbit > 1e9 or rate_kbps > 1e9:
        return {"evaluated": False, "reason": "The data volume and the transmission rate must not exceed 1e9 (Mbit, kbit/s)."}
    need_s = volume_mbit * 1e6 / (rate_kbps * 1e3)
    sent_s, plan = 0.0, []
    for s in tl:
        if s["state"] is not True or s["t1"] <= start_et:
            continue
        a = max(s["t0"], start_et)
        use = min(s["t1"] - a, need_s - sent_s)
        if use <= 0:
            break
        plan.append({"start_et": a, "end_et": a + use, "start_utc": _iso(a), "end_utc": _iso(a + use),
                     "sent_mbit": use * rate_kbps * 1e3 / 1e6, "uncertain": bool(s.get("uncertain"))})
        sent_s += use
        if sent_s >= need_s - 1e-9:
            break
    done = sent_s >= need_s - 1e-9
    return {"evaluated": True, "volume_mbit": volume_mbit, "rate_kbps": rate_kbps, "transmit_time_h": need_s / 3600.0,
            "start_utc": _iso(start_et), "contacts_used": len(plan), "plan": plan[:200],
            "complete": done, "completion_utc": plan[-1]["end_utc"] if done and plan else None,
            "elapsed_h": ((plan[-1]["end_et"] - start_et) / 3600.0) if done and plan else None,
            "sent_mbit": sent_s * rate_kbps * 1e3 / 1e6, "remaining_mbit": max(0.0, volume_mbit - sent_s * rate_kbps * 1e3 / 1e6),
            "queued_h": (((plan[-1]["end_et"] - start_et) - need_s) / 3600.0) if done and plan else None,
            "note": ("High-level contact-planning simulation: data waits in a queue during gaps and is sent at the "
                     "configured rate during open contacts. Not a DTN (Bundle Protocol) or LunaNet implementation; no "
                     "protocol overhead, acknowledgement, light time, handover or ground scheduling is modelled.")}


# ------------------------------------------------------------------ the full simulation
def simulate(body: dict) -> dict:
    rid = body.get("result_id")
    res = load_result(rid) if rid else None
    if res is None:
        raise LookupError("The analysis result is not available. Run the analysis for this site and window first.")
    et0, et1 = float(res["window"]["start_et"]), float(res["window"]["end_et"])
    d = direct(res)
    ets, dist = d["ets"], d["dist_km"]
    direct_rf, direct_link = rf_timeline(d["visible"], ets, dist, body.get("direct_link"))
    out_rows = {"earth_visible": d["visible"], "terrain_blocked": d["terrain_blocked"], "direct_rf": direct_rf}
    relay_out = None
    relay_problems = None
    relay_geo_tl = relay_rf_tl = None
    g = None
    if body.get("relay"):
        try:
            g = relay_geometry(res, body["relay"])
        except RelayConfigError as exc:
            relay_problems = exc.problems
    if g is not None:
        up_m = _margin_series(body.get("relay_up_link"), g["leg1"]["range_km"])
        dn_m = _margin_series(body.get("relay_down_link"), g["leg2"]["range_km"])
        relay_geo_tl = g["both_tl"]
        up_info = rf_timeline(g["leg1_tl"], g["ets"], g["leg1"]["range_km"], body.get("relay_up_link"))
        dn_info = rf_timeline(g["leg2_tl"], g["ets"], g["leg2"]["range_km"], body.get("relay_down_link"))
        if up_m is not None and dn_m is not None:
            relay_rf_tl = W.combine("and", up_info[0], dn_info[0])
        out_rows.update({"relay_leg1": g["leg1_tl"], "relay_leg2": g["leg2_tl"], "relay_geometric": relay_geo_tl,
                         "relay_rf": relay_rf_tl})
        el = g["elements"]
        st = RL.orbit_summary(el, g["gm"])
        l1, l2 = g["leg1"], g["leg2"]
        relay_out = {
            "label": "Hypothetical relay (user-defined orbit; not an actual NASA satellite)",
            "elements": {"a_km": el.a_km, "e": el.e, "i_deg": el.i_deg, "raan_deg": el.raan_deg, "argp_deg": el.argp_deg,
                         "m0_deg": el.m0_deg, "epoch_utc": _iso(el.epoch_et), "frame": el.frame},
            "orbit": {k: round(v, 4) for k, v in st.items()}, "step_s": g["step_s"], "samples": int(g["ets"].size),
            "grazing_alt_km": g["grazing_km"],
            "leg1": {"range_km": _mm(l1["range_km"]), "el_deg": _mm(l1["el_deg"]),
                     "unknown_share": float(l1["unknown"].mean()), "uncertain_share": float(l1["uncertain"].mean()),
                     "stats": W.round_stats(W.stats(g["leg1_tl"], et0, et1)), "link": up_info[1]},
            "leg2": {"range_km": _mm(l2["range_km"]), "stats": W.round_stats(W.stats(g["leg2_tl"], et0, et1)), "link": dn_info[1]},
            "both": W.round_stats(W.stats(relay_geo_tl, et0, et1)),
            "rf": None if relay_rf_tl is None else W.round_stats(W.stats(relay_rf_tl, et0, et1)),
            "series": _relay_series(g),
        }
    geo_any = W.combine("or", d["visible"], relay_geo_tl) if relay_geo_tl is not None else d["visible"]
    rf_any = None
    if direct_rf is not None and (relay_geo_tl is None or relay_rf_tl is not None):
        rf_any = W.combine("or", direct_rf, relay_rf_tl) if relay_rf_tl is not None else direct_rf
    out_rows["any_geometric"] = geo_any
    out_rows["any_rf"] = rf_any
    no_path = [{**s, "state": (None if s["state"] is None else (not s["state"]))} for s in geo_any]
    out_rows["no_geometric_path"] = W.merge(no_path)
    comparison = {
        "direct_geometric": W.round_stats(W.stats(d["visible"], et0, et1)),
        "direct_rf": None if direct_rf is None else W.round_stats(W.stats(direct_rf, et0, et1)),
        "relay_geometric": None if relay_geo_tl is None else W.round_stats(W.stats(relay_geo_tl, et0, et1)),
        "relay_rf": None if relay_rf_tl is None else W.round_stats(W.stats(relay_rf_tl, et0, et1)),
        "any_geometric": W.round_stats(W.stats(geo_any, et0, et1)),
        "any_rf": None if rf_any is None else W.round_stats(W.stats(rf_any, et0, et1)),
    }
    if relay_geo_tl is not None:
        add = W.combine("and_not", relay_geo_tl, d["visible"])
        comparison["relay_adds_geometric_h"] = round(W.stats(add, et0, et1)["open_h"], 5)
        if relay_rf_tl is not None and direct_rf is not None:
            comparison["relay_adds_rf_h"] = round(W.stats(W.combine("and_not", relay_rf_tl, direct_rf), et0, et1)["open_h"], 5)
    ref = body.get("reference_utc")
    try:
        ref_et = parse_utc(ref) if ref else et0
    except Exception:  # noqa: BLE001
        ref_et = et0
    ref_et = min(max(ref_et, et0), et1 - 1e-3)
    nxt = {k: _nc(v, ref_et) for k, v in out_rows.items() if v is not None}
    dtn_cfg = body.get("dtn")
    dtn = None
    if dtn_cfg:
        path = dtn_cfg.get("path") or "direct_rf"
        tl = out_rows.get(path)
        start, start_problem = ref_et, None
        if dtn_cfg.get("start_utc"):
            try:
                start = parse_utc(dtn_cfg["start_utc"])
            except Exception as exc:  # noqa: BLE001 - the parser's message is shown
                start_problem = f"Start time: {exc}"   # never replaced by another time silently
        dtn = ({"path": path, "evaluated": False, "reason": start_problem} if start_problem else
               {"path": path, **store_and_forward(tl, dtn_cfg.get("volume_mbit"), dtn_cfg.get("rate_kbps"), start, et1)})
    se = res["series"]
    return plain({
        "comms_version": COMMS_VERSION, "comms_status": VALIDATION_STATUS, "result_id": res["id"],
        "site": {k: res["site"].get(k) for k in ("lat", "lon", "name", "ground_h_m", "terrain_level_at_site", "coverage")},
        "window": res["window"], "series_step_s": se["step_s"], "reference_utc": _iso(ref_et),
        "engine_labels": _labels(res), "engine_label_reasons": _label_reasons(res), "geometric_not_radio": res.get("geometric_not_radio"),
        "direct": {"rule": d["rule"], "stats": W.round_stats(W.stats(d["visible"], et0, et1)),
                   "terrain_blocked_stats": W.round_stats(W.stats(d["terrain_blocked"], et0, et1)),
                   "horizon_incomplete_share": res["horizon"].get("incomplete_share"),
                   "series": {"utc": se["utc"], "el": se["earth"]["el"], "az": se["earth"]["az"], "dist_km": se["earth"]["dist_km"],
                              "light_time_s": se["earth"]["light_time_s"], "clearance_deg": se["earth"]["c"], "f": se["earth"]["f"]},
                   "link": direct_link},
        "relay": relay_out,
        "relay_problems": relay_problems,
        "timeline": {k: (None if v is None else W.to_json(v, _iso)) for k, v in out_rows.items()},
        "next": nxt, "comparison": comparison, "dtn": dtn,
        "provenance": provenance(res, body),
    })


def plain(o):
    """JSON-safe copy: NumPy scalars and arrays become Python numbers, booleans and lists; non-finite floats become None."""
    if isinstance(o, dict):
        return {k: plain(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [plain(v) for v in o]
    if isinstance(o, np.ndarray):
        return plain(o.tolist())
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, (float, np.floating)):
        f = float(o)
        return f if np.isfinite(f) else None
    return o


def _mm(a) -> dict:
    a = np.asarray(a, float)
    f = a[np.isfinite(a)]
    return {"min": float(f.min()), "max": float(f.max()), "mean": float(f.mean())} if f.size else {"min": None, "max": None, "mean": None}


def _nc(tl, t):
    r = W.next_change(tl, t)
    if r is None:
        return None
    return {**r, "until_utc": _iso(r["until_et"]), "next_open_utc": None if r["next_open_et"] is None else _iso(r["next_open_et"])}


def _relay_series(g: dict, max_points: int = 2000) -> dict:
    n = g["ets"].size
    idx = np.unique(np.linspace(0, n - 1, min(n, max_points)).astype(int))
    l1, l2 = g["leg1"], g["leg2"]
    r = lambda a, nd: [None if not np.isfinite(v) else round(float(v), nd) for v in np.asarray(a)[idx]]  # noqa: E731
    return {"utc": [_iso(t) for t in g["ets"][idx]], "el_deg": r(l1["el_deg"], 3), "az_deg": r(l1["az_deg"], 3),
            "clearance_deg": r(l1["clearance_deg"], 3), "range_km": r(l1["range_km"], 1),
            "earth_limb_clearance_deg": r(l2["clearance_deg"], 3), "earth_range_km": r(l2["range_km"], 0),
            "alt_km": r(g["alt_km"], 1), "decimated": bool(idx.size < n)}


def provenance(res: dict, body: dict) -> dict:
    p = res["provenance"]
    gm = moon_gm()
    return {
        "comms_version": COMMS_VERSION, "comms_code_sha256": comms_code_hash(), "status": VALIDATION_STATUS,
        "status_note": ("The official LUNA-OPS validation report covers the science engine (backend/lunaops) only. RF, "
                        "relay, timeline-algebra and planner results here are outside it and have not been validated. "
                        "Direct-to-Earth geometry and its labels come unchanged from the engine result."),
        "engine": {"result_id": res["id"], "algorithm_version": p.get("algorithm_version"),
                   "code_fingerprint": p.get("code_fingerprint"), "labels": _labels(res),
                   "aberration": p.get("aberration"), "event_detection": p.get("event_detection"),
                   "earth_model_atmosphere": p["parameters"]["earth_model"].get("atmosphere"),
                   "dte_rule": p["parameters"]["rules"]["dte"]},
        "engine_code_fingerprint_now": code_fingerprint(),
        "kernels": [{"name": f.get("name"), "role": f.get("role"), "sha256": f.get("sha256")} for f in (p.get("kernels") or {}).get("files", [])],
        "frame": "lunar body-fixed frame of the loaded kernels (engine setting); J2000 for inertial states",
        "terrain": {"horizon_levels": [lv.get("key") for lv in res["horizon"].get("levels", [])],
                    "incomplete_share": res["horizon"].get("incomplete_share")},
        "gm": gm,
        "constants": {"k_boltzmann": "1.380649e-23 J/K (exact, SI)", "c": "299792458 m/s (exact, SI)",
                      "moon_radius_km": R_MOON_KM},
        "link_configs": {k: (body.get(k) or None) for k in ("direct_link", "relay_up_link", "relay_down_link")},
        "relay_config": body.get("relay"),
        "methods": {
            "direct": "Engine analysis result (series and adaptive Earth-visibility intervals of the result's DTE rule); not recomputed",
            "terrain_blocked_row": "Series grid: Earth centre above 0 deg elevation but its clearance above the terrain horizon <= 0; boundaries by linear interpolation",
            "rf": "Free-space link budget at each sample's distance; RF-feasible = geometric open AND margin > 0 (margin boundaries by linear interpolation)",
            "relay": "Two-body Keplerian orbit (GM from gm_de440.tpc); J2000 states; SPICE pxform to the lunar body-fixed frame; leg 1 vs the site's terrain horizon and the lunar sphere; leg 2 vs the lunar sphere (+ grazing altitude)",
            "timelines": "Three-valued (open, closed, unknown); unknown is never counted as open or closed",
        },
        "limitations": [
            "A geometrically visible Earth or relay does not guarantee a working radio link.",
            "Free-space link budget only: no atmosphere, rain, polarisation, multipath, diffraction or lunar-surface propagation effects (see NASA Glenn's Lunar Surface Propagation research).",
            "Every RF parameter is user-entered; LUNA-OPS supplies no hardware values and no default.",
            "The Earth endpoint is the Earth's centre; ground stations, DSN availability and scheduling are not modelled.",
            "The relay is hypothetical and propagated as a two-body Keplerian orbit; gravity-field harmonics and third-body perturbations are neglected, so real orbits with the same elements diverge.",
            "Relay windows come from sampling at the stated step; contacts shorter than one step can be missed.",
            "The store-and-forward planner is a high-level contact-planning simulation, not DTN or LunaNet.",
        ],
    }
