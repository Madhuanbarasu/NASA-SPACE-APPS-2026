"""Limb-darkened solar power indicator (Phase 3 item 2; extension D01).

The solar disk is not uniformly bright. Its centre-to-limb intensity follows the fifth-order polynomial of
Neckel & Labs (1994):

    I(mu) / I(1) = sum_k A_k mu^k,   mu = cos(theta)  (theta: heliocentric angle; mu = 0 at the limb).

Source: H. Neckel and D. Labs, "Solar limb darkening 1986-1990 (lambda lambda 303 to 1099 nm)", Solar Physics
153, 91-114 (1994), Table I (p. 98), row lambda = 541.760 nm, used exactly as printed: no interpolation
between wavelengths. 541.760 nm is the tabulated wavelength nearest the V-band centre (550 nm; 8.24 nm away,
against 9.95 nm for 559.950 nm). The single wavelength is a labelled assumption: a broadband, cell-weighted
law would need the panel's spectral response, which is out of scope.

Verification against the paper (tests/test_phase3_power.py, all 30 transcribed rows): sum A_k = 1 (its
Eq. 5) and F/I = 2 sum A_k / (k + 2) (its Eq. 6) reproduce the printed F/I column. The paper tabulates no
separate I(mu) values, so these two printed relations are the available check.

Geometry. A point at angular distance s from the disk centre has sin(theta) = sin(s) / sin(rho) exactly (rho
the solar angular radius), so mu = sqrt(1 - sin^2 s / sin^2 rho). Intensities are integrated over solid
angle, like the visible fraction f, and normalised by the full-disk flux (also over solid angle):

    F = 2 pi sin^2(rho) int_0^1 I(mu) mu / sqrt(1 - sin^2(rho) (1 - mu^2)) d mu,

whose small-disk limit F / (pi sin^2 rho) is the paper's F/I. Hence f_I = (flux of the visible part) / F:
exactly 1 for a fully visible Sun (so P_rel_LD = P_rel there) and 0 when hidden. Limb darkening only
redistributes flux within the disk; it changes the indicator only while the Sun is partly hidden.

    P_rel_LD = f_I (1 au / r)^2 k,    P_rel (uniform disk) unchanged.
"""
from __future__ import annotations

import math

import numpy as np
from numba import njit

from .earth import _elaz, _t_at_az
from .visibility import (SPHERICAL_EL_DEG, _E, _N, _U, _gl, _hilo, _horizon_crossings, _limb_crossings, _occulter,
                         _surely_apart, cap_points)

LD_CITATION = ("H. Neckel and D. Labs, Solar Limb Darkening 1986-1990 (303 to 1099 nm), Solar Physics 153, "
               "91-114 (1994), Table I, p. 98")
LD_WAVELENGTH_NM = 541.760
LD_COEFFS = (0.26073, 1.27428, -1.30352, 1.47085, -0.96618, 0.26384)     # A0..A5, exactly as printed
LD_PRINTED_F_OVER_I = 0.8002                                             # the same row's printed F/I
LD_TOL = 1e-10            # adaptive tolerance of the visible-intensity integral
LD_ORDERS = (16, 256)     # first and largest Gauss-Legendre order (outer and inner) per piece
LD_METHOD_VERSION = "ld/v1: NL94 polynomial, solid-angle full-disk-flux normalisation, nested adaptive GL"
LD_LABEL = ("Estimated (D01: Neckel & Labs 1994 Table I limb darkening at 541.760 nm, full-disk-flux "
            "normalised)")


def ld_settings() -> dict:
    """Every limb-darkening parameter that changes an output (hashed into result IDs)."""
    return {"citation": LD_CITATION, "wavelength_nm": LD_WAVELENGTH_NM, "coefficients": list(LD_COEFFS),
            "normalisation": "full-disk flux over solid angle", "tol": LD_TOL, "orders": list(LD_ORDERS),
            "version": LD_METHOD_VERSION}


def intensity(mu, coeffs=LD_COEFFS):
    """I(mu) / I(1)."""
    mu = np.asarray(mu, dtype=float)
    return sum(a * mu ** k for k, a in enumerate(coeffs))


