"""Hypothetical lunar relay: two-body Keplerian propagation and the two communication legs.

THE RELAY IS HYPOTHETICAL. Its orbit comes only from the elements the user enters; it is never an actual NASA
satellite, and no ground-station (DSN) availability or schedule is modelled.

Propagation (analytic two-body, Moon point mass): n = sqrt(GM / a^3), M(t) = M0 + n (t - t_epoch), Kepler's equation
E - e sin E = M solved by Newton iteration, perifocal position (a (cos E - e), a sqrt(1 - e^2) sin E, 0) and velocity,
rotated by R3(-RAAN) R1(-i) R3(-argp) into the element frame. GM = BODY301_GM from NAIF gm_de440.tpc (constants.py).
Neglected: lunar gravity-field harmonics (mascons, J2, C22), Earth and Sun third-body perturbations, solar radiation
pressure. For low lunar orbits these change the orbit within days; the propagated relay is an idealised orbit, and
its geometry drifts from any real spacecraft with the same initial elements.

Element frames (both Moon-centred and inertial):
  "J2000"    : axes of SPICE J2000.
  "LME_EPOCH": axes of the engine's lunar body-fixed frame (the loaded kernels' MOON_ME frame) frozen at the epoch,
               i.e. inclination and RAAN measured from the lunar mean equator and the prime-meridian direction at the
               epoch. r_J2000 = pxform(MOON_ME -> J2000, epoch) r_LME.
States are carried in J2000 and turned into the body-fixed frame at each sample time with pxform(J2000 -> MOON_ME, t),
the same SPICE environment and frame the validated engine uses (read only; no kernel is added to the pool).

Leg 1, lander -> relay: line from the site (engine Site position, including the observer height) to the relay; open
when it does not cross the 1737.4 km sphere (or, for a site below that sphere, a sphere just below the site) and the
relay's elevation is above the site's terrain horizon (the engine's
horizon profile from the analysis result) at the relay's azimuth. Unknown when that horizon bin is incomplete. The
horizon test is direction-based, exact when the blocking terrain is nearer than the relay (always true for relays above
the terrain, which lies within tens of km).
Leg 2, relay -> Earth: open when the straight line from the relay to the Earth's centre clears the 1737.4 km sphere by
the user-configured grazing altitude (default none: 0 km). The Earth's position relative to the Moon's centre is the
SPICE apparent position (the engine's aberration setting). Earth's own disk, atmosphere and ground stations are not
modelled.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import spiceypy as sp

from lunaops import settings
from lunaops.engine.ephem import Site
from lunaops.engine.kernels import SPICE_LOCK, load
from lunaops.engine.visibility import HorizonProfile

from .constants import R_MOON_KM, moon_gm

FRAMES = ("J2000", "LME_EPOCH")
MAX_SAMPLES = 50_000
MIN_STEP_S, MAX_STEP_S = 10.0, 3600.0


class RelayInputError(ValueError):
    pass


@dataclass
class Elements:
    a_km: float
    e: float
    i_deg: float
    raan_deg: float
    argp_deg: float
    m0_deg: float
    epoch_et: float
    frame: str


def validate_elements(p: dict | None, et_parse) -> tuple[Elements | None, list[str]]:
    """Elements from user input; every field is required (no defaults). Returns (elements or None, problems)."""
    if not p:
        return None, ["No relay is configured."]
    need = {"a_km": "Semi-major axis (km)", "e": "Eccentricity", "i_deg": "Inclination (deg)", "raan_deg": "RAAN (deg)",
            "argp_deg": "Argument of periapsis (deg)", "m0_deg": "Mean anomaly at epoch (deg)", "epoch_utc": "Epoch (UTC)",
            "frame": "Element frame"}
    probs = [f"{label} is missing" for k, label in need.items() if p.get(k) in (None, "")]
    if probs:
        return None, probs
    try:
        a, e, i = float(p["a_km"]), float(p["e"]), float(p["i_deg"])
        raan, argp, m0 = float(p["raan_deg"]), float(p["argp_deg"]), float(p["m0_deg"])
    except (TypeError, ValueError):
        return None, ["Orbital elements must be numbers."]
    if not all(math.isfinite(v) for v in (a, e, i, raan, argp, m0)):
        probs.append("Orbital elements must be finite.")
    if p["frame"] not in FRAMES:
        probs.append(f"Element frame must be one of {', '.join(FRAMES)}.")
    if not (0.0 <= e < 1.0):
        probs.append("Eccentricity must be at least 0 and below 1 (closed orbits only).")
    if not (0.0 <= i <= 180.0):
        probs.append("Inclination must be between 0 and 180 deg.")
    if a <= 0:
        probs.append("The semi-major axis must be positive.")
    elif 0.0 <= e < 1.0 and a * (1.0 - e) <= R_MOON_KM:
        probs.append(f"Periapsis radius {a * (1 - e):.1f} km is not above the 1737.4 km lunar sphere: the orbit "
                     "intersects the Moon.")
    elif a > 66_000.0:
        probs.append("The semi-major axis must not exceed 66,000 km (the Moon's Hill sphere radius is about 60,000 km; "
                     "two-body motion about the Moon is meaningless beyond it).")
    try:
        et0 = et_parse(str(p["epoch_utc"]))
    except Exception as exc:  # noqa: BLE001 - the parser's message is shown
        probs.append(f"Epoch: {exc}")
        et0 = None
    if probs:
        return None, probs
    return Elements(a, e, i, raan % 360.0, argp % 360.0, m0 % 360.0, et0, p["frame"]), []


def kepler_E(M: np.ndarray, e: float) -> np.ndarray:
    """Eccentric anomaly from mean anomaly (Newton; |residual| < 1e-14 rad)."""
    M = np.mod(M, 2 * math.pi)
    E = M + e * np.sin(M) if e < 0.8 else np.full_like(M, math.pi)
    for _ in range(60):
        f = E - e * np.sin(E) - M
        d = f / (1.0 - e * np.cos(E))
        E = E - d
        if np.max(np.abs(d)) < 1e-15:
            break
    return E


def _rot(el: Elements) -> np.ndarray:
    """Perifocal -> element frame: R3(-RAAN) R1(-i) R3(-argp)."""
    O, i, w = (math.radians(el.raan_deg), math.radians(el.i_deg), math.radians(el.argp_deg))
    cO, sO, ci, si, cw, sw = math.cos(O), math.sin(O), math.cos(i), math.sin(i), math.cos(w), math.sin(w)
    return np.array([[cO * cw - sO * sw * ci, -cO * sw - sO * cw * ci, sO * si],
                     [sO * cw + cO * sw * ci, -sO * sw + cO * cw * ci, -cO * si],
                     [sw * si, cw * si, ci]])


def propagate(el: Elements, ets: np.ndarray, gm: float) -> tuple[np.ndarray, np.ndarray]:
    """Position (km) and velocity (km/s) in the ELEMENT frame at the given ETs."""
    a, e = el.a_km, el.e
    n = math.sqrt(gm / a ** 3)
    M = math.radians(el.m0_deg) + n * (np.asarray(ets, float) - el.epoch_et)
    E = kepler_E(M, e)
    cE, sE = np.cos(E), np.sin(E)
    b = a * math.sqrt(1 - e * e)
    rp = np.stack([a * (cE - e), b * sE, np.zeros_like(E)], axis=1)
    edot = n / (1.0 - e * cE)
    vp = np.stack([-a * sE * edot, b * cE * edot, np.zeros_like(E)], axis=1)
    R = _rot(el)
    return rp @ R.T, vp @ R.T


def element_to_j2000(el: Elements) -> np.ndarray:
    if el.frame == "J2000":
        return np.eye(3)
    ks = load()
    with SPICE_LOCK:
        return np.array(sp.pxform(ks.frame, "J2000", float(el.epoch_et)))


def orbit_summary(el: Elements, gm: float) -> dict:
    T = 2 * math.pi * math.sqrt(el.a_km ** 3 / gm)
    return {"period_h": T / 3600.0, "periapsis_alt_km": el.a_km * (1 - el.e) - R_MOON_KM,
            "apoapsis_alt_km": el.a_km * (1 + el.e) - R_MOON_KM, "mean_motion_deg_per_h": 360.0 / (T / 3600.0)}


def sphere_clear_km(p0: np.ndarray, p1: np.ndarray, radius_km: float) -> np.ndarray:
    """Minimum distance (km) of each segment p0[i] -> p1[i] from the origin, minus radius (positive = clears)."""
    d = p1 - p0
    dd = np.einsum("ij,ij->i", d, d)
    t = np.clip(-np.einsum("ij,ij->i", p0, d) / np.maximum(dd, 1e-300), 0.0, 1.0)
    closest = p0 + t[:, None] * d
    return np.linalg.norm(closest, axis=1) - radius_km


def earth_limb_clearance_deg(r_relay: np.ndarray, r_earth: np.ndarray) -> np.ndarray:
    """Angle (deg) of the Earth's centre outside the lunar disk seen from the relay: angle(Earth, Moon centre) minus
    the Moon's angular radius asin(R / |r|). Positive = Earth's centre not behind the Moon's disk."""
    to_e = r_earth - r_relay
    to_m = -r_relay
    ce = np.einsum("ij,ij->i", to_e, to_m) / (np.linalg.norm(to_e, axis=1) * np.linalg.norm(to_m, axis=1))
    ang = np.degrees(np.arccos(np.clip(ce, -1, 1)))
    rad = np.degrees(np.arcsin(np.clip(R_MOON_KM / np.linalg.norm(r_relay, axis=1), -1, 1)))
    return ang - rad


