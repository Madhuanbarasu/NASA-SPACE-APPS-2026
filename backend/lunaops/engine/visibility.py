"""Disk visibility (blueprint Section 8.5; tests V-08, V-13).

Each disk is the spherical cap of angular radius rho around its apparent
direction. Up to 60 deg elevation the cap is solved in closed form against the
horizon (piecewise linear in azimuth and elevation): visible solid-angle
fraction f and the true elevation clearances of its top and bottom edges. Above
60 deg (and for a cap containing the zenith) the cap is integrated on
area-weighted sample points. Incomplete bins are lower bounds: a 'hidden'
verdict resting on them stays valid, any other result touching them is
reported as unknown (NaN).
"""
from __future__ import annotations

import math

import numpy as np
from numba import njit

from .earth import _elaz, _t_at_az
from .frames import cross3

RULES = ("any", "centre", "full")


# ------------------------------------------------------------------ exact spherical disk
# The disk is the spherical cap of angular radius r around (A, E). In azimuth-elevation
# coordinates, with x = Az - A (radians), the cap occupies |x| <= hw = asin(sin r / cos E) and,
# for each x, the elevation range [lo(x), hi(x)] with
#     hi, lo = phi(x) +/- d(x),  phi = atan2(sin E, cos E cos x),  d = atan2(sqrt(K^2 - cos^2 r), cos r),
#     K^2 = cos^2 E cos^2 x + sin^2 E.
# hi is concave and lo convex on the band (verified numerically for -5..60 deg, r up to 1.05 deg).
# The horizon is piecewise linear in (Az, El), so on each node interval H(x) = k x + c and the
# visible solid angle  integral (sin hi - sin max(lo, min(H, hi))) dx  has closed forms:
#     int sin(hi) dx = cos r atan(sin E tan x) + [asin(v / sin r) - cos r atan2(cos r v, sqrt(sin^2 r - v^2))],
#     int sin(lo) dx = cos r atan(sin E tan x) - [ ... ],          v = cos E sin x,
# whose band total is the cap area 2 pi (1 - cos r). Edge clearances are true elevation
# differences el_p - H(az_p), the same definition as the spherical branch.

@njit(cache=True)
def _hilo(x, P, Q, cr):
    cx = math.cos(x)
    s = P * P * cx * cx + Q * Q - cr * cr
    if s < 0.0:
        s = 0.0
    phi = math.atan2(Q, P * cx)
    d = math.atan2(math.sqrt(s), cr)
    return phi - d, phi + d


@njit(cache=True)
def _F(x, P, Q, cr, sr, sign):
    """Antiderivative of sin(hi) (sign +1) or sin(lo) (sign -1) in x.

    The second term asin(q) - cr atan2(cr v, sqrt(sr^2 - v^2)), q = v / sr, is evaluated as
    G(theta) = theta - cr atan2(cr sin theta, cos theta) with theta = asin(q). At the cap's azimuth extremes
    q -> +-1, where asin is ill-conditioned (a rounding error of 1e-16 in q moves it by ~1e-8); G is flat
    there (dG/dtheta = 0 at theta = +-pi/2), so the area no longer inherits that error. The former form took
    the square root of sr^2 - v^2 separately, the two terms rounded inconsistently and visible fractions
    of partly hidden disks could be off by up to ~1e-4 (Phase 3 item 4, test_phase3_joint)."""
    v = P * math.sin(x)
    q = v / sr
    if q > 1.0:
        q = 1.0
    if q < -1.0:
        q = -1.0
    th = math.asin(q)
    return cr * math.atan(Q * math.tan(x)) + sign * (th - cr * math.atan2(cr * math.sin(th), math.cos(th)))


@njit(cache=True)
def _sin_lin_int(k, c, a, b):
    """Integral of sin(k x + c) from a to b, stable for k -> 0."""
    half = 0.5 * (b - a)
    z = k * half
    sinc = 1.0 - z * z / 6.0 if abs(z) < 1e-4 else math.sin(z) / z
    return 2.0 * half * math.sin(k * 0.5 * (a + b) + c) * sinc


@njit(cache=True)
def _fval(mode, x, k, c, P, Q, cr):
    """mode 0: hi'(x) - k   1: lo'(x) - k   2: hi(x) - (k x + c)   3: lo(x) - (k x + c)."""
    sx = math.sin(x)
    cx = math.cos(x)
    K2 = P * P * cx * cx + Q * Q
    s = K2 - cr * cr
    if s < 1e-30:
        s = 1e-30
    if mode < 2:
        a = Q * P * sx / K2
        b = cr * P * P * sx * cx / (K2 * math.sqrt(s))
        return (a - b - k) if mode == 0 else (a + b - k)
    phi = math.atan2(Q, P * cx)
    d = math.atan2(math.sqrt(s), cr)
    return (phi + d if mode == 2 else phi - d) - (k * x + c)


@njit(cache=True)
def _zeroin(mode, a, b, fa, fb, k, c, P, Q, cr):
    """Brent's root finder for _fval(mode) on [a, b] with fa, fb of opposite sign (tolerance ~1e-13 rad)."""
    cc = a
    fc = fa
    d = b - a
    e = d
    for _ in range(100):
        if (fb > 0.0) == (fc > 0.0):
            cc = a
            fc = fa
            d = b - a
            e = d
        if abs(fc) < abs(fb):
            a = b
            b = cc
            cc = a
            fa = fb
            fb = fc
            fc = fa
        tol = 4.4e-16 * abs(b) + 5e-14
        m = 0.5 * (cc - b)
        if abs(m) <= tol or fb == 0.0:
            return b
        if abs(e) >= tol and abs(fa) > abs(fb):
            s_ = fb / fa
            if a == cc:
                pp = 2.0 * m * s_
                qq = 1.0 - s_
            else:
                q_ = fa / fc
                r_ = fb / fc
                pp = s_ * (2.0 * m * q_ * (q_ - r_) - (b - a) * (r_ - 1.0))
                qq = (q_ - 1.0) * (r_ - 1.0) * (s_ - 1.0)
            if pp > 0.0:
                qq = -qq
            else:
                pp = -pp
            if 2.0 * pp < min(3.0 * m * qq - abs(tol * qq), abs(e * qq)):
                e = d
                d = pp / qq
            else:
                d = m
                e = m
        else:
            d = m
            e = m
        a = b
        fa = fb
        if abs(d) > tol:
            b += d
        else:
            b += tol if m > 0 else -tol
        fb = _fval(mode, b, k, c, P, Q, cr)
    return b