def full_disk_flux(rho_rad: float, coeffs=LD_COEFFS) -> float:
    """Flux of the whole disk over solid angle, in units of I(1) x steradian (see module docstring). The
    integrand is a polynomial times a smooth factor, so 64-point Gauss-Legendre is exact to rounding."""
    s2 = math.sin(rho_rad) ** 2
    x, w = _gl(64)
    mu = 0.5 * (x + 1.0)
    vals = intensity(mu, coeffs) * mu / np.sqrt(1.0 - s2 * (1.0 - mu * mu))
    return float(2.0 * math.pi * s2 * 0.5 * np.sum(w * vals))


def planar_f_over_i(coeffs=LD_COEFFS) -> float:
    """The paper's Eq. (6): F/I = 2 sum A_k / (k + 2), the small-disk limit of F / (pi sin^2 rho)."""
    return 2.0 * sum(a / (k + 2) for k, a in enumerate(coeffs))


# ------------------------------------------------------------------ visible intensity
@njit(cache=True)
def _mu(x, el, E, s2r):
    """mu at relative azimuth x, elevation el, for a Sun centred at elevation E (s2r = sin^2 rho);
    sin^2 s from the haversine form (no cancellation for small s)."""
    hv = math.sin(0.5 * (el - E)) ** 2 + math.cos(el) * math.cos(E) * math.sin(0.5 * x) ** 2
    s2 = 4.0 * hv * (1.0 - hv)
    m2 = 1.0 - s2 / s2r
    return math.sqrt(m2) if m2 > 0.0 else 0.0


@njit(cache=True)
def _poly(mu, a):
    v = 0.0
    p = 1.0
    for k in range(a.shape[0]):
        v += a[k] * p
        p *= mu
    return v


@njit(cache=True)
def _seg(p, q, x, E, s2r, a, gx, gw):
    """int_p^q I(mu) cos(el) d el with el = m + h sin(tau) (removes the square root of mu at the limb)."""
    if q <= p:
        return 0.0
    m = 0.5 * (p + q)
    hh = 0.5 * (q - p)
    acc = 0.0
    for j in range(gx.shape[0]):
        tau = 0.5 * math.pi * gx[j]
        el = m + hh * math.sin(tau)
        acc += gw[j] * math.cos(tau) * _poly(_mu(x, el, E, s2r), a) * math.cos(el)
    return acc * hh * 0.5 * math.pi


@njit(cache=True)
def _ld_integral(h, binw, use_terrain, use_earth, az_s, el_s, r_s, Q0, QA, QB, a, cuts, gx, gw):
    """Flux (I(1) x sr) of the solar cap above the horizon and outside Earth's exact limb: outer integral over
    the Sun's azimuth span (pieces between `cuts`, sine substitution, Gauss-Legendre), inner integral over each
    visible elevation segment (exact ends: _hilo for the Sun, the closed-form limb points for Earth)."""
    Ps, Qs, crs = math.cos(el_s), math.sin(el_s), math.cos(r_s)
    s2r = math.sin(r_s) ** 2
    nb = h.shape[0]
    acc = 0.0
    for j in range(cuts.shape[0] - 1):
        pa = cuts[j]
        pb = cuts[j + 1]
        if pb <= pa:
            continue
        m = 0.5 * (pa + pb)
        hh = 0.5 * (pb - pa)
        for i in range(gx.shape[0]):
            th = 0.5 * math.pi * gx[i]
            x = m + hh * math.sin(th)
            wx = hh * math.cos(th) * 0.5 * math.pi * gw[i]
            lo, hi = _hilo(x, Ps, Qs, crs)
            L = lo
            A = az_s + x
            if use_terrain:
                fpos = (math.degrees(A) % 360.0) / binw
                i0 = int(math.floor(fpos)) % nb
                i1 = (i0 + 1) % nb
                tt = fpos - math.floor(fpos)
                H = math.radians(h[i0] * (1.0 - tt) + h[i1] * tt)
                if H > L:
                    L = H
            if L >= hi:
                continue
            v = 0.0
            done = False
            if use_earth:
                ts, cnt = _t_at_az(A, Q0, QA, QB, _E, _N)
                if cnt == 2:
                    e1, _ = _elaz(ts[0], Q0, QA, QB, _U, _E, _N)
                    e2, _ = _elaz(ts[1], Q0, QA, QB, _U, _E, _N)
                    ea = max(L, min(e1, e2))
                    eb = min(hi, max(e1, e2))
                    if eb > ea:
                        v = _seg(L, ea, x, el_s, s2r, a, gx, gw) + _seg(eb, hi, x, el_s, s2r, a, gx, gw)
                        done = True
            if not done:
                v = _seg(L, hi, x, el_s, s2r, a, gx, gw)
            acc += v * wx
    return acc


