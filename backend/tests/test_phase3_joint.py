"""Phase 3, item 4: exact Sun-Earth joint visibility, and the solar disk fraction fix.

* spherical_cap_lens_area: accuracy against an independent 1-D spherical integral, every branch (concentric,
  contained, disjoint, tangent), continuity across branch boundaries, symmetry, monotonicity, no NaN;
* the Earth occulting radius from the Item 1 ellipse, with a rigorous sandwich bound for the ellipse;
* the joint visible fraction: exact branches and the adaptive three-way integration against independent
  dense references;
* visibility._disk_exact: the asin conditioning fix (visible fraction of partly hidden disks).
"""
from __future__ import annotations

import math

import numpy as np
import pytest
from numba import njit

from conftest import needs_kernels
from earth_helpers import E_AX, N_AX, U_AX, direction, horizon, random_unit, synth_geo
from lunaops.engine.visibility import spherical_cap_lens_area as _lens

GL_X, GL_W = np.polynomial.legendre.leggauss(400)


# ------------------------------------------------------------------ independent references
def lens_reference(r1, r2, d):
    """Cap intersection area by direct integration in polar coordinates about cap 1:
    A = int_0^r1 2 Phi(rho) sin(rho) d rho, Phi the half-angle of the circle of radius rho inside cap 2.
    Phi is pi below r2 - d (if positive) and 0 beyond d + r2; between, it has square-root ends, removed by
    rho = b1 + (b2 - b1)(1 - cos th)/2, then 400-point Gauss-Legendre in th. Half-angle forms throughout
    (1 - cos x = 2 sin^2(x/2)), so small caps keep full relative precision."""
    hv = lambda x: np.sin(0.5 * x) ** 2                                 # noqa: E731
    if d < 1e-300:
        return cap(min(r1, r2))
    area = 0.0
    full = min(r1, r2 - d)
    if full > 0:
        area += cap(full)
    b1, b2 = abs(d - r2), min(r1, d + r2)
    if b2 > b1:
        th = 0.5 * math.pi * (GL_X + 1.0)
        rho = b1 + (b2 - b1) * 0.5 * (1 - np.cos(th))
        drho = (b2 - b1) * 0.5 * np.sin(th) * 0.5 * math.pi
        num = 2 * (hv(rho) + hv(d) - hv(r2)) - 4 * hv(rho) * hv(d)        # cos r2 - cos rho cos d
        phi = np.arccos(np.clip(num / (np.sin(rho) * math.sin(d)), -1, 1))
        area += float(np.sum(GL_W * 2 * phi * np.sin(rho) * drho))
    return area


def cap(r):
    return 4 * math.pi * math.sin(0.5 * r) ** 2