@njit(cache=True)
def _extremum(a, b, k, c, P, Q, cr, top):
    """Max of hi(x) - (k x + c) (top; concave) or min of lo(x) - (k x + c) (convex) on [a, b].

    The extremum is where the derivative crosses zero (hi' - k decreasing, lo' - k increasing),
    found by Brent's method; otherwise it is the end point the derivative points to."""
    mode = 0 if top else 1
    da = _fval(mode, a, k, c, P, Q, cr)
    db = _fval(mode, b, k, c, P, Q, cr)
    if top:
        if da <= 0.0:
            x = a
        elif db >= 0.0:
            x = b
        else:
            x = _zeroin(mode, a, b, da, db, k, c, P, Q, cr)
    else:
        if da >= 0.0:
            x = a
        elif db <= 0.0:
            x = b
        else:
            x = _zeroin(mode, a, b, da, db, k, c, P, Q, cr)
    return x, _fval(2 if top else 3, x, k, c, P, Q, cr)


@njit(cache=True)
def _root(a, b, k, c, P, Q, cr, top):
    """Sign change of hi(x) - H(x) (top) or lo(x) - H(x) between a and b."""
    mode = 2 if top else 3
    fa = _fval(mode, a, k, c, P, Q, cr)
    fb = _fval(mode, b, k, c, P, Q, cr)
    if fa == 0.0:
        return a
    if fb == 0.0 or (fa > 0.0) == (fb > 0.0):
        return b
    return _zeroin(mode, a, b, fa, fb, k, c, P, Q, cr)


@njit(cache=True)
def _disk_exact(h, inc, binw, az, el, rho):
    """Exact spherical-cap disk quantities for a horizon piecewise linear in (Az, El).

    Returns (f, g_top, g_bot, hmax_span, hmin_span, inc_span); clearances in degrees. Valid while
    the cap does not contain the zenith (el + rho < 90); disk_state uses it up to SPHERICAL_EL_DEG.
    """
    n = h.shape[0]
    E = math.radians(el)
    r = math.radians(rho)
    P = math.cos(E)
    Q = math.sin(E)
    cr = math.cos(r)
    sr = math.sin(r)
    s_hw = sr / max(P, 1e-12)
    hw = math.asin(s_hw) if s_hw < 1.0 else 0.5 * math.pi
    hw_deg = math.degrees(hw)
    i0 = int(math.floor((az - hw_deg) / binw))
    i1 = int(math.ceil((az + hw_deg) / binw))
    g_top = -1e300
    g_bot = 1e300
    area = 0.0
    hmax = -1e300
    hmin = 1e300
    inc_any = False
    for i in range(i0, i1 + 1):
        v = h[i % n]
        if v > hmax:
            hmax = v
        if v < hmin:
            hmin = v
        if inc[i % n]:
            inc_any = True
    for i in range(i0, i1):
        xa0 = math.radians(i * binw - az)
        xb0 = math.radians((i + 1) * binw - az)
        ya = math.radians(h[i % n])
        yb = math.radians(h[(i + 1) % n])
        k = (yb - ya) / (xb0 - xa0)
        c = ya - k * xa0                      # H(x) = k x + c, radians
        xa = max(xa0, -hw)
        xb = min(xb0, hw)
        if xb <= xa:
            continue
        xt, gt = _extremum(xa, xb, k, c, P, Q, cr, True)
        xbm, gb = _extremum(xa, xb, k, c, P, Q, cr, False)
        if gt > g_top:
            g_top = gt
        if gb < g_bot:
            g_bot = gb
        # split points where the horizon line meets the cap boundary
        pts = [xa, xb]
        if gt > 0.0:                          # hi - H is concave: up to one crossing each side of xt
            la, ha = _hilo(xa, P, Q, cr)
            if ha - (k * xa + c) < 0.0 and xt > xa:
                pts.append(_root(xa, xt, k, c, P, Q, cr, True))
            lb, hb = _hilo(xb, P, Q, cr)
            if hb - (k * xb + c) < 0.0 and xb > xt:
                pts.append(_root(xt, xb, k, c, P, Q, cr, True))
        if gb < 0.0:                          # lo - H is convex: up to one crossing each side of xbm
            la, ha = _hilo(xa, P, Q, cr)
            if la - (k * xa + c) > 0.0 and xbm > xa:
                pts.append(_root(xa, xbm, k, c, P, Q, cr, False))
            lb, hb = _hilo(xb, P, Q, cr)
            if lb - (k * xb + c) > 0.0 and xb > xbm:
                pts.append(_root(xbm, xb, k, c, P, Q, cr, False))
        pts.sort()
        for j in range(len(pts) - 1):
            a = pts[j]
            b = pts[j + 1]
            if b <= a:
                continue
            xm = 0.5 * (a + b)
            lm, hm = _hilo(xm, P, Q, cr)
            Hm = k * xm + c
            if Hm >= hm:
                continue                       # horizon above the disk here
            top_int = _F(b, P, Q, cr, sr, 1.0) - _F(a, P, Q, cr, sr, 1.0)
            if Hm <= lm:
                area += top_int - (_F(b, P, Q, cr, sr, -1.0) - _F(a, P, Q, cr, sr, -1.0))
            else:
                area += top_int - _sin_lin_int(k, c, a, b)
    f = area / (2.0 * math.pi * (1.0 - cr))
    if f < 0.0:
        f = 0.0
    if f > 1.0:
        f = 1.0
    return f, math.degrees(g_top), math.degrees(g_bot), hmax, hmin, inc_any


