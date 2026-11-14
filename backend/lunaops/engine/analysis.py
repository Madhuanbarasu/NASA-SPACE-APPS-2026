"""Site analysis: one request -> one deterministic result object (blueprint Section 9).

Every view (map, sky panorama, timeline, comparison, export) reads this
object; none recomputes a scientific quantity (C09). The payload excludes
wall-clock time so identical inputs give byte-identical JSON (C04, U-05);
computation time travels in a separate envelope.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field

import numpy as np

from .. import ALGORITHM_VERSION, settings
from .cache import get_cached_horizon, put_cached_horizon
from .dem import TerrainError, coverage_check
from .earth import earth_disk_state, earth_model_settings
from .ephem import Site, earth_geo, sample_target, separation_deg
from .limb_darkening import LD_LABEL, ld_settings, limb_darkened_fraction
from .events import EventConfig, EventDetector, build_intervals, intersect, summarize
from .frames import validate_latlon
from .horizon import compute_horizon, horizon_key, l_corr_label, uncertainty_settings
from .kernels import load
from .power import METRICS_POLICY, PANELS, p_rel, window_metrics
from .provenance import label_rules_digest, labels, record
from .timeutil import check_window, parse_utc, to_utc
from .visibility import HorizonProfile, disk_state, earth_limb_enu, joint_settings, sun_joint_state

OBSERVER_PROFILES = {
    "surface": {"label": "Surface reference", "default_m": 0.0},
    "astronaut": {"label": "Astronaut eye height", "default_m": None},
    "equipment": {"label": "Equipment or antenna", "default_m": None},
}


@dataclass
class AnalysisRequest:
    lat: float
    lon: float
    start_utc: str
    end_utc: str
    step_s: float = settings.DEFAULT_SERIES_STEP_S
    observer_profile: str = "surface"
    observer_h_m: float = 0.0
    sunlit_rule: str = "any"
    dte_rule: str = "centre"
    margin_deg: float = 0.0
    panel_model: str = "vertical_tracking"
    panel_az_deg: float = 0.0
    site_name: str | None = None
    site_id: str | None = None

    def canonical(self) -> dict:
        lat, lon = validate_latlon(self.lat, self.lon)
        return {"lat": round(lat, 7), "lon": round(lon, 7), "start_utc": self.start_utc, "end_utc": self.end_utc,
                "step_s": float(self.step_s), "observer_profile": self.observer_profile,
                "observer_h_m": round(float(self.observer_h_m), 4), "sunlit_rule": self.sunlit_rule,
                "dte_rule": self.dte_rule, "margin_deg": round(float(self.margin_deg), 6),
                "panel_model": self.panel_model, "panel_az_deg": round(float(self.panel_az_deg), 4),
                "site_name": self.site_name, "site_id": self.site_id}


def validate_request(req: AnalysisRequest) -> None:
    if req.observer_profile not in OBSERVER_PROFILES:
        raise ValueError(f"Unknown observer profile '{req.observer_profile}'")
    if not (0.0 <= float(req.observer_h_m) <= 100.0):
        raise ValueError("Observer height must be between 0 and 100 m.")
    for r in (req.sunlit_rule, req.dte_rule):
        if r not in ("any", "centre", "full"):
            raise ValueError(f"Unknown visibility rule '{r}'")
    if not (0.0 <= float(req.margin_deg) <= 10.0):
        raise ValueError("The full-disk margin must be between 0 and 10 degrees.")
    if req.panel_model not in PANELS:
        raise ValueError(f"Unknown panel model '{req.panel_model}'")


def result_id(req: AnalysisRequest) -> str:
    ks = load()
    lock_digest = hashlib.sha256(json.dumps([f["sha256"] for f in ks.files]).encode()).hexdigest()
    hk = horizon_key(*validate_latlon(req.lat, req.lon), float(req.observer_h_m), settings.HORIZON_BINS)
    from ..fingerprint import code_fingerprint
    from .provenance import report_digest
    # code and validation-report digests in the ID: edited code or a new report can never be served a stale result
    payload = json.dumps({"req": req.canonical(), "kernels": lock_digest, "horizon": hk, "alg": ALGORITHM_VERSION,
                          "code": code_fingerprint(), "validation": report_digest(),
                          "uncertain_sigma_k": settings.UNCERTAIN_SIGMA_K,
                          "power_metrics_policy": METRICS_POLICY, "label_rules": label_rules_digest(),
                          "earth_model": earth_model_settings(), "joint": joint_settings(),
                          "limb_darkening": ld_settings()},
                         sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:24]


def get_horizon(lat: float, lon: float, obs_h_m: float, progress=None):
    key = horizon_key(lat, lon, obs_h_m, settings.HORIZON_BINS)
    hz = get_cached_horizon(key)
    if hz is not None:
        return hz
    if progress:
        progress("Building terrain horizon from LOLA DEMs", 0.1)
    hz = compute_horizon(lat, lon, obs_h_m)
    put_cached_horizon(hz)
    return hz


def used_products(hz) -> list[dict]:
    """The terrain products this result's horizon used, with their error maps (for the label terrain pin)."""
    from .dem import products_digest
    digest = {k: (sha, em) for k, sha, em in products_digest()}
    out = []
    for lv in hz.levels:
        sha, em = digest.get(lv.get("key"), (lv.get("sha256"), None))
        out.append({"key": lv.get("key"), "sha256": sha, "error_map_sha256": em, "synthetic": bool(lv.get("synthetic"))})
    return out


