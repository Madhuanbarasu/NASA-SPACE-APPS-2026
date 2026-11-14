"""Earth as an oblate spheroid seen from a lunar site (Phase 3, item 1; pole of date since Phase 4).

Geometry. Earth is the IERS 2010 spheroid (a, a, b) with its spin axis the Celestial Intermediate Pole
of date: IAU 2006 precession with IAU 2000B nutation (engine.earth_orientation, the SOFA/ERFA pn06 + nut00b
combination, about 1 mas). Until algorithm 1.5.0 the axis was frozen at the J2000 Z axis; that pole
drifted from the true one by about 20 arcsec per year (Phase 4 investigation in docs/AUDIT_2026-11.md).
The deviation from the IAU_EARTH pole is still measured per epoch in the tests. Seen from an
observer at O, the limb is the set of tangent points of the observer's cone: in coordinates scaled by
(1/a, 1/a, 1/b) the spheroid is the unit sphere and the limb a circle (centre w'/|w'|^2, radius
sqrt(1 - 1/|w'|^2)); mapped back it is a planar 3-D ellipse. The vector from the observer to the limb
point with parameter t is therefore exactly

    q(t) = Q0 + cos t QA + sin t QB.

Disk quantities against a horizon H(az) (piecewise linear in azimuth, nodes every bin):
  * c       centre clearance, el_c - H(az_c) (independent of the limb);
  * g_top   max over the limb of el(t) - H(az(t)); g_bot the min. For a fixed azimuth el - H increases
            with el, so these are the extremes over the whole disk. They are found piecewise: the limb is
            cut at the closed-form parameters where az(t) crosses a horizon node, the clearance is smooth
            on each piece, and each piece is bracketed and refined by Brent's safeguarded method;
  * f       visible solid-angle fraction, from strips in azimuth: dA = cos el del daz, so the area above
            H is the integral over az of [sin el_hi - sin max(el_lo, H)]+. The azimuth range is cut at
            nodes and at limb/horizon crossings; on each strip the limb parts are integrated over t
            (Gauss-Legendre, smooth) and the horizon part in closed form.
All extrema use a 64-point bracket, Brent refinement and a verification against the bracket samples,
with a dense fallback that is counted.

A circular cap (radius rho_cap = (rho_up + rho_down)/2, centre offset (rho_up - rho_down)/2 along the
vertical) is used for a sample only when its proven errors are within tolerance: the full-limb deviation
delta_max, the edge bound E_g = delta_max (1 + S/c_min) and the closed-form area bound
E_f = (dA+ + dA-)/(A_C - dA-). Otherwise the full ellipse is used (the normal case at Earth's oblateness).
"""
from __future__ import annotations

import math

import numpy as np
import spiceypy as sp
from numba import njit

from .. import settings
from .frames import cross3
from .kernels import SPICE_LOCK

TWO_PI = 2.0 * math.pi
GL_N = 20
_GL_X, _GL_W = np.polynomial.legendre.leggauss(GL_N)


def earth_model_settings() -> dict:
    """Every Earth-model parameter that changes an output (hashed into result IDs)."""
    return {"radii_km": list(settings.EARTH_RADII_KM), "pole_model": settings.EARTH_POLE_MODEL,
            "limb_tol_deg": settings.EARTH_LIMB_TOL_DEG, "f_tol": settings.EARTH_F_TOL,
            "solver": dict(settings.EARTH_SOLVER), "rate_inflation": settings.CURVATURE_INFLATION}


# ------------------------------------------------------------------ pole and limb ellipse (vectorised)
def pole_in_frame(ets, frame: str) -> tuple[np.ndarray, np.ndarray]:
    """Earth's pole of date (CIP: IAU 2006 precession + IAU 2000B nutation, engine.earth_orientation)
    expressed in the body-fixed frame, and its time derivative. With R(t) the J2000 -> frame rotation from
    SPICE (sxform), p = R z and dp/dt = R' z + R z', where z is the CIP in J2000/GCRS axes."""
    from .earth_orientation import earth_pole_gcrs
    ets = np.atleast_1d(np.asarray(ets, dtype=float))
    z, zd = earth_pole_gcrs(ets)
    p = np.empty((ets.size, 3))
    pd = np.empty((ets.size, 3))
    with SPICE_LOCK:
        for i, et in enumerate(ets):
            x = np.asarray(sp.sxform("J2000", frame, float(et)))
            p[i] = x[:3, :3] @ z[i]
            pd[i] = x[3:, :3] @ z[i] + x[:3, :3] @ zd[i]
    return p, pd


