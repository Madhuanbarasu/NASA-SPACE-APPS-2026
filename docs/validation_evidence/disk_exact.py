"""Independent exact spherical reference for disk quantities (diagnostic, not part of the project).

For a cap of angular radius rho centred at (az, el) and a piecewise-linear horizon H(az):
- g_top = max over the cap of (el_p - H(az_p)); attained on the top arc for each azimuth column.
- g_bot = min over the cap of (el_p - H(az_p)); attained on the bottom arc.
- f = (cap area above H) / (cap area), integrated exactly in elevation per azimuth slice
  (dA = cos(el) d(el) d(az)), with fine azimuth slices.
"""
import math, numpy as np

def cap_column(az, el, rho, azs):
    """For each azimuth in azs (deg), the elevation range [lo, hi] of the cap (NaN if outside)."""
    A, E, r = math.radians(az), math.radians(el), math.radians(rho)
    c = np.array([math.cos(E)*math.sin(A), math.cos(E)*math.cos(A), math.sin(E)])
    a = np.radians(azs)
    # points on meridian at azimuth a: p(e) = (cos e sin a, cos e cos a, sin e); p.c = cos r
    # p.c = cos e (sin a cx + cos a cy) + sin e cz = cos r  -> K cos(e - phi) = cos r
    P = np.sin(a)*c[0] + np.cos(a)*c[1]
    Q = c[2]
    K = np.hypot(P, Q); phi = np.arctan2(Q, P)
    ok = K >= math.cos(r)
    d = np.arccos(np.clip(math.cos(r)/K, -1, 1))
    lo = np.where(ok, phi - d, np.nan); hi = np.where(ok, phi + d, np.nan)
    return np.degrees(lo), np.degrees(hi)

def exact(hp, az, el, rho, n=400001):
    hw = math.degrees(math.asin(min(1.0, math.sin(math.radians(rho))/math.cos(math.radians(el)))))
    azs = az + np.linspace(-hw, hw, n)
    lo, hi = cap_column(az, el, rho, azs)
    m = np.isfinite(lo)
    azs, lo, hi = azs[m], lo[m], hi[m]
    H = hp.at(azs)
    g_top = float(np.max(hi - H)); g_bot = float(np.min(lo - H))
    e1 = np.clip(H, lo, hi)
    vis = np.sin(np.radians(hi)) - np.sin(np.radians(e1))
    tot = np.sin(np.radians(hi)) - np.sin(np.radians(lo))
    da = np.gradient(np.radians(azs))
    f = float(np.sum(vis*da)/np.sum(tot*da))
    return f, g_top, g_bot