class HorizonProfile:
    """Periodic piecewise-linear horizon H(alpha) with incomplete-bin flags."""

    def __init__(self, h_deg: np.ndarray, incomplete: np.ndarray, sigma_deg: np.ndarray | None = None,
                 flags: dict | None = None):
        self.h = np.asarray(h_deg, dtype=float)
        self.inc = np.asarray(incomplete, dtype=bool)
        self.sigma = None if sigma_deg is None else np.asarray(sigma_deg, dtype=float)
        # optional per-bin flags from the horizon (Phase 2): near_field, sigma_nonlinear, discrepancy_unknown
        flags = flags or {}
        self.near_field = self._bool(flags.get("near_field"))
        self.sigma_nonlinear = self._bool(flags.get("sigma_nonlinear"))
        self.discrepancy_unknown = self._bool(flags.get("discrepancy_unknown"))
        # Phase 3 item 7: sub-bin peak excess per bin (deg) and its unknown flag; None when not computed
        ex = flags.get("subbin_excess_deg")
        self.subbin_excess = None if ex is None else np.asarray(ex, dtype=float)
        self.subbin_unknown = self._bool(flags.get("subbin_unknown"))
        self.n = self.h.size
        self.bin = 360.0 / self.n
        self.hmax = float(self.h.max())
        self.hmin = float(self.h.min())
        self.abs_dh = np.abs(np.diff(np.append(self.h, self.h[0])))   # |H_k+1 - H_k| (deg), node to node

    def at(self, az):
        az = np.asarray(az, dtype=float) % 360.0
        f = az / self.bin
        i0 = np.floor(f).astype(int) % self.n
        i1 = (i0 + 1) % self.n
        t = f - np.floor(f)
        return self.h[i0] * (1 - t) + self.h[i1] * t

    def span_nodes(self, az_lo: float, az_hi: float) -> np.ndarray:
        """Indices of nodes within [az_lo, az_hi] (deg, may wrap) plus the bracketing nodes."""
        width = az_hi - az_lo
        if width >= 360.0:
            return np.arange(self.n)
        i0 = int(math.floor(az_lo / self.bin))
        i1 = int(math.ceil(az_hi / self.bin))
        return np.arange(i0, i1 + 1) % self.n

    def span_extremes(self, az: float, half_width: float) -> tuple[float, float, bool]:
        idx = self.span_nodes(az - half_width, az + half_width)
        return float(self.h[idx].max()), float(self.h[idx].min()), bool(self.inc[idx].any())

    def sigma_at(self, az: float) -> float:
        if self.sigma is None:
            return float("nan")
        i = int(round((az % 360.0) / self.bin)) % self.n
        return float(self.sigma[i])

    @staticmethod
    def _bool(a):
        return None if a is None else np.asarray(a, dtype=bool)

    def span_flags(self, az: float, half_width: float) -> dict:
        """Horizon uncertainty over the bins a disk of this azimuth half-width spans (its limiting edge).

        sigma_max: largest finite sigma over the span (NaN if none is known); near_field, nonlinear and
        discrepancy_unknown: whether any spanned bin carries that flag. subbin_excess_max: largest sub-bin peak
        excess over the spanned bins (NaN when not computed); subbin_unknown: any spanned bin's excess unknown
        (Phase 3 item 7; never used by the uncertainty flags)."""
        idx = self.span_nodes(az - half_width, az + half_width)
        sig = float("nan")
        if self.sigma is not None:
            s = self.sigma[idx]
            s = s[np.isfinite(s)]
            if s.size:
                sig = float(s.max())
        return {"sigma_max": sig,
                "near_field": bool(self.near_field is not None and self.near_field[idx].any()),
                "nonlinear": bool(self.sigma_nonlinear is not None and self.sigma_nonlinear[idx].any()),
                "discrepancy_unknown": bool(self.discrepancy_unknown is not None
                                            and self.discrepancy_unknown[idx].any()),
                "subbin_excess_max": (float("nan") if self.subbin_excess is None
                                      else float(np.max(self.subbin_excess[idx]))),
                "subbin_unknown": bool(self.subbin_unknown is not None and self.subbin_unknown[idx].any())}


def half_width_az(el_deg: float, rho_deg: float) -> float:
    """Exact azimuth half-width of a cap of radius rho centred at elevation el (360 if it holds a pole)."""
    if el_deg + rho_deg >= 90.0 or el_deg - rho_deg <= -90.0:
        return 360.0
    s = math.sin(math.radians(rho_deg)) / max(math.cos(math.radians(el_deg)), 1e-12)
    return 360.0 if s >= 1.0 else math.degrees(math.asin(s))


SPHERICAL_EL_DEG = 60.0   # above this elevation the disk is integrated on the sphere (exact geometry)


def enu_from_azel(az_deg, el_deg) -> np.ndarray:
    a, e = np.radians(az_deg), np.radians(el_deg)
    return np.stack([np.cos(e) * np.sin(a), np.cos(e) * np.cos(a), np.sin(e)], axis=-1)


def cap_points(az: float, el: float, rho: float, n_rings: int = 60, n_az: int = 96):
    """Area-weighted points covering a spherical cap of angular radius rho around (az, el).

    Returns (az_deg, el_deg, weights, enu_points, boundary_mask). Exact spherical geometry,
    valid at any elevation including a disk that contains the zenith.
    """
    c = enu_from_azel(az, el)
    A = math.radians(az)
    t1 = np.array([math.cos(A), -math.sin(A), 0.0])
    t2 = np.cross(c, t1)
    t2 /= np.linalg.norm(t2)
    r = math.radians(rho)
    edges = r * np.sqrt(np.arange(n_rings + 1) / n_rings)
    mids = 0.5 * (edges[:-1] + edges[1:])
    ring_area = 2 * np.pi * (np.cos(edges[:-1]) - np.cos(edges[1:]))
    phi = (np.arange(n_az) + 0.5) * 2 * np.pi / n_az
    R, P = np.meshgrid(np.append(mids, r), phi, indexing="ij")
    w = np.vstack([np.repeat((ring_area / n_az)[:, None], n_az, axis=1), np.zeros((1, n_az))])
    boundary = np.zeros_like(w, dtype=bool)
    boundary[-1, :] = True
    pts = (np.cos(R)[..., None] * c + np.sin(R)[..., None] *
           (np.cos(P)[..., None] * t1 + np.sin(P)[..., None] * t2)).reshape(-1, 3)
    el_p = np.degrees(np.arcsin(np.clip(pts[:, 2], -1, 1)))
    az_p = np.degrees(np.arctan2(pts[:, 0], pts[:, 1])) % 360.0
    return az_p, el_p, w.ravel(), pts, boundary.ravel()