def limb_ellipse(r: np.ndarray, pole: np.ndarray, a: float | None = None, b: float | None = None):
    """Q0, QA, QB (n, 3) such that q(t) = Q0 + cos t QA + sin t QB (km) is the observer->limb vector.

    r: observer->Earth-centre vectors (n, 3), km; pole: unit spin axes (n, 3) in the same frame."""
    a = settings.EARTH_RADII_KM[0] if a is None else a
    b = settings.EARTH_RADII_KM[2] if b is None else b
    r = np.atleast_2d(np.asarray(r, dtype=float))
    z = np.atleast_2d(np.asarray(pole, dtype=float))
    z = z / np.linalg.norm(z, axis=1)[:, None]
    # any unit vector perpendicular to the pole serves as the first equatorial axis (the spheroid is symmetric
    # about its axis); built from a fixed reference, so a pole along the line of sight is not degenerate
    ref = np.where(np.abs(z[:, 0:1]) < 0.9, np.array([[1.0, 0.0, 0.0]]), np.array([[0.0, 1.0, 0.0]]))
    x = cross3(z, ref)
    x /= np.linalg.norm(x, axis=1)[:, None]
    y = cross3(z, x)
    w = -r                                                    # Earth centre -> observer
    ws = np.stack([np.sum(w * x, 1) / a, np.sum(w * y, 1) / a, np.sum(w * z, 1) / b], axis=1)
    D2 = np.sum(ws * ws, 1)
    c_s = ws / D2[:, None]
    rad = np.sqrt(1.0 - 1.0 / D2)
    wh = ws / np.sqrt(D2)[:, None]
    ref = np.where(np.abs(wh[:, 2:3]) < 0.9, np.array([[0.0, 0.0, 1.0]]), np.array([[1.0, 0.0, 0.0]]))
    e1 = cross3(wh, ref)
    e1 /= np.linalg.norm(e1, axis=1)[:, None]
    e2 = cross3(wh, e1)

    def to_frame(v):                                          # scaled Earth coords -> body-fixed frame
        return (a * v[:, 0:1]) * x + (a * v[:, 1:2]) * y + (b * v[:, 2:3]) * z
    return r + to_frame(c_s), to_frame(rad[:, None] * e1), to_frame(rad[:, None] * e2)


# ------------------------------------------------------------------ scalar kernels
@njit(cache=True)
def _q(t, Q0, QA, QB):
    c = math.cos(t)
    s = math.sin(t)
    return (Q0[0] + c * QA[0] + s * QB[0], Q0[1] + c * QA[1] + s * QB[1], Q0[2] + c * QA[2] + s * QB[2])


@njit(cache=True)
def _elaz(t, Q0, QA, QB, u, e, n):
    qx, qy, qz = _q(t, Q0, QA, QB)
    nq = math.sqrt(qx * qx + qy * qy + qz * qz)
    su = (qx * u[0] + qy * u[1] + qz * u[2]) / nq
    su = min(1.0, max(-1.0, su))
    qe = qx * e[0] + qy * e[1] + qz * e[2]
    qn = qx * n[0] + qy * n[1] + qz * n[2]
    return math.asin(su), math.atan2(qe, qn)


@njit(cache=True)
def _wrap(x):
    return (x + math.pi) % TWO_PI - math.pi


@njit(cache=True)
def _H(az_rad, h, binw_deg):
    """Horizon elevation (rad) at azimuth (rad), linear between nodes."""
    nb = h.shape[0]
    f = (math.degrees(az_rad) % 360.0) / binw_deg
    i0 = int(math.floor(f)) % nb
    i1 = (i0 + 1) % nb
    w = f - math.floor(f)
    return math.radians(h[i0] * (1.0 - w) + h[i1] * w)


@njit(cache=True)
def _obj(mode, t, Q0, QA, QB, u, e, n, o, az_c, h, binw):
    """Objectives: 0 elevation; 1 angle from direction o; 2 azimuth relative to az_c; 3 clearance."""
    if mode == 1:
        qx, qy, qz = _q(t, Q0, QA, QB)
        nq = math.sqrt(qx * qx + qy * qy + qz * qz)
        cx = (qy * o[2] - qz * o[1])
        cy = (qz * o[0] - qx * o[2])
        cz = (qx * o[1] - qy * o[0])
        return math.atan2(math.sqrt(cx * cx + cy * cy + cz * cz), qx * o[0] + qy * o[1] + qz * o[2])
    el, az = _elaz(t, Q0, QA, QB, u, e, n)
    if mode == 0:
        return el
    if mode == 2:
        return _wrap(az - az_c)
    return el - _H(az, h, binw)