def site_leg(site_km: np.ndarray, basis, r_bf: np.ndarray, hp: HorizonProfile) -> dict:
    """Lander -> relay geometry for body-fixed relay positions (km)."""
    e, n, u = basis
    d = r_bf - site_km[None, :]
    rng = np.linalg.norm(d, axis=1)
    du = d / rng[:, None]
    el = np.degrees(np.arcsin(np.clip(du @ u, -1, 1)))
    az = np.degrees(np.arctan2(du @ e, du @ n)) % 360.0
    hor = hp.at(az)
    # occulting sphere: the 1737.4 km sphere, or a sphere just below the site when the site lies below it (polar
    # crater floors do), so the line from the site is never "inside the Moon" at its own start point
    r_occ = min(R_MOON_KM, float(np.linalg.norm(site_km)) - 1e-3)
    clear_sphere = sphere_clear_km(np.repeat(site_km[None, :], len(r_bf), 0), r_bf, r_occ)
    i0 = np.floor(az / hp.bin).astype(int) % hp.n
    unknown = hp.inc[i0] | hp.inc[(i0 + 1) % hp.n]
    sig = hp.sigma[i0] if hp.sigma is not None else np.full(az.size, np.nan)
    clearance = el - hor
    # a line that crosses the sphere is blocked whatever the DEM horizon says (the DEM may not reach that far)
    clearance = np.where(clear_sphere < 0, np.minimum(clearance, -1e-9), clearance)
    uncertain = np.isfinite(sig) & (np.abs(clearance) <= sig)
    return {"range_km": rng, "el_deg": el, "az_deg": az, "horizon_deg": hor, "clearance_deg": clearance,
            "unknown": unknown & (clear_sphere >= 0), "uncertain": uncertain, "sphere_clear_km": clear_sphere}