def strip_reference(hp, sun, earth_r, earth, n=2_000_000, terrain=True, limb=None):
    """Visible solar fraction above the horizon (if terrain) and outside Earth, from n azimuth strips evaluated
    with NumPy (independent of the numba integrator). Earth is a circle of radius earth_r (deg) or, with
    limb, the exact ellipse, whose elevation range per azimuth is interpolated from 4e5 dense limb samples."""
    az_s, el_s, rs = (math.radians(sun[k]) for k in ("az", "el", "rho"))
    hw = math.asin(math.sin(rs) / math.cos(el_s))
    x = -hw + (np.arange(n) + 0.5) * (2 * hw / n)

    def hilo(x, E, r):
        K2 = (np.cos(E) * np.cos(x)) ** 2 + math.sin(E) ** 2
        phi = np.arctan2(math.sin(E), math.cos(E) * np.cos(x))
        dd = np.arctan2(np.sqrt(np.maximum(K2 - math.cos(r) ** 2, 0)), math.cos(r))
        inside = K2 >= math.cos(r) ** 2
        return phi - dd, phi + dd, inside
    lo, hi, _ = hilo(x, el_s, rs)
    L = np.maximum(lo, np.radians(hp.at(np.degrees(az_s + x)))) if terrain else lo
    v = np.maximum(0.0, np.sin(hi) - np.sin(np.minimum(L, hi)))
    if limb is None:
        az_e, el_e, re = math.radians(earth["az"]), math.radians(earth["el"]), math.radians(earth_r)
        xe = (az_s + x - az_e + math.pi) % (2 * math.pi) - math.pi
        elo, ehi, ins = hilo(xe, el_e, re)
        ins &= np.abs(xe) < math.pi / 2
    else:
        t = np.linspace(0, 2 * np.pi, 400_000, endpoint=False)
        q = limb[0][None] + np.cos(t)[:, None] * limb[1] + np.sin(t)[:, None] * limb[2]
        el_l = np.arcsin(q[:, 2] / np.linalg.norm(q, axis=1))
        ar = (np.arctan2(q[:, 0], q[:, 1]) - az_s + math.pi) % (2 * math.pi) - math.pi
        i0, i1 = int(np.argmin(ar)), int(np.argmax(ar))
        idx = np.arange(t.size)
        arcs = [np.roll(idx, -i0)[: (i1 - i0) % t.size + 1], np.roll(idx, -i1)[: (i0 - i1) % t.size + 1]]
        cur = []
        for arc in arcs:
            o = np.argsort(ar[arc])
            cur.append(np.interp(x, ar[arc][o], el_l[arc][o]))
        elo, ehi = np.minimum(cur[0], cur[1]), np.maximum(cur[0], cur[1])
        ins = (x > ar[i0]) & (x < ar[i1])
    a, b = np.maximum(L, elo), np.minimum(hi, ehi)
    v -= np.where(ins & (b > a), np.sin(b) - np.sin(np.minimum(a, b)), 0.0)
    return float(np.sum(v) * (2 * hw / n) / cap(rs))


# ------------------------------------------------------------------ lens: accuracy
def test_lens_matches_independent_integral():
    """Relative 1e-9 over a grid of radii (both r_s < r_e and r_s > r_e) and separations across every regime."""
    from lunaops.engine.visibility import spherical_cap_lens_area
    worst = 0.0
    for r1 in np.radians([0.01, 0.2666, 0.95, 5.0, 30.0]):
        for r2 in np.radians([0.02, 0.2666, 0.95, 3.0, 45.0]):
            for frac in np.linspace(0.0, 1.05, 43):
                d = frac * (r1 + r2)
                A = spherical_cap_lens_area(r1, r2, d)
                R = lens_reference(r1, r2, d)
                small = cap(min(r1, r2))
                assert abs(A - R) <= 1e-9 * small, (r1, r2, d, A, R)
                worst = max(worst, abs(A - R) / small)
    print(f"lens vs integral: worst relative error {worst:.1e}")


def test_lens_small_angle_limit_is_planar():
    """At 0.01 deg the spherical lens equals the planar formula to 1e-6 relative. (At 1 deg caps the spherical
    correction is O(r^2) ~ 1e-4, which is why the planar formula was replaced.)"""
    from lunaops.engine.visibility import circle_overlap_fraction, spherical_cap_lens_area
    rs, re = math.radians(0.01), math.radians(0.035)
    for frac in np.linspace(0.05, 0.95, 19):
        d = (rs + re) * frac + abs(re - rs) * (1 - frac)
        sph = spherical_cap_lens_area(rs, re, d) / cap(rs)
        pla = circle_overlap_fraction(rs, re, d)
        assert abs(sph - pla) <= 1e-6 * max(pla, 1e-3), (frac, sph, pla)
    rs, re = math.radians(0.27), math.radians(0.95)
    d = 0.5 * (rs + re + abs(re - rs))
    assert abs(spherical_cap_lens_area(rs, re, d) / cap(rs) - circle_overlap_fraction(rs, re, d)) > 1e-6