@njit(cache=True)
def _brent_max(mode, sign, a, b, Q0, QA, QB, u, e, n, o, az_c, h, binw, tol, maxit):
    """Brent's safeguarded (golden section + parabolic) maximisation of sign*objective on [a, b]."""
    cg = 0.3819660112501051
    x = w = v = a + cg * (b - a)
    fx = fw = fv = -sign * _obj(mode, x, Q0, QA, QB, u, e, n, o, az_c, h, binw)
    d = 0.0
    ee = 0.0
    for _ in range(maxit):
        xm = 0.5 * (a + b)
        tol1 = tol * abs(x) + 1e-16
        tol2 = 2.0 * tol1
        if abs(x - xm) <= tol2 - 0.5 * (b - a):
            break
        if abs(ee) > tol1:
            r = (x - w) * (fx - fv)
            q = (x - v) * (fx - fw)
            p = (x - v) * q - (x - w) * r
            q = 2.0 * (q - r)
            if q > 0.0:
                p = -p
            q = abs(q)
            etemp = ee
            ee = d
            if abs(p) >= abs(0.5 * q * etemp) or p <= q * (a - x) or p >= q * (b - x):
                ee = (a - x) if x >= xm else (b - x)
                d = cg * ee
            else:
                d = p / q
                uu = x + d
                if uu - a < tol2 or b - uu < tol2:
                    d = tol1 if xm - x >= 0 else -tol1
        else:
            ee = (a - x) if x >= xm else (b - x)
            d = cg * ee
        uu = x + d if abs(d) >= tol1 else x + (tol1 if d >= 0 else -tol1)
        fu = -sign * _obj(mode, uu, Q0, QA, QB, u, e, n, o, az_c, h, binw)
        if fu <= fx:
            if uu >= x:
                a = x
            else:
                b = x
            v, w, x = w, x, uu
            fv, fw, fx = fw, fx, fu
        else:
            if uu < x:
                a = uu
            else:
                b = uu
            if fu <= fw or w == x:
                v, w = w, uu
                fv, fw = fw, fu
            elif fu <= fv or v == x or v == w:
                v = uu
                fv = fu
    return x, -sign * fx


@njit(cache=True)
def _global_extremum(mode, sign, Q0, QA, QB, u, e, n, o, az_c, h, binw, nbr, tol, maxit):
    """Global extremum over the closed limb: bracket on nbr samples, Brent, verify; dense fallback.
    Returns (t, value, fallback_used)."""
    best = -1e300
    kb = 0
    step = TWO_PI / nbr
    for k in range(nbr):
        val = sign * _obj(mode, k * step, Q0, QA, QB, u, e, n, o, az_c, h, binw)
        if val > best:
            best = val
            kb = k
    t, val = _brent_max(mode, sign, (kb - 1) * step, (kb + 1) * step, Q0, QA, QB, u, e, n, o, az_c, h, binw,
                        tol, maxit)
    if sign * val >= best - 1e-15:
        return t % TWO_PI, val, False
    # fallback: 16x denser bracket
    nd = nbr * 16
    step = TWO_PI / nd
    best = -1e300
    for k in range(nd):
        vv = sign * _obj(mode, k * step, Q0, QA, QB, u, e, n, o, az_c, h, binw)
        if vv > best:
            best = vv
            kb = k
    t, val = _brent_max(mode, sign, (kb - 1) * step, (kb + 1) * step, Q0, QA, QB, u, e, n, o, az_c, h, binw,
                        tol, maxit)
    if sign * val < best:
        return (kb * step) % TWO_PI, sign * best, True
    return t % TWO_PI, val, True


@njit(cache=True)
def _t_at_az(A, Q0, QA, QB, e, n):
    """The (up to two) limb parameters where az(t) = A (rad), in closed form; count of solutions."""
    sA = math.sin(A)
    cA = math.cos(A)
    m0 = sA * n[0] - cA * e[0]
    m1 = sA * n[1] - cA * e[1]
    m2 = sA * n[2] - cA * e[2]
    P = m0 * QA[0] + m1 * QA[1] + m2 * QA[2]
    R = m0 * QB[0] + m1 * QB[1] + m2 * QB[2]
    K = m0 * Q0[0] + m1 * Q0[1] + m2 * Q0[2]
    Rr = math.hypot(P, R)
    out = np.empty(2)
    cnt = 0
    if Rr <= 0.0 or abs(K) > Rr:
        return out, 0
    ph = math.atan2(R, P)
    dd = math.acos(min(1.0, max(-1.0, -K / Rr)))
    for t in (ph + dd, ph - dd):
        qx, qy, qz = _q(t, Q0, QA, QB)
        if qx * (cA * n[0] + sA * e[0]) + qy * (cA * n[1] + sA * e[1]) + qz * (cA * n[2] + sA * e[2]) > 0.0:
            out[cnt] = t % TWO_PI
            cnt += 1
    return out, cnt


@njit(cache=True)
def _zeroin(a, b, fa, fb, Q0, QA, QB, u, e, n, az_c, h, binw):
    """Safeguarded root of the clearance on [a, b] with fa*fb <= 0 (bisection + secant)."""
    for _ in range(200):
        if b - a < 1e-15:
            break
        m = 0.5 * (a + b)
        if fb != fa:
            s = b - fb * (b - a) / (fb - fa)
            if not (a < s < b) or abs(s - m) > 0.25 * (b - a):
                s = m
        else:
            s = m
        fs = _obj(3, s, Q0, QA, QB, u, e, n, u, az_c, h, binw)
        if fs == 0.0:
            return s
        if (fa < 0.0) == (fs < 0.0):
            a, fa = s, fs
        else:
            b, fb = s, fs
    return 0.5 * (a + b)


