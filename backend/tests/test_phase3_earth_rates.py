"""Phase 3, item 1: Earth limb rate bounds and event timing.

The detector's r0 for earth_top / earth_bot is the complete edge-clearance derivative bound B (centre elevation
rate, horizon movement under the centre's azimuth motion, limb motion relative to the centre V_limb, the 1/cos el
azimuth scaling and the map term, times the curvature inflation). Finite differences appear only here, in tests:
each term is checked against an independent difference of the quantity it bounds, the total against the
difference of g_top / g_bot on 1e4 cases (including maximiser jumps), and Earth limb events against a brute-force
scan.
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from conftest import needs_kernels
from earth_helpers import el_az, horizon, limb_q, pole_axis_frame

SITE = (-89.0, 45.0)


def _richardson(f, t, taus=(60.0, 30.0, 15.0)):
    """Richardson-extrapolated central difference (two levels) of f at t."""
    d = [(f(t + h) - f(t - h)) / (2 * h) for h in taus]
    d1 = [(4 * d[i + 1] - d[i]) / 3 for i in range(len(d) - 1)]
    return (16 * d1[1] - d1[0]) / 15


def _ets(n, start="2025-01-01T00:00:00", end="2043-08-01T00:00:00"):
    import spiceypy as sp
    return np.linspace(sp.str2et(start), sp.str2et(end), n) + 1234.5


def _site():
    from lunaops.engine.ephem import Site
    return Site(SITE[0], SITE[1], 0.0, 0.0)


# ------------------------------------------------------------------ component checks
@needs_kernels
def test_centre_rates_match_finite_differences(kernels):
    from lunaops.engine.ephem import sample_target
    site = _site()
    for et in _ets(200):
        t = sample_target(site, "earth", [et])

        def el(x):
            return float(sample_target(site, "earth", [x]).el[0])

        def az(x):
            v = float(sample_target(site, "earth", [x]).az[0])
            return (v - t.az[0] + 180.0) % 360.0 - 180.0
        for ana, fd in ((t.el_rate[0], _richardson(el, et)), (t.az_rate[0], _richardson(az, et))):
            assert abs(ana - fd) <= 1e-3 * abs(fd) + 1e-10, (et, ana, fd)


def _psi(site, et):
    """Position angle (rad) of Earth's projected pole relative to the local vertical, from positions only."""
    from lunaops.engine.earth import pole_in_frame
    from lunaops.engine.ephem import sample_target
    from lunaops.engine.kernels import load
    t = sample_target(site, "earth", [et])
    p, _ = pole_in_frame([et], load().frame)
    rh, u, p = t.unit[0], site.basis[2], p[0]
    X = u @ p - (rh @ u) * (p @ rh)
    Y = np.cross(u, p) @ rh
    return math.atan2(Y, X)


@needs_kernels
def test_psi_rate_matches_finite_differences(kernels):
    from lunaops.engine.ephem import sample_target
    site = _site()
    for et in _ets(200):
        t = sample_target(site, "earth", [et])
        base = _psi(site, et)

        def psi(x):
            return (_psi(site, x) - base + math.pi) % (2 * math.pi) - math.pi
        fd = _richardson(psi, et)
        assert abs(t.earth["psi_dot"][0] - fd) <= 1e-3 * abs(fd) + 1e-14, (et, t.earth["psi_dot"][0], fd)