def _disk_state_spherical(hp: "HorizonProfile", az: float, el: float, rho: float, c: float,
                          hmax_span: float, hmin_span: float, inc_span: bool) -> dict:
    az_p, el_p, w, _pts, _b = cap_points(az, el, rho)
    clear = el_p - hp.at(az_p)
    g_top, g_bot = float(clear.max()), float(clear.min())
    if el - rho > hmax_span:
        return {"f": float("nan") if inc_span else 1.0, "c": c, "g_top": g_top, "g_bot": g_bot,
                "unknown": bool(inc_span), "quick": True, "method": "spherical"}
    if el + rho < hmin_span:
        return {"f": 0.0, "c": c, "g_top": g_top, "g_bot": g_bot, "unknown": False, "quick": True,
                "method": "spherical"}
    f = float(np.sum(w * (clear > 0)) / np.sum(w))
    unknown = inc_span and f > 0.0
    return {"f": float("nan") if unknown else f, "c": c, "g_top": g_top, "g_bot": g_bot,
            "unknown": bool(unknown), "quick": False, "method": "spherical"}


def disk_state(hp: HorizonProfile, az: float, el: float, rho: float) -> dict:
    """Visible fraction f, centre clearance c, edge clearances g_top/g_bot for one disk.

    Below SPHERICAL_EL_DEG the spherical cap is solved in closed form against the piecewise-linear
    horizon (exact geometry, no flattening, no sampling); above it the cap is integrated on area-
    weighted sample points. Incomplete bins are lower bounds: a hidden verdict over them stands,
    anything visible becomes unknown.
    """
    c = el - float(hp.at(az))
    if el > SPHERICAL_EL_DEG or el + rho >= 90.0:
        hw = half_width_az(el, rho)
        hmax_span, hmin_span, inc_span = hp.span_extremes(az, hw)
        return _disk_state_spherical(hp, az, el, rho, c, hmax_span, hmin_span, inc_span)
    f, g_top, g_bot, hmax_span, hmin_span, inc_span = _disk_exact(hp.h, hp.inc, hp.bin, float(az), float(el), float(rho))
    quick = (el - rho > hmax_span) or (el + rho < hmin_span)
    if el + rho < hmin_span:
        f = 0.0
    elif el - rho > hmax_span:
        f = 1.0           # whole disk above every horizon node it spans: exactly visible (Phase 3 item 4)
    unknown = bool(inc_span) and f > 0.0
    return {"f": float("nan") if unknown else float(f), "c": c, "g_top": float(g_top), "g_bot": float(g_bot),
            "unknown": unknown, "quick": quick, "method": "sphere-exact"}


# ------------------------------------------------------------------ Sun-Earth joint visibility (Phase 3 item 4)
LENS_CONCENTRIC_RAD = 1e-15     # separations below this are treated as concentric
JOINT_TOL = 1e-5                # three-way (terrain + Earth) fraction: adaptive tolerance
OCC_TOL = 1e-9                  # Earth's share of the Sun (no terrain) against the exact limb ellipse
JOINT_STRIPS = (16, 512)        # first and largest Gauss-Legendre order per piece (doubling)
JOINT_METHOD_VERSION = ("joint/v1: exact Earth limb ellipse; spherical lens for circular caps (stable branches); "
                        "exact branches; adaptive sine-substituted azimuth strips")


def joint_settings() -> dict:
    """Every joint-visibility parameter that changes an output (hashed into result IDs)."""
    return {"version": JOINT_METHOD_VERSION, "concentric_rad": LENS_CONCENTRIC_RAD, "tol": JOINT_TOL,
            "occ_tol": OCC_TOL, "strips": list(JOINT_STRIPS)}


def cap_area(r: float) -> float:
    """Solid angle of a spherical cap of angular radius r (rad): 2 pi (1 - cos r) = 4 pi sin^2(r/2)."""
    return 4.0 * math.pi * math.sin(0.5 * r) ** 2


@njit(cache=True)
def spherical_cap_lens_area(r1: float, r2: float, d: float) -> float:
    """Solid angle of the intersection of two spherical caps (radii r1, r2, centre separation d; radians).

    Branches, in order: concentric (d <= 1e-15) and contained / internally tangent (d <= |r1 - r2|): the
    smaller cap; disjoint / externally tangent (d >= r1 + r2): 0; otherwise the lens
        A = 2 a1 (1 - cos r1) + 2 a2 (1 - cos r2) - 2 E
    (two sectors minus the kite of two triangles c1-c2-vertex; Gauss-Bonnet), where a1, a2 are the
    triangle's angles at the centres and E its spherical excess. Every quantity is cancellation-free:
    1 - cos r = 2 sin^2(r/2); the angles are atan2(sqrt(D), N) with the Gram determinant
    D = 4 sin s sin(s-r1) sin(s-r2) sin(s-d) (s the half perimeter) and the numerators N in half-angle
    form; E from L'Huilier's formula. No acos, so no out-of-range arguments at tangency. The radii are put
    in a fixed order first, so A(r1, r2, d) = A(r2, r1, d) exactly."""
    if r1 > r2:
        r1, r2 = r2, r1
    if d <= LENS_CONCENTRIC_RAD or d <= abs(r1 - r2):
        r = min(r1, r2)
        return 4.0 * math.pi * math.sin(0.5 * r) ** 2
    if d >= r1 + r2:
        return 0.0
    h1 = math.sin(0.5 * r1) ** 2
    h2 = math.sin(0.5 * r2) ** 2
    hd = math.sin(0.5 * d) ** 2
    s = 0.5 * (r1 + r2 + d)
    D = 4.0 * math.sin(s) * max(math.sin(s - r1), 0.0) * max(math.sin(s - r2), 0.0) * max(math.sin(s - d), 0.0)
    sq = math.sqrt(max(D, 0.0))
    # cos r2 - cos d cos r1 = 2 hd (1 - 2 h1) + 2 (h1 - h2), with h1 - h2 = sin((r1-r2)/2) sin((r1+r2)/2)
    # exactly; grouped so that hd (~d^2/4) is never added to h1 first and lost (equal radii, tiny d)
    dh = math.sin(0.5 * (r1 - r2)) * math.sin(0.5 * (r1 + r2))
    n1 = 2.0 * hd * (1.0 - 2.0 * h1) + 2.0 * dh
    n2 = 2.0 * hd * (1.0 - 2.0 * h2) - 2.0 * dh
    a1 = math.atan2(sq, n1)
    a2 = math.atan2(sq, n2)
    t = (math.tan(0.5 * s) * max(math.tan(0.5 * (s - r1)), 0.0) * max(math.tan(0.5 * (s - r2)), 0.0)
         * max(math.tan(0.5 * (s - d)), 0.0))
    E = 4.0 * math.atan(math.sqrt(max(t, 0.0)))
    A = 4.0 * a1 * h1 + 4.0 * a2 * h2 - 2.0 * E
    cap = 4.0 * math.pi * min(h1, h2)
    return min(max(A, 0.0), cap)