@njit(cache=True)
def _arc_integral(t1, t2, Q0, QA, QB, u, e, n, gx, gw):
    """Integral of sin(el) d(az) along the limb from t1 to t2 (Gauss-Legendre in t)."""
    if t1 == t2:
        return 0.0
    half = 0.5 * (t2 - t1)
    mid = 0.5 * (t2 + t1)
    acc = 0.0
    for k in range(gx.shape[0]):
        t = mid + half * gx[k]
        c = math.cos(t)
        s = math.sin(t)
        qx = Q0[0] + c * QA[0] + s * QB[0]
        qy = Q0[1] + c * QA[1] + s * QB[1]
        qz = Q0[2] + c * QA[2] + s * QB[2]
        dx = -s * QA[0] + c * QB[0]
        dy = -s * QA[1] + c * QB[1]
        dz = -s * QA[2] + c * QB[2]
        qe = qx * e[0] + qy * e[1] + qz * e[2]
        qn = qx * n[0] + qy * n[1] + qz * n[2]
        de = dx * e[0] + dy * e[1] + dz * e[2]
        dn = dx * n[0] + dy * n[1] + dz * n[2]
        nq = math.sqrt(qx * qx + qy * qy + qz * qz)
        sin_el = (qx * u[0] + qy * u[1] + qz * u[2]) / nq
        daz = (qn * de - qe * dn) / (qe * qe + qn * qn)
        acc += gw[k] * sin_el * daz
    return acc * half


@njit(cache=True)
def _sin_lin_integral(H1, H2, A1, A2):
    """Integral of sin(H) over azimuth [A1, A2] (rad) with H linear from H1 to H2.

    (cos H1 - cos H2)/k with k = (H2 - H1)/(A2 - A1), written without cancellation:
    cos H1 - cos H2 = 2 sin(Hm) sin(dH/2), so the integral is sin(Hm) (A2 - A1) sinc(dH/2)."""
    if A2 == A1:
        return 0.0
    x = 0.5 * (H2 - H1)
    sinc = 1.0 - x * x / 6.0 if abs(x) < 1e-4 else math.sin(x) / x
    return math.sin(0.5 * (H1 + H2)) * (A2 - A1) * sinc


@njit(cache=True)
def _arc_interval(t_start, t_end, t_through):
    """Unwrapped [lo, hi] from t_start to t_end that contains t_through (the arc's apex)."""
    lo = t_start
    for k in (-1, 0, 1):
        hi = t_end + k * TWO_PI
        if hi <= lo or hi - lo >= TWO_PI:
            continue
        m = t_through
        while m < lo:
            m += TWO_PI
        while m > lo + TWO_PI:
            m -= TWO_PI
        if lo <= m <= hi:
            return lo, hi
    # apex not between start and end going forward: the arc runs the other way
    hi = t_start
    lo = t_end
    while lo > hi:
        lo -= TWO_PI
    while lo <= hi - TWO_PI:
        lo += TWO_PI
    return lo, hi


@njit(cache=True)
def _into(t, lo, hi):
    """Map t into [lo, hi] modulo 2 pi (nearest representative when slightly outside)."""
    best = t
    bd = 1e300
    for k in range(-2, 3):
        c = t + k * TWO_PI
        d = 0.0 if lo <= c <= hi else min(abs(c - lo), abs(c - hi))
        if d < bd:
            bd = d
            best = c
    return best


@njit(cache=True)
def _arc_t(A, a_lo, a_hi, lo, hi, t_lo_end, t_hi_end, az_c, Q0, QA, QB, e, n):
    """Limb parameter at azimuth az_c + A (A relative) on the arc [lo, hi]; exact ends at the extremes."""
    if A <= a_lo:
        return _into(t_lo_end, lo, hi)
    if A >= a_hi:
        return _into(t_hi_end, lo, hi)
    ts, cnt = _t_at_az(az_c + A, Q0, QA, QB, e, n)
    best = math.nan
    bd = 1e300
    for j in range(cnt):
        c = _into(ts[j], lo, hi)
        d = 0.0 if lo <= c <= hi else min(abs(c - lo), abs(c - hi))
        if d < bd:
            bd = d
            best = c
    return best