@needs_kernels
def test_limb_radial_speeds_and_limb_speed_bound(kernels):
    """Per limb: the radial speeds d rho_up/dt and d rho_down/dt from the solver agree with Richardson differences
    of SPICE-edlimb-based rho_up / rho_down (1e-3 relative or 1e-12 deg/s), and both stay below V_limb.
    V_limb also bounds the largest rate of change of the limb's radial function r(psi) about the centre, in the
    frame of the local vertical (which bounds the Hausdorff motion of the limb relative to the centre)."""
    import spiceypy as sp
    from lunaops import settings
    from lunaops.engine.earth import limb_speed_bound
    from lunaops.engine.ephem import sample_target
    site = _site()
    e, n, u = site.basis
    a, _, b = settings.EARTH_RADII_KM

    def spice_rho(et):
        t = sample_target(site, "earth", [et])
        r = t.unit[0] * t.dist_km[0]
        M = pole_axis_frame(t.earth["pole"][0])     # edlimb about the engine's pole of date (see earth_helpers)
        rJ = M @ r
        c, smaj, smin = (np.asarray(x) for x in sp.el2cgv(sp.edlimb(a, a, b, -rJ)))
        tt = np.linspace(0, 2 * np.pi, 200_000, endpoint=False)
        q = ((rJ + c)[None] + np.cos(tt)[:, None] * smaj + np.sin(tt)[:, None] * smin) @ M
        el, _ = el_az(q, e, n, u)
        k1, k2 = int(np.argmax(el)), int(np.argmin(el))
        # quadratic refinement of the dense extremum
        def peak(k):
            y0, y1, y2 = el[k - 1], el[k], el[(k + 1) % el.size]
            return y1 - 0.125 * (y2 - y0) ** 2 / (y2 - 2 * y1 + y0)
        el_c = math.radians(t.el[0])
        return peak(k1) - el_c, el_c - peak(k2), t

    for et in _ets(60):
        t = sample_target(site, "earth", [et])
        v = float(limb_speed_bound(t.dist_km[0], t.earth["d_dot"][0], t.earth["psi_dot"][0], t.earth["lam_dot"][0]))
        for j, name in ((0, "rho_up"), (1, "rho_down")):
            ours = _richardson(lambda x: float(sample_target(site, "earth", [x]).earth[name][0]), et)
            ref = _richardson(lambda x: spice_rho(x)[j], et, taus=(600.0, 300.0, 150.0))
            assert abs(ours - ref) <= 1e-3 * abs(ref) + math.radians(1e-12), (et, name, ours, ref)
            assert abs(ours) <= v, (et, name, ours, v)
        # radial function r(psi) about the centre, local-vertical frame
        rf = []
        for x in (et - 30.0, et + 30.0):
            tx = sample_target(site, "earth", [x])
            E = tx.earth
            q = limb_q(E["Q0"][0], E["QA"][0], E["QB"][0], np.linspace(0, 2 * np.pi, 200_000, endpoint=False))
            q /= np.linalg.norm(q, axis=1)[:, None]
            c = tx.unit[0]
            up = u - (u @ c) * c
            up /= np.linalg.norm(up)
            east = np.cross(up, c)
            ang = np.arctan2(np.linalg.norm(np.cross(q, c), axis=1), q @ c)
            psi = np.arctan2(q @ east, q @ up)
            o = np.argsort(psi)
            grid = np.linspace(-np.pi, np.pi, 4096, endpoint=False)
            rf.append(np.interp(grid, psi[o], ang[o], period=2 * np.pi))
        assert np.max(np.abs(rf[1] - rf[0])) / 60.0 <= v, et


# ------------------------------------------------------------------ total derivative bound
def _cases():
    """(horizon kind, epoch block): 100 blocks of 25 epochs per kind across 18.6 years (fast and slow libration),
    each block with a horizon placed on Earth's azimuth at the block centre so that the horizon features
    (slope, notch, two notches) sit under the disk."""
    return [(kind, blk) for kind in ("flat", "sloped", "notched", "two_notch") for blk in range(100)]


@needs_kernels
def test_complete_rate_bound_covers_the_clearance_derivative(kernels):
    """B_top >= |dg_top/dt| and B_bot >= |dg_bot/dt| at 1e4 (epoch, horizon) cases, checked separately and with
    one-sided 1 s differences on both sides (maximiser jumps make g only one-sided differentiable). The detector's
    r0 is used as B. Margin statistics, and how often the pre-Phase-3 single-radius r0 would have under-bounded,
    are printed for AUDIT."""
    from lunaops.engine.earth import earth_disk_state
    from lunaops.engine.ephem import earth_geo, sample_target
    from lunaops.engine.events import EventConfig, EventDetector

    site = _site()
    centres = _ets(100)
    worst = 0.0
    old_under = 0
    n_cases = 0
    for kind, blk in _cases():
        et_c = centres[blk]
        t_c = sample_target(site, "earth", [et_c])
        az0, el0 = float(t_c.az[0]), float(t_c.el[0])
        rng = np.random.default_rng(blk)
        level = el0 + rng.uniform(-0.8, 0.8)
        hp = horizon(kind, az0, level, slope=rng.uniform(0.5, 2.0) * rng.choice([-1, 1]),
                     depth=rng.uniform(0.3, 1.5), width_deg=rng.uniform(0.1, 0.6))
        det = EventDetector(site, hp, EventConfig())
        ets = et_c + np.arange(-12, 13) * 600.0
        both = np.concatenate([ets - 1.0, ets + 1.0])
        tt = sample_target(site, "earth", both)
        tc = sample_target(site, "earth", ets)
        g = {}
        for i in range(both.size):
            st = earth_disk_state(hp, earth_geo(tt, i), want_f=False)
            g[i] = (st["g_top"], st["g_bot"])
        for i, et in enumerate(ets):
            smp = det.evaluate(et)
            gm, gp = g[i], g[i + ets.size]
            for j, fn in ((0, "earth_top"), (1, "earth_bot")):
                g0 = smp.vals[fn]
                fd = max(abs(gp[j] - g0), abs(g0 - gm[j]))            # one-sided, both sides, tau = 1 s
                B = smp.r0[fn]
                assert fd <= B, (kind, blk, et, fn, fd, B)
                worst = max(worst, fd / B)
                ge = smp.geo["earth"]
                cos_el = max(math.cos(math.radians(ge["el"])), 1e-9)
                d, dd = float(tc.dist_km[i]), float(tc.earth["d_dot"][i])
                old_rho_rate = math.degrees(6378.137 * abs(dd) / (d * math.sqrt(d * d - 6378.137 ** 2)))
                old = (abs(ge["el_rate"]) + ge["S"] * abs(ge["az_rate"]) + (1 + ge["S"] / cos_el) * old_rho_rate
                       + ge["S"] * math.radians(ge["rho"]) * math.sin(math.radians(abs(ge["el"]))) / cos_el ** 2
                       * abs(ge["el_rate"]))
                old_under += fd > old
                n_cases += 1
    assert n_cases >= 10_000
    print(f"rate bound: max |FD| / B = {worst:.3f} over {n_cases} cases; pre-Phase-3 r0 under-bounded {old_under}")


