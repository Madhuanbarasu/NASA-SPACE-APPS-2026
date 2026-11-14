"""Sun and Earth directions from a lunar site (blueprint Sections 8.2-8.3; V-03, V-04).

For each epoch the apparent vector from the site to the target is taken from
SPICE (spkcpo, constant-position observer on the Moon) in the pinned
body-fixed frame with converged light time and stellar aberration (CN+S).
Libration needs no separate model: it comes from the DE440 lunar
orientation and the body-fixed geometry. No refraction is applied.

Rates of elevation, azimuth and angular radius are computed analytically
from the apparent state's velocity, for the adaptive event detector.

Earth (Phase 3) is the IERS 2010 oblate spheroid; its spin axis is the pole of date (CIP: IAU 2006 precession
+ IAU 2000B nutation, engine.earth_orientation, since Phase 4) (engine.earth): each
sample carries its exact limb ellipse, the upper/lower limb extents rho_up/rho_down, the full-limb
deviation from a circle and the quantities of the complete edge-clearance rate bound. Its `rho` is the
mean vertical extent (rho_up + rho_down)/2 and `rho_rate` is kept for display only: the detector's
Earth limb bounds come from engine.earth.clearance_rate_bound, never from rho_rate.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import spiceypy as sp

from .. import settings
from .frames import enu_basis, latlon_to_xyz_m
from .kernels import SPICE_LOCK, load

TARGETS = {"sun": ("SUN", settings.R_SUN_KM), "earth": ("EARTH", settings.R_EARTH_KM)}


@dataclass
class Site:
    lat: float          # planetocentric deg
    lon: float          # east deg [0, 360)
    ground_h_m: float   # DEM height above 1737.4 km (0 if no terrain)
    obs_h_m: float      # observer height above ground

    # Both depend only on the fields; they are computed once per site instead of at every sample_target call
    # (Phase 3 item 8) and handed out as copies, so a caller can never alter the cached value. A changed field
    # gives a fresh value.
    @property
    def pos_km(self) -> np.ndarray:
        key = (self.lat, self.lon, self.ground_h_m + self.obs_h_m)
        c = self.__dict__.get("_pos_cache")
        if c is None or c[0] != key:
            c = self.__dict__["_pos_cache"] = (key, latlon_to_xyz_m(self.lat, self.lon,
                                                                    self.ground_h_m + self.obs_h_m) / 1000.0)
        return c[1].copy()

    @property
    def basis(self):
        key = (self.lat, self.lon)
        c = self.__dict__.get("_basis_cache")
        if c is None or c[0] != key:
            c = self.__dict__["_basis_cache"] = (key, enu_basis(self.lat, self.lon))
        return tuple(v.copy() for v in c[1])


@dataclass
class TargetSample:
    et: np.ndarray
    az: np.ndarray       # deg [0, 360)
    el: np.ndarray       # deg
    rho: np.ndarray      # angular radius, deg
    dist_km: np.ndarray
    az_rate: np.ndarray  # deg/s
    el_rate: np.ndarray  # deg/s
    rho_rate: np.ndarray # deg/s
    unit: np.ndarray     # (n, 3) body-fixed unit vectors
    unit_rate: np.ndarray  # (n, 3) per second
    earth: dict | None = None  # Earth only: limb geometry per sample (see engine.earth)


def sample_target(site: Site, target: str, ets) -> TargetSample:
    """Apparent topocentric geometry of 'sun' or 'earth' at the given ETs."""
    ks = load()
    name, radius_km = TARGETS[target]
    ets = np.atleast_1d(np.asarray(ets, dtype=float))
    n = ets.size
    e, nn, u = site.basis
    obs = site.pos_km
    states = np.empty((n, 6))
    with SPICE_LOCK:
        for i, et in enumerate(ets):
            st, _lt = sp.spkcpo(name, float(et), ks.frame, "OBSERVER", settings.ABCORR,
                                obs, "MOON", ks.frame)
            states[i] = st
    r = states[:, :3]
    v = states[:, 3:]
    d = np.linalg.norm(r, axis=1)
    rh = r / d[:, None]
    drh = (v - rh * np.sum(rh * v, axis=1)[:, None]) / d[:, None]
    su = rh @ u
    se = rh @ e
    sn = rh @ nn
    el = np.degrees(np.arcsin(np.clip(su, -1.0, 1.0)))
    az = np.degrees(np.arctan2(se, sn)) % 360.0
    cos_el = np.sqrt(np.maximum(1.0 - su * su, 1e-300))
    el_rate = np.degrees((drh @ u) / cos_el)
    h2 = se * se + sn * sn
    az_rate = np.degrees((sn * (drh @ e) - se * (drh @ nn)) / np.maximum(h2, 1e-300))
    ddot = np.sum(rh * v, axis=1)
    if target == "earth":
        return _earth_sample(ets, az, el, d, az_rate, el_rate, ddot, r, rh, drh, ks.frame, e, nn, u)
    rho = np.degrees(np.arcsin(radius_km / d))
    rho_rate = np.degrees(-radius_km * ddot / (d * np.sqrt(d * d - radius_km ** 2)))
    return TargetSample(ets, az, el, rho, d, az_rate, el_rate, rho_rate, rh, drh)


def _earth_sample(ets, az, el, d, az_rate, el_rate, ddot, r, rh, drh, frame, e, nn, u) -> TargetSample:
    from .earth import intrinsic_radii, lambda_rate_bound, limb_ellipse, limb_extrema, pole_in_frame, psi_rate

    pole, pole_dot = pole_in_frame(ets, frame)
    Q0, QA, QB = limb_ellipse(r, pole)
    sv = settings.EARTH_SOLVER
    n = ets.size
    ru = np.empty(n)
    rd = np.empty(n)
    dm = np.empty(n)
    fb = 0
    for i in range(n):
        ru[i], rd[i], dm[i], f = limb_extrema(Q0[i], QA[i], QB[i], u, e, nn, np.radians(el[i]), np.radians(az[i]),
                                              sv["bracket"], sv["tol"], sv["maxiter"])
        fb += f
    alpha, beta = intrinsic_radii(d)
    rho = np.degrees(0.5 * (ru + rd))
    r_eff = d * np.sin(np.radians(rho))
    rho_rate = np.degrees(-r_eff * ddot / (d * np.sqrt(d * d - r_eff ** 2)))   # display only
    earth = {"Q0": Q0, "QA": QA, "QB": QB, "rho_up": ru, "rho_down": rd, "delta_max": dm, "alpha": alpha,
             "beta": beta, "pole": pole, "psi_dot": psi_rate(rh, drh, pole, pole_dot, u), "d_dot": ddot,
             "lam_dot": lambda_rate_bound(drh, pole_dot),
             "basis": (e, nn, u), "solver_fallbacks": fb}
    return TargetSample(ets, az, el, rho, d, az_rate, el_rate, rho_rate, rh, drh, earth)


def earth_geo(t: TargetSample, i: int) -> dict:
    """One sample's Earth geometry in the form engine.earth.earth_disk_state expects."""
    E = t.earth
    e, n, u = E["basis"]
    return {"az": float(t.az[i]), "el": float(t.el[i]), "Q0": E["Q0"][i], "QA": E["QA"][i], "QB": E["QB"][i],
            "rho_up": float(E["rho_up"][i]), "rho_down": float(E["rho_down"][i]),
            "delta_max": float(E["delta_max"][i]), "alpha": float(E["alpha"][i]), "beta": float(E["beta"][i]),
            "e": e, "n": n, "u": u}


def separation_deg(a: TargetSample, b: TargetSample) -> tuple[np.ndarray, np.ndarray]:
    """Angular separation (deg) between two targets and its rate (deg/s)."""
    c = np.clip(np.sum(a.unit * b.unit, axis=1), -1.0, 1.0)
    g = np.arccos(c)
    dc = np.sum(a.unit_rate * b.unit, axis=1) + np.sum(a.unit * b.unit_rate, axis=1)
    rate = -dc / np.maximum(np.sin(g), 1e-12)
    return np.degrees(g), np.degrees(rate)


def light_time_s(dist_km: np.ndarray) -> np.ndarray:
    return dist_km / sp.clight()
