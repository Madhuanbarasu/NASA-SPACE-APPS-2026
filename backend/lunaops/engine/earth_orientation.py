"""Earth's spin axis of date: IAU 2006 precession with IAU 2000B nutation (Phase 4).

The pole used for Earth's oblate limb (engine.earth) is the Celestial Intermediate Pole (CIP) of date,
expressed in the GCRS. It is the third row of the bias-precession-nutation matrix built from the IAU 2006
Fukushima-Williams angles with the IAU 2000B nutation added in longitude and obliquity, i.e. exactly the
SOFA/ERFA combination eraPn06(date, eraNut00b(date)) (row 3 of rbpn):

    NPB = R1(-(eps_A + deps)) R3(-(psi_bar + dpsi)) R1(phi_bar) R3(gamma_bar),    CIP = NPB[2, :]

Sources (coefficients transcribed mechanically from ERFA 2.0.1 = SOFA 2023-10-11, BSD licence):
  * IAU 2006 precession, Fukushima-Williams angles: Capitaine, Wallace & Chapront 2003, A&A 412, 567;
    IERS Conventions (2010), IERS TN 36, eq. 5.40; SOFA/ERFA pfw06, obl06, fw2m.
  * IAU 2000B nutation: McCarthy & Luzum 2003, Celest. Mech. Dyn. Astr. 85, 37; IERS Conventions (2010)
    section 5.5.1; SOFA/ERFA nut00b (77 luni-solar terms, Simon et al. 1994 Delaunay arguments, fixed
    offsets -0.135 mas / +0.388 mas in lieu of the planetary terms).

Accuracy: SOFA states the IAU 2000B pole is good to 1 mas from 1900 to 2100 (very occasionally just over).
Neglected, all far below 1 arcsec: polar motion and free-core nutation (unpredictable; about 0.3 arcsec and
0.2 mas), the IAU 2006 adjustments to the nutation amplitudes (micro-arcseconds), and the TT-TDB difference
(under 2 ms of time). SPICE's J2000 frame is taken as the ICRF/GCRS axes, as NAIF does for the DE
ephemerides; the frame bias between EME2000 and the ICRS (about 23 mas) is already inside the
Fukushima-Williams angles. The model is analytic and deterministic: the demo and production kernel sets give
the same pole (only the J2000 -> lunar body-fixed rotation comes from the kernels).
"""
from __future__ import annotations

import math

import numpy as np
from numba import njit

DAS2R = 4.848136811095359935899141e-6          # arcseconds to radians (ERFA_DAS2R)
DMAS2R = DAS2R / 1e3                           # milliarcseconds to radians
U2R = DAS2R / 1e7                              # 0.1 microarcsecond to radians
TURNAS = 1296000.0                             # arcseconds in a full circle
D2PI = 6.283185307179586476925287
SEC_PER_CENTURY = 86400.0 * 36525.0
DPPLAN = -0.135 * DMAS2R                       # IAU 2000B fixed offsets in lieu of planetary nutation
DEPLAN = 0.388 * DMAS2R
POLE_DERIV_STEP_S = 3600.0                     # central-difference step for the CIP's own (tiny) rate