def earth_limb_enu(geo: dict) -> tuple:
    """Earth's limb ellipse (observer -> limb vectors Q0, QA, QB) in local east-north-up coordinates."""
    e, n, u = geo["e"], geo["n"], geo["u"]
    return tuple(np.array([float(v @ e), float(v @ n), float(v @ u)]) for v in (geo["Q0"], geo["QA"], geo["QB"]))


def limb_radius_toward(limb: tuple, c: np.ndarray, dirs: np.ndarray) -> np.ndarray:
    """Angular radius (rad) of Earth's limb ellipse from its centre direction c toward each unit direction in
    dirs (n, 3), all in the same frame. Closed form: with e1 the unit tangent from c toward p and
    e2 = c x e1, the limb point in that direction solves q(t).e2 = K + P cos t + R sin t = 0, q(t).e1 > 0."""
    Q0, QA, QB = limb
    dirs = np.atleast_2d(np.asarray(dirs, dtype=float))
    e1 = dirs - (dirs @ c)[:, None] * c[None, :]
    ne = np.linalg.norm(e1, axis=1)
    e1 = np.where(ne[:, None] > 1e-15, e1 / np.maximum(ne, 1e-300)[:, None], np.array([[1.0, 0.0, 0.0]]))
    e2 = cross3(c[None, :], e1)
    K, P, R = e2 @ Q0, e2 @ QA, e2 @ QB
    rr = np.hypot(P, R)
    ph = np.arctan2(R, P)
    dd = np.arccos(np.clip(-K / np.maximum(rr, 1e-300), -1.0, 1.0))
    best = np.zeros(dirs.shape[0])
    for sgn in (1.0, -1.0):
        t = ph + sgn * dd
        q = Q0[None, :] + np.cos(t)[:, None] * QA[None, :] + np.sin(t)[:, None] * QB[None, :]
        ok = np.sum(q * e1, axis=1) > 0.0
        r = np.arctan2(np.linalg.norm(cross3(q, c[None, :]), axis=1), q @ c)
        best = np.where(ok, r, best)
    return best


def earth_radius_toward_sun(sun: dict, earth: dict) -> float:
    """Earth's occulting radius (deg): the limb ellipse's radius toward the Sun's centre when the limb is
    given (Phase 3: item 1 ellipse), else the circular radius earth['rho']."""
    limb = earth.get("limb")
    if limb is None:
        return float(earth["rho"])
    c = enu_from_azel(earth["az"], earth["el"])
    s = enu_from_azel(sun["az"], sun["el"])
    return math.degrees(float(limb_radius_toward(limb, c, s[None, :])[0]))


@njit(cache=True)
def _joint_integral(h, binw, use_terrain, use_earth, az_s, el_s, r_s, Q0, QA, QB, cuts, gx, gw):
    """Visible solid angle of the solar cap above the horizon (if use_terrain) and outside Earth's exact limb
    ellipse (if use_earth), integrated over the Sun's azimuth span.

    In each azimuth x (relative to the Sun) the Sun's elevation range is exact (_hilo) and Earth's is exact
    (the two limb points at that azimuth, closed form), so the integrand sin(el_hi) - sin(el_lo) of the
    visible elevation set is exact. The span is cut at `cuts` (the Sun's and Earth's azimuth extremes,
    where the integrand has square-root ends, and the limb crossings and horizon nodes, where it has
    kinks) and each piece is integrated in theta with x = m + h sin(theta), which removes the square roots,
    by Gauss-Legendre (nodes gx, weights gw on [-1, 1]); each piece being smooth, this converges fast."""
    Ps, Qs, crs = math.cos(el_s), math.sin(el_s), math.cos(r_s)
    E_ = np.array([1.0, 0.0, 0.0])
    N_ = np.array([0.0, 1.0, 0.0])
    U_ = np.array([0.0, 0.0, 1.0])
    acc = 0.0
    nb = h.shape[0]
    for j in range(cuts.shape[0] - 1):
        a = cuts[j]
        b = cuts[j + 1]
        if b <= a:
            continue
        m = 0.5 * (a + b)
        hh = 0.5 * (b - a)
        for i in range(gx.shape[0]):
            th = 0.5 * math.pi * gx[i]
            x = m + hh * math.sin(th)
            wgt = hh * math.cos(th) * 0.5 * math.pi * gw[i]
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
            v = math.sin(hi) - math.sin(L)
            if use_earth:
                ts, cnt = _t_at_az(A, Q0, QA, QB, E_, N_)
                if cnt == 2:
                    e1, _ = _elaz(ts[0], Q0, QA, QB, U_, E_, N_)
                    e2, _ = _elaz(ts[1], Q0, QA, QB, U_, E_, N_)
                    ea = max(L, min(e1, e2))
                    eb = min(hi, max(e1, e2))
                    if eb > ea:
                        v -= math.sin(eb) - math.sin(ea)
            acc += v * wgt
    return acc


def _occulter(earth: dict) -> dict:
    """Earth's limb (ENU observer -> limb vectors), extreme radii about its centre, elevation extent and azimuth
    extremes. A circular Earth (no 'limb' given) becomes the exact cone of radius earth['rho']."""
    from .earth import _global_extremum, cap_limb, limb_extrema
    az, el = float(earth["az"]), float(earth["el"])
    if earth.get("limb") is None:
        r = math.radians(float(earth["rho"]))
        limb = tuple(np.asarray(v, dtype=float) for v in cap_limb(az, el, r, _E, _N, _U))
        circle = True
    else:
        limb = tuple(np.asarray(v, dtype=float) for v in earth["limb"])
        circle = False
    c = enu_from_azel(az, el)
    dummy = np.zeros(1)
    _, r_hi, _ = _global_extremum(1, 1.0, *limb, _U, _E, _N, c, 0.0, dummy, 1.0, 64, 1e-14, 60)
    _, r_lo, _ = _global_extremum(1, -1.0, *limb, _U, _E, _N, c, 0.0, dummy, 1.0, 64, 1e-14, 60)
    ru, rd, _dm, _fb = limb_extrema(*limb, _U, _E, _N, math.radians(el), math.radians(az), 64, 1e-14, 60)
    if circle:
        r_hi = r_lo = ru = rd = math.radians(float(earth["rho"]))
    return {"limb": limb, "circle": circle, "c": c, "r_lo": r_lo, "r_hi": r_hi,
            "el_lo": el - math.degrees(rd), "el_hi": el + math.degrees(ru)}