def uncertainty_warnings(hz) -> list[str]:
    """Plain-language warnings for the horizon's uncertainty model and flags."""
    out = []
    if hz.sigma_deg is not None:
        out.append(l_corr_label() + ".")
        if hz.discrepancy_unknown is not None and hz.discrepancy_unknown.any():
            out.append(
                f"Cross-product terrain discrepancy could not be measured for {100 * hz.discrepancy_unknown.mean():.1f}% "
                f"of horizon bins (fewer than {settings.CROSS_PRODUCT_SAMPLING['min_pairs']} overlapping samples); "
                "their uncertainty is unknown and affected windows are flagged uncertain.")
        if hz.sigma_nonlinear is not None and hz.sigma_nonlinear.any():
            out.append(
                f"{100 * hz.sigma_nonlinear.mean():.1f}% of horizon bins have an uncertainty above "
                f"{settings.SIGMA_NONLINEAR_DEG:g} deg, beyond the range where first-order propagation is trusted; "
                "affected windows are flagged uncertain.")
    if hz.near_field is not None and hz.near_field.any():
        dist = (hz.params.get("near_field") or {}).get("distance_m")
        out.append(
            f"{100 * hz.near_field.mean():.1f}% of horizon bins are set by terrain within {dist:g} m of the observer "
            "(the DEM's local slope at its resolution); windows that depend on them are marked near_field.")
    return out


def _iso(et):
    return to_utc(et, 0)


def _round(a, nd):
    return [None if (v is None or not math.isfinite(v)) else round(float(v), nd) for v in a]


def _complement(on: list[dict], et0: float, et1: float) -> list[dict]:
    """Full True/False interval list from True-only intervals (for gaps)."""
    out, t = [], et0
    for iv in on:
        if iv["start_et"] > t:
            out.append({"start_et": t, "end_et": iv["start_et"], "state": False,
                        "duration_s": iv["start_et"] - t, "brief": False, "uncertain": None,
                        "uncertain_reasons": [], "near_field": False, "subbin_peak": False})
        out.append(iv)
        t = iv["end_et"]
    if t < et1:
        out.append({"start_et": t, "end_et": et1, "state": False, "duration_s": et1 - t,
                    "brief": False, "uncertain": None, "uncertain_reasons": [], "near_field": False,
                    "subbin_peak": False})
    return out