# ------------------------------------------------------------------ lens: edge cases
def test_lens_branches_and_tangencies():
    from lunaops.engine.visibility import spherical_cap_lens_area as L
    rs, re = math.radians(0.2666), math.radians(0.95)
    for a, b in ((rs, re), (re, rs)):
        small = cap(min(a, b))
        assert L(a, b, 0.0) == small and L(a, b, 1e-16) == small                      # concentric
        assert L(a, b, 0.5 * abs(a - b)) == small                                     # contained
        assert L(a, b, a + b) == 0.0 and L(a, b, 1.5 * (a + b)) == 0.0               # tangent / disjoint
        ext, inn = a + b, abs(a - b)
        for d in (np.nextafter(ext, 0), np.nextafter(np.nextafter(ext, 0), 0), ext * (1 - 1e-12)):
            v = L(a, b, d)
            assert math.isfinite(v) and 0.0 <= v <= 1e-12 * small, (d, v)             # just inside external
        for d in (np.nextafter(inn, 1), inn * (1 + 1e-12)):
            v = L(a, b, d)
            assert math.isfinite(v) and abs(v - small) <= 1e-12 * small, (d, v)       # just past internal
    r = math.radians(0.5)                                  # equal radii, d -> 0: A = cap - 2 r d (1 + O(d, r^2))
    for d in (1e-15, 1e-14, 1e-12, 1e-9, 1e-6):
        v = L(r, r, d)
        assert abs(v - lens_reference(r, r, d)) <= 1e-10 * cap(r), d          # reference: arccos near 1
        if d >= 1e-12:                                     # below that the concentric branch (error 2 r d)
            assert abs((cap(r) - v) - 2 * r * d) <= 1e-4 * 2 * r * d, d
    v = L(r, r, r)                                                                   # r_s = r_e = gamma
    assert abs(v - lens_reference(r, r, r)) <= 1e-12 * cap(r)


def test_lens_is_continuous_across_every_branch_boundary():
    from lunaops.engine.visibility import spherical_cap_lens_area as L
    rng = np.random.default_rng(4)
    for _ in range(2000):
        a, b = np.radians(rng.uniform(0.01, 5.0, 2))
        small = cap(min(a, b))
        for edge in (a + b, abs(a - b)):
            if edge <= 0:
                continue
            lo, hi = L(a, b, edge * (1 - 1e-13)), L(a, b, edge * (1 + 1e-13))
            assert abs(lo - hi) <= 1e-12 * small, (a, b, edge, lo, hi)


@njit(cache=False)
def _batch(r1, r2, d, out):
    for i in range(r1.shape[0]):
        out[i] = _lens(r1[i], r2[i], d[i])


def test_lens_safety_symmetry_monotonicity_on_a_million_cases():
    """No NaN on 1e6 random cases including degenerate values; A(r1, r2, d) = A(r2, r1, d) to 1e-15 relative;
    A never above the smaller cap; A non-increasing in d."""
    from lunaops.engine.visibility import spherical_cap_lens_area as L
    rng = np.random.default_rng(8)
    n = 1_000_000
    r1 = np.radians(rng.uniform(1e-6, 10.0, n))
    r2 = np.radians(rng.uniform(1e-6, 10.0, n))
    mode = rng.integers(0, 5, n)
    d = np.where(mode == 0, rng.uniform(0, 1.2, n) * (r1 + r2),
        np.where(mode == 1, r1 + r2, np.where(mode == 2, np.abs(r1 - r2), np.where(mode == 3, 0.0,
                 np.abs(r1 - r2) * (1 + rng.choice([-1, 1], n) * 1e-15)))))
    a, b = np.empty(n), np.empty(n)
    with np.errstate(all="raise"):
        _batch(r1, r2, d, a)
        _batch(r2, r1, d, b)
    assert np.all(np.isfinite(a))
    small = 4 * np.pi * np.sin(0.5 * np.minimum(r1, r2)) ** 2
    assert np.all(a >= 0) and np.all(a <= small * (1 + 1e-15))
    assert np.all(np.abs(a - b) <= 1e-15 * small + 1e-300)
    for _ in range(300):                                    # monotone in d
        x, y = np.radians(rng.uniform(0.01, 3.0, 2))
        ds = np.linspace(0, x + y, 2001)
        v = np.array([L(x, y, t) for t in ds])
        assert np.all(np.diff(v) <= 1e-15 * cap(min(x, y)))