_E = np.array([1.0, 0.0, 0.0])
_N = np.array([0.0, 1.0, 0.0])
_U = np.array([0.0, 0.0, 1.0])


@njit(cache=True)
def _edge_forms(xs, h, binw, az_s, el_s, r_s, Q0, QA, QB, out):
    """At relative azimuths xs: Sun top - H, Sun bottom - H, Earth top - H, Earth bottom - H (rad; Earth
    entries NaN where Earth has no limb at that azimuth). Sign changes are where the horizon crosses a limb."""
    Ps, Qs, crs = math.cos(el_s), math.sin(el_s), math.cos(r_s)
    E_ = np.array([1.0, 0.0, 0.0])
    N_ = np.array([0.0, 1.0, 0.0])
    U_ = np.array([0.0, 0.0, 1.0])
    nb = h.shape[0]
    for k in range(xs.shape[0]):
        x = xs[k]
        lo, hi = _hilo(x, Ps, Qs, crs)
        A = az_s + x
        fpos = (math.degrees(A) % 360.0) / binw
        i0 = int(math.floor(fpos)) % nb
        i1 = (i0 + 1) % nb
        tt = fpos - math.floor(fpos)
        H = math.radians(h[i0] * (1.0 - tt) + h[i1] * tt)
        out[k, 0] = hi - H
        out[k, 1] = lo - H
        ts, cnt = _t_at_az(A, Q0, QA, QB, E_, N_)
        if cnt == 2:
            e1, _ = _elaz(ts[0], Q0, QA, QB, U_, E_, N_)
            e2, _ = _elaz(ts[1], Q0, QA, QB, U_, E_, N_)
            out[k, 2] = max(e1, e2) - H
            out[k, 3] = min(e1, e2) - H
        else:
            out[k, 2] = math.nan
            out[k, 3] = math.nan


def _horizon_crossings(hp, sun: dict, oc: dict, cuts: np.ndarray, earth_ext: list, per: int = 32) -> list:
    """Relative azimuths where the horizon crosses the Sun's or Earth's limb, inside each existing piece:
    sign changes on `per` samples per piece, refined by bisection to ~1e-15 rad. earth_ext lists Earth's
    azimuth extremes as (x, el): there the two limb points merge and the closed-form limb solver may round
    to "no limb", so the exact extreme elevation is used for a sample that falls on one."""
    az_s, el_s, rs = math.radians(sun["az"]), math.radians(sun["el"]), math.radians(sun["rho"])
    args = (hp.h, hp.bin, az_s, el_s, rs, *oc["limb"])
    out = []
    for a, b in zip(cuts[:-1], cuts[1:]):
        if b <= a:
            continue
        xs = np.linspace(a, b, per + 1)
        v = np.empty((xs.size, 4))
        _edge_forms(xs, *args, v)
        for k in (0, per):
            if not np.isfinite(v[k, 2]):
                for x_e, el_e in earth_ext:
                    if abs(xs[k] - x_e) <= 1e-12:
                        H = math.radians(float(hp.at(math.degrees(az_s + xs[k]))))
                        v[k, 2] = v[k, 3] = el_e - H
        for j in range(4):
            f = v[:, j]
            for k in range(per):
                if not (np.isfinite(f[k]) and np.isfinite(f[k + 1])) or (f[k] > 0) == (f[k + 1] > 0):
                    continue
                lo, hi, flo = xs[k], xs[k + 1], f[k]
                one = np.empty((1, 4))
                for _ in range(60):
                    mid = 0.5 * (lo + hi)
                    _edge_forms(np.array([mid]), *args, one)
                    fm = one[0, j]
                    if not np.isfinite(fm):
                        break
                    if (fm > 0) == (flo > 0):
                        lo, flo = mid, fm
                    else:
                        hi = mid
                out.append(0.5 * (lo + hi))
    return out


_GL_CACHE: dict = {}


def _gl(n: int):
    """Gauss-Legendre nodes and weights on [-1, 1] (cached)."""
    if n not in _GL_CACHE:
        _GL_CACHE[n] = np.polynomial.legendre.leggauss(n)
    return _GL_CACHE[n]


def _limb_crossings(sun: dict, oc: dict, n: int = 4096) -> list:
    """Azimuths (rad, relative to the Sun) where Earth's limb crosses the Sun's limb: sign changes of the
    radial distance outside Earth along the solar limb, refined by bisection to ~1e-15 rad in angle."""
    s = enu_from_azel(sun["az"], sun["el"])
    rr = math.radians(sun["rho"])
    t1 = np.cross(s, _U)
    nt = np.linalg.norm(t1)
    t1 = t1 / nt if nt > 1e-12 else np.cross(s, _E) / np.linalg.norm(np.cross(s, _E))
    t2 = np.cross(s, t1)

    def pts(ph):
        ph = np.atleast_1d(ph)
        return math.cos(rr) * s[None, :] + math.sin(rr) * (np.cos(ph)[:, None] * t1 + np.sin(ph)[:, None] * t2)

    ph = np.linspace(0.0, 2 * math.pi, n + 1)
    f = _dist_outside_earth(pts(ph), oc)
    idx = np.nonzero(np.sign(f[:-1]) != np.sign(f[1:]))[0]
    if idx.size == 0:
        return []
    lo, hi, flo = ph[idx], ph[idx + 1], f[idx]
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        fm = _dist_outside_earth(pts(mid), oc)
        same = np.sign(fm) == np.sign(flo)
        lo, flo, hi = np.where(same, mid, lo), np.where(same, fm, flo), np.where(same, hi, mid)
    p = pts(0.5 * (lo + hi))
    az = np.arctan2(p[:, 0], p[:, 1])
    return list((az - math.radians(sun["az"]) + math.pi) % (2 * math.pi) - math.pi)