def build_series(site: Site, hp: HorizonProfile, et0: float, et1: float, step_s: float, req: AnalysisRequest) -> dict:
    n = int(math.floor((et1 - et0) / step_s)) + 1
    ets = et0 + step_s * np.arange(n)
    if ets[-1] < et1:
        ets = np.append(ets, et1)
    s = sample_target(site, "sun", ets)
    e = sample_target(site, "earth", ets)
    g, _ = separation_deg(s, e)
    sun_f, sun_c, earth_f, earth_c, occ_l = [], [], [], [], []
    methods: dict[str, int] = {}
    joint_methods: dict[str, int] = {}
    joint_err = 0.0
    sun_fi: list[float] = []                      # limb-darkened visible flux fraction (Phase 3 item 2)
    ld_methods: dict[str, int] = {}
    ld_err = 0.0
    for i in range(ets.size):
        st = disk_state(hp, s.az[i], s.el[i], s.rho[i])
        et_ = earth_disk_state(hp, earth_geo(e, i))
        methods[et_["method"]] = methods.get(et_["method"], 0) + 1
        eg = earth_geo(e, i)
        sun_d = {"az": s.az[i], "el": s.el[i], "rho": s.rho[i], "gamma": g[i]}
        earth_d = {"az": e.az[i], "el": e.el[i], "rho": e.rho[i], "limb": earth_limb_enu(eg)}
        js = sun_joint_state(hp, sun_d, earth_d, st)
        f, occ = js["f"], js["occ"]
        ld = limb_darkened_fraction(hp, sun_d, earth_d, f)
        sun_fi.append(ld["f_I"])
        ld_methods[ld["method"].split(" (")[0]] = ld_methods.get(ld["method"].split(" (")[0], 0) + 1
        if ld["method"].startswith("adaptive"):
            ld_err = max(ld_err, ld["err"])
        joint_methods[js["method"]] = joint_methods.get(js["method"], 0) + 1
        if js["method"].startswith("adaptive"):
            joint_err = max(joint_err, js["err"])
        sun_f.append(f)
        sun_c.append(st["c"])
        earth_f.append(et_["f"])
        earth_c.append(et_["c"])
        occ_l.append(occ)
    sun_f = np.array(sun_f, dtype=float)
    sun_fi = np.array(sun_fi, dtype=float)
    power = {}
    for model in PANELS:
        p = p_rel(sun_f, s.dist_km, s.az, s.el, model, req.panel_az_deg)
        p_ld = p_rel(sun_fi, s.dist_km, s.az, s.el, model, req.panel_az_deg)
        power[model] = {"series": _round(p, 5), "metrics": window_metrics(ets - et0, p),
                        "series_ld": _round(p_ld, 5), "metrics_ld": window_metrics(ets - et0, p_ld)}
    return {
        "utc": [_iso(t) for t in ets],
        "et": [round(float(t), 3) for t in ets],
        "sun": {"az": _round(s.az, 5), "el": _round(s.el, 5), "rho": _round(s.rho, 5),
                "f": _round(sun_f, 5), "f_ld": _round(sun_fi, 5), "c": _round(sun_c, 5),
                "dist_km": _round(s.dist_km, 1),
                "unit": [[round(float(x), 7) for x in v] for v in s.unit]},
        "earth": {"az": _round(e.az, 5), "el": _round(e.el, 5), "rho": _round(e.rho, 5),
                  "f": _round(earth_f, 5), "c": _round(earth_c, 5), "dist_km": _round(e.dist_km, 1),
                  "light_time_s": _round(e.dist_km / 299792.458, 4),
                  "unit": [[round(float(x), 7) for x in v] for v in e.unit]},
        "earth_occults_sun": _round(occ_l, 5),
        "power": power,
        "step_s": step_s,
        "note": "Display series on a uniform grid; event times come from adaptive detection, not from this grid.",
        "_earth_stats": {"disk_methods": methods,
                         "max_delta_max_deg": float(np.degrees(np.max(e.earth["delta_max"]))),
                         "solver_fallbacks": int(e.earth["solver_fallbacks"])},
        "_joint_stats": {"methods": joint_methods, "max_adaptive_error": joint_err},
        "_ld_stats": {"methods": ld_methods, "max_adaptive_error": ld_err},
    }


