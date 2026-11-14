"""Communication relay geometry: lunaops_comms.relay against independent calculations (read only).

Independent methods (no code shared with the package):
  * propagation: Kepler's equation solved by BISECTION on [M - e - 1, M + e + 1] (not Newton), true anomaly from
    tan(nu/2) = sqrt((1+e)/(1-e)) tan(E/2), radius r = a(1 - e^2)/(1 + e cos nu), position from the classical
    perifocal-to-inertial rotation written out with explicit sines/cosines;
  * identities: orbital period T = 2 pi sqrt(a^3 / GM) closes the orbit (r(t0 + T) = r(t0)); vis-viva |v|^2 = GM (2/r - 1/a);
    specific angular momentum constant;
  * leg 2 (relay -> Earth) line-of-sight clearance: closed-form distance from the Moon's centre to the segment
    relay -> Earth centre (projection clamped to the segment), minus the sphere radius.
Illustrative orbits only (not real spacecraft). Usage: python relay_independent.py <out json>
"""
import json, math, sys
sys.path.insert(0, r"E:\LUNA-OPS\backend")
import numpy as np

from lunaops_comms.constants import moon_gm
from lunaops_comms.relay import Elements, propagate, sphere_clear_km

GM = float(moon_gm()["gm_km3_s2"]) if isinstance(moon_gm(), dict) and "gm_km3_s2" in moon_gm() else None
if GM is None:
    g = moon_gm(); GM = float(next(v for k, v in g.items() if isinstance(v, (int, float)) and 4000 < v < 5000))
R_MOON = 1737.4


def kepler_bisect(M, e):
    lo, hi = M - e - 1.0, M + e + 1.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if mid - e * math.sin(mid) - M > 0:
            hi = mid
        else:
            lo = mid
    return 0.5 * (lo + hi)


def indep_pos(el, t):
    n = math.sqrt(GM / el.a_km ** 3)
    M = math.radians(el.m0_deg) + n * (t - el.epoch_et)
    M = math.atan2(math.sin(M), math.cos(M))
    E = kepler_bisect(M, el.e)
    nu = 2 * math.atan2(math.sqrt(1 + el.e) * math.sin(E / 2), math.sqrt(1 - el.e) * math.cos(E / 2))
    r = el.a_km * (1 - el.e ** 2) / (1 + el.e * math.cos(nu))
    O, i, w = (math.radians(x) for x in (el.raan_deg, el.i_deg, el.argp_deg))
    u = w + nu
    return np.array([r * (math.cos(O) * math.cos(u) - math.sin(O) * math.sin(u) * math.cos(i)),
                     r * (math.sin(O) * math.cos(u) + math.cos(O) * math.sin(u) * math.cos(i)),
                     r * (math.sin(u) * math.sin(i))])


cases = [Elements(6000.0, 0.6, 60.0, 0.0, 90.0, 0.0, 0.0, "J2000"),        # the elliptic illustrative relay used in the UI tests
         Elements(1837.4, 0.0, 90.0, 45.0, 0.0, 30.0, 0.0, "J2000"),       # 100 km circular polar
         Elements(9000.0, 0.75, 85.0, 120.0, 270.0, 200.0, 1000.0, "J2000")]  # frozen-orbit-like, apoapsis over the south pole
out = {"gm_km3_s2": GM, "cases": []}
worst = 0.0
for el in cases:
    T = 2 * math.pi * math.sqrt(el.a_km ** 3 / GM)
    ts = el.epoch_et + np.linspace(0, T, 241)
    rp, vp = propagate(el, ts, GM)
    ind = np.array([indep_pos(el, t) for t in ts])
    dpos = float(np.max(np.linalg.norm(rp - ind, axis=1)))
    r = np.linalg.norm(rp, axis=1); v2 = np.sum(vp * vp, axis=1)
    visviva = float(np.max(np.abs(v2 - GM * (2 / r - 1 / el.a_km)) / (GM / el.a_km)))
    h = np.linalg.norm(np.cross(rp, vp), axis=1)
    closure = float(np.linalg.norm(propagate(el, np.array([el.epoch_et + T]), GM)[0][0] - propagate(el, np.array([el.epoch_et]), GM)[0][0]))
    worst = max(worst, dpos)
    out["cases"].append({"elements": el.__dict__, "period_h": T / 3600, "max_position_diff_km": dpos, "visviva_rel_err_max": visviva,
                         "angular_momentum_rel_spread": float((h.max() - h.min()) / h.mean()), "period_closure_km": closure,
                         "periapsis_alt_km": el.a_km * (1 - el.e) - R_MOON})
    print(f"a={el.a_km} e={el.e} i={el.i_deg}: period {T/3600:.3f} h; |r_pkg - r_indep| max {dpos:.2e} km; vis-viva rel err {visviva:.1e}; "
          f"h spread {(h.max()-h.min())/h.mean():.1e}; closure {closure:.2e} km")

# leg 2: segment relay -> Earth centre, clearance of the 1737.4 km sphere, against a closed form
rng = np.random.default_rng(3)
P0 = rng.normal(size=(500, 3)); P0 = P0 / np.linalg.norm(P0, axis=1)[:, None] * rng.uniform(1800, 12000, (500, 1))
P1 = rng.normal(size=(500, 3)); P1 = P1 / np.linalg.norm(P1, axis=1)[:, None] * 384400.0
pkg = sphere_clear_km(P0, P1, R_MOON)
d = P1 - P0; tt = np.clip(-np.sum(P0 * d, axis=1) / np.sum(d * d, axis=1), 0, 1)
ind = np.linalg.norm(P0 + tt[:, None] * d, axis=1) - R_MOON
dl = float(np.max(np.abs(pkg - ind)))
agree = int(np.sum((pkg > 0) == (ind > 0)))
out["leg2"] = {"samples": 500, "max_clearance_diff_km": dl, "open_blocked_verdicts_agree": agree}
print(f"leg 2 line of sight: 500 random relay/Earth geometries; max clearance difference {dl:.2e} km; open/blocked verdicts agree {agree}/500")
out["worst_position_diff_km"] = worst
json.dump(out, open(sys.argv[1], "w"), indent=1, default=float)
