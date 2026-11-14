"""Independent references for the Phase 3 oblate-Earth tests (dense NumPy sampling, golden-section
refinement, strip integration). Nothing here calls the engine's solver or disk kernel."""
from __future__ import annotations

import math

import numpy as np

E_AX = np.array([1.0, 0.0, 0.0])      # site basis for synthetic geometry: east, north, up
N_AX = np.array([0.0, 1.0, 0.0])
U_AX = np.array([0.0, 0.0, 1.0])
GR = (math.sqrt(5.0) - 1.0) / 2.0


def direction(az_deg, el_deg):
    a, e = math.radians(az_deg), math.radians(el_deg)
    return np.array([math.cos(e) * math.sin(a), math.cos(e) * math.cos(a), math.sin(e)])


def pole_axis_frame(pole):
    """Rotation M (rows x, y, z) from the body frame to an Earth-axis frame whose z is the given pole (any
    x perpendicular to it: the spheroid is symmetric about its axis). Used to hand SPICE edlimb, which takes the
    spheroid aligned with the frame axes, the same Earth orientation the engine uses; the pole itself is
    validated separately (tests/test_phase4_earth_pole.py against ERFA)."""
    z = np.asarray(pole, dtype=float)
    z = z / np.linalg.norm(z)
    ref = np.array([1.0, 0.0, 0.0]) if abs(z[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    x = np.cross(ref, z)
    x /= np.linalg.norm(x)
    return np.array([x, np.cross(z, x), z])


def random_unit(rng):
    v = rng.normal(size=3)
    return v / np.linalg.norm(v)


def rotate_toward(p, eps, rng):
    """p rotated by exactly eps (rad) about a random axis perpendicular to it."""
    k = np.cross(p, random_unit(rng))
    k /= np.linalg.norm(k)
    return p * math.cos(eps) + np.cross(k, p) * math.sin(eps)


def synth_geo(az_deg, el_deg, d_km, pole, a=None, b=None, basis=(E_AX, N_AX, U_AX)):
    """Geometry dict (as ephem.earth_geo) for an Earth centre at (az, el, d) with the given pole."""
    from lunaops import settings
    from lunaops.engine.earth import limb_ellipse, limb_extrema

    a = settings.EARTH_RADII_KM[0] if a is None else a
    b = settings.EARTH_RADII_KM[2] if b is None else b
    e, n, u = basis
    rh = direction(az_deg, el_deg)
    r = d_km * (rh[0] * e + rh[1] * n + rh[2] * u)
    Q0, QA, QB = (x[0] for x in limb_ellipse(r[None], np.asarray(pole, float)[None], a, b))
    sv = settings.EARTH_SOLVER
    ru, rd, dm, fb = limb_extrema(Q0, QA, QB, u, e, n, math.radians(el_deg), math.radians(az_deg),
                                  sv["bracket"], sv["tol"], sv["maxiter"])
    return {"az": float(az_deg), "el": float(el_deg), "Q0": Q0, "QA": QA, "QB": QB, "rho_up": ru, "rho_down": rd,
            "delta_max": dm, "alpha": math.asin(a / d_km), "beta": math.asin(b / d_km), "e": e, "n": n, "u": u,
            "fallbacks": fb, "r": r}


# ------------------------------------------------------------------ dense limb evaluation
def limb_q(Q0, QA, QB, t):
    t = np.asarray(t, dtype=float)
    return Q0[None, :] + np.cos(t)[:, None] * QA[None, :] + np.sin(t)[:, None] * QB[None, :]


def el_az(q, e, n, u):
    nq = np.linalg.norm(q, axis=1)
    el = np.arcsin(np.clip((q @ u) / nq, -1.0, 1.0))
    az = np.arctan2(q @ e, q @ n)
    return el, az


def golden_extremum(fun, a, b, sign=1.0, tol=1e-13, it=200):
    """Golden-section search for the max (sign=+1) or min (sign=-1) of a scalar function on [a, b]."""
    c = b - GR * (b - a)
    d = a + GR * (b - a)
    fc, fd = sign * fun(c), sign * fun(d)
    for _ in range(it):
        if abs(b - a) < tol:
            break
        if fc > fd:
            b, d, fd = d, c, fc
            c = b - GR * (b - a)
            fc = sign * fun(c)
        else:
            a, c, fc = c, d, fd
            d = a + GR * (b - a)
            fd = sign * fun(d)
    x = 0.5 * (a + b)
    return x, fun(x)


def dense_extremum(vec_fun, sign=1.0, m=100_000):
    """Global extremum of a 2 pi-periodic function: m-point dense sampling, then golden refinement."""
    t = np.linspace(0.0, 2 * math.pi, m, endpoint=False)
    v = vec_fun(t)
    k = int(np.argmax(sign * v))
    h = 2 * math.pi / m
    best_v = v[k]
    x, val = golden_extremum(lambda s: float(vec_fun(np.array([s]))[0]), t[k] - h, t[k] + h, sign)
    return (val if sign * val >= sign * best_v else best_v)


def H_rad(hp, az_rad):
    return np.radians(hp.at(np.degrees(az_rad) % 360.0))


def ref_clearance(geo, hp, m=1_000_000):
    """(g_top, g_bot) in radians: dense limb sampling against the horizon, golden refinement."""
    Q0, QA, QB, e, n, u = geo["Q0"], geo["QA"], geo["QB"], geo["e"], geo["n"], geo["u"]

    def clr(t):
        el, az = el_az(limb_q(Q0, QA, QB, t), e, n, u)
        return el - H_rad(hp, az)
    return dense_extremum(clr, 1.0, m), dense_extremum(clr, -1.0, m)


def ref_fraction(geo, hp, m=400_000, strips=400_000):
    """Visible solid-angle fraction of the exact limb against the horizon by azimuth strips:
    A = sum over strips of [sin el_hi - sin max(el_lo, H)]+ daz (midpoint rule), limb arcs interpolated
    from m dense limb samples. Independent of the engine's crossing logic and Gauss-Legendre arcs."""
    Q0, QA, QB, e, n, u = geo["Q0"], geo["QA"], geo["QB"], geo["e"], geo["n"], geo["u"]
    az_c = math.radians(geo["az"])
    t = np.linspace(0.0, 2 * math.pi, m, endpoint=False)
    el, az = el_az(limb_q(Q0, QA, QB, t), e, n, u)
    ar = (az - az_c + math.pi) % (2 * math.pi) - math.pi
    i0, i1 = int(np.argmin(ar)), int(np.argmax(ar))
    idx = np.arange(m)
    arc1 = np.roll(idx, -i0)[: (i1 - i0) % m + 1]          # from the azimuth minimum to the maximum
    arc2 = np.roll(idx, -i1)[: (i0 - i1) % m + 1]          # back from the maximum to the minimum
    a_lo, a_hi = ar[i0], ar[i1]
    grid = a_lo + (np.arange(strips) + 0.5) * (a_hi - a_lo) / strips
    w = (a_hi - a_lo) / strips
    curves = []
    for arc in (arc1, arc2):
        x, y = ar[arc], el[arc]
        o = np.argsort(x)
        curves.append(np.interp(grid, x[o], y[o]))
    hi, lo = (curves[0], curves[1]) if curves[0].mean() > curves[1].mean() else (curves[1], curves[0])
    Hg = H_rad(hp, grid + az_c)
    tot = np.sum(np.sin(hi) - np.sin(lo)) * w
    vis = np.sum(np.maximum(0.0, np.sin(hi) - np.sin(np.maximum(lo, Hg)))) * w
    return vis / tot


# ------------------------------------------------------------------ horizons
def horizon(kind, az0_deg, level_deg, slope=0.0, depth=0.0, width_deg=0.5, az1_deg=None, nbins=3600):
    """Periodic piecewise-linear horizon (degrees) near azimuth az0: flat, sloped (clipped ramp), notched
    (V notch at az1) or two_notch (two equal V notches either side of az0: maximiser jumps)."""
    from lunaops.engine.visibility import HorizonProfile

    az = np.arange(nbins) * 360.0 / nbins
    rel = (az - az0_deg + 180.0) % 360.0 - 180.0
    h = np.full(nbins, float(level_deg))
    if kind in ("sloped", "notched", "two_notch"):
        h += slope * np.clip(rel, -5.0, 5.0)
    if kind == "notched":
        r1 = (az - (az0_deg if az1_deg is None else az1_deg) + 180.0) % 360.0 - 180.0
        h -= depth * np.maximum(0.0, 1.0 - np.abs(r1) / width_deg)
    if kind == "two_notch":
        for c in (-0.4, 0.4):
            r1 = rel - c
            h -= depth * np.maximum(0.0, 1.0 - np.abs(r1) / width_deg)
    return HorizonProfile(h, np.zeros(nbins, dtype=bool))


def random_case(rng, ecc_max=0.2):
    """Random oblate limb geometry and horizon: (geo, hp, kind)."""
    from lunaops import settings

    a = settings.EARTH_RADII_KM[0]
    ecc = rng.uniform(0.0, ecc_max) if rng.random() < 0.8 else 10 ** rng.uniform(-6, -2)
    b = a * math.sqrt(1.0 - ecc * ecc)
    d = rng.uniform(356_000.0, 407_000.0)
    az = rng.uniform(0.0, 360.0)
    el = rng.uniform(-10.0, 35.0)
    geo = synth_geo(az, el, d, random_unit(rng), a, b)
    alpha = math.degrees(geo["alpha"])
    kind = ("flat", "sloped", "notched", "two_notch")[rng.integers(4)]
    level = el + rng.uniform(-1.3, 1.3) * alpha
    slope = rng.uniform(0.0, 2.0) * rng.choice([-1.0, 1.0])
    depth = rng.uniform(0.0, 2.0) * alpha
    width = rng.uniform(0.05, 1.0)
    az1 = az + rng.uniform(-1.0, 1.0) * alpha
    hp = horizon(kind, az, level, slope, depth, width, az1)
    return geo, hp, kind