def analyze(req: AnalysisRequest, progress=None) -> dict:
    validate_request(req)
    ks = load()
    lat, lon = validate_latlon(req.lat, req.lon)
    cov = coverage_check(lat, lon)
    if not cov["covered"]:
        raise TerrainError(f"Terrain-adjusted results are withheld for this site: {cov['reason']}")
    et0, et1 = parse_utc(req.start_utc), parse_utc(req.end_utc)
    warnings = check_window(et0, et1, req.step_s, settings.MAX_WINDOW_DAYS)
    hz = get_horizon(lat, lon, float(req.observer_h_m), progress)
    if hz.incomplete.any():
        warnings.append(
            f"{100 * hz.incomplete.mean():.1f}% of horizon bins are incomplete (terrain coverage ran out); their "
            "values are lower bounds and dependent visible results are reported as unknown.")
    warnings += uncertainty_warnings(hz)
    site = Site(lat, lon, hz.ground_h_m, float(req.observer_h_m))
    hp = HorizonProfile(hz.h_deg, hz.incomplete, hz.sigma_deg, flags=hz.flag_arrays())
    cfg = EventConfig(sunlit_rule=req.sunlit_rule, dte_rule=req.dte_rule, margin_deg=req.margin_deg)
    det = EventDetector(site, hp, cfg)
    if progress:
        progress("Detecting sunlight and Earth-visibility events", 0.4)
    run = det.run(et0, et1)
    intervals = build_intervals(det, et0, et1, run["events"], run["samples"])
    sun_key, dte_key = f"sun_{req.sunlit_rule}", f"earth_{req.dte_rule}"
    overlap_on = intersect(intervals[sun_key], intervals[dte_key])
    overlap = _complement(overlap_on, et0, et1)
    if progress:
        progress("Building display series", 0.8)
    series = build_series(site, hp, et0, et1, float(req.step_s), req)
    earth_stats = series.pop("_earth_stats")
    joint_stats = series.pop("_joint_stats")
    ld_stats = series.pop("_ld_stats")
    summary = {k: summarize(v, et0, et1) for k, v in intervals.items()}
    summary["overlap"] = summarize(overlap, et0, et1)
    summary["power"] = {m: series["power"][m]["metrics"] for m in PANELS}
    summary["power_ld"] = {m: series["power"][m]["metrics_ld"] for m in PANELS}
    summary["mean_sun_fraction"] = window_metrics(np.asarray(series["et"]) - et0,
                                                  np.asarray([np.nan if v is None else v for v in series["sun"]["f"]]))["mean"]
    events = [{"utc": _iso(ev["et"]), "et": round(ev["et"], 3), "name": ev["name"], "function": ev["function"],
               "direction": ev["direction"], "target": ev["target"]} for ev in run["events"]]

    def iv_json(ivs):
        return [{"start_utc": _iso(iv["start_et"]), "end_utc": _iso(iv["end_et"]),
                 "start_et": round(iv["start_et"], 3), "end_et": round(iv["end_et"], 3),
                 "state": iv["state"], "duration_h": round(iv["duration_s"] / 3600.0, 5),
                 "brief": bool(iv.get("brief")), "uncertain": iv.get("uncertain"),
                 "uncertain_reasons": list(iv.get("uncertain_reasons") or []),
                 "near_field": bool(iv.get("near_field")), "subbin_peak": iv.get("subbin_peak")} for iv in ivs]

    params = {
        "request": req.canonical(),
        "observer": {"profile": req.observer_profile, "label": OBSERVER_PROFILES[req.observer_profile]["label"],
                     "height_m": float(req.observer_h_m)},
        "rules": {"sunlit": req.sunlit_rule, "dte": req.dte_rule, "full_disk_margin_deg": req.margin_deg},
        "panel": {"model": req.panel_model, "description": PANELS[req.panel_model], "azimuth_deg": req.panel_az_deg},
        "event_step_cap_s": cfg.cap_s, "event_step_floor_s": cfg.floor_s, "event_tolerance_s": cfg.tol_s,
        "curvature_inflation": cfg.inflation,
        "horizon_bins": settings.HORIZON_BINS,
        "power_metrics_policy": METRICS_POLICY,
        "earth_model": {**earth_model_settings(), "pole_label": settings.EARTH_POLE_LABEL,
                        "atmosphere": "not modelled (geometric line of sight to the solid Earth)", **earth_stats},
        "sun_earth_joint": {**joint_settings(), **joint_stats},
        "limb_darkening": {**ld_settings(), "label": LD_LABEL, "applies_to": "power series_ld / metrics_ld only; "
                           "series and metrics (uniform disk) are unchanged", **ld_stats},
        "horizon_uncertainty": {**uncertainty_settings(), "L_corr_label": l_corr_label(),
                                "sigma_computed": hz.sigma_deg is not None},
    }
    det_log = {"samples": det.log.samples, "estimate_failures": det.log.estimate_failures,
               "curvature_estimates": det.log.curvature, "angular_speed_estimates": det.log.angular_speed}
    rid = result_id(req)
    used_synthetic = any(bool(lv.get("synthetic")) for lv in hz.levels)
    result = {
        "id": rid,
        "site": {"lat": lat, "lon": lon, "name": req.site_name, "id": req.site_id,
                 "ground_h_m": round(hz.ground_h_m, 3), "terrain_level_at_site": hz.site_level,
                 "coverage": cov},
        "window": {"start_utc": _iso(et0), "end_utc": _iso(et1), "start_et": round(et0, 3), "end_et": round(et1, 3)},
        "horizon": hz.to_json(compact=True),
        "events": events,
        "intervals": {k: iv_json(v) for k, v in intervals.items()} | {"overlap": iv_json(overlap)},
        "summary": summary,
        "series": series,
        "labels": labels(synthetic=used_synthetic, l_corr_assumed=hz.sigma_deg is not None,
                         used_products=used_products(hz)),
        "warnings": warnings + ks.warnings,
        "provenance": record(params, {"key": hz.key, "params": hz.params, "levels": hz.levels}, det_log,
                             synthetic=used_synthetic),
        "geometric_not_radio": ("Earth above the terrain horizon is geometric line of sight. It does not by itself "
                                "guarantee a usable radio link (antenna, power, frequency, multipath and ground "
                                "station availability also matter)."),
    }
    canonical = json.dumps(result, sort_keys=True, separators=(",", ":"))
    result["sha256"] = hashlib.sha256(canonical.encode()).hexdigest()
    return result