@njit(cache=True)
def _sun_forms(xs, h, binw, az_s, el_s, r_s, out):
    """Sun top - H and Sun bottom - H at relative azimuths xs (sign changes: horizon crosses the solar limb)."""
    Ps, Qs, crs = math.cos(el_s), math.sin(el_s), math.cos(r_s)
    nb = h.shape[0]
    for k in range(xs.shape[0]):
        lo, hi = _hilo(xs[k], Ps, Qs, crs)
        fpos = (math.degrees(az_s + xs[k]) % 360.0) / binw
        i0 = int(math.floor(fpos)) % nb
        i1 = (i0 + 1) % nb
        tt = fpos - math.floor(fpos)
        H = math.radians(h[i0] * (1.0 - tt) + h[i1] * tt)
        out[k, 0] = hi - H
        out[k, 1] = lo - H


def _sun_horizon_crossings(hp, sun: dict, cuts: np.ndarray, per: int = 32) -> list:
    az_s, el_s, rs = math.radians(sun["az"]), math.radians(sun["el"]), math.radians(sun["rho"])
    out = []
    for a, b in zip(cuts[:-1], cuts[1:]):
        if b <= a:
            continue
        xs = np.linspace(a, b, per + 1)
        v = np.empty((xs.size, 2))
        _sun_forms(xs, hp.h, hp.bin, az_s, el_s, rs, v)
        for j in range(2):
            f = v[:, j]
            for k in range(per):
                if (f[k] > 0) == (f[k + 1] > 0):
                    continue
                lo, hi, flo = xs[k], xs[k + 1], f[k]
                one = np.empty((1, 2))
                for _ in range(60):
                    mid = 0.5 * (lo + hi)
                    _sun_forms(np.array([mid]), hp.h, hp.bin, az_s, el_s, rs, one)
                    if (one[0, j] > 0) == (flo > 0):
                        lo, flo = mid, one[0, j]
                    else:
                        hi = mid
                out.append(0.5 * (lo + hi))
    return out


def _cuts(hp, sun: dict, oc: dict | None, use_terrain: bool) -> tuple[np.ndarray, float]:
    """Azimuths (relative to the Sun) where the integrand changes form: the Sun's azimuth extremes, Earth's
    azimuth extremes and the limb crossings (with Earth), horizon nodes and horizon-limb crossings (terrain)."""
    from .earth import _global_extremum
    az_s, el_s, rs = math.radians(sun["az"]), math.radians(sun["el"]), math.radians(sun["rho"])
    hw = math.asin(min(1.0, math.sin(rs) / max(math.cos(el_s), 1e-12)))
    cuts = [-hw, hw]
    earth_ext = []
    if oc is not None:
        dummy = np.zeros(1)
        for sg in (1.0, -1.0):
            t_x, a_rel, _ = _global_extremum(2, sg, *oc["limb"], _U, _E, _N, _U, az_s, dummy, 1.0, 64, 1e-14, 60)
            cuts.append(a_rel)
            earth_ext.append((a_rel, _elaz(t_x, *oc["limb"], _U, _E, _N)[0]))
        cuts += _limb_crossings(sun, oc)
    if use_terrain:
        k0 = math.floor(math.degrees(az_s - hw) / hp.bin)
        k1 = math.ceil(math.degrees(az_s + hw) / hp.bin)
        cuts += [math.radians(k * hp.bin) - az_s for k in range(k0, k1 + 1)]
    cuts = np.unique(np.clip(np.array(cuts, dtype=float), -hw, hw))
    if use_terrain:
        extra = (_horizon_crossings(hp, sun, oc, cuts, earth_ext) if oc is not None
                 else _sun_horizon_crossings(hp, sun, cuts))
        cuts = np.unique(np.clip(np.append(cuts, extra), -hw, hw))
    return cuts, hw