# IAU 2000B luni-solar nutation (McCarthy & Luzum 2003; ERFA nut00b, same order). Columns: multipliers of
# l, l', F, D, Om; longitude sin, t*sin, cos; obliquity cos, t*cos, sin; units 0.1 microarcsecond (per
# Julian century for the t terms).
NUT00B = np.array([
    ( 0,  0,  0,  0,  1, -172064161.0, -174666.0, 33386.0, 92052331.0, 9086.0, 15377.0),
    ( 0,  0,  2, -2,  2, -13170906.0, -1675.0, -13696.0, 5730336.0, -3015.0, -4587.0),
    ( 0,  0,  2,  0,  2, -2276413.0, -234.0, 2796.0, 978459.0, -485.0, 1374.0),
    ( 0,  0,  0,  0,  2, 2074554.0, 207.0, -698.0, -897492.0, 470.0, -291.0),
    ( 0,  1,  0,  0,  0, 1475877.0, -3633.0, 11817.0, 73871.0, -184.0, -1924.0),
    ( 0,  1,  2, -2,  2, -516821.0, 1226.0, -524.0, 224386.0, -677.0, -174.0),
    ( 1,  0,  0,  0,  0, 711159.0, 73.0, -872.0, -6750.0, 0.0, 358.0),
    ( 0,  0,  2,  0,  1, -387298.0, -367.0, 380.0, 200728.0, 18.0, 318.0),
    ( 1,  0,  2,  0,  2, -301461.0, -36.0, 816.0, 129025.0, -63.0, 367.0),
    ( 0, -1,  2, -2,  2, 215829.0, -494.0, 111.0, -95929.0, 299.0, 132.0),
    ( 0,  0,  2, -2,  1, 128227.0, 137.0, 181.0, -68982.0, -9.0, 39.0),
    (-1,  0,  2,  0,  2, 123457.0, 11.0, 19.0, -53311.0, 32.0, -4.0),
    (-1,  0,  0,  2,  0, 156994.0, 10.0, -168.0, -1235.0, 0.0, 82.0),
    ( 1,  0,  0,  0,  1, 63110.0, 63.0, 27.0, -33228.0, 0.0, -9.0),
    (-1,  0,  0,  0,  1, -57976.0, -63.0, -189.0, 31429.0, 0.0, -75.0),
    (-1,  0,  2,  2,  2, -59641.0, -11.0, 149.0, 25543.0, -11.0, 66.0),
    ( 1,  0,  2,  0,  1, -51613.0, -42.0, 129.0, 26366.0, 0.0, 78.0),
    (-2,  0,  2,  0,  1, 45893.0, 50.0, 31.0, -24236.0, -10.0, 20.0),
    ( 0,  0,  0,  2,  0, 63384.0, 11.0, -150.0, -1220.0, 0.0, 29.0),
    ( 0,  0,  2,  2,  2, -38571.0, -1.0, 158.0, 16452.0, -11.0, 68.0),
    ( 0, -2,  2, -2,  2, 32481.0, 0.0, 0.0, -13870.0, 0.0, 0.0),
    (-2,  0,  0,  2,  0, -47722.0, 0.0, -18.0, 477.0, 0.0, -25.0),
    ( 2,  0,  2,  0,  2, -31046.0, -1.0, 131.0, 13238.0, -11.0, 59.0),
    ( 1,  0,  2, -2,  2, 28593.0, 0.0, -1.0, -12338.0, 10.0, -3.0),
    (-1,  0,  2,  0,  1, 20441.0, 21.0, 10.0, -10758.0, 0.0, -3.0),
    ( 2,  0,  0,  0,  0, 29243.0, 0.0, -74.0, -609.0, 0.0, 13.0),
    ( 0,  0,  2,  0,  0, 25887.0, 0.0, -66.0, -550.0, 0.0, 11.0),
    ( 0,  1,  0,  0,  1, -14053.0, -25.0, 79.0, 8551.0, -2.0, -45.0),
    (-1,  0,  0,  2,  1, 15164.0, 10.0, 11.0, -8001.0, 0.0, -1.0),
    ( 0,  2,  2, -2,  2, -15794.0, 72.0, -16.0, 6850.0, -42.0, -5.0),
    ( 0,  0, -2,  2,  0, 21783.0, 0.0, 13.0, -167.0, 0.0, 13.0),
    ( 1,  0,  0, -2,  1, -12873.0, -10.0, -37.0, 6953.0, 0.0, -14.0),
    ( 0, -1,  0,  0,  1, -12654.0, 11.0, 63.0, 6415.0, 0.0, 26.0),
    (-1,  0,  2,  2,  1, -10204.0, 0.0, 25.0, 5222.0, 0.0, 15.0),
    ( 0,  2,  0,  0,  0, 16707.0, -85.0, -10.0, 168.0, -1.0, 10.0),
    ( 1,  0,  2,  2,  2, -7691.0, 0.0, 44.0, 3268.0, 0.0, 19.0),
    (-2,  0,  2,  0,  0, -11024.0, 0.0, -14.0, 104.0, 0.0, 2.0),
    ( 0,  1,  2,  0,  2, 7566.0, -21.0, -11.0, -3250.0, 0.0, -5.0),
    ( 0,  0,  2,  2,  1, -6637.0, -11.0, 25.0, 3353.0, 0.0, 14.0),
    ( 0, -1,  2,  0,  2, -7141.0, 21.0, 8.0, 3070.0, 0.0, 4.0),
    ( 0,  0,  0,  2,  1, -6302.0, -11.0, 2.0, 3272.0, 0.0, 4.0),
    ( 1,  0,  2, -2,  1, 5800.0, 10.0, 2.0, -3045.0, 0.0, -1.0),
    ( 2,  0,  2, -2,  2, 6443.0, 0.0, -7.0, -2768.0, 0.0, -4.0),
    (-2,  0,  0,  2,  1, -5774.0, -11.0, -15.0, 3041.0, 0.0, -5.0),
    ( 2,  0,  2,  0,  1, -5350.0, 0.0, 21.0, 2695.0, 0.0, 12.0),
    ( 0, -1,  2, -2,  1, -4752.0, -11.0, -3.0, 2719.0, 0.0, -3.0),
    ( 0,  0,  0, -2,  1, -4940.0, -11.0, -21.0, 2720.0, 0.0, -9.0),
    (-1, -1,  0,  2,  0, 7350.0, 0.0, -8.0, -51.0, 0.0, 4.0),
    ( 2,  0,  0, -2,  1, 4065.0, 0.0, 6.0, -2206.0, 0.0, 1.0),
    ( 1,  0,  0,  2,  0, 6579.0, 0.0, -24.0, -199.0, 0.0, 2.0),
    ( 0,  1,  2, -2,  1, 3579.0, 0.0, 5.0, -1900.0, 0.0, 1.0),
    ( 1, -1,  0,  0,  0, 4725.0, 0.0, -6.0, -41.0, 0.0, 3.0),
    (-2,  0,  2,  0,  2, -3075.0, 0.0, -2.0, 1313.0, 0.0, -1.0),
    ( 3,  0,  2,  0,  2, -2904.0, 0.0, 15.0, 1233.0, 0.0, 7.0),
    ( 0, -1,  0,  2,  0, 4348.0, 0.0, -10.0, -81.0, 0.0, 2.0),
    ( 1, -1,  2,  0,  2, -2878.0, 0.0, 8.0, 1232.0, 0.0, 4.0),
    ( 0,  0,  0,  1,  0, -4230.0, 0.0, 5.0, -20.0, 0.0, -2.0),
    (-1, -1,  2,  2,  2, -2819.0, 0.0, 7.0, 1207.0, 0.0, 3.0),
    (-1,  0,  2,  0,  0, -4056.0, 0.0, 5.0, 40.0, 0.0, -2.0),
    ( 0, -1,  2,  2,  2, -2647.0, 0.0, 11.0, 1129.0, 0.0, 5.0),
    (-2,  0,  0,  0,  1, -2294.0, 0.0, -10.0, 1266.0, 0.0, -4.0),
    ( 1,  1,  2,  0,  2, 2481.0, 0.0, -7.0, -1062.0, 0.0, -3.0),
    ( 2,  0,  0,  0,  1, 2179.0, 0.0, -2.0, -1129.0, 0.0, -2.0),
    (-1,  1,  0,  1,  0, 3276.0, 0.0, 1.0, -9.0, 0.0, 0.0),
    ( 1,  1,  0,  0,  0, -3389.0, 0.0, 5.0, 35.0, 0.0, -2.0),
    ( 1,  0,  2,  0,  0, 3339.0, 0.0, -13.0, -107.0, 0.0, 1.0),
    (-1,  0,  2, -2,  1, -1987.0, 0.0, -6.0, 1073.0, 0.0, -2.0),
    ( 1,  0,  0,  0,  2, -1981.0, 0.0, 0.0, 854.0, 0.0, 0.0),
    (-1,  0,  0,  1,  0, 4026.0, 0.0, -353.0, -553.0, 0.0, -139.0),
    ( 0,  0,  2,  1,  2, 1660.0, 0.0, -5.0, -710.0, 0.0, -2.0),
    (-1,  0,  2,  4,  2, -1521.0, 0.0, 9.0, 647.0, 0.0, 4.0),
    (-1,  1,  0,  1,  1, 1314.0, 0.0, 0.0, -700.0, 0.0, 0.0),
    ( 0, -2,  2, -2,  1, -1283.0, 0.0, 0.0, 672.0, 0.0, 0.0),
    ( 1,  0,  2,  2,  1, -1331.0, 0.0, 8.0, 663.0, 0.0, 4.0),
    (-2,  0,  2,  2,  2, 1383.0, 0.0, -2.0, -594.0, 0.0, -2.0),
    (-1,  0,  0,  0,  2, 1405.0, 0.0, 4.0, -610.0, 0.0, 2.0),
    ( 1,  1,  2, -2,  2, 1290.0, 0.0, 0.0, -556.0, 0.0, 0.0),
])