def joint_fraction(hp, sun: dict, earth: dict, use_terrain: bool = True, tol: float = JOINT_TOL,
                   occ: dict | None = None) -> tuple[float, float, int]:
    """Adaptive integration of the visible solar fraction (terrain if use_terrain, Earth's exact ellipse).

    The Sun's azimuth span is cut wherever the integrand changes form: the Sun's and Earth's azimuth
    extremes (square-root ends, removed by the sine substitution), the crossings of the two limbs and, with
    terrain, every horizon node and every crossing of the horizon with either limb. Each piece is then smooth, the midpoint rule in theta converges fast and
    regularly: the Gauss-Legendre order per piece doubles until two successive doublings change f by less than
    tol / 2 and tol. Returns (f, error estimate = last change, order per piece)."""
    from .earth import _global_extremum
    oc = occ or _occulter(earth)
    az_s, el_s, rs = math.radians(sun["az"]), math.radians(sun["el"]), math.radians(sun["rho"])
    hw = math.asin(min(1.0, math.sin(rs) / max(math.cos(el_s), 1e-12)))
    dummy = np.zeros(1)
    cuts = [-hw, hw]
    earth_ext = []
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
        cuts = np.unique(np.clip(np.append(cuts, _horizon_crossings(hp, sun, oc, cuts, earth_ext)), -hw, hw))
    area = cap_area(rs)
    n = JOINT_STRIPS[0]
    f_prev = _joint_integral(hp.h, hp.bin, use_terrain, True, az_s, el_s, rs, *oc["limb"], cuts, *_gl(n)) / area
    err = prev_err = math.inf
    while n < JOINT_STRIPS[1]:
        n *= 2
        f = _joint_integral(hp.h, hp.bin, use_terrain, True, az_s, el_s, rs, *oc["limb"], cuts, *_gl(n)) / area
        prev_err, err = err, abs(f - f_prev)
        f_prev = f
        if err < 0.5 * tol and prev_err < tol:
            break
    return min(1.0, max(0.0, f_prev)), err, n


def sun_joint_state(hp: HorizonProfile, sun: dict, earth: dict, sun_terrain: dict) -> dict:
    """Visible solar fraction with terrain and Earth (Section 8.3), the share of the Sun behind Earth (occ),
    the combined clearance g_vis and the method.

    Earth is its exact limb ellipse (Phase 3 item 1) when earth['limb'] is given, else a circle of radius
    earth['rho']. With r_lo, r_hi the limb's extreme radii about Earth's centre:
      * gamma >= r_s + r_hi: no overlap (exact); gamma <= r_lo - r_s: the Sun is wholly behind Earth;
      * occ: the spherical lens (exact, stable branches) for a circular Earth, else the adaptive exact-ellipse
        integral to OCC_TOL;
      * f exact branches: hidden by terrain or Earth (0); terrain clears the whole Sun (1 - occ); Earth's
        overlap entirely above the terrain span (f_terrain - occ) or entirely below it (f_terrain);
      * only where terrain and Earth both cut the Sun is f integrated (adaptive, error estimate recorded);
        above SPHERICAL_EL_DEG that case falls back to the sampled cap (labelled)."""
    gamma, rs = float(sun["gamma"]), float(sun["rho"])
    rs_r, g_r = math.radians(rs), math.radians(gamma)
    f_t = sun_terrain["f"]
    if _surely_apart(sun, earth):
        return {"f": f_t, "occ": 0.0, "g_vis": sun_terrain["g_top"], "method": "no overlap", "err": 0.0}
    oc = _occulter(earth)
    g_vis = sun_vis_clearance(hp, sun, earth, sun_terrain, oc)
    if g_r >= rs_r + oc["r_hi"]:
        return {"f": f_t, "occ": 0.0, "g_vis": g_vis, "method": "no overlap", "err": 0.0}
    if g_r <= oc["r_lo"] - rs_r:
        occ, occ_err, occ_m = 1.0, 0.0, "contained"
    elif oc["circle"]:
        occ = min(1.0, max(0.0, spherical_cap_lens_area(rs_r, oc["r_hi"], g_r) / cap_area(rs_r)))
        occ_err, occ_m = 0.0, "lens"
    else:
        f_free, occ_err, n = joint_fraction(hp, sun, earth, use_terrain=False, tol=OCC_TOL, occ=oc)
        occ, occ_m = 1.0 - f_free, f"ellipse ({n})"
    out = {"occ": occ, "g_vis": g_vis, "err": occ_err}
    if not np.isfinite(f_t):
        return {**out, "f": f_t, "method": f"unknown (terrain); occ {occ_m}"}
    hw = half_width_az(sun["el"], rs)
    hmax_span, hmin_span, _inc = hp.span_extremes(sun["az"], hw)
    lap_lo = max(sun["el"] - rs, oc["el_lo"])                 # Earth's overlap with the Sun lies inside both
    lap_hi = min(sun["el"] + rs, oc["el_hi"])
    if occ >= 1.0 or f_t <= 0.0:
        return {**out, "f": 0.0, "method": "exact: hidden"}
    if sun_terrain["g_bot"] > 0.0:
        return {**out, "f": max(0.0, 1.0 - occ), "method": f"exact: terrain clear; occ {occ_m}"}
    if lap_lo > hmax_span:
        return {**out, "f": min(1.0, max(0.0, f_t - occ)), "method": f"exact: overlap above terrain; occ {occ_m}"}
    if lap_hi < hmin_span:
        return {**out, "f": f_t, "method": "exact: overlap below terrain"}
    if sun["el"] > SPHERICAL_EL_DEG or sun["el"] + rs >= 90.0:
        return {**out, "f": _joint_sampled(hp, sun, oc), "method": "sampled (above 60 deg)", "err": float("nan")}
    f, err, n = joint_fraction(hp, sun, earth, occ=oc)
    return {**out, "f": f, "method": f"adaptive strips ({n})", "err": max(err, occ_err)}


def _surely_apart(sun: dict, earth: dict) -> bool:
    """Cheap exact pre-check: no overlap is possible. Every limb radius is <= alpha = asin(a/d) and the mean
    vertical extent earth['rho'] is >= beta, with alpha / beta < a / b (1 + 1e-5) < 1.01."""
    return float(sun["gamma"]) >= float(sun["rho"]) + 1.01 * float(earth["rho"])


def sun_vis_clearance(hp: HorizonProfile, sun: dict, earth: dict, sun_terrain: dict, oc: dict | None = None) -> float:
    """The combined clearance g_vis alone (what the event detector needs), without the visible fraction.

    It switches from the terrain clearance to the joint value at the same contact as the event function
    ecl_contact (gamma = rho_sun + Earth's radius toward the Sun), so its one discontinuity (the switch)
    coincides with an event the detector already resolves at its minimum step."""
    if _surely_apart(sun, earth):
        return sun_terrain["g_top"]
    if float(sun["gamma"]) >= float(sun["rho"]) + earth_radius_toward_sun(sun, earth):
        return sun_terrain["g_top"]
    return _g_vis(hp, sun, earth, oc or _occulter(earth))