def compare(sites: list[dict], windows: list[dict], base: dict, progress=None) -> dict:
    """Comparison of sites x windows; every cell is the single-site result (C01, C09, U-03)."""
    cells = []
    total = len(sites) * len(windows)
    k = 0
    for s in sites:
        for w in windows:
            req = AnalysisRequest(lat=s["lat"], lon=s["lon"], site_name=s.get("name"), site_id=s.get("id"),
                                  start_utc=w["start_utc"], end_utc=w["end_utc"], **base)
            try:
                res = cached_analyze(req, progress)
                cells.append({"site": s, "window": w, "result_id": res["id"], "summary": res["summary"],
                              "labels": res["labels"], "warnings": res["warnings"], "error": None})
            except Exception as exc:  # report per cell; never invent a value
                cells.append({"site": s, "window": w, "result_id": None, "summary": None, "error": str(exc)})
            k += 1
            if progress:
                progress(f"Compared {k} of {total}", 0.05 + 0.9 * k / total)
    return {"sites": sites, "windows": windows, "base": base, "cells": cells}


def cached_analyze(req: AnalysisRequest, progress=None) -> dict:
    from .cache import get_result, put_result

    rid = result_id(req)
    res = get_result(rid)
    if res is None:
        res = analyze(req, progress)
        put_result(res)
    return res