def visible_flux_fraction(hp, sun: dict, earth: dict | None = None, use_terrain: bool = True,
                          coeffs=LD_COEFFS, tol: float = LD_TOL) -> tuple[float, float, int]:
    """Adaptive f_I (no short-circuit): the Gauss-Legendre order (outer and inner) doubles until two successive
    changes are below tol / 2 and tol. Returns (f_I, error estimate, order). Valid below SPHERICAL_EL_DEG."""
    oc = None
    if earth is not None and not _surely_apart(sun, earth):
        oc = _occulter(earth)
        if math.radians(float(sun["gamma"])) >= math.radians(float(sun["rho"])) + oc["r_hi"]:
            oc = None
    cuts, _hw = _cuts(hp, sun, oc, use_terrain)
    az_s, el_s, rs = math.radians(sun["az"]), math.radians(sun["el"]), math.radians(sun["rho"])
    limb = oc["limb"] if oc is not None else (_U, _E, _N)
    a = np.asarray(coeffs, dtype=float)
    F = full_disk_flux(rs, coeffs)
    n = LD_ORDERS[0]
    f_prev = _ld_integral(hp.h, hp.bin, use_terrain, oc is not None, az_s, el_s, rs, *limb, a, cuts, *_gl(n)) / F
    err = prev = math.inf
    while n < LD_ORDERS[1]:
        n *= 2
        f = _ld_integral(hp.h, hp.bin, use_terrain, oc is not None, az_s, el_s, rs, *limb, a, cuts, *_gl(n)) / F
        prev, err = err, abs(f - f_prev)
        f_prev = f
        if err < 0.5 * tol and prev < tol:
            break
    return min(1.0, max(0.0, f_prev)), err, n


def _sampled(hp, sun: dict, earth: dict | None, coeffs) -> float:
    """Above SPHERICAL_EL_DEG (never at south polar sites): intensity-weighted area-weighted cap points."""
    from .visibility import _dist_outside_earth
    az_p, el_p, w, pts, _b = cap_points(sun["az"], sun["el"], sun["rho"])
    s_vec = np.array([math.cos(math.radians(sun["el"])) * math.sin(math.radians(sun["az"])),
                      math.cos(math.radians(sun["el"])) * math.cos(math.radians(sun["az"])),
                      math.sin(math.radians(sun["el"]))])
    s = np.arctan2(np.linalg.norm(np.cross(pts, s_vec), axis=1), pts @ s_vec)
    mu = np.sqrt(np.maximum(0.0, 1.0 - np.sin(s) ** 2 / math.sin(math.radians(sun["rho"])) ** 2))
    wi = w * intensity(mu, coeffs)
    vis = el_p - hp.at(az_p) > 0
    if earth is not None and not _surely_apart(sun, earth):
        vis &= _dist_outside_earth(pts, _occulter(earth)) > 0
    return float(np.sum(wi * vis) / np.sum(wi))


def limb_darkened_fraction(hp, sun: dict, earth: dict | None, f: float, coeffs=LD_COEFFS) -> dict:
    """f_I for one sample, given its (uniform-disk) visible fraction f: exactly f when f is 0, 1 or unknown
    (NaN), so P_rel_LD equals P_rel bitwise there; otherwise the adaptive integral (or the sampled cap above
    SPHERICAL_EL_DEG), with method and error estimate."""
    if not np.isfinite(f):
        return {"f_I": float("nan"), "method": "unknown", "err": 0.0}
    if f <= 0.0:
        return {"f_I": 0.0, "method": "exact: hidden", "err": 0.0}
    if f >= 1.0:
        return {"f_I": 1.0, "method": "exact: fully visible", "err": 0.0}
    if sun["el"] > SPHERICAL_EL_DEG or sun["el"] + sun["rho"] >= 90.0:
        return {"f_I": _sampled(hp, sun, earth, coeffs), "method": "sampled (above 60 deg)", "err": float("nan")}
    fi, err, n = visible_flux_fraction(hp, sun, earth, coeffs=coeffs)
    return {"f_I": fi, "method": f"adaptive ({n})", "err": err}