_NUT_MULT = NUT00B[::-1, :5].copy()           # smallest terms first, the order in which ERFA adds them
_NUT_COEF = NUT00B[::-1, 5:].copy()


# Scalar kernels (numba, compiled once and cached like the other engine kernels). Each formula appears once;
# the NumPy-facing functions below only loop over epochs.
@njit(cache=True)
def _nut00b_s(t, mult, coef):
    el = np.fmod(485868.249036 + 1717915923.2178 * t, TURNAS) * DAS2R
    elp = np.fmod(1287104.79305 + 129596581.0481 * t, TURNAS) * DAS2R
    f = np.fmod(335779.526232 + 1739527262.8478 * t, TURNAS) * DAS2R
    d = np.fmod(1072260.70369 + 1602961601.2090 * t, TURNAS) * DAS2R
    om = np.fmod(450160.398036 - 6962890.5431 * t, TURNAS) * DAS2R
    dp = 0.0
    de = 0.0
    for i in range(mult.shape[0]):
        arg = np.fmod(mult[i, 0] * el + mult[i, 1] * elp + mult[i, 2] * f + mult[i, 3] * d + mult[i, 4] * om,
                        D2PI)
        sarg = math.sin(arg)
        carg = math.cos(arg)
        dp += (coef[i, 0] + coef[i, 1] * t) * sarg + coef[i, 2] * carg
        de += (coef[i, 3] + coef[i, 4] * t) * carg + coef[i, 5] * sarg
    return dp * U2R + DPPLAN, de * U2R + DEPLAN