def simulate(el: Elements, et0: float, et1: float, step_s: float, site: Site, hp: HorizonProfile,
             grazing_km: float = 0.0) -> dict:
    """Relay geometry on a uniform grid over [et0, et1] (plus et1)."""
    if not (MIN_STEP_S <= step_s <= MAX_STEP_S):
        raise RelayInputError(f"The relay sampling step must be between {MIN_STEP_S:g} and {MAX_STEP_S:g} s.")
    n = int(math.floor((et1 - et0) / step_s)) + 1
    if n > MAX_SAMPLES:
        raise RelayInputError(f"{n} relay samples exceed the {MAX_SAMPLES} limit; use a larger step or a shorter window.")
    ets = et0 + step_s * np.arange(n)
    if ets[-1] < et1:
        ets = np.append(ets, et1)
    gm = moon_gm()["gm_km3_s2"]
    r_el, v_el = propagate(el, ets, gm)
    Rj = element_to_j2000(el)
    r_j = r_el @ Rj.T
    ks = load()
    r_bf = np.empty_like(r_j)
    r_earth = np.empty_like(r_j)
    with SPICE_LOCK:
        for k, t in enumerate(ets):
            m = np.array(sp.pxform("J2000", ks.frame, float(t)))
            r_bf[k] = m @ r_j[k]
            pe, _lt = sp.spkpos("EARTH", float(t), "J2000", settings.ABCORR, "MOON")
            r_earth[k] = pe
    leg1 = site_leg(site.pos_km, site.basis, r_bf, hp)
    seg = sphere_clear_km(r_j, r_earth, R_MOON_KM + grazing_km)
    leg2_clear = earth_limb_clearance_deg(r_j, r_earth)
    rad = np.degrees(np.arcsin(np.clip((R_MOON_KM + grazing_km) / np.linalg.norm(r_j, axis=1), -1, 1)))
    rad0 = np.degrees(np.arcsin(np.clip(R_MOON_KM / np.linalg.norm(r_j, axis=1), -1, 1)))
    leg2_clear = leg2_clear - (rad - rad0)          # the grazing altitude enlarges the occulting disk
    return {"ets": ets, "r_j2000_km": r_j, "r_bf_km": r_bf, "alt_km": np.linalg.norm(r_j, axis=1) - R_MOON_KM,
            "speed_km_s": np.linalg.norm(v_el, axis=1), "leg1": leg1,
            "leg2": {"range_km": np.linalg.norm(r_earth - r_j, axis=1), "clearance_deg": leg2_clear, "segment_clear_km": seg},
            "gm": gm, "element_to_j2000": Rj}
