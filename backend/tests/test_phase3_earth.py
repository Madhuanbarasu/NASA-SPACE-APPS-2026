"""Phase 3, item 1: Earth as an oblate spheroid (IERS 2010) with the frozen J2000 mean pole.

Upper and lower limbs are validated separately against SPICE edlimb; the full-limb deviation from a circle,
the rigorous cap bounds E_f / E_g and the frozen-pole bounds (P1 angles, P2 clearances, P3 area fraction)
are property-tested; the full-ellipse disk quantities are checked against an independent dense reference.
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from conftest import needs_kernels
from earth_helpers import (E_AX, N_AX, U_AX, dense_extremum, direction, el_az, horizon, limb_q, pole_axis_frame,
                           random_case, random_unit, ref_clearance, ref_fraction, rotate_toward, synth_geo)

SITES = [(-89.5, 0.0), (-85.0, 120.0), (-60.0, 200.0), (-20.0, 300.0)]
N_PROPERTY = 10_000


def _epochs(n):
    import spiceypy as sp
    t0, t1 = sp.str2et("2025-01-01T00:00:00"), sp.str2et("2043-08-01T00:00:00")   # one 18.6 yr nodal cycle
    return np.linspace(t0, t1, n) + 3671.3


def _spice_limb(ks, t, i):
    """Observer->limb vectors (body frame) of SPICE edlimb's ellipse for sample i, as a function of t. The
    spheroid's axis is the engine's pole for that sample (the CIP of date since Phase 4; it was the J2000 Z axis
    while the pole was frozen), so edlimb is checked for the same Earth orientation."""
    import spiceypy as sp
    from lunaops import settings

    a, _, b = settings.EARTH_RADII_KM
    r = t.unit[i] * t.dist_km[i]
    M = pole_axis_frame(t.earth["pole"][i])                     # body -> Earth-axis frame (z = the pole)
    rJ = M @ r
    c, smaj, smin = (np.asarray(x) for x in sp.el2cgv(sp.edlimb(a, a, b, -rJ)))

    def q(tt):
        tt = np.asarray(tt, dtype=float)
        qJ = (rJ + c)[None, :] + np.cos(tt)[:, None] * smaj[None, :] + np.sin(tt)[:, None] * smin[None, :]
        return qJ @ M                                            # back to the body frame (M orthonormal)
    return q


def _sweep(kernels):
    from lunaops.engine.ephem import Site, sample_target
    out = []
    for lat, lon in SITES:
        site = Site(lat, lon, 0.0, 0.0)
        t = sample_target(site, "earth", _epochs(50))
        out.append((site, t))
    return out


# ------------------------------------------------------------------ SPICE validation of both limbs
@needs_kernels
def test_upper_and_lower_limbs_match_spice_edlimb(kernels):
    """At 200 epochs over 18.6 years and four sites, rho_up and rho_down each agree with the SPICE edlimb
    ellipse (dense 1e5-point sampling + golden-section refinement) to 1e-9 rad. Asserted separately."""
    worst_up = worst_dn = 0.0
    for site, t in _sweep(kernels):
        e, n, u = t.earth["basis"]
        for i in range(t.et.size):
            q = _spice_limb(kernels, t, i)

            def el(tt):
                return el_az(q(tt), e, n, u)[0]
            el_c = math.radians(t.el[i])
            up = dense_extremum(el, +1.0) - el_c
            dn = el_c - dense_extremum(el, -1.0)
            worst_up = max(worst_up, abs(t.earth["rho_up"][i] - up))
            worst_dn = max(worst_dn, abs(t.earth["rho_down"][i] - dn))
        assert t.earth["solver_fallbacks"] == 0
    assert worst_up < 1e-9, worst_up
    assert worst_dn < 1e-9, worst_dn


@needs_kernels
def test_full_limb_deviation_matches_spice(kernels):
    """delta_max (max over the whole limb of |angle from the cap centre - rho_cap|) equals the value from dense
    sampling of the SPICE edlimb limb within 1e-12 rad, for the same cap."""
    worst = 0.0
    for site, t in _sweep(kernels):
        e, n, u = t.earth["basis"]
        for i in range(0, t.et.size, 2):
            q = _spice_limb(kernels, t, i)
            ru, rd = t.earth["rho_up"][i], t.earth["rho_down"][i]
            el_o = math.radians(t.el[i]) + 0.5 * (ru - rd)
            az_c = math.radians(t.az[i])
            o = math.cos(el_o) * (math.sin(az_c) * e + math.cos(az_c) * n) + math.sin(el_o) * u
            rho_cap = 0.5 * (ru + rd)

            def ang(tt):
                qq = q(tt)
                return np.arctan2(np.linalg.norm(np.cross(qq, o), axis=1), qq @ o)
            dm = max(dense_extremum(ang, +1.0) - rho_cap, rho_cap - dense_extremum(ang, -1.0))
            worst = max(worst, abs(dm - t.earth["delta_max"][i]))
    assert worst < 1e-12, worst


@needs_kernels
def test_shape_bounds_on_real_geometry(kernels):
    """beta <= rho_up, rho_down <= alpha (intrinsic radii) at every sweep epoch; delta_max ~ (alpha-beta)/2 scale,
    far above the cap tolerance, so the full ellipse is the normal path."""
    from lunaops import settings
    for site, t in _sweep(kernels):
        E = t.earth
        for x in (E["rho_up"], E["rho_down"]):
            assert np.all(x >= E["beta"] - 1e-12) and np.all(x <= E["alpha"] + 1e-12)
        assert np.all(np.degrees(E["delta_max"]) > settings.EARTH_LIMB_TOL_DEG)
        assert np.all(E["delta_max"] <= (E["alpha"] - E["beta"]) + 1e-12)


def test_synthetic_poles_reach_both_shape_extremes():
    """Pole along the line of sight: a circle of radius atan(a / sqrt(d^2 - b^2)) (between beta and alpha;
    delta_max = 0, cap path chosen). Pole perpendicular to it in the vertical plane: rho_up = rho_down =
    atan(b / sqrt(d^2 - a^2)) (>= beta). Pole perpendicular and horizontal: the vertical extent lies in the
    equatorial plane, alpha = asin(a/d) (the upper bound is reached)."""
    from lunaops import settings
    from lunaops.engine.earth import earth_disk_state

    a, _, b = settings.EARTH_RADII_KM
    d, az, el = 384_400.0, 30.0, 5.0
    los = direction(az, el)
    g = synth_geo(az, el, d, los)
    alpha = math.asin(a / d)
    circ = math.atan(a / math.sqrt(d * d - b * b))
    assert math.asin(b / d) < circ < alpha
    assert abs(g["rho_up"] - circ) < 1e-12 and abs(g["rho_down"] - circ) < 1e-12 and g["delta_max"] < 1e-12
    st = earth_disk_state(horizon("flat", az, el - 0.3), g)
    assert st["method"] == "cap"
    vert = direction(az, el + 90.0)                     # perpendicular to the line of sight, in the vertical plane
    g = synth_geo(az, el, d, vert)
    ext = math.atan(b / math.sqrt(d * d - a * a))
    assert abs(g["rho_up"] - ext) < 1e-12 and abs(g["rho_down"] - ext) < 1e-12
    assert ext >= math.asin(b / d)
    assert abs(g["delta_max"] - (alpha - ext)) < 1e-12        # cap = vertical extent; horizontal deviates
    assert earth_disk_state(horizon("flat", az, el - 0.3), g)["method"] == "elliptical"
    side = np.cross(los, vert)                          # perpendicular to the line of sight, horizontal
    g = synth_geo(az, el, d, side)
    assert abs(g["rho_up"] - alpha) < 1e-12 and abs(g["rho_down"] - alpha) < 1e-12


# ------------------------------------------------------------------ full ellipse vs an independent reference
def test_full_ellipse_matches_dense_reference():
    """g_top and g_bot (exact limb against the piecewise-linear horizon) within 1e-12 rad of 1e6-point dense
    sampling; f within 1e-6 of an independent azimuth-strip integration (4e5 strips)."""
    from lunaops.engine.earth import earth_disk_state

    rng = np.random.default_rng(11)
    worst_g = worst_f = 0.0
    n_f = 0
    for _ in range(40):
        geo, hp, kind = random_case(rng)
        st = earth_disk_state(hp, geo, force="ellipse")
        gt, gb = ref_clearance(geo, hp)
        worst_g = max(worst_g, abs(math.radians(st["g_top"]) - gt), abs(math.radians(st["g_bot"]) - gb))
        if not math.isnan(st["f"]) and 0.0 < st["f"] < 1.0:
            worst_f = max(worst_f, abs(ref_fraction(geo, hp) - st["f"]))
            n_f += 1
    assert worst_g < 1e-12, worst_g
    assert worst_f < 1e-6, worst_f
    assert n_f >= 10                                    # partial disks are actually exercised


# ------------------------------------------------------------------ cap bounds (property test)
def test_cap_bounds_hold_on_random_cases():
    """|f_ellipse - f_cap| <= E_f = (dA+ + dA-)/(A_C - dA-) and |g_ellipse - g_cap| <= E_g = delta (1 + S/c_min),
    c identical, on 1e4 random oblate limbs (eccentricity up to 0.2, all orientations) and horizons (flat,
    sloped up to 2, notched, two notches). Numerical floors: 1e-12 rad on g, 1e-9 on f (kernel accuracy). The
    closed-form E_f always exceeds its first-order term in delta, delta sin(rho) / sin^2(rho/2) (the higher-order
    terms only add). (The planar expansion 4 delta / rho is *not* a lower bound on the sphere: E_f is
    4 delta / rho (1 - rho^2/12 + ...), slightly below it.)"""
    from lunaops.engine.earth import cap_area_bound, earth_disk_state

    rng = np.random.default_rng(5)
    tight_g = tight_f = 0.0
    for k in range(N_PROPERTY):
        geo, hp, kind = random_case(rng)
        ell = earth_disk_state(hp, geo, force="ellipse")
        cap = earth_disk_state(hp, geo, force="cap")
        rho_cap = 0.5 * (geo["rho_up"] + geo["rho_down"])
        off = 0.5 * abs(geo["rho_up"] - geo["rho_down"])
        assert off < rho_cap - geo["delta_max"], k               # star-shape precondition
        assert cap["c"] == ell["c"]
        eg = math.radians(ell["E_g_deg"])
        for f in ("g_top", "g_bot"):
            dg = abs(math.radians(cap[f] - ell[f]))
            assert dg <= eg + 1e-12, (k, kind, f, dg, eg)
            tight_g = max(tight_g, dg / max(eg, 1e-300) if eg > 1e-10 else 0.0)
        ef = ell["E_f"]
        assert ef == cap_area_bound(rho_cap, geo["delta_max"])
        if geo["delta_max"] > 0:          # closed form >= its spherical linearisation in delta
            lin = geo["delta_max"] * math.sin(rho_cap) / math.sin(0.5 * rho_cap) ** 2
            assert ef >= lin * (1 - 1e-12), (k, ef, lin)
        if not (math.isnan(cap["f"]) or math.isnan(ell["f"])):
            df = abs(cap["f"] - ell["f"])
            assert df <= ef + 1e-9, (k, kind, df, ef)
            tight_f = max(tight_f, df / ef if ef > 1e-7 else 0.0)
    assert tight_g <= 1.0 and tight_f <= 1.0
    print(f"cap bounds tightness: g {tight_g:.3f}, f {tight_f:.3f}")


def test_decision_rule_uses_the_ellipse_whenever_a_bound_exceeds_tolerance():
    from lunaops import settings
    from lunaops.engine.earth import earth_disk_state

    rng = np.random.default_rng(9)
    for _ in range(300):
        geo, hp, _ = random_case(rng)
        st = earth_disk_state(hp, geo)
        ok = (st["delta_max_deg"] <= settings.EARTH_LIMB_TOL_DEG and st["E_g_deg"] <= settings.EARTH_LIMB_TOL_DEG
              and st["E_f"] < settings.EARTH_F_TOL)
        assert st["method"] == ("cap" if ok else "elliptical")


# ------------------------------------------------------------------ frozen-pole bounds (property test)
def test_frozen_pole_bounds_hold_on_random_rotations():
    """For poles rotated by eps in [1", 1 deg], with eta = (alpha - beta) sin eps:
    (P1) |d rho_up|, |d rho_down| <= eta (1 + 1e-6) + 1e-13 rad; delta_max moves by <= 3 eta (limb points
    and the cap centre each move by <= eta, rho_cap by <= eta);
    (P2) |d g_top|, |d g_bot| <= eta (1 + S/c_min) + 1e-12 rad;
    (P3) |d f| <= E_f,pole(alpha, beta, eta) + 1e-9;
    on 1e4 random geometries and horizons. The measured Lipschitz constant of the limb radii is <= alpha - beta."""
    from lunaops import settings
    from lunaops.engine.earth import earth_disk_state, pole_area_bound

    a = settings.EARTH_RADII_KM[0]
    rng = np.random.default_rng(13)
    worst = {"P1": 0.0, "delta": 0.0, "P2": 0.0, "P3": 0.0}
    for k in range(N_PROPERTY):
        ecc = rng.uniform(0.0, 0.2)
        b = a * math.sqrt(1.0 - ecc * ecc)
        d = rng.uniform(356_000.0, 407_000.0)
        az, el = rng.uniform(0.0, 360.0), rng.uniform(-10.0, 35.0)
        eps = math.radians(10 ** rng.uniform(math.log10(1.0 / 3600.0), 0.0))
        p1 = random_unit(rng)
        p2 = rotate_toward(p1, eps, rng)
        g1, g2 = synth_geo(az, el, d, p1, a, b), synth_geo(az, el, d, p2, a, b)
        eta = (g1["alpha"] - g1["beta"]) * math.sin(eps)
        lim = eta * (1 + 1e-6) + 1e-13
        for f in ("rho_up", "rho_down"):
            dv = abs(g1[f] - g2[f])
            assert dv <= lim, (k, f, dv, eta)
            worst["P1"] = max(worst["P1"], dv / lim)
        dd = abs(g1["delta_max"] - g2["delta_max"])
        assert dd <= 3 * eta + 1e-13, (k, dd, eta)
        worst["delta"] = max(worst["delta"], dd / (eta + 1e-13))
        level = el + rng.uniform(-1.3, 1.3) * math.degrees(g1["alpha"])
        kind = ("flat", "sloped", "notched", "two_notch")[k % 4]
        hp = horizon(kind, az, level, rng.uniform(-2, 2), rng.uniform(0, 2) * math.degrees(g1["alpha"]),
                     rng.uniform(0.05, 1.0), az + rng.uniform(-1, 1))
        s1, s2 = earth_disk_state(hp, g1, force="ellipse"), earth_disk_state(hp, g2, force="ellipse")
        c_min = min(s1["c_min"], s2["c_min"])
        S = max(s1["slope_span"], s2["slope_span"])
        lim2 = eta * (1 + S / c_min) + 1e-12
        for f in ("g_top", "g_bot"):
            dv = abs(math.radians(s1[f] - s2[f]))
            assert dv <= lim2, (k, kind, f, dv, lim2)
            worst["P2"] = max(worst["P2"], dv / lim2)
        assert s1["c"] == s2["c"]
        if not (math.isnan(s1["f"]) or math.isnan(s2["f"])):
            lim3 = pole_area_bound(g1["alpha"], g1["beta"], eta) + 1e-9
            dv = abs(s1["f"] - s2["f"])
            assert dv <= lim3, (k, kind, dv, lim3)
            worst["P3"] = max(worst["P3"], dv / lim3)
    print("frozen-pole bound tightness (max actual / bound):", {k: round(v, 4) for k, v in worst.items()})


def test_pole_bound_reproduces_alpha_minus_beta_epsilon():
    """Kernel-free check: synthetic rotations of 1", 1' and 0.5 deg move the limb radii by at most and close to
    (alpha - beta) eps for the worst-case orientation (pole near the plane of the sky, 45 deg position angle)."""
    from lunaops import settings
    a, _, b = settings.EARTH_RADII_KM
    d, az, el = 384_400.0, 10.0, 3.0
    los = direction(az, el)
    up = direction(az, el + 90.0)
    side = np.cross(los, up)
    p = (up + side) / math.sqrt(2.0)
    for eps_deg in (1 / 3600, 1 / 60, 0.5):
        eps = math.radians(eps_deg)
        p2 = p * math.cos(eps) + np.cross(los, p) * math.sin(eps)     # rotate about the line of sight
        g1, g2 = synth_geo(az, el, d, p), synth_geo(az, el, d, p2)
        eta = (g1["alpha"] - g1["beta"]) * math.sin(eps)
        dv = abs(g1["rho_up"] - g2["rho_up"])
        assert dv <= eta * (1 + 1e-6) + 1e-13
        assert dv >= 0.9 * eta * (1 - eps)                              # the bound is tight here


@needs_kernels
def test_frozen_pole_against_iau_earth(kernels):
    """Per epoch (no precession rate assumed): eps(t) = angle(J2000 Z, IAU_EARTH Z) from pxform with the
    production pck00011; every limb quantity computed with both poles obeys P1/P2/P3 with that epoch's eps.
    Skipped when the loaded kernels define no Earth orientation (the demo set)."""
    import spiceypy as sp
    from lunaops.engine.earth import earth_disk_state, limb_ellipse, limb_extrema, pole_area_bound
    from lunaops.engine.ephem import Site, earth_geo, sample_target
    from lunaops import settings

    try:
        sp.pxform("IAU_EARTH", "J2000", 0.0)
    except Exception:  # noqa: BLE001 - SPICE raises when the PCK lacks BODY399 orientation
        pytest.skip("IAU_EARTH orientation not loaded (production pck00011.tpc not installed)")
    sv = settings.EARTH_SOLVER
    t0, t1 = sp.str2et("2000-01-01T12:00:00"), sp.str2et("2049-12-01T00:00:00")
    ets = np.linspace(t0, t1, 200)
    site = Site(-89.0, 45.0, 0.0, 0.0)
    t = sample_target(site, "earth", ets)
    e, n, u = t.earth["basis"]
    hp = horizon("sloped", float(np.median(t.az)), float(np.median(t.el)), 0.8)
    worst = {"eps_arcsec": 0.0, "P1": 0.0, "P2": 0.0, "P3": 0.0}
    for i, et in enumerate(ets):
        p_j = t.earth["pole"][i]
        p_i = np.asarray(sp.pxform("IAU_EARTH", kernels.frame, float(et)))[:, 2]
        eps = math.acos(min(1.0, float(p_j @ p_i)))
        worst["eps_arcsec"] = max(worst["eps_arcsec"], math.degrees(eps) * 3600)
        r = t.unit[i] * t.dist_km[i]
        Q0, QA, QB = (x[0] for x in limb_ellipse(r[None], p_i[None]))
        ru, rd, dm, _ = limb_extrema(Q0, QA, QB, u, e, n, math.radians(t.el[i]), math.radians(t.az[i]),
                                     sv["bracket"], sv["tol"], sv["maxiter"])
        g1 = earth_geo(t, i)
        g2 = {**g1, "Q0": Q0, "QA": QA, "QB": QB, "rho_up": ru, "rho_down": rd, "delta_max": dm}
        eta = (g1["alpha"] - g1["beta"]) * math.sin(eps)
        for x, y in ((g1["rho_up"], ru), (g1["rho_down"], rd)):
            assert abs(x - y) <= eta * (1 + 1e-6) + 1e-12
            worst["P1"] = max(worst["P1"], abs(x - y))
        s1, s2 = earth_disk_state(hp, g1, force="ellipse"), earth_disk_state(hp, g2, force="ellipse")
        lim2 = eta * (1 + max(s1["slope_span"], s2["slope_span"]) / min(s1["c_min"], s2["c_min"])) + 1e-12
        for f in ("g_top", "g_bot"):
            assert abs(math.radians(s1[f] - s2[f])) <= lim2
            worst["P2"] = max(worst["P2"], abs(math.radians(s1[f] - s2[f])))
        assert s1["c"] == s2["c"]
        if not (math.isnan(s1["f"]) or math.isnan(s2["f"])):
            assert abs(s1["f"] - s2["f"]) <= pole_area_bound(g1["alpha"], g1["beta"], eta) + 1e-9
            worst["P3"] = max(worst["P3"], abs(s1["f"] - s2["f"]))
    assert math.degrees(worst["P1"]) < 1e-5 and math.degrees(worst["P2"]) < 1e-5
    print("IAU_EARTH vs frozen J2000 pole:", worst)


# ------------------------------------------------------------------ solver robustness
def _adversarial():
    """Arbitrary planar ellipses (not from a spheroid): highly tilted, nearly circular, extremely eccentric,
    extrema near t = 0 / 2 pi."""
    rng = np.random.default_rng(3)
    out = []
    centre = 384_400.0 * direction(40.0, 4.0)
    for k in range(60):
        r1 = 6400.0
        r2 = r1 * (10 ** rng.uniform(-3, 0)) if k % 3 else r1 * (1 - 1e-9)
        ax = random_unit(rng)
        ax2 = np.cross(ax, random_unit(rng))
        ax2 /= np.linalg.norm(ax2)
        QA, QB = r1 * ax, r2 * ax2
        if k % 5 == 0:                                   # put the elevation maximum at t ~ 0 (wrap)
            QA = r1 * U_AX + 1e-6 * ax
            QB = r2 * np.cross(U_AX, direction(40.0, 4.0))
        out.append((centre, QA, QB))
    return out


def test_solver_matches_dense_sampling_on_adversarial_ellipses():
    from lunaops import settings
    from lunaops.engine.earth import limb_extrema
    sv = settings.EARTH_SOLVER
    for Q0, QA, QB in _adversarial():
        el_c, az_c = math.radians(4.0), math.radians(40.0)
        ru, rd, dm, fb = limb_extrema(Q0, QA, QB, U_AX, E_AX, N_AX, el_c, az_c, sv["bracket"], sv["tol"],
                                      sv["maxiter"])

        def el(tt):
            return el_az(limb_q(Q0, QA, QB, tt), E_AX, N_AX, U_AX)[0]
        assert abs((el_c + ru) - dense_extremum(el, 1.0, 1_000_000)) < 1e-12
        assert abs((el_c - rd) - dense_extremum(el, -1.0, 1_000_000)) < 1e-12


def test_solver_fallback_branch_is_exercised_and_safe():
    """A clearance with a notch much narrower than the bracket spacing, centred on the best bracket sample:
    Brent converges to the smooth local maximum, the verification rejects it, the 16x denser fallback runs (and
    is counted) and the result is never below any sample of either grid. (On real limbs the disk kernel cuts the
    limb at every horizon node, so such notches never sit inside one piece.)"""
    from lunaops.engine.earth import _global_extremum, _obj
    Q0 = 384_400.0 * N_AX                                 # Earth due north on the horizon
    QA, QB = 6378.0 * U_AX, 6378.0 * E_AX                 # t = 0 top, t = pi/2 east
    binw = 0.01
    h = np.zeros(36000)
    az_s = math.degrees(math.atan2(6378.0 * math.sin(math.pi / 4), 384_400.0))
    k = int(round(az_s / binw))
    h[k - 1:k + 2] = -5.0                                 # notch at the azimuth of the t = pi/4 sample only
    t, v, fb = _global_extremum(3, 1.0, Q0, QA, QB, U_AX, E_AX, N_AX, U_AX, 0.0, h, binw, 8, 1e-14, 60)
    assert fb
    for m in (8, 128):
        grid = max(_obj(3, s, Q0, QA, QB, U_AX, E_AX, N_AX, U_AX, 0.0, h, binw)
                   for s in np.linspace(0, 2 * math.pi, m, endpoint=False))
        assert v >= grid - 1e-15
    # with the notch removed the bracket + Brent path succeeds without the fallback
    t, v, fb = _global_extremum(3, 1.0, Q0, QA, QB, U_AX, E_AX, N_AX, U_AX, 0.0, np.zeros(36000), binw, 64,
                                1e-14, 60)
    assert not fb and abs(v - math.atan2(6378.0, 384_400.0)) < 1e-12


def test_horizon_segment_integral_is_cancellation_free():
    """Regression (found by the pole property test): with H1, H2 equal up to rounding, (cos H1 - cos H2)/k lost
    all digits and doubled a strip's horizon area. The sinc form is exact to rounding."""
    from lunaops.engine.earth import _sin_lin_integral
    H = 0.5216656
    for dH in (0.0, 1e-17, 1e-16, 1e-14, 1e-10, 1e-6, 1e-3, 0.3):
        A1, A2 = 0.01931858, 0.01941986
        got = _sin_lin_integral(H, H + dH, A1, A2)
        k = dH / (A2 - A1)
        exact = math.sin(H + dH / 2) * (A2 - A1) * (1.0 if dH == 0 else math.sin(dH / 2) / (dH / 2))
        assert abs(got - exact) <= 1e-15 * abs(exact), (dH, got, exact)
        if dH > 1e-6:                                     # and the plain closed form where it is well conditioned
            assert abs(got - (math.cos(H) - math.cos(H + dH)) / k) <= 1e-9 * abs(got)


# ------------------------------------------------------------------ Sun unchanged, keys, provenance
@needs_kernels
def test_sun_sampling_is_bitwise_unchanged(kernels):
    """The Sun path of sample_target never touches the Earth model: identical with any Earth settings."""
    from lunaops import settings
    from lunaops.engine.ephem import Site, sample_target
    site = Site(-89.0, 45.0, 0.0, 0.0)
    ets = _epochs(30)
    a = sample_target(site, "sun", ets)
    old = settings.EARTH_RADII_KM
    try:
        settings.EARTH_RADII_KM = (7000.0, 7000.0, 6000.0)
        b = sample_target(site, "sun", ets)
    finally:
        settings.EARTH_RADII_KM = old
    assert a.earth is None and b.earth is None
    for f in ("az", "el", "rho", "dist_km", "az_rate", "el_rate", "rho_rate", "unit", "unit_rate"):
        assert np.array_equal(getattr(a, f), getattr(b, f)), f


@needs_kernels
def test_earth_parameters_are_in_the_result_key(monkeypatch, kernels, synthetic_crater):
    from lunaops import settings
    from lunaops.engine.analysis import AnalysisRequest, result_id
    req = AnalysisRequest(lat=-89.0, lon=45.0, start_utc="2026-11-14T00:00:00Z", end_utc="2026-11-15T00:00:00Z")
    rid = result_id(req)
    for name, value in (("EARTH_RADII_KM", (6378.137, 6378.137, 6356.752)), ("EARTH_POLE_MODEL", "x"),
                        ("EARTH_LIMB_TOL_DEG", 1e-5), ("EARTH_F_TOL", 1e-6),
                        ("EARTH_SOLVER", {"bracket": 32, "tol": 1e-14, "maxiter": 60}),
                        ("CURVATURE_INFLATION", 2.0)):
        old = getattr(settings, name)
        monkeypatch.setattr(settings, name, value)
        assert result_id(req) != rid, name
        monkeypatch.setattr(settings, name, old)
        assert result_id(req) == rid, name


def test_every_earth_setting_is_keyed():
    """Completeness guard: every EARTH_* constant in settings feeds earth_model_settings (the result key),
    except the human-readable pole label, which is fixed by the pole model ID."""
    from lunaops import settings
    from lunaops.engine.earth import earth_model_settings
    keyed = {"EARTH_RADII_KM", "EARTH_POLE_MODEL", "EARTH_LIMB_TOL_DEG", "EARTH_F_TOL", "EARTH_SOLVER"}
    names = {k for k in dir(settings) if k.startswith("EARTH_")}
    assert names - keyed == {"EARTH_POLE_LABEL"}, names - keyed
    em = earth_model_settings()
    assert em["pole_model"] == settings.EARTH_POLE_MODEL and em["radii_km"] == list(settings.EARTH_RADII_KM)


def test_iers_radii_and_pole_label():
    from lunaops import settings
    a, a2, b = settings.EARTH_RADII_KM
    assert a == a2 == 6378.1366
    assert abs(b - 6356.7519) < 1e-4
    assert settings.EARTH_POLE_LABEL.startswith("pole of date (Celestial Intermediate Pole)")
    assert settings.EARTH_POLE_MODEL == "CIP-IAU2006-precession-IAU2000B-nutation"


@needs_kernels
def test_provenance_records_the_earth_model(kernels, synthetic_crater):
    from lunaops import settings
    from lunaops.engine.analysis import AnalysisRequest, analyze
    res = analyze(AnalysisRequest(lat=-89.0, lon=45.0, start_utc="2026-11-14T00:00:00Z",
                                  end_utc="2026-11-15T00:00:00Z"))
    prov = res["provenance"]
    assert prov["earth_pole"] == settings.EARTH_POLE_LABEL
    em = prov["parameters"]["earth_model"]
    assert em["pole_label"] == settings.EARTH_POLE_LABEL and em["solver_fallbacks"] == 0
    assert sum(em["disk_methods"].values()) == len(res["series"]["et"])
    assert em["max_delta_max_deg"] > settings.EARTH_LIMB_TOL_DEG
    # timing margin: a cap-path sample's edge error (<= EARTH_LIMB_TOL_DEG) must cost < 1 s at the edge rate
    assert em["disk_methods"].get("cap", 0) == 0                     # at Earth's oblateness: always the ellipse
