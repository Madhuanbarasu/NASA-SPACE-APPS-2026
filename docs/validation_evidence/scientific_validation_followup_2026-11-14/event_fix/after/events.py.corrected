"""Event detection (blueprint Sections 8.6-8.7; test V-14).

Bound-guided adaptive sampling: after a sample at t the change of each event
function g over a step tau is estimated as R0*tau + 0.5*A*tau^2, and the step
is the tau at which that estimate reaches |g(t)|:

    tau* = 2|g| / (R0 + sqrt(R0^2 + 2 A |g|)),  dt = clip(tau*, 1 s, 600 s)

R0 uses analytic SPICE rates at the sample; A is estimated from an hourly grid
and inflated by 1.5, so detection performance is established by V-14, not
proven. A runtime check halves the step and doubles A whenever an observed
change exceeds the estimate, and logs it in provenance. Samples are also
placed at every horizon-table node the target crosses. Each sign change is
bisected to 1 s.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .. import settings
from .ephem import Site, TargetSample, sample_target, separation_deg
from .visibility import (HorizonProfile, disk_state, earth_radius_toward_sun, rule_state, sun_fraction_with_earth,
                         sun_vis_clearance)

FUNCS = ["sun_c", "sun_top", "sun_bot", "sun_vis", "earth_c", "earth_top", "earth_bot",
         "ecl_contact", "ecl_centre", "ecl_total"]
FAR_TESTABLE = {"sun_c", "sun_top", "sun_bot", "earth_c", "earth_top", "earth_bot"}
EVENT_NAMES = {
    ("sun_top", +1): "First light (any part of the Sun)",
    ("sun_top", -1): "Last light (Sun fully below terrain)",
    ("sun_c", +1): "Sun centre rises",
    ("sun_c", -1): "Sun centre sets",
    ("sun_bot", +1): "Whole Sun clears the margin",
    ("sun_bot", -1): "Terrain starts to cover the Sun",
    ("earth_top", +1): "Earthrise (any part)",
    ("earth_top", -1): "Earthset (last part)",
    ("earth_c", +1): "Earth centre rises",
    ("earth_c", -1): "Earth centre sets",
    ("earth_bot", +1): "Whole Earth clears the margin",
    ("earth_bot", -1): "Terrain starts to cover Earth",
    ("ecl_contact", -1): "Earth begins to cover the Sun",
    ("ecl_contact", +1): "Earth stops covering the Sun",
    ("ecl_centre", -1): "Sun's centre passes behind Earth",
    ("ecl_centre", +1): "Sun's centre emerges from behind Earth",
    ("sun_vis", +1): "Sun visible again (terrain and Earth considered)",
    ("sun_vis", -1): "No part of the Sun visible (terrain and Earth considered)",
    ("ecl_total", -1): "Sun fully covered by Earth",
    ("ecl_total", +1): "Sun reappears from behind Earth",
}


@dataclass
class EventConfig:
    sunlit_rule: str = "any"
    dte_rule: str = "centre"
    margin_deg: float = 0.0
    cap_s: float = settings.EVENT_STEP_CAP_S
    floor_s: float = settings.EVENT_STEP_FLOOR_S
    tol_s: float = settings.EVENT_TOL_S
    inflation: float = settings.CURVATURE_INFLATION


@dataclass
class Sample:
    et: float
    vals: dict
    r0: dict
    far: dict
    geo: dict


@dataclass
class DetectionLog:
    samples: int = 0
    estimate_failures: list = field(default_factory=list)
    curvature: dict = field(default_factory=dict)
    angular_speed: dict = field(default_factory=dict)


class EventDetector:
    def __init__(self, site: Site, hp: HorizonProfile, cfg: EventConfig):
        self.site = site
        self.hp = hp
        self.cfg = cfg
        self.slopes = np.abs(np.diff(np.append(hp.h, hp.h[0]))) / hp.bin  # deg/deg per interval
        self.log = DetectionLog()

    # ----------------------------------------------------------- geometry
    def _targets(self, ets) -> tuple[TargetSample, TargetSample, np.ndarray, np.ndarray]:
        s = sample_target(self.site, "sun", ets)
        e = sample_target(self.site, "earth", ets)
        g, gr = separation_deg(s, e)
        return s, e, g, gr

    def _slope_near(self, az: float, az_rate: float, hw: float) -> float:
        reach = abs(az_rate) * self.cfg.cap_s + hw + self.hp.bin
        idx = self.hp.span_nodes(az - reach, az + reach)
        return float(self.slopes[idx].max())

    def _earth_entry(self, t, vals: dict, r0: dict, far: dict, geo: dict) -> None:
        """Earth from its exact limb (engine.earth). r0 for earth_top / earth_bot is the complete
        edge-clearance derivative bound B (centre elevation, horizon under the centre's azimuth motion,
        limb motion relative to the centre, 1/cos el scaling, map term), never rho_rate."""
        from .earth import clearance_rate_bound, earth_disk_state, limb_speed_bound
        from .ephem import earth_geo
        from .visibility import earth_limb_enu

        g = earth_geo(t, 0)
        # the event functions need only the clearances; the visible fraction (the costly part of the exact
        # ellipse) is computed where a state is evaluated (full_state), from the same geometry (Phase 3 item 8)
        st = earth_disk_state(self.hp, g, want_f=False)
        az, el = g["az"], g["el"]
        vals["earth_c"] = st["c"]
        vals["earth_top"] = st["g_top"]
        vals["earth_bot"] = st["g_bot"] - self.cfg.margin_deg
        alpha_deg = math.degrees(g["alpha"])
        c_min = st["c_min"]
        hw = alpha_deg / max(c_min, 1e-9)
        el_rate, az_rate = float(t.el_rate[0]), float(t.az_rate[0])
        S = self._slope_near(az, az_rate, hw)
        cos_el = max(math.cos(math.radians(el)), 1e-9)
        map_term = S * g["alpha"] * math.sin(math.radians(abs(el))) / cos_el ** 2 * abs(el_rate)
        v_limb = float(limb_speed_bound(t.dist_km[0], t.earth["d_dot"][0], t.earth["psi_dot"][0],
                                        t.earth["lam_dot"][0]))
        r0["earth_c"] = abs(el_rate) + S * abs(az_rate)
        bound = clearance_rate_bound(el_rate, az_rate, S, c_min, v_limb, g["alpha"], map_term)
        r0["earth_top"] = bound
        r0["earth_bot"] = bound
        far["earth"] = max(el - alpha_deg - self.hp.hmax, self.hp.hmin - (el + alpha_deg))
        geo["earth"] = {"az": az, "el": el, "rho": float(t.rho[0]), "az_rate": az_rate, "el_rate": el_rate,
                        "state": st, "S": S, "rate_bound": bound, "v_limb": v_limb, "c_min": c_min,
                        "limb": earth_limb_enu(g), "shape_rad": g["alpha"] - g["beta"], "g": g}

    def evaluate(self, et: float) -> Sample:
        s, e, g, gr = self._targets([et])
        vals, r0, far, geo = {}, {}, {}, {}
        for name, t in (("sun", s), ("earth", e)):
            az, el, rho = float(t.az[0]), float(t.el[0]), float(t.rho[0])
            if name == "earth" and t.earth is not None:
                self._earth_entry(t, vals, r0, far, geo)
                continue
            st = disk_state(self.hp, az, el, rho)
            vals[f"{name}_c"] = st["c"]
            vals[f"{name}_top"] = st["g_top"]
            vals[f"{name}_bot"] = st["g_bot"] - self.cfg.margin_deg
            hw = rho / max(math.cos(math.radians(el)), 1e-9)
            S = self._slope_near(az, float(t.az_rate[0]), hw)
            cos_el = max(math.cos(math.radians(el)), 1e-9)
            map_term = S * math.radians(rho) * math.sin(math.radians(abs(el))) / cos_el ** 2 * abs(t.el_rate[0])
            base = abs(t.el_rate[0]) + S * abs(t.az_rate[0])
            r0[f"{name}_c"] = base
            edge = base + (1 + S / cos_el) * abs(t.rho_rate[0]) + map_term
            r0[f"{name}_top"] = edge
            r0[f"{name}_bot"] = edge
            gap_above = el - rho - self.hp.hmax
            gap_below = self.hp.hmin - (el + rho)
            far[name] = max(gap_above, gap_below)  # > 0 means the state cannot change until El moves by it
            geo[name] = {"az": az, "el": el, "rho": rho, "az_rate": float(t.az_rate[0]),
                         "el_rate": float(t.el_rate[0]), "state": st, "S": S}
        rs = float(s.rho[0])
        sun_d = {"az": geo["sun"]["az"], "el": geo["sun"]["el"], "rho": rs, "gamma": float(g[0])}
        earth_d = _earth_occulter(geo["earth"])
        re = earth_radius_toward_sun(sun_d, earth_d)       # Phase 3: limb-ellipse radius toward the Sun
        vals["ecl_contact"] = float(g[0]) - (rs + re)
        vals["ecl_centre"] = float(g[0]) - re
        vals["ecl_total"] = float(g[0]) - (re - rs)
        # relative angular speed of Earth with respect to the Sun (bounds |d gamma/dt| even when gamma is stationary)
        rel = float(np.degrees(np.linalg.norm(e.unit_rate[0] - s.unit_rate[0])))
        # Earth's radius rate: the safe limb-speed bound (rho_rate is display-only for Earth)
        e_rho_rate = (math.degrees(geo["earth"]["v_limb"]) if "v_limb" in geo["earth"]
                      else abs(float(e.rho_rate[0])))
        # the radius toward the Sun also changes as the Sun's position angle about Earth's centre turns:
        # |dr/dpsi| <= alpha - beta and |dpsi/dt| <= rel / sin(gamma)
        shape = math.degrees(geo["earth"].get("shape_rad", 0.0))
        psi_term = shape * math.radians(rel) / max(math.sin(math.radians(float(g[0]))), 1e-6)
        ecl_r0 = rel + abs(float(s.rho_rate[0])) + e_rho_rate + psi_term
        for fn in ("ecl_contact", "ecl_centre", "ecl_total"):
            r0[fn] = ecl_r0
        geo["gamma"] = float(g[0])
        vals["sun_vis"] = sun_vis_clearance(self.hp, sun_d, earth_d, geo["sun"]["state"])
        r0["sun_vis"] = max(r0["sun_top"], ecl_r0)
        return Sample(et, vals, r0, far, geo)

    # -------------------------------------------------- curvature estimates
    def _estimate_curvature(self, et0: float, et1: float) -> dict:
        h = 3600.0
        grid = np.arange(et0 - h, et1 + 2 * h, h)
        s, e, g, _ = self._targets(grid)
        out = {}
        speeds = {}
        for name, t in (("sun", s), ("earth", e)):
            el = t.el
            az = np.degrees(np.unwrap(np.radians(t.az)))
            rho = t.rho
            a_el = np.max(np.abs(np.diff(el, 2))) / h ** 2 if el.size > 2 else 0.0
            a_az = np.max(np.abs(np.diff(az, 2))) / h ** 2 if az.size > 2 else 0.0
            a_rho = np.max(np.abs(np.diff(rho, 2))) / h ** 2 if rho.size > 2 else 0.0
            k = self.cfg.inflation
            out[name] = {"el": k * a_el, "az": k * a_az, "rho": k * a_rho}
            speed = np.sqrt((t.az_rate * np.cos(np.radians(t.el))) ** 2 + t.el_rate ** 2)
            speeds[name] = self.cfg.inflation * float(np.max(speed))
        a_g = np.max(np.abs(np.diff(g, 2))) / h ** 2 if g.size > 2 else 0.0
        out["ecl"] = {"gamma": self.cfg.inflation * a_g,
                      "rho": out["sun"]["rho"] + out["earth"]["rho"]}
        self.log.curvature = {k: {kk: float(vv) for kk, vv in v.items()} for k, v in out.items()}
        self.log.angular_speed = speeds
        self._speeds = speeds
        return out

    def _a_hat(self, fn: str, smp: Sample, curv: dict) -> float:
        if fn.startswith("ecl"):
            return curv["ecl"]["gamma"] + curv["ecl"]["rho"]
        if fn == "sun_vis":
            return max(self._a_hat("sun_top", smp, curv), curv["ecl"]["gamma"] + curv["ecl"]["rho"])
        tgt = "sun" if fn.startswith("sun") else "earth"
        cv = curv[tgt]
        S = smp.geo[tgt]["S"]
        el = smp.geo[tgt]["el"]
        cos_el = max(math.cos(math.radians(el)), 1e-9)
        a = cv["el"] + S * cv["az"]
        if not fn.endswith("_c"):
            a += (1 + S / cos_el) * cv["rho"]
        return a

    @staticmethod
    def _tau(g: float, r0: float, a: float) -> float:
        g = abs(g)
        if g == 0.0:
            return 0.0
        den = r0 + math.sqrt(r0 * r0 + 2 * a * g)
        if den == 0.0:
            return math.inf
        return 2 * g / den

    def _step(self, smp: Sample, curv: dict) -> float:
        taus = []
        for fn in FUNCS:
            tgt = ("sun" if fn.startswith("sun") else "earth") if fn in FAR_TESTABLE else None
            if tgt and smp.far[tgt] > 0:
                speed = max(self._speeds[tgt], 1e-12)
                taus.append(smp.far[tgt] / speed)
                continue
            taus.append(self._tau(smp.vals[fn], smp.r0[fn], self._a_hat(fn, smp, curv)))
        dt = min(taus)
        # node samples: land just past the next horizon-table node for targets near the horizon
        for tgt in ("sun", "earth"):
            if smp.far[tgt] > 0:
                continue
            az, rate = smp.geo[tgt]["az"], smp.geo[tgt]["az_rate"]
            if abs(rate) > 1e-12:
                b = self.hp.bin
                nxt = (math.floor(az / b) + 1) * b if rate > 0 else math.ceil(az / b) * b - b
                dist = abs(nxt - az) if abs(nxt - az) > 1e-9 else b
                dt = min(dt, dist / abs(rate) + 0.5)
        return min(max(dt, self.cfg.floor_s), self.cfg.cap_s)

    # ----------------------------------------------------------- detection
    def run(self, et0: float, et1: float) -> dict:
        curv = self._estimate_curvature(et0, et1)
        samples = [self.evaluate(et0)]
        t = et0
        while t < et1:
            cur = samples[-1]
            dt = min(self._step(cur, curv), et1 - t)
            for _attempt in range(8):
                nxt = self.evaluate(t + dt)
                failed = None
                for fn in FUNCS:
                    tgt = ("sun" if fn.startswith("sun") else "earth") if fn in FAR_TESTABLE else None
                    if tgt and cur.far[tgt] > 0:
                        continue
                    a = self._a_hat(fn, cur, curv)
                    predicted = cur.r0[fn] * dt + 0.5 * a * dt * dt
                    observed = abs(nxt.vals[fn] - cur.vals[fn])
                    if observed > predicted * (1 + 1e-6) + 1e-9:
                        failed = (fn, observed, predicted)
                        break
                if failed is None or dt <= self.cfg.floor_s:
                    break
                fn, obs, pred = failed
                self.log.estimate_failures.append(
                    {"et": t, "function": fn, "observed_deg": obs, "predicted_deg": pred, "dt_s": dt})
                keys = ["ecl"] if fn.startswith("ecl") else (["sun", "ecl"] if fn == "sun_vis" else
                                                             ["sun" if fn.startswith("sun") else "earth"])
                for key in keys:
                    for kk in curv[key]:
                        curv[key][kk] *= 2.0
                dt = max(dt / 2.0, self.cfg.floor_s)
            samples.append(nxt)
            t = nxt.et
        self.log.samples = len(samples)
        events = self._refine(samples)
        return {"samples": samples, "events": events}

    def _refine(self, samples: list[Sample]) -> list[dict]:
        events = []
        for i in range(len(samples) - 1):
            a, b = samples[i], samples[i + 1]
            for fn in FUNCS:
                va, vb = a.vals[fn], b.vals[fn]
                if (va > 0) == (vb > 0) or not (math.isfinite(va) and math.isfinite(vb)):
                    continue
                ta, tb = a.et, b.et
                sa = va > 0
                while tb - ta > self.cfg.tol_s:
                    tm = 0.5 * (ta + tb)
                    vm = self.evaluate(tm).vals[fn]
                    if (vm > 0) == sa:
                        ta = tm
                    else:
                        tb = tm
                direction = +1 if vb > 0 else -1
                if fn == "sun_vis":
                    chk = self.evaluate(0.5 * (ta + tb))
                    if chk.vals["ecl_contact"] > 0:
                        continue  # no occultation: identical to the terrain-only sun_top event
                events.append({"et": 0.5 * (ta + tb), "function": fn, "direction": direction,
                               "name": EVENT_NAMES[(fn, direction)],
                               "target": "sun" if fn.startswith(("sun", "ecl")) else "earth"})
        events.sort(key=lambda ev: ev["et"])
        return events


def _earth_occulter(earth_geo_entry: dict) -> dict:
    """Earth as an occulter of the Sun: centre direction, display radius and (Phase 3) its limb ellipse."""
    d = {"az": earth_geo_entry["az"], "el": earth_geo_entry["el"], "rho": earth_geo_entry["rho"]}
    if earth_geo_entry.get("limb") is not None:
        d["limb"] = earth_geo_entry["limb"]
    return d


# --------------------------------------------------------------- states
def full_state(det: EventDetector, et: float) -> dict:
    """All rule states at one time, including Earth occultation of the Sun."""
    smp = det.evaluate(et)
    sun = smp.geo["sun"]
    earth = smp.geo["earth"]
    gamma = smp.geo["gamma"]
    sun_d = {"az": sun["az"], "el": sun["el"], "rho": sun["rho"], "gamma": gamma}
    if "g" in earth:                         # the detector skipped Earth's visible fraction: compute it here
        from .earth import earth_disk_state
        earth = {**earth, "state": earth_disk_state(det.hp, earth["g"], want_f=True)}
    earth_d = _earth_occulter(earth)
    f_sun, occ = sun_fraction_with_earth(det.hp, sun_d, earth_d, sun["state"])
    sun_st = dict(sun["state"])
    sun_st["f"] = f_sun
    centre_behind_earth = gamma < earth_radius_toward_sun(sun_d, earth_d)
    out = {"et": et, "sun": sun_st, "earth": earth["state"], "occulted": occ, "gamma": gamma,
           "sun_geo": {k: sun[k] for k in ("az", "el", "rho")},
           "earth_geo": {k: earth[k] for k in ("az", "el", "rho")}}
    m = det.cfg.margin_deg
    rules = {}
    for rule in ("any", "centre", "full"):
        s = rule_state(sun_st, rule, m)
        if s is not None:
            if rule == "centre" and centre_behind_earth:
                s = False
            if rule == "full" and occ > 0:
                s = False
        rules[f"sun_{rule}"] = s
        rules[f"earth_{rule}"] = rule_state(earth["state"], rule, m)
    out["rules"] = rules
    return out


# Missing-terrain boundaries (2026-11-14, scientific_validation_followup): a disk whose azimuth span touches incomplete
# (lower-bound) horizon bins while it would be visible is "unknown" (visibility.disk_state, earth.earth_disk_state).
# Entering or leaving such bins is not a geometric event function, and interval states are taken at segment midpoints,
# so without these cuts a segment that only partly rests on incomplete bins took one state for its whole length and
# unknown time could be reported as visible. The cuts are found from the engine's own per-target unknown flag
# (Sample.geo[target]["state"]["unknown"]) on a fixed grid and refined by bisection to the event tolerance. They are
# computed only when the horizon has incomplete bins, so complete horizons keep exactly the previous intervals.
INCOMPLETE_SCAN_S = 60.0


def _unknown_flags(det: EventDetector, et: float) -> tuple[bool, bool]:
    geo = det.evaluate(et).geo
    return bool(geo["sun"]["state"].get("unknown")), bool(geo["earth"]["state"].get("unknown"))


def incomplete_cuts(det: EventDetector, et0: float, et1: float) -> list[float]:
    """Times (ET) at which the Sun's or Earth's verdict starts or stops resting on incomplete horizon bins."""
    if not det.hp.inc.any() or et1 <= et0:
        return []
    n = max(2, int(math.ceil((et1 - et0) / INCOMPLETE_SCAN_S)) + 1)
    ts = np.linspace(et0, et1, n)
    flags = [_unknown_flags(det, float(t)) for t in ts]
    out = []
    for k in range(n - 1):
        for j in (0, 1):
            if flags[k][j] == flags[k + 1][j]:
                continue
            a, b, fa = float(ts[k]), float(ts[k + 1]), flags[k][j]
            while b - a > det.cfg.tol_s:
                m = 0.5 * (a + b)
                if _unknown_flags(det, m)[j] == fa:
                    a = m
                else:
                    b = m
            out.append(0.5 * (a + b))
    return out


def build_intervals(det: EventDetector, et0: float, et1: float, events: list[dict], samples: list[Sample]) -> dict:
    base = {et0, et1, *[ev["et"] for ev in events if et0 < ev["et"] < et1]}
    for t in incomplete_cuts(det, et0, et1):
        if et0 < t < et1 and min(abs(t - b) for b in base) > det.cfg.tol_s:
            base.add(t)
    cuts = sorted(base)
    segs = []
    for a, b in zip(cuts[:-1], cuts[1:]):
        if b - a <= 0:
            continue
        st = full_state(det, 0.5 * (a + b))
        segs.append((a, b, st["rules"]))
    keys = [f"{t}_{r}" for t in ("sun", "earth") for r in ("any", "centre", "full")]
    out = {}
    for key in keys:
        ivs = []
        for a, b, rules in segs:
            v = rules[key]
            if ivs and ivs[-1]["state"] == v and abs(ivs[-1]["end_et"] - a) < 1e-6:
                ivs[-1]["end_et"] = b
            else:
                ivs.append({"start_et": a, "end_et": b, "state": v})
        out[key] = ivs
    _flag_intervals(det, out, samples)
    return out


def interval_flags(hp: HorizonProfile, state: bool | None, fn: str, tgt: str, inside: list[Sample],
                   k: float | None = None) -> dict:
    """Uncertainty and near-field flags of one interval from the samples inside it.

    At each sample the threshold is s = k * (largest sigma over the bins the target disk spans: its
    limiting edge, not its centre); g is the interval's clearance function.
      window (state True): uncertain if max_t (g - s) < 0  - no sample clears the terrain by more than k sigma;
      gap (state False):   uncertain if min_t (g + s) > 0  - no sample is hidden by more than k sigma.
    A spanned bin whose sigma is beyond first-order validity (sigma_nonlinear) or whose cross-product
    discrepancy could not be measured (discrepancy_unknown) makes the interval uncertain whatever its
    clearance: its stated sigma is never used to clear a flag. No usable sigma at any sample: None.
    near_field: the target passes over horizon bins set by terrain within the near-field distance.
    """
    k = settings.UNCERTAIN_SIGMA_K if k is None else k
    out = {"uncertain": None, "uncertain_reasons": [], "near_field": False}
    if state is None or not inside:
        return out
    reasons, extremes, near = [], [], False
    for smp in inside:
        geo = smp.geo[tgt]
        hw = geo["rho"] / max(math.cos(math.radians(geo["el"])), 1e-9)
        sf = hp.span_flags(geo["az"], hw)
        near = near or sf["near_field"]
        if sf["nonlinear"] and "sigma_nonlinear" not in reasons:
            reasons.append("sigma_nonlinear")
        if sf["discrepancy_unknown"] and "cross_product_discrepancy_unknown" not in reasons:
            reasons.append("cross_product_discrepancy_unknown")
        if math.isfinite(sf["sigma_max"]):
            s = k * sf["sigma_max"]
            g = smp.vals[fn]
            extremes.append(g - s if state else g + s)
    out["near_field"] = bool(near)
    if extremes and ((max(extremes) < 0.0) if state else (min(extremes) > 0.0)):
        reasons.insert(0, "below_k_sigma")
    if reasons:
        out["uncertain"] = True
    elif extremes:
        out["uncertain"] = False
    out["uncertain_reasons"] = reasons
    return out


def subbin_peak(hp: HorizonProfile, state: bool | None, fn: str, tgt: str, inside: list[Sample]) -> bool | None:
    """Sub-bin peak flag of one interval (Phase 3 item 7), kept apart from the uncertainty flags, which it
    never changes.

    window (state True): True if max_t (g - E) < 0, with E the largest sub-bin peak excess over the bins the
    disk spans (its limiting edge): a peak between horizon nodes as high as the measured one could hide the
    whole window. None if that excess is unknown (incomplete rays) in a spanned bin, or was not computed.
    gap (state False): always False - a missed peak can only raise the horizon, never open a gap.
    unknown interval (state None): None."""
    if state is False:
        return False
    if state is None or not inside:
        return None
    best = -math.inf
    for smp in inside:
        geo = smp.geo[tgt]
        hw = geo["rho"] / max(math.cos(math.radians(geo["el"])), 1e-9)
        sf = hp.span_flags(geo["az"], hw)
        if sf["subbin_unknown"] or not math.isfinite(sf["subbin_excess_max"]):
            return None
        best = max(best, smp.vals[fn] - sf["subbin_excess_max"])
    return bool(best < 0.0)


def _flag_intervals(det: EventDetector, intervals: dict, samples: list[Sample]) -> None:
    fn_for = {"any": "top", "centre": "c", "full": "bot"}
    ets = np.array([s.et for s in samples])
    mids: dict[float, Sample] = {}

    def midpoint(et: float) -> Sample:     # every interval is also evaluated at its midpoint
        if et not in mids:
            mids[et] = det.evaluate(et)
        return mids[et]

    for key, ivs in intervals.items():
        tgt, rule = key.split("_")
        fn = "sun_vis" if (tgt == "sun" and rule == "any") else f"{tgt}_{fn_for[rule]}"
        for iv in ivs:
            iv["duration_s"] = iv["end_et"] - iv["start_et"]
            iv["brief"] = bool(iv["state"] is True and iv["duration_s"] < settings.BRIEF_WINDOW_S)
            inside = []
            if iv["state"] is not None:
                idx = np.where((ets > iv["start_et"]) & (ets < iv["end_et"]))[0]
                inside = [samples[i] for i in idx] + [midpoint(0.5 * (iv["start_et"] + iv["end_et"]))]
            iv.update(interval_flags(det.hp, iv["state"], fn, tgt, inside))
            iv["subbin_peak"] = subbin_peak(det.hp, iv["state"], fn, tgt, inside)


def summarize(intervals: list[dict], et0: float, et1: float) -> dict:
    total = et1 - et0
    on = [iv for iv in intervals if iv["state"] is True]
    off = [iv for iv in intervals if iv["state"] is False]
    unk = [iv for iv in intervals if iv["state"] is None]
    dur_on = sum(iv["duration_s"] for iv in on)
    return {
        "hours": dur_on / 3600.0,
        "percent": 100.0 * dur_on / total,
        "windows": len(on),
        "longest_window_h": max((iv["duration_s"] for iv in on), default=0.0) / 3600.0,
        "longest_gap_h": max((iv["duration_s"] for iv in off), default=0.0) / 3600.0,
        "unknown_hours": sum(iv["duration_s"] for iv in unk) / 3600.0,
        "brief_windows": sum(1 for iv in on if iv["brief"]),
        "uncertain_windows": sum(1 for iv in on if iv.get("uncertain")),
        "uncertain_gaps": sum(1 for iv in off if iv.get("uncertain")),
        "near_field_windows": sum(1 for iv in on if iv.get("near_field")),
        "subbin_peak_windows": sum(1 for iv in on if iv.get("subbin_peak")),
        "transitions": max(0, len([iv for iv in intervals if iv["state"] is not None]) - 1),
    }


def _or_uncertain(x, y):
    """True if either is True; None only if both are None; otherwise False."""
    if x is True or y is True:
        return True
    if x is None and y is None:
        return None
    return False


def intersect(a: list[dict], b: list[dict]) -> list[dict]:
    """Intervals where both a and b are True (operational window: sunlit and in contact).

    Each overlap inherits its two parents' flags: uncertain if either parent is (reasons merged),
    None only if both parents are None; near_field if either parent is; subbin_peak like uncertain."""
    out = []
    A = [x for x in a if x["state"] is True]
    B = [x for x in b if x["state"] is True]
    i = j = 0
    while i < len(A) and j < len(B):
        lo, hi = max(A[i]["start_et"], B[j]["start_et"]), min(A[i]["end_et"], B[j]["end_et"])
        if hi > lo:
            reasons = list(dict.fromkeys((A[i].get("uncertain_reasons") or []) + (B[j].get("uncertain_reasons") or [])))
            out.append({"start_et": lo, "end_et": hi, "state": True, "duration_s": hi - lo,
                        "brief": hi - lo < settings.BRIEF_WINDOW_S,
                        "uncertain": _or_uncertain(A[i].get("uncertain"), B[j].get("uncertain")),
                        "uncertain_reasons": reasons,
                        "near_field": bool(A[i].get("near_field") or B[j].get("near_field")),
                        "subbin_peak": _or_uncertain(A[i].get("subbin_peak"), B[j].get("subbin_peak"))})
        if A[i]["end_et"] < B[j]["end_et"]:
            i += 1
        else:
            j += 1
    return out