@njit(cache=True)
def _obl06_s(t):
    return (84381.406 + (-46.836769 + (-0.0001831 + (0.00200340 + (-0.000000576 + (-0.0000000434) * t)
                                                                  * t) * t) * t) * t) * DAS2R


@njit(cache=True)
def _pfw06_s(t):
    gamb = (-0.052928 + (10.556378 + (0.4932044 + (-0.00031238 + (-0.000002788 + (0.0000000260) * t) * t) * t)
                         * t) * t) * DAS2R
    phib = (84381.412819 + (-46.811016 + (0.0511268 + (0.00053289 + (-0.000000440 + (-0.0000000176) * t) * t)
                                          * t) * t) * t) * DAS2R
    psib = (-0.041775 + (5038.481484 + (1.5584175 + (-0.00018522 + (-0.000026452 + (-0.0000000148) * t) * t)
                                        * t) * t) * t) * DAS2R
    return gamb, phib, psib, _obl06_s(t)


@njit(cache=True)
def _cip_many(ts, nutation, mult, coef):
    out = np.empty((ts.size, 3))
    for k in range(ts.size):
        t = ts[k]
        gamb, phib, psi, eps = _pfw06_s(t)
        if nutation:
            dpsi, deps = _nut00b_s(t, mult, coef)
            psi += dpsi
            eps += deps
        # third row of fw2m(gamb, phib, psi, eps) = R1(-eps) R3(-psi) R1(phib) R3(gamb), multiplied out
        se, ce = math.sin(eps), math.cos(eps)
        a = se * math.sin(psi)
        b = se * math.cos(psi) * math.cos(phib) - ce * math.sin(phib)
        x = a * math.cos(gamb) - b * math.sin(gamb)
        y = a * math.sin(gamb) + b * math.cos(gamb)
        z = se * math.cos(psi) * math.sin(phib) + ce * math.cos(phib)
        r = math.sqrt(x * x + y * y + z * z)
        out[k, 0] = x / r
        out[k, 1] = y / r
        out[k, 2] = z / r
    return out


@njit(cache=True)
def _nut_many(ts, mult, coef):
    out = np.empty((ts.size, 2))
    for k in range(ts.size):
        out[k, 0], out[k, 1] = _nut00b_s(ts[k], mult, coef)
    return out


