"""Power-generation potential indicator (blueprint Section 8.8; requirement A06; test V-08b).

P_rel(t) = f_sun(t) * (1 au / r_sun(t))^2 * k(t)

with k the cosine of incidence for a named reference panel. This is a
labelled, relative estimate of available sunlight (label: Estimated), not an
electrical-output prediction: efficiency, temperature and storage belong to
extension D02. f_sun weights the visible solar disk uniformly; the
limb-darkened companion P_rel_LD (extension D01, Phase 3 item 2) replaces it by
the visible share of the disk's flux (engine.limb_darkening) and is reported
beside P_rel, which is unchanged.
"""
from __future__ import annotations

import math

import numpy as np

from .. import settings

PANELS = {
    "vertical_tracking": "Vertical panel turning to face the Sun in azimuth (default)",
    "horizontal": "Horizontal panel",
    "fixed_vertical": "Vertical panel fixed at a chosen azimuth",
}


def incidence_factor(model: str, sun_az, sun_el, panel_az: float = 0.0):
    el = np.radians(np.asarray(sun_el, dtype=float))
    if model == "vertical_tracking":
        return np.cos(el) * (el > -math.pi / 2)
    if model == "horizontal":
        return np.maximum(0.0, np.sin(el))
    if model == "fixed_vertical":
        daz = np.radians(np.asarray(sun_az, dtype=float) - panel_az)
        return np.cos(el) * np.maximum(0.0, np.cos(daz))
    raise ValueError(f"Unknown panel model '{model}'")


def p_rel(f_sun, sun_dist_km, sun_az, sun_el, model: str, panel_az: float = 0.0):
    f = np.asarray(f_sun, dtype=float)          # unknown (NaN) visibility stays unknown
    scale = (settings.AU_KM / np.asarray(sun_dist_km, dtype=float)) ** 2
    return f * scale * incidence_factor(model, sun_az, sun_el, panel_az)


METRICS_POLICY = "known-intervals-only/v1"   # recorded in provenance and the result key


def _trapezoid(v: np.ndarray, t: np.ndarray) -> float:
    return float(np.trapezoid(v, t)) if hasattr(np, "trapezoid") else float(np.trapz(v, t))


def window_metrics(times_s: np.ndarray, p: np.ndarray) -> dict:
    """Mean indicator and equivalent full-Sun hours from a series on its time grid (C08-safe).

    Unknown samples (NaN) are never bridged: the trapezoid rule is applied only to grid intervals whose
    both endpoints are known, so unknown time contributes nothing and is reported instead.

      known_time   = sum of the lengths of fully known intervals
      mean         = (integral over known intervals) / known_time
      equivalent_full_sun_h = (integral over known intervals) / 3600 s; since the indicator is >= 0 this is
                     a lower bound of the full-window value whenever coverage < 1 (`lower_bound`)
      coverage     = known_time / window span (time-weighted, not a sample count)
      unknown_hours = (span - known_time) / 3600 s

    With every sample known this is exactly the plain trapezoid over the whole grid (same arithmetic).
    A known sample whose two neighbours are unknown adds no interval and therefore no time.
    """
    t = np.asarray(times_s, dtype=float)
    v = np.asarray(p, dtype=float)
    span = float(t[-1] - t[0]) if t.size >= 2 else 0.0
    ok = np.isfinite(v)
    if t.size < 2 or span <= 0.0:
        return {"mean": None, "equivalent_full_sun_h": None, "coverage": 0.0, "known_hours": 0.0,
                "unknown_hours": span / 3600.0, "lower_bound": True, "policy": METRICS_POLICY}
    if ok.all():
        integral = _trapezoid(v, t)
        known = span
    else:
        seg = ok[:-1] & ok[1:]
        dt = np.diff(t)
        integral = float(np.sum(0.5 * (v[:-1][seg] + v[1:][seg]) * dt[seg]))
        known = float(np.sum(dt[seg]))
    if known <= 0.0:
        return {"mean": None, "equivalent_full_sun_h": None, "coverage": 0.0, "known_hours": 0.0,
                "unknown_hours": span / 3600.0, "lower_bound": True, "policy": METRICS_POLICY}
    return {"mean": integral / known,
            "equivalent_full_sun_h": integral / 3600.0,
            "coverage": known / span,
            "known_hours": known / 3600.0,
            "unknown_hours": (span - known) / 3600.0,
            "lower_bound": bool(known < span),
            "policy": METRICS_POLICY}