# ------------------------------------------------------------------ Earth occulting radius
def _eclipse_geometry(rng):
    """Synthetic Sun near a random oblate Earth (ENU basis = body frame)."""
    d = rng.uniform(356_000.0, 407_000.0)
    az_e, el_e = rng.uniform(0, 360), rng.uniform(-5, 40)
    g = synth_geo(az_e, el_e, d, random_unit(rng))
    return g


def test_limb_radius_toward_matches_dense_limb():
    """The closed-form limb radius toward a direction equals dense limb sampling (interpolated in position
    angle) to 1e-12 rad."""
    from lunaops.engine.visibility import earth_limb_enu, limb_radius_toward
    rng = np.random.default_rng(2)
    for _ in range(50):
        g = _eclipse_geometry(rng)
        limb = earth_limb_enu(g)
        c = direction(g["az"], g["el"])
        up = U_AX - (U_AX @ c) * c
        up /= np.linalg.norm(up)
        east = np.cross(up, c)
        t = np.linspace(0, 2 * np.pi, 400_000, endpoint=False)
        q = limb[0][None] + np.cos(t)[:, None] * limb[1] + np.sin(t)[:, None] * limb[2]
        q /= np.linalg.norm(q, axis=1)[:, None]
        r = np.arctan2(np.linalg.norm(np.cross(q, c), axis=1), q @ c)
        psi = np.arctan2(q @ east, q @ up)
        o = np.argsort(psi)
        for p in rng.uniform(-np.pi, np.pi, 20):
            dirn = math.cos(0.01) * c + math.sin(0.01) * (math.cos(p) * up + math.sin(p) * east)
            got = limb_radius_toward(limb, c, dirn[None])[0]
            ref = np.interp(p, psi[o], r[o], period=2 * np.pi)
            assert abs(got - ref) < 1e-12, (got, ref)
            assert g["beta"] - 1e-12 <= got <= g["alpha"] + 1e-12