@njit(cache=True)
def _pfw_many(ts):
    out = np.empty((ts.size, 4))
    for k in range(ts.size):
        out[k, 0], out[k, 1], out[k, 2], out[k, 3] = _pfw06_s(ts[k])
    return out


def _flat(t):
    t = np.asarray(t, dtype=float)
    return t.shape, np.ascontiguousarray(t.ravel())


def nut00b(t):
    """IAU 2000B nutation (dpsi, deps) in radians for TT Julian centuries t since J2000.0 (ERFA nut00b)."""
    shape, ts = _flat(t)
    r = _nut_many(ts, _NUT_MULT, _NUT_COEF)
    return r[:, 0].reshape(shape), r[:, 1].reshape(shape)


def obl06(t):
    """IAU 2006 mean obliquity of the ecliptic (radians), t in TT Julian centuries (ERFA obl06)."""
    shape, ts = _flat(t)
    return _pfw_many(ts)[:, 3].reshape(shape)


def pfw06(t):
    """IAU 2006 bias-precession Fukushima-Williams angles (gamma_bar, phi_bar, psi_bar, eps_A) in radians
    (ERFA pfw06)."""
    shape, ts = _flat(t)
    r = _pfw_many(ts)
    return tuple(r[:, j].reshape(shape) for j in range(4))


def _rx(a):
    c, s = np.cos(a), np.sin(a)
    o, z = np.ones_like(a), np.zeros_like(a)
    return np.stack([np.stack([o, z, z], -1), np.stack([z, c, s], -1), np.stack([z, -s, c], -1)], -2)


def _rz(a):
    c, s = np.cos(a), np.sin(a)
    o, z = np.ones_like(a), np.zeros_like(a)
    return np.stack([np.stack([c, s, z], -1), np.stack([-s, c, z], -1), np.stack([z, z, o], -1)], -2)


def fw2m(gamb, phib, psi, eps):
    """Fukushima-Williams angles to the rotation matrix (n, 3, 3), GCRS -> true (or mean) of date
    (ERFA fw2m: R1(-eps) R3(-psi) R1(phib) R3(gamb), SOFA rotation-of-axes convention)."""
    gamb, phib, psi, eps = (np.atleast_1d(np.asarray(x, dtype=float)) for x in (gamb, phib, psi, eps))
    return _rx(-eps) @ _rz(-psi) @ _rx(phib) @ _rz(gamb)


def cip_gcrs(t, nutation: bool = True) -> np.ndarray:
    """Unit vector of Earth's pole of date in the GCRS for TT Julian centuries t: the CIP (IAU 2006
    precession + IAU 2000B nutation) or, with nutation=False, the IAU 2006 mean pole of date."""
    return _cip_many(np.ascontiguousarray(np.atleast_1d(np.asarray(t, dtype=float)).ravel()), nutation,
                     _NUT_MULT, _NUT_COEF)


def tt_centuries(ets) -> np.ndarray:
    """TT Julian centuries since J2000.0 for SPICE ephemeris times (TDB seconds past J2000)."""
    import spiceypy as sp
    from .kernels import SPICE_LOCK
    ets = np.atleast_1d(np.asarray(ets, dtype=float))
    with SPICE_LOCK:
        tt = np.array([sp.unitim(float(et), "TDB", "TT") for et in ets])
    return tt / SEC_PER_CENTURY


def earth_pole_gcrs(ets) -> tuple[np.ndarray, np.ndarray]:
    """Earth's pole of date (CIP) in GCRS/J2000 axes at the given ephemeris times, and its time derivative
    (rad/s) from a central difference over POLE_DERIV_STEP_S (the CIP moves by about 1e-12 rad/s)."""
    ets = np.atleast_1d(np.asarray(ets, dtype=float))
    t = tt_centuries(ets)
    h = POLE_DERIV_STEP_S / SEC_PER_CENTURY
    zz = cip_gcrs(np.concatenate([t, t + h, t - h]))      # one evaluation for the value and both neighbours
    n = t.size
    z = zz[:n]
    zd = (zz[n:2 * n] - zz[2 * n:]) / (2.0 * POLE_DERIV_STEP_S)
    return z, zd