def _dist_outside_earth(pts, oc) -> np.ndarray:
    """Angular distance (deg) of each point outside Earth's limb, measured radially from Earth's centre
    (positive outside; exact sign for the ellipse)."""
    c = oc["c"]
    ang = np.arctan2(np.linalg.norm(np.cross(pts, c[None, :]), axis=1), pts @ c)
    rad = np.full(ang.shape, oc["r_hi"]) if oc["circle"] else limb_radius_toward(oc["limb"], c, pts)
    return np.degrees(ang - rad)


def _g_vis(hp, sun, earth, oc) -> float:
    """Combined clearance: largest over solar-disk points of min(terrain clearance, angular distance outside
    Earth's limb), on the area-weighted sample points plus the solar limb point farthest from Earth."""
    az_p, el_p, w, pts, _b = cap_points(sun["az"], sun["el"], sun["rho"])
    e_vec = oc["c"]
    s_vec = enu_from_azel(sun["az"], sun["el"])
    away = s_vec * float(s_vec @ e_vec) - e_vec
    na = float(np.linalg.norm(away))
    if na > 1e-12:
        rr = math.radians(sun["rho"])
        far = math.cos(rr) * s_vec + math.sin(rr) * away / na
        pts = np.vstack([pts, far])
        el_p = np.append(el_p, math.degrees(math.asin(max(-1.0, min(1.0, far[2])))))
        az_p = np.append(az_p, math.degrees(math.atan2(far[0], far[1])) % 360.0)
    clear = el_p - hp.at(az_p)
    return float(np.max(np.minimum(clear, _dist_outside_earth(pts, oc))))


def _joint_sampled(hp, sun, oc) -> float:
    az_p, el_p, w, pts, _b = cap_points(sun["az"], sun["el"], sun["rho"])
    vis = (el_p - hp.at(az_p) > 0) & (_dist_outside_earth(pts, oc) > 0)
    return float(np.sum(w * vis) / np.sum(w))


def circle_overlap_fraction(r_s: float, r_e: float, gamma: float) -> float:
    """Fraction of a disk of radius r_s covered by a disk of radius r_e at separation gamma (planar; kept as the
    small-angle reference for spherical_cap_lens_area, no longer used for results)."""
    if gamma >= r_s + r_e:
        return 0.0
    if gamma <= abs(r_e - r_s):
        return 1.0 if r_e >= r_s else (r_e * r_e) / (r_s * r_s)
    a1 = r_s * r_s * math.acos((gamma * gamma + r_s * r_s - r_e * r_e) / (2 * gamma * r_s))
    a2 = r_e * r_e * math.acos((gamma * gamma + r_e * r_e - r_s * r_s) / (2 * gamma * r_e))
    a3 = 0.5 * math.sqrt(max(0.0, (-gamma + r_s + r_e) * (gamma + r_s - r_e) * (gamma - r_s + r_e) * (gamma + r_s + r_e)))
    return (a1 + a2 - a3) / (math.pi * r_s * r_s)


def sun_fraction_with_earth(hp: HorizonProfile, sun: dict, earth: dict, sun_terrain: dict) -> tuple[float, float]:
    """Visible solar fraction including Earth occultation (Section 8.3). Returns (f, occulted_share)."""
    st = sun_joint_state(hp, sun, earth, sun_terrain)
    return st["f"], st["occ"]


def sun_visibility_with_earth(hp: HorizonProfile, sun: dict, earth: dict, sun_terrain: dict) -> tuple[float, float, float]:
    """(visible fraction, share covered by Earth, combined clearance g_vis in degrees).

    g_vis is the largest, over solar-disk points, of min(terrain clearance, angular distance outside
    Earth's cap). It is positive exactly when some part of the Sun is visible, so its zero crossings are the
    any-part sunrise/sunset boundaries including eclipses. See sun_joint_state for f and occ.
    """
    st = sun_joint_state(hp, sun, earth, sun_terrain)
    return st["f"], st["occ"], st["g_vis"]


def rule_state(state: dict, rule: str, margin_deg: float = 0.0):
    """Boolean visibility under a rule; None when unknown."""
    if state.get("unknown"):
        return None
    if rule == "any":
        return state["f"] > 0.0
    if rule == "centre":
        return state["c"] >= 0.0
    if rule == "full":
        return state["g_bot"] >= margin_deg
    raise ValueError(f"Unknown rule {rule}")


def segment_area_fraction(rho: float, a: float) -> float:
    """Analytic visible fraction for a straight level horizon a below the centre (V-08)."""
    a = max(-rho, min(rho, a))
    blocked = rho * rho * math.acos(a / rho) - a * math.sqrt(rho * rho - a * a)
    return 1.0 - blocked / (math.pi * rho * rho)


@njit(cache=True)
def _edges_many(h, inc, binw, az, el, rho, out):
    for i in range(az.shape[0]):
        f, gt, gb, _hx, _hn, _ic = _disk_exact(h, inc, binw, az[i], el[i], rho[i])
        out[i, 0] = gt
        out[i, 1] = gb
        out[i, 2] = f


def disk_edges_many(hp: HorizonProfile, az: np.ndarray, el: np.ndarray, rho: np.ndarray) -> dict:
    """Vectorized c, g_top, g_bot, f for many samples (brute-force references for V-14).

    Calls the same exact kernel as disk_state, so values are identical wherever disk_state uses
    the closed-form spherical model; samples above SPHERICAL_EL_DEG go through disk_state one by one.
    """
    az = np.ascontiguousarray(az, float); el = np.ascontiguousarray(el, float); rho = np.ascontiguousarray(rho, float)
    out = np.empty((az.size, 3))
    sph = (el > SPHERICAL_EL_DEG) | (el + rho >= 90.0)
    idx = np.where(~sph)[0]
    if idx.size:
        sub = np.empty((idx.size, 3))
        _edges_many(hp.h, hp.inc, hp.bin, az[idx], el[idx], rho[idx], sub)
        out[idx] = sub
    for i in np.where(sph)[0]:
        st = disk_state(hp, float(az[i]), float(el[i]), float(rho[i]))
        out[i] = (st["g_top"], st["g_bot"], st["f"])
    return {"c": el - hp.at(az), "g_top": out[:, 0], "g_bot": out[:, 1], "f": out[:, 2]}