@njit(cache=True)
def earth_disk_kernel(Q0, QA, QB, u, e, n, az_c, el_c, h, inc, binw, want_f, nbr, tol, maxit, prune=True):
    """Exact full-ellipse disk quantities. Returns (g_top, g_bot, f, inc_span, h_max, h_min, fallbacks)
    in radians (clearances) and as a fraction (f; NaN when not requested)."""
    fb = 0
    nb = h.shape[0]
    # azimuth extent of the limb
    t_amax, a_hi, f1 = _global_extremum(2, 1.0, Q0, QA, QB, u, e, n, u, az_c, h, binw, nbr, tol, maxit)
    t_amin, a_lo, f2 = _global_extremum(2, -1.0, Q0, QA, QB, u, e, n, u, az_c, h, binw, nbr, tol, maxit)
    fb += f1 + f2
    # horizon nodes inside the extent; span statistics
    k0 = int(math.floor(math.degrees(az_c + a_lo) / binw))
    k1 = int(math.ceil(math.degrees(az_c + a_hi) / binw))
    hmax = -1e300
    hmin = 1e300
    incs = False
    for k in range(k0, k1 + 1):
        v = h[k % nb]
        hmax = max(hmax, v)
        hmin = min(hmin, v)
        if inc[k % nb]:
            incs = True
    # breakpoints in t: node crossings plus the azimuth extremes
    bps = [t_amin, t_amax]
    for k in range(k0 + 1, k1):
        A = math.radians(k * binw)
        ts, cnt = _t_at_az(A, Q0, QA, QB, e, n)
        for j in range(cnt):
            bps.append(ts[j])
    bp = np.sort(np.array(bps))
    m = bp.shape[0]
    # Pass 1: 4 sub-samples per piece (bracketing each piece's max and min) and, for f, the horizon crossings.
    p_ta = np.empty(m)
    p_tb = np.empty(m)
    p_hi = np.full(m, -1e300)
    p_lo = np.full(m, 1e300)
    p_jh = np.zeros(m, dtype=np.int64)
    p_jl = np.zeros(m, dtype=np.int64)
    p_ok = np.zeros(m, dtype=np.bool_)
    roots = []
    for i in range(m):
        ta = bp[i]
        tb = bp[i + 1] if i + 1 < m else bp[0] + TWO_PI
        p_ta[i] = ta
        p_tb[i] = tb
        if tb - ta < 1e-15:
            continue
        p_ok[i] = True
        vals = np.empty(5)
        for j in range(5):
            tt = ta + (tb - ta) * j / 4.0
            vals[j] = _obj(3, tt, Q0, QA, QB, u, e, n, u, az_c, h, binw)
            if vals[j] > p_hi[i]:
                p_hi[i] = vals[j]
                p_jh[i] = j
            if vals[j] < p_lo[i]:
                p_lo[i] = vals[j]
                p_jl[i] = j
            if j > 0 and (vals[j - 1] < 0.0) != (vals[j] < 0.0):
                t0 = ta + (tb - ta) * (j - 1) / 4.0
                roots.append(_zeroin(t0, tt, vals[j - 1], vals[j], Q0, QA, QB, u, e, n, az_c, h, binw) % TWO_PI)
    # Pass 2: Brent refinement, only where it can change the result (Phase 3 item 8). The clearance is
    # L-Lipschitz along the limb, L = omega (1 + S / c_min): omega bounds the limb's angular speed (q = Q0 + v,
    # |v| <= R = sqrt(|QA|^2 + |QB|^2), so |dq/dt| / |q| <= R / (|Q0| - R)), S the horizon slopes over the span and
    # c_min the cosine of the largest |el| on the limb (within asin(R / |Q0|) of Q0's direction). A piece's maximum
    # is then at most its best sample + L h / 2 (h the sample spacing); a piece whose bound is below a value
    # already reached cannot hold the maximum, and since max() does not depend on order the result is bitwise
    # the same as refining every piece. Likewise for the minimum.
    nq0 = math.sqrt(Q0[0] * Q0[0] + Q0[1] * Q0[1] + Q0[2] * Q0[2])
    R = math.sqrt(QA[0] * QA[0] + QA[1] * QA[1] + QA[2] * QA[2] + QB[0] * QB[0] + QB[1] * QB[1] + QB[2] * QB[2])
    L = math.inf
    if R < 0.5 * nq0:
        el0 = math.asin(min(1.0, max(-1.0, (Q0[0] * u[0] + Q0[1] * u[1] + Q0[2] * u[2]) / nq0)))
        ang = abs(el0) + math.asin(R / nq0)
        c_min = math.cos(ang) if ang < 0.5 * math.pi else 0.0
        S = 0.0
        for k in range(k0, k1 + 1):
            S = max(S, abs(h[(k + 1) % nb] - h[k % nb]) / binw)
        if c_min > 1e-6 and prune:
            L = 1.01 * (R / (nq0 - R)) * (1.0 + S / c_min)
    g_top = -1e300
    g_bot = 1e300
    for i in range(m):
        if p_ok[i]:
            g_top = max(g_top, p_hi[i])
            g_bot = min(g_bot, p_lo[i])
    order = np.argsort(-p_hi)
    for ii in range(m):
        i = order[ii]
        if not p_ok[i]:
            continue
        ta = p_ta[i]
        tb = p_tb[i]
        if p_hi[i] + L * 0.125 * (tb - ta) < g_top:
            continue
        jh = p_jh[i]
        lo = ta + (tb - ta) * max(jh - 1, 0) / 4.0
        hi = ta + (tb - ta) * min(jh + 1, 4) / 4.0
        _, vmax = _brent_max(3, 1.0, lo, hi, Q0, QA, QB, u, e, n, u, az_c, h, binw, tol, maxit)
        g_top = max(g_top, vmax)
    order = np.argsort(p_lo)
    for ii in range(m):
        i = order[ii]
        if not p_ok[i]:
            continue
        ta = p_ta[i]
        tb = p_tb[i]
        if p_lo[i] - L * 0.125 * (tb - ta) > g_bot:
            continue
        jl = p_jl[i]
        lo = ta + (tb - ta) * max(jl - 1, 0) / 4.0
        hi = ta + (tb - ta) * min(jl + 1, 4) / 4.0
        _, vmin = _brent_max(3, -1.0, lo, hi, Q0, QA, QB, u, e, n, u, az_c, h, binw, tol, maxit)
        g_bot = min(g_bot, vmin)
    f = math.nan
    if want_f:
        el_top_v = -1e300
        el_bot_v = 1e300
        # quick verdicts from the clearance extremes
        if g_bot > 0.0:
            f = 1.0
        elif g_top <= 0.0:
            f = 0.0
        else:
            # azimuth breakpoints (relative to az_c): nodes, limb/horizon crossings, the extremes
            azs = [a_lo, a_hi]
            for k in range(k0 + 1, k1):
                azs.append(_wrap(math.radians(k * binw) - az_c))
            for tr in roots:
                _, azr = _elaz(tr, Q0, QA, QB, u, e, n)
                azs.append(_wrap(azr - az_c))
            ab = np.sort(np.array(azs))
            # the two arcs between the azimuth extremes, as unwrapped parameter intervals through their apexes
            t_top, _, f3 = _global_extremum(0, 1.0, Q0, QA, QB, u, e, n, u, az_c, h, binw, nbr, tol, maxit)
            t_bot, _, f4 = _global_extremum(0, -1.0, Q0, QA, QB, u, e, n, u, az_c, h, binw, nbr, tol, maxit)
            fb += f3 + f4
            ulo, uhi = _arc_interval(t_amin, t_amax, t_top)
            llo, lhi = _arc_interval(t_amin, t_amax, t_bot)
            a_tot = 0.0
            a_vis = 0.0
            for i in range(ab.shape[0] - 1):
                A1 = ab[i]
                A2 = ab[i + 1]
                if A2 - A1 < 1e-15 or A1 < a_lo or A2 > a_hi:
                    continue
                Am = 0.5 * (A1 + A2)
                th1 = _arc_t(A1, a_lo, a_hi, ulo, uhi, t_amin, t_amax, az_c, Q0, QA, QB, e, n)
                th2 = _arc_t(A2, a_lo, a_hi, ulo, uhi, t_amin, t_amax, az_c, Q0, QA, QB, e, n)
                tl1 = _arc_t(A1, a_lo, a_hi, llo, lhi, t_amin, t_amax, az_c, Q0, QA, QB, e, n)
                tl2 = _arc_t(A2, a_lo, a_hi, llo, lhi, t_amin, t_amax, az_c, Q0, QA, QB, e, n)
                i_hi = _arc_integral(th1, th2, Q0, QA, QB, u, e, n, _GL_X, _GL_W)
                i_lo = _arc_integral(tl1, tl2, Q0, QA, QB, u, e, n, _GL_X, _GL_W)
                a_tot += i_hi - i_lo
                thm = _arc_t(Am, a_lo, a_hi, ulo, uhi, t_amin, t_amax, az_c, Q0, QA, QB, e, n)
                tlm = _arc_t(Am, a_lo, a_hi, llo, lhi, t_amin, t_amax, az_c, Q0, QA, QB, e, n)
                el_hi_m, _ = _elaz(thm, Q0, QA, QB, u, e, n)
                el_lo_m, _ = _elaz(tlm, Q0, QA, QB, u, e, n)
                Hm = _H(az_c + Am, h, binw)
                if Hm <= el_lo_m:
                    a_vis += i_hi - i_lo
                elif Hm < el_hi_m:
                    a_vis += i_hi - _sin_lin_integral(_H(az_c + A1, h, binw), _H(az_c + A2, h, binw), A1, A2)
            f = min(1.0, max(0.0, a_vis / a_tot)) if a_tot > 0.0 else math.nan
    return g_top, g_bot, f, incs, math.radians(hmax), math.radians(hmin), fb