@needs_kernels
def test_earth_limb_r0_does_not_use_rho_rate(kernels, monkeypatch):
    """Code path: the detector's earth_top / earth_bot (and earth_c) r0 is unchanged when Earth's rho_rate is
    replaced by garbage; only the display field would change."""
    from lunaops.engine import events
    from lunaops.engine.ephem import sample_target as real

    hp = horizon("sloped", 312.0, -3.0, slope=1.0)
    det = events.EventDetector(_site(), hp, events.EventConfig())
    et = float(_ets(1, "2026-11-14T21:00:00", "2026-11-14T21:00:01")[0])
    before = det.evaluate(et).r0

    def poisoned(site, target, ets):
        t = real(site, target, ets)
        if target == "earth":
            t.rho_rate = np.full_like(t.rho_rate, 1e9)
        return t
    monkeypatch.setattr(events, "sample_target", poisoned)
    after = det.evaluate(et).r0
    for fn in ("earth_c", "earth_top", "earth_bot"):
        assert after[fn] == before[fn], fn


# ------------------------------------------------------------------ event timing vs brute force
def _g(site, hp, ets):
    from lunaops.engine.earth import earth_disk_state
    from lunaops.engine.ephem import earth_geo, sample_target
    t = sample_target(site, "earth", np.atleast_1d(ets))
    out = np.empty((t.et.size, 2))
    for i in range(t.et.size):
        st = earth_disk_state(hp, earth_geo(t, i), want_f=False)
        out[i] = st["g_top"], st["g_bot"]
    return out


def _brute_events(site, hp, et0, et1):
    """Earth limb crossings from a 60 s grid, rescanned at 1 s wherever a crossing could hide, bisected to 1 ms."""
    grid = np.arange(et0, et1 + 1.0, 60.0)
    g = _g(site, hp, grid)
    out = {0: [], 1: []}
    step_max = np.max(np.abs(np.diff(g, axis=0)), axis=0)
    for j in (0, 1):
        for k in range(grid.size - 1):
            a, b = g[k, j], g[k + 1, j]
            if (a > 0) == (b > 0) and min(abs(a), abs(b)) > 10 * step_max[j]:
                continue
            fine = np.arange(grid[k], grid[k + 1] + 0.5, 1.0)
            gf = _g(site, hp, fine)[:, j]
            for m in range(fine.size - 1):
                if (gf[m] > 0) != (gf[m + 1] > 0):
                    lo, hi, slo = fine[m], fine[m + 1], gf[m] > 0
                    while hi - lo > 1e-3:
                        mid = 0.5 * (lo + hi)
                        if (_g(site, hp, [mid])[0, j] > 0) == slo:
                            lo = mid
                        else:
                            hi = mid
                    out[j].append((0.5 * (lo + hi), +1 if gf[m + 1] > 0 else -1))
    return out


WINDOWS = [("2026-11-05T12:00:00", 320.66), ("2026-11-14T21:00:00", 312.59)]


@needs_kernels
@pytest.mark.parametrize("kind", ["flat", "sloped", "notched"])
@pytest.mark.parametrize("window", WINDOWS, ids=["earthset", "earthrise"])
def test_earth_limb_events_match_brute_force(kernels, kind, window):
    """Every detector event for earth_top and earth_bot within 1 s of the brute-force crossing (direction-aware,
    separately per limb), no missed or spurious events, and no runtime estimate failures for Earth limb
    functions."""
    import spiceypy as sp
    from lunaops.engine.events import EventConfig, EventDetector

    utc, az0 = window
    et_c = sp.str2et(utc)
    et0, et1 = et_c - 1.5 * 86400, et_c + 1.5 * 86400
    hp = horizon(kind, az0, -3.0, slope=0.6, depth=0.8, width_deg=0.5)
    site = _site()
    det = EventDetector(site, hp, EventConfig())
    run = det.run(et0, et1)
    ref = _brute_events(site, hp, et0, et1)
    for j, fn in ((0, "earth_top"), (1, "earth_bot")):
        got = [(ev["et"], ev["direction"]) for ev in run["events"] if ev["function"] == fn]
        assert len(got) == len(ref[j]), (fn, got, ref[j])
        for (tg, dg), (tr, dr) in zip(got, ref[j]):
            assert dg == dr and abs(tg - tr) <= 1.0, (fn, tg, tr)
    assert ref[0] and ref[1], "window must contain both limb events"
    fails = [f for f in det.log.estimate_failures if f["function"] in ("earth_top", "earth_bot")]
    assert not fails, fails