def test_ellipse_occultation_is_sandwiched_and_exact():
    """The share of the Sun behind the true Earth ellipse (dense ray-spheroid test over the solar cap) lies
    between the lens values for the smallest and largest limb radius over the solar points. The engine's
    exact-ellipse occ agrees with that dense test to its sampling resolution. The radius-toward-the-Sun circle
    of the original plan is printed for comparison: it is off by up to ~2e-4, which is why the engine
    integrates the exact ellipse instead."""
    from lunaops.engine.visibility import disk_state, sun_joint_state
    from lunaops import settings
    from lunaops.engine.visibility import earth_limb_enu, limb_radius_toward, spherical_cap_lens_area
    a, _, b = settings.EARTH_RADII_KM
    rng = np.random.default_rng(6)
    rs = math.radians(0.2666)
    worst_bound = worst_err = worst_eng = 0.0
    for _ in range(40):
        pole = random_unit(rng)
        d = rng.uniform(356_000.0, 407_000.0)
        g = synth_geo(30.0, 10.0, d, pole)
        limb = earth_limb_enu(g)
        c = direction(30.0, 10.0)
        re_mean = 0.5 * (g["rho_up"] + g["rho_down"])
        gamma = rng.uniform(abs(re_mean - rs) * 0.5, re_mean + rs)
        p = rng.uniform(0, 2 * np.pi)
        up = U_AX - (U_AX @ c) * c
        up /= np.linalg.norm(up)
        east = np.cross(up, c)
        s = math.cos(gamma) * c + math.sin(gamma) * (math.cos(p) * up + math.sin(p) * east)
        # dense solar cap points (area-weighted rings)
        nr, na = 600, 1200
        edges = rs * np.sqrt(np.arange(nr + 1) / nr)
        mids = 0.5 * (edges[:-1] + edges[1:])
        wr = 2 * np.pi * (np.cos(edges[:-1]) - np.cos(edges[1:])) / na
        t1 = np.cross(s, U_AX)
        t1 /= np.linalg.norm(t1)
        t2 = np.cross(s, t1)
        ph = (np.arange(na) + 0.5) * 2 * np.pi / na
        R, P = np.meshgrid(mids, ph, indexing="ij")
        pts = (np.cos(R)[..., None] * s + np.sin(R)[..., None] * (np.cos(P)[..., None] * t1
                                                                  + np.sin(P)[..., None] * t2)).reshape(-1, 3)
        w = np.repeat(wr, na)
        # ray-spheroid test: observer at origin, Earth centre r, pole z
        r = g["r"]
        z = pole / np.linalg.norm(pole)
        def sc(v):
            vz = v @ z
            return v - np.outer(vz, z), vz
        vp, vz = sc(pts)
        wp, wz = sc(-r[None])
        A_ = np.sum(vp * vp, 1) / a ** 2 + vz ** 2 / b ** 2
        B_ = 2 * (np.sum(vp * wp, 1) / a ** 2 + vz * wz / b ** 2)
        C_ = np.sum(wp * wp, 1) / a ** 2 + wz ** 2 / b ** 2 - 1
        hit = B_ * B_ - 4 * A_ * C_ >= 0
        occ_true = float(np.sum(w * hit) / np.sum(w))
        rad = limb_radius_toward(limb, c, pts)
        rmin, rmax = float(rad.min()), float(rad.max())
        o_lo = spherical_cap_lens_area(rs, rmin, gamma) / cap(rs)
        o_hi = spherical_cap_lens_area(rs, rmax, gamma) / cap(rs)
        o_dir = spherical_cap_lens_area(rs, float(limb_radius_toward(limb, c, s[None])[0]), gamma) / cap(rs)
        grid_err = 3e-4                                       # area-sampling resolution of the dense reference
        assert o_lo - grid_err <= occ_true <= o_hi + grid_err
        assert o_lo <= o_dir <= o_hi
        az_s = math.degrees(math.atan2(s[0], s[1])) % 360
        sun = {"az": az_s, "el": math.degrees(math.asin(s[2])), "rho": math.degrees(rs), "gamma": math.degrees(gamma)}
        earth = {"az": 30.0, "el": 10.0, "rho": math.degrees(re_mean), "limb": limb}
        hp = horizon("flat", 0.0, -40.0)
        js = sun_joint_state(hp, sun, earth, disk_state(hp, sun["az"], sun["el"], sun["rho"]))
        assert abs(js["occ"] - occ_true) <= grid_err, (js["occ"], occ_true)
        worst_bound = max(worst_bound, o_hi - o_lo)
        worst_err = max(worst_err, abs(o_dir - occ_true))
        worst_eng = max(worst_eng, abs(js["occ"] - occ_true))
    print(f"ellipse occ: engine vs dense ray test {worst_eng:.1e} (grid resolution); radius-toward-Sun circle "
          f"would differ by {worst_err:.1e} (sandwich width up to {worst_bound:.1e})")


# ------------------------------------------------------------------ joint fraction
def _sun_earth(gamma_deg, pa_deg, el_s=8.0, az_s=120.0, rs=0.2666, re=0.95):
    sun = {"az": az_s, "el": el_s, "rho": rs, "gamma": gamma_deg}
    c = direction(az_s, el_s)
    up = U_AX - (U_AX @ c) * c
    up /= np.linalg.norm(up)
    east = np.cross(up, c)
    g, p = math.radians(gamma_deg), math.radians(pa_deg)
    e = math.cos(g) * c + math.sin(g) * (math.cos(p) * up + math.sin(p) * east)
    earth = {"az": math.degrees(math.atan2(e[0], e[1])) % 360, "el": math.degrees(math.asin(e[2])), "rho": re}
    return sun, earth