# ------------------------------------------------------------------ limb extrema and deviation
@njit(cache=True)
def limb_extrema(Q0, QA, QB, u, e, n, el_c, az_c, nbr, tol, maxit):
    """(rho_up, rho_down, delta_max, fallbacks), radians. rho_up = el_top - el_c, rho_down = el_c - el_bot;
    delta_max = max over the whole limb of |angle from the offset cap centre - rho_cap|."""
    dummy = np.zeros(1)
    _, el_top, f1 = _global_extremum(0, 1.0, Q0, QA, QB, u, e, n, u, az_c, dummy, 1.0, nbr, tol, maxit)
    _, el_bot, f2 = _global_extremum(0, -1.0, Q0, QA, QB, u, e, n, u, az_c, dummy, 1.0, nbr, tol, maxit)
    rho_up = el_top - el_c
    rho_down = el_c - el_bot
    off = 0.5 * (rho_up - rho_down)
    rho_cap = 0.5 * (rho_up + rho_down)
    elo = el_c + off
    ce = math.cos(elo)
    o = np.empty(3)
    for k in range(3):
        o[k] = ce * math.sin(az_c) * e[k] + ce * math.cos(az_c) * n[k] + math.sin(elo) * u[k]
    _, dmax, f3 = _global_extremum(1, 1.0, Q0, QA, QB, u, e, n, o, az_c, dummy, 1.0, nbr, tol, maxit)
    _, dmin, f4 = _global_extremum(1, -1.0, Q0, QA, QB, u, e, n, o, az_c, dummy, 1.0, nbr, tol, maxit)
    return rho_up, rho_down, max(dmax - rho_cap, rho_cap - dmin), f1 + f2 + f3 + f4