def test_joint_exact_branches_match_dense_reference():
    """Each exact branch is chosen only where its condition holds and agrees with an independent 2e6-strip
    reference to 1e-8; the adaptive three-way branch agrees to 1e-8 as well (its tolerance is 1e-5; with every
    limb crossing and horizon node cut it converges far below that)."""
    from lunaops.engine.visibility import disk_state, sun_joint_state
    seen = set()
    rng = np.random.default_rng(10)
    for _ in range(160):
        gamma, pa = rng.uniform(0.0, 1.3), rng.uniform(0, 360)
        sun, earth = _sun_earth(gamma, pa)
        level = sun["el"] + rng.choice([-3.0, -0.2, 0.0, 0.1, 3.0]) + rng.uniform(-0.3, 0.3)
        hp = horizon(("flat", "sloped", "notched")[rng.integers(3)], sun["az"], level, rng.uniform(-1, 1),
                     rng.uniform(0, 1), 0.4, sun["az"] + rng.uniform(-0.5, 0.5))
        st = disk_state(hp, sun["az"], sun["el"], sun["rho"])
        js = sun_joint_state(hp, sun, earth, st)
        seen.add(js["method"].split(" (")[0] if js["method"].startswith("adaptive") else js["method"])
        if js["method"].startswith("exact") or js["method"] == "no overlap":
            ref = strip_reference(hp, sun, earth["rho"], earth)
            assert abs(js["f"] - ref) <= 1e-8, (js["method"], js["f"], ref, gamma, level)
        else:
            ref = strip_reference(hp, sun, earth["rho"], earth)
            assert abs(js["f"] - ref) <= 1e-8, (js["method"], js["f"], ref, js["err"])
    assert {"no overlap", "exact: hidden", "exact: terrain clear; occ lens", "exact: overlap above terrain; occ lens",
            "exact: overlap below terrain", "adaptive strips"} <= seen, seen


def test_joint_occultation_without_terrain_is_the_lens():
    """Terrain far below and a circular Earth: occ is the spherical lens exactly, f = 1 - occ, and the adaptive
    integrator (an independent route) reproduces 1 - occ to 1e-9."""
    from lunaops.engine.visibility import disk_state, joint_fraction, spherical_cap_lens_area, sun_joint_state
    hp = horizon("flat", 0.0, -40.0)
    rs, re = math.radians(0.2666), math.radians(0.95)
    for gamma in (0.0, 0.3, 0.6833, 0.6834, 0.9, 1.2, 1.2165, 1.2166 - 1e-9, 1.2167):
        sun, earth = _sun_earth(gamma, 33.0)
        st = disk_state(hp, sun["az"], sun["el"], sun["rho"])
        js = sun_joint_state(hp, sun, earth, st)
        occ = spherical_cap_lens_area(rs, re, math.radians(gamma)) / cap(rs)
        assert js["occ"] == pytest.approx(occ, abs=1e-15), gamma
        assert js["f"] == pytest.approx(1 - occ, abs=1e-15), gamma
        if 0 < occ < 1:
            f_int, err, _ = joint_fraction(hp, sun, earth, use_terrain=False, tol=1e-10)
            assert abs(f_int - (1 - occ)) <= 1e-9, (gamma, f_int, 1 - occ, err)


def test_adaptive_three_way_converges_and_reports_its_error():
    """Three-way cases (terrain and Earth both cut the Sun): the adaptive result is within 1e-8 of an independent
    4e6-strip reference (tolerance 1e-5), and its error estimate is below the tolerance."""
    from lunaops.engine.visibility import JOINT_TOL, disk_state, sun_joint_state
    rng = np.random.default_rng(12)
    n = 0
    while n < 30:
        sun, earth = _sun_earth(rng.uniform(0.75, 1.15), rng.uniform(0, 360))
        hp = horizon("sloped", sun["az"], sun["el"] + rng.uniform(-0.2, 0.2), rng.uniform(-1.5, 1.5))
        st = disk_state(hp, sun["az"], sun["el"], sun["rho"])
        js = sun_joint_state(hp, sun, earth, st)
        if not js["method"].startswith("adaptive"):
            continue
        n += 1
        ref = strip_reference(hp, sun, earth["rho"], earth, n=4_000_000)
        assert abs(js["f"] - ref) <= 1e-8, (js, ref)
        assert js["err"] < JOINT_TOL