def cap_limb(az_deg: float, el_deg: float, rho: float, e, n, u):
    """(Q0, QA, QB) of the exact circular cone of half-angle rho (rad) about the direction (az, el): unit
    vectors q(t) = cos rho o + sin rho (cos t p1 + sin t p2), so the disk kernel evaluates the cap exactly."""
    a, el = math.radians(az_deg), math.radians(el_deg)
    o = math.cos(el) * (math.sin(a) * e + math.cos(a) * n) + math.sin(el) * u
    p1 = math.cos(a) * e - math.sin(a) * n                    # horizontal, perpendicular to o
    p2 = np.cross(o, p1)
    return math.cos(rho) * o, math.sin(rho) * p1, math.sin(rho) * p2


def cap_area_bound(rho: float, delta: float) -> float:
    """E_f = (dA+ + dA-)/(A_C - dA-): exact spherical bound on |f_ellipse - f_cap| (dimensionless)."""
    dap = 4.0 * math.pi * math.sin(rho + 0.5 * delta) * math.sin(0.5 * delta)
    dam = 4.0 * math.pi * math.sin(max(rho - 0.5 * delta, 0.0)) * math.sin(0.5 * delta)
    a_c = 4.0 * math.pi * math.sin(0.5 * rho) ** 2
    return (dap + dam) / (a_c - dam) if a_c > dam else math.inf


def pole_area_bound(alpha: float, beta: float, eta: float) -> float:
    """E_f,pole = (dA+ + dA-)/(4 pi sin^2(beta/2) - dA-) for limbs differing radially by at most eta."""
    dap = 4.0 * math.pi * math.sin(alpha + 0.5 * eta) * math.sin(0.5 * eta)
    dam = 4.0 * math.pi * math.sin(max(alpha - 0.5 * eta, 0.0)) * math.sin(0.5 * eta)
    a_min = 4.0 * math.pi * math.sin(0.5 * beta) ** 2
    return (dap + dam) / (a_min - dam) if a_min > dam else math.inf


def edge_bound(delta: float, slope: float, c_min: float) -> float:
    """E_g = delta (1 + S/c_min): bound on edge-clearance change when every limb point moves <= delta."""
    return delta * (1.0 + slope / max(c_min, 1e-12))


def intrinsic_radii(d_km) -> tuple[np.ndarray, np.ndarray]:
    """alpha = asin(a/d), beta = asin(b/d) (radians): intrinsic equatorial and polar angular radii."""
    a, _, b = settings.EARTH_RADII_KM
    d = np.asarray(d_km, dtype=float)
    return np.arcsin(a / d), np.arcsin(b / d)


def psi_rate(rh, drh, pole, pole_dot, u) -> np.ndarray:
    """d psi / dt (rad/s): rotation of Earth's projected pole relative to the local vertical in the sky.
    psi = atan2(Y, X), X = u.p - (u.r)(p.r), Y = (u x p).r, with r the unit direction to Earth."""
    ur = rh @ u
    up = pole @ u
    pr = np.sum(pole * rh, 1)
    X = up - ur * pr
    uxp = cross3(u, pole)
    Y = np.sum(uxp * rh, 1)
    Xd = pole_dot @ u - (drh @ u) * pr - ur * (np.sum(pole_dot * rh, 1) + np.sum(pole * drh, 1))
    Yd = np.sum(cross3(u, pole_dot) * rh, 1) + np.sum(uxp * drh, 1)
    return (X * Yd - Y * Xd) / np.maximum(X * X + Y * Y, 1e-300)


def lambda_rate_bound(drh, pole_dot) -> np.ndarray:
    """Bound (rad/s) on the rate of the angle between Earth's pole and the line of sight: |d rh/dt| + |dp/dt|."""
    return np.linalg.norm(np.atleast_2d(drh), axis=1) + np.linalg.norm(np.atleast_2d(pole_dot), axis=1)


def limb_speed_bound(d_km, d_dot, psi_dot, lam_dot=0.0) -> np.ndarray:
    """V_limb (rad/s): largest sky-plane speed of any limb point relative to the centre, bounded by
    (a) the radial growth from the distance change, |d alpha/dt| = a|d'|/(d sqrt(d^2 - a^2));
    (b) the shape change, (alpha - beta)(|psi'| + |lambda'|): the projected flattening rotates with the
        position angle psi of the pole and changes with its tilt lambda to the line of sight (both enter
        the radial function with a Lipschitz constant <= alpha - beta);
    (c) the rigid rotation of the limb with the local vertical, alpha |psi'|."""
    a = settings.EARTH_RADII_KM[0]
    d = np.asarray(d_km, dtype=float)
    alpha, beta = intrinsic_radii(d)
    radial = a * np.abs(d_dot) / (d * np.sqrt(d * d - a * a))
    return radial + (alpha - beta) * (np.abs(psi_dot) + np.abs(lam_dot)) + alpha * np.abs(psi_dot)


def clearance_rate_bound(el_rate_deg, az_rate_deg, slope, c_min, v_limb_rad, alpha_rad, map_term_deg) -> float:
    """B (deg/s) on |d g_top/dt| and |d g_bot/dt|: centre elevation rate, horizon movement under the centre's
    azimuth motion, limb motion relative to the centre, change of the 1/cos el azimuth scaling, map term;
    times the curvature inflation."""
    v = math.degrees(v_limb_rad)
    # (iv) d(1/cos el_p)/dt for the limb point itself, whose elevation rate is at most |el_rate| + V_limb
    term_iv = (slope * alpha_rad * math.sqrt(max(0.0, 1.0 - c_min * c_min)) / max(c_min, 1e-12) ** 2
               * (abs(el_rate_deg) + v))
    total = (abs(el_rate_deg) + slope * abs(az_rate_deg) + (1.0 + slope / max(c_min, 1e-12)) * v + term_iv
             + map_term_deg)
    return settings.CURVATURE_INFLATION * total


def earth_disk_state(hp, geo: dict, want_f: bool = True, force: str | None = None) -> dict:
    """Disk quantities (degrees, like visibility.disk_state) for Earth from its exact limb.

    geo: one sample's Earth geometry from ephem (az, el in deg; Q0, QA, QB; rho_up, rho_down, delta_max in
    rad; e, n, u basis). force: None (decide), "ellipse" or "cap" (tests)."""
    from .visibility import SPHERICAL_EL_DEG, disk_state
    az, el = float(geo["az"]), float(geo["el"])
    c = el - float(hp.at(az))
    ru, rd, dm = geo["rho_up"], geo["rho_down"], geo["delta_max"]
    rho_cap = 0.5 * (ru + rd)
    alpha_deg = math.degrees(geo["alpha"])
    c_min = max(math.cos(max(abs(math.radians(el) + ru), abs(math.radians(el) - rd))), 1e-12)
    hw = min(alpha_deg / c_min, 180.0)
    idx = hp.span_nodes(az - hw, az + hw)
    slope = float(np.max(hp.abs_dh[idx % hp.n]) / hp.bin) if idx.size else 0.0
    e_g = edge_bound(dm, slope, c_min)
    e_f = cap_area_bound(rho_cap, dm)
    extra = {"delta_max_deg": math.degrees(dm), "E_g_deg": math.degrees(e_g), "E_f": e_f, "c_min": c_min,
             "slope_span": slope}
    if el + alpha_deg >= SPHERICAL_EL_DEG:
        # never at south polar sites; the cap of radius alpha about the centre contains the whole limb
        st = disk_state(hp, az, el, alpha_deg)
        return {**st, "method": "spherical (cap of radius alpha above 60 deg)", **extra}
    use_cap = (force == "cap") or (force is None and math.degrees(dm) <= settings.EARTH_LIMB_TOL_DEG
                                   and math.degrees(e_g) <= settings.EARTH_LIMB_TOL_DEG
                                   and e_f < settings.EARTH_F_TOL)
    # Both paths use the same exact disk kernel; the cap path replaces the limb by the exact circular cone
    # (radius rho_cap about the offset centre). visibility._disk_exact is not used for Earth: it carries a
    # numerical f error of up to ~1e-4 on some steep horizons (AUDIT, Phase 3 item 1), larger than EARTH_F_TOL.
    if use_cap:
        off = math.degrees(0.5 * (ru - rd))
        Q0, QA, QB = cap_limb(az, el + off, rho_cap, geo["e"], geo["n"], geo["u"])
        method = "cap"
    else:
        Q0, QA, QB = geo["Q0"], geo["QA"], geo["QB"]
        method = "elliptical"
    sv = settings.EARTH_SOLVER
    gt, gb, f, inc_span, hmx, hmn, fbk = earth_disk_kernel(
        Q0, QA, QB, geo["u"], geo["e"], geo["n"], math.radians(az), math.radians(el),
        hp.h, hp.inc, hp.bin, want_f, sv["bracket"], sv["tol"], sv["maxiter"])
    g_top, g_bot = math.degrees(gt), math.degrees(gb)
    hmax, hmin = math.degrees(hmx), math.degrees(hmn)
    el_top = el + math.degrees(ru)
    el_bot = el - math.degrees(rd)
    quick = (el_bot > hmax) or (el_top < hmin)
    if el_top < hmin:
        f = 0.0
    # some part visible  <=>  f > 0  <=>  g_top > 0; over incomplete (lower-bound) bins that becomes unknown
    unknown = bool(inc_span) and g_top > 0.0
    return {"f": float("nan") if (unknown or not want_f) else float(f), "c": c, "g_top": float(g_top),
            "g_bot": float(g_bot), "unknown": unknown, "quick": quick, "method": method, **extra}