def test_g_vis_contacts_unchanged():
    """Terrain far below: the combined clearance still equals gamma + rho_sun - rho_earth exactly (V-08)."""
    from lunaops.engine.visibility import disk_state, sun_vis_clearance
    hp = horizon("flat", 0.0, -30.0)
    for gamma in (0.10, 0.6, 0.68, 0.70, 1.1):
        sun = {"az": 40.0, "el": 10.0, "rho": 0.2667, "gamma": gamma}
        earth = {"az": 40.0, "el": 10.0 + gamma, "rho": 0.95}
        st = disk_state(hp, 40.0, 10.0, 0.2667)
        assert abs(sun_vis_clearance(hp, sun, earth, st) - (gamma + 0.2667 - 0.95)) < 1e-9


# ------------------------------------------------------------------ solar disk fraction fix
def test_disk_exact_visible_fraction_regression():
    """Before the fix, asin(q) at the cap's azimuth extremes (q -> +-1) and a separately rounded sqrt term made
    the visible fraction of this partly hidden Sun 0.4050631 instead of 0.4051626."""
    from lunaops.engine.visibility import _disk_exact
    hp = horizon("sloped", 259.11775591596137, 8.817694572419772, 0.9177874259672132, 0.4895451460686505,
                 0.7378971468482601, 258.787577019352)
    f = _disk_exact(hp.h, hp.inc, hp.bin, 259.11775591596137, 8.763336903992483, 0.2666)[0]
    assert abs(f - 0.40516256212119445) < 1e-9, f


def test_disk_exact_agrees_with_the_independent_kernel():
    """Sun-sized and Earth-sized circles on random flat, sloped, notched and two-notch horizons: the closed form
    agrees with the independent exact-limb kernel (engine.earth on an exact cone) to 1e-9 in f and 1e-12 rad in
    the clearances."""
    from lunaops.engine.earth import cap_limb, earth_disk_kernel
    from lunaops.engine.visibility import _disk_exact
    rng = np.random.default_rng(1)
    worst_f = worst_g = 0.0
    for k in range(3000):
        az, el = rng.uniform(0, 360), rng.uniform(-5, 30)
        rho = math.radians(rng.choice([0.2666, 0.95]))
        kind = ("flat", "sloped", "notched", "two_notch")[k % 4]
        hp = horizon(kind, az, el + rng.uniform(-1.3, 1.3) * math.degrees(rho), rng.uniform(-2, 2),
                     rng.uniform(0, 2) * math.degrees(rho), rng.uniform(0.05, 1), az + rng.uniform(-1, 1))
        Q0, QA, QB = cap_limb(az, el, rho, E_AX, N_AX, U_AX)
        gt, gb, f, *_ = earth_disk_kernel(Q0, QA, QB, U_AX, E_AX, N_AX, math.radians(az), math.radians(el), hp.h,
                                          hp.inc, hp.bin, True, 64, 1e-14, 60)
        f2, gt2, gb2, *_ = _disk_exact(hp.h, hp.inc, hp.bin, az, el, math.degrees(rho))
        worst_f = max(worst_f, abs(f - f2))
        worst_g = max(worst_g, abs(math.radians(gt2) - gt), abs(math.radians(gb2) - gb))
    assert worst_f < 1e-9, worst_f
    assert worst_g < 1e-12, worst_g
    print(f"_disk_exact vs exact-limb kernel: f {worst_f:.1e}, g {worst_g:.1e} rad")


# ------------------------------------------------------------------ real eclipse, keys
@needs_kernels
def test_real_eclipse_joint_fraction(kernels):
    """Across the 3 March 2026 eclipse seen from (80 S, 0) and (0, 60 E) (Sun at about 10 and 35 deg), with
    horizons cutting the Sun: occ (exact ellipse) and f within 1e-8 of the independent
    exact-ellipse strip reference at every overlapping sample. The width of the circle sandwich (how far a
    single-radius Earth could be off) is reported."""
    from lunaops.engine.ephem import Site, earth_geo, sample_target, separation_deg
    from lunaops.engine.timeutil import parse_utc
    from lunaops.engine.visibility import (disk_state, earth_limb_enu, limb_radius_toward, spherical_cap_lens_area,
                                           sun_joint_state)
    ets = np.arange(parse_utc("2026-03-03T09:00:00Z"), parse_utc("2026-03-03T14:00:00Z"), 600.0)
    worst_bound = worst_f = worst_occ = 0.0
    n_overlap = 0
    methods = set()
    cases = []
    for lat, lon in ((-80.0, 0.0), (0.0, 60.0)):
        site = Site(lat, lon, 0.0, 0.0)
        s, e = sample_target(site, "sun", ets), sample_target(site, "earth", ets)
        gam, _ = separation_deg(s, e)
        for i in range(ets.size):
            for dz, slope in ((0.05, 0.7), (-0.15, -1.2), (-5.0, 0.0)):
                cases.append((s, e, gam, i, dz, slope))
    for s, e, gam, i, dz, slope in cases:
        hp = horizon("sloped", float(s.az[i]), float(s.el[i]) + dz, slope)
        sun = {"az": float(s.az[i]), "el": float(s.el[i]), "rho": float(s.rho[i]), "gamma": float(gam[i])}
        limb = earth_limb_enu(earth_geo(e, i))
        earth = {"az": float(e.az[i]), "el": float(e.el[i]), "rho": float(e.rho[i]), "limb": limb}
        st = disk_state(hp, sun["az"], sun["el"], sun["rho"])
        js = sun_joint_state(hp, sun, earth, st)
        if js["method"] == "no overlap":
            continue
        n_overlap += 1
        methods.add(js["method"].split(" (")[0])
        ref_occ = 1 - strip_reference(hp, sun, None, earth, n=2_000_000, terrain=False, limb=limb)
        assert abs(js["occ"] - ref_occ) <= 1e-8, (i, js["occ"], ref_occ)
        worst_occ = max(worst_occ, abs(js["occ"] - ref_occ))
        if sun["el"] <= 60.0 and np.isfinite(js["f"]):
            ref = strip_reference(hp, sun, None, earth, n=2_000_000, limb=limb)
            assert abs(js["f"] - ref) <= 1e-8, (i, js, ref)
            worst_f = max(worst_f, abs(js["f"] - ref))
        c = direction(earth["az"], earth["el"])
        sv = direction(sun["az"], sun["el"])
        t1 = np.cross(sv, U_AX) / np.linalg.norm(np.cross(sv, U_AX))
        t2 = np.cross(sv, t1)
        rr = math.radians(sun["rho"])
        ring = np.array([math.cos(rr) * sv + math.sin(rr) * (math.cos(p) * t1 + math.sin(p) * t2)
                         for p in np.linspace(0, 2 * np.pi, 720, endpoint=False)] + [sv])
        rad = limb_radius_toward(limb, c, ring)
        gr = math.radians(sun["gamma"])
        b = (spherical_cap_lens_area(rr, rad.max(), gr) - spherical_cap_lens_area(rr, rad.min(), gr)) / cap(rr)
        worst_bound = max(worst_bound, b)
    assert n_overlap >= 50
    assert {"adaptive strips", "exact: hidden"} <= methods and any(m.startswith("exact: terrain clear") for m in methods)
    print(f"real eclipse: {n_overlap} overlapping samples, methods {sorted(methods)}; occ vs reference "
          f"{worst_occ:.1e}, f vs reference {worst_f:.1e}; single-radius sandwich width up to {worst_bound:.1e}")


@needs_kernels
def test_joint_parameters_are_in_the_result_key(monkeypatch, kernels, synthetic_crater):
    from lunaops.engine import visibility
    from lunaops.engine.analysis import AnalysisRequest, result_id
    req = AnalysisRequest(lat=-89.0, lon=45.0, start_utc="2026-11-14T00:00:00Z", end_utc="2026-11-15T00:00:00Z")
    rid = result_id(req)
    for name, value in (("JOINT_TOL", 1e-6), ("OCC_TOL", 1e-8), ("JOINT_STRIPS", (512, 1 << 16)),
                        ("LENS_CONCENTRIC_RAD", 1e-14), ("JOINT_METHOD_VERSION", "x")):
        old = getattr(visibility, name)
        monkeypatch.setattr(visibility, name, value)
        assert result_id(req) != rid, name
        monkeypatch.setattr(visibility, name, old)
        assert result_id(req) == rid
