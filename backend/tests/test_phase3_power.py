"""Phase 3, item 2: limb-darkened power indicator (extension D01).

The coefficients are checked against the source (Neckel & Labs 1994, Solar Physics 153, 91-114, Table I, p. 98,
transcribed below in full, exactly as printed), the full-disk-flux normalisation against direct integration,
and the visible-flux fraction against an independent polar-coordinate reference. P_rel (uniform disk) must be
bitwise unchanged.
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from conftest import needs_kernels
from earth_helpers import U_AX, direction, horizon

# Neckel & Labs (1994), Table I, p. 98: lambda (nm), N86, N87, A0..A5, F/I -- exactly as printed.
# '*' marks the 6 wavelengths observed exclusively since 1988.
TABLE_I = [
    ("303.327", 13, 12, 0.08011, 0.70695, 0.49910, -0.31080, -0.02177, 0.04642, 0.6826),
    ("310.843", 11, 10, 0.08160, 0.71609, 0.69685, -0.87703, 0.47008, -0.08760, 0.6883),
    ("320.468", 13, 12, 0.08833, 0.77285, 0.65382, -1.04647, 0.72921, -0.19775, 0.6985),
    ("329.897*", 17, 9, 0.09188, 0.92459, 0.19604, -0.39546, 0.23599, -0.05303, 0.7116),
    ("349.947", 14, 8, 0.11012, 1.02168, -0.10924, -0.00055, -0.08688, 0.06487, 0.7260),
    ("365.875", 14, 10, 0.12828, 1.04969, 0.17482, -1.13371, 1.23882, -0.45990, 0.7445),
    ("374.086", 12, 10, 0.12579, 0.85402, 0.54601, -1.15048, 0.88928, -0.26462, 0.7288),
    ("390.915", 13, 10, 0.12995, 0.91836, -0.07566, 0.19149, -0.28712, 0.12298, 0.7204),
    ("401.970*", 13, 10, 0.12323, 1.08648, -0.43974, 0.45912, -0.32759, 0.09850, 0.7303),
    ("416.319", 14, 7, 0.12814, 1.19947, -0.84407, 1.07201, -0.79537, 0.23982, 0.7380),
    ("427.930", 12, 8, 0.14249, 1.28796, -1.19564, 1.68603, -1.36658, 0.44572, 0.7495),
    ("443.885", 15, 8, 0.16220, 1.24893, -0.92165, 0.89978, -0.50148, 0.11220, 0.7588),
    ("445.125*", 13, 8, 0.15248, 1.38517, -1.49615, 1.99886, -1.48155, 0.44119, 0.7596),
    ("457.345", 13, 10, 0.16604, 1.38544, -1.52275, 2.00232, -1.45969, 0.42864, 0.7651),
    ("477.427", 13, 8, 0.19571, 1.30551, -1.25845, 1.50626, -1.05472, 0.30570, 0.7751),
    ("492.905", 22, 8, 0.20924, 1.30798, -1.20411, 1.21505, -0.67196, 0.14381, 0.7823),
    ("519.930*", 17, 12, 0.23695, 1.29927, -1.28034, 1.37760, -0.85054, 0.21706, 0.7925),
    ("541.760", 12, 12, 0.26073, 1.27428, -1.30352, 1.47085, -0.96618, 0.26384, 0.8002),
    ("559.950", 10, 8, 0.26892, 1.34319, -1.58427, 1.91271, -1.31350, 0.37295, 0.8061),
    ("579.880", 13, 8, 0.28392, 1.36896, -1.75998, 2.22154, -1.56074, 0.44630, 0.8125),
    ("610.975", 11, 6, 0.30854, 1.36620, -1.83572, 2.33221, -1.63082, 0.45959, 0.8221),
    ("640.970", 14, 6, 0.33644, 1.30590, -1.79238, 2.45040, -1.89979, 0.59943, 0.8290),
    ("669.400*", 14, 6, 0.34685, 1.37539, -2.04425, 2.70493, -1.94290, 0.55999, 0.8360),
    ("700.875", 12, 6, 0.37885, 1.25553, -1.70908, 2.19647, -1.59554, 0.47378, 0.8434),
    ("748.710", 14, 8, 0.40627, 1.22842, -1.67877, 2.05535, -1.39972, 0.38845, 0.8524),
    ("811.760", 10, 6, 0.42977, 1.25182, -1.85164, 2.31949, -1.59101, 0.44155, 0.8621),
    ("869.600", 10, 6, 0.45396, 1.25101, -2.02958, 2.75410, -2.02287, 0.59338, 0.8701),
    ("948.850", 10, 8, 0.47855, 1.19813, -1.86296, 2.36939, -1.64367, 0.46056, 0.8773),
    ("1046.600*", 11, 8, 0.49870, 1.21429, -2.06976, 2.80703, -2.05247, 0.60221, 0.8841),
    ("1098.950", 9, 8, 0.51149, 1.19354, -2.00174, 2.66936, -1.94981, 0.57715, 0.8890),
]
# As printed, the 365.875 nm row violates both Eq. (5) (sum = 0.99800) and Eq. (6) (0.74354 vs 0.7445); A2 = 0.17682
# instead of the printed 0.17482 would satisfy both. A misprint in the source; not the row used here, kept as printed.
PRINTED_INCONSISTENT = {"365.875"}
RHO_SUN = math.radians(0.2666)


def _wl(row):
    return float(row[0].rstrip("*"))


# ------------------------------------------------------------------ coefficients vs the source
def test_selected_row_is_exactly_a_table_entry():
    """The law is the printed 541.760 nm row, unmodified (no interpolation), and 541.760 nm is the tabulated
    wavelength nearest the V-band centre, 550 nm."""
    from lunaops.engine import limb_darkening as L
    row = next(r for r in TABLE_I if r[0] == "541.760")
    assert L.LD_WAVELENGTH_NM == 541.760
    assert L.LD_COEFFS == row[3:9]
    assert L.LD_PRINTED_F_OVER_I == row[9]
    assert min(TABLE_I, key=lambda r: abs(_wl(r) - 550.0))[0] == "541.760"
    assert abs(_wl(row) - 550.0) == pytest.approx(8.24) and abs(559.950 - 550.0) == pytest.approx(9.95)
    assert all(_wl(r) != L.LD_WAVELENGTH_NM for r in TABLE_I if r[0] != "541.760")


def test_table_satisfies_the_papers_printed_relations():
    """Every transcribed row satisfies the paper's Eq. (5), sum A_n = 1 (within the 5-decimal rounding of six
    coefficients, 3e-5), and Eq. (6), F/I = 2 sum A_k/(k+2), reproduces the printed F/I to its 4 decimals. This
    verifies the transcription. The only exception is the printed misprint at 365.875 nm (documented)."""
    from lunaops.engine.limb_darkening import planar_f_over_i
    failing = set()
    for r in TABLE_I:
        a, fi = r[3:9], r[9]
        ok = abs(sum(a) - 1.0) <= 3e-5 and abs(planar_f_over_i(a) - fi) <= 5e-5 + 1e-12
        if not ok:
            failing.add(r[0])
    assert failing == PRINTED_INCONSISTENT
    bad = next(r for r in TABLE_I if r[0] == "365.875")
    fixed = (bad[3], bad[4], 0.17682, *bad[6:9])
    assert abs(sum(fixed) - 1.0) <= 3e-5 and round(planar_f_over_i(fixed), 4) == bad[9]


def test_selected_law_is_normalised_positive_and_monotone():
    from lunaops.engine.limb_darkening import LD_COEFFS, intensity, planar_f_over_i
    assert abs(sum(LD_COEFFS) - 1.0) < 1e-12                        # I(1) = 1 exactly for this row
    assert round(planar_f_over_i(), 4) == 0.8002
    mu = np.linspace(0.0, 1.0, 100_001)
    I = intensity(mu)
    assert np.all(I > 0) and np.all(np.diff(I) > 0)
    assert intensity(0.0) == pytest.approx(0.26073)                 # limb-to-centre ratio A0
    print(f"I(mu=0)/I(1) = {float(intensity(0.0)):.5f}; disk-averaged F/I = {planar_f_over_i():.6f}")


# ------------------------------------------------------------------ normalisation
def _flux_reference(rho, coeffs=None, n=1_000_000):
    """int_cap I dOmega = 2 pi int_0^rho I(mu(s)) sin s ds, midpoint rule on 1e6 points after the substitution
    s = rho sin(t), which removes the square root of mu at the limb."""
    from lunaops.engine.limb_darkening import LD_COEFFS, intensity
    coeffs = LD_COEFFS if coeffs is None else coeffs
    t = (np.arange(n) + 0.5) * (0.5 * math.pi / n)
    s = rho * np.sin(t)
    ds = rho * np.cos(t) * (0.5 * math.pi / n)
    mu = np.sqrt(np.maximum(0.0, 1.0 - np.sin(s) ** 2 / math.sin(rho) ** 2))
    return float(2 * math.pi * np.sum(intensity(mu, coeffs) * np.sin(s) * ds))


@pytest.mark.parametrize("rho_deg", [0.2666, 0.2725, 1.0, 5.0])
def test_full_disk_flux_matches_direct_integration(rho_deg):
    from lunaops.engine.limb_darkening import full_disk_flux
    r = math.radians(rho_deg)
    for coeffs in ((1, 0, 0, 0, 0, 0), None):
        args = () if coeffs is None else (coeffs,)
        assert abs(full_disk_flux(r, *args) / _flux_reference(r, *args) - 1.0) < 1e-12


def test_full_disk_flux_small_disk_limit_is_the_papers_f_over_i():
    """F / (pi sin^2 rho) tends to the paper's Eq. (6) value; at the Sun's size the spherical correction is
    O(rho^2), 4.8e-6 relative; the uniform law gives the cap area exactly."""
    from lunaops.engine.limb_darkening import full_disk_flux, planar_f_over_i
    from lunaops.engine.visibility import cap_area
    assert abs(full_disk_flux(RHO_SUN, (1, 0, 0, 0, 0, 0)) - cap_area(RHO_SUN)) < 1e-18
    for deg, lim in ((0.01, 1e-8), (0.2666, 1e-5)):
        r = math.radians(deg)
        assert abs(full_disk_flux(r) / (math.pi * math.sin(r) ** 2) / planar_f_over_i() - 1.0) < lim


# ------------------------------------------------------------------ independent polar reference
def polar_reference(sun, level_deg, earth=None, n_scan=20_000, n_phi=64, n_s=64, coeffs=None):
    """Visible flux fraction for a level horizon (el > level) and an optional circular Earth, in polar
    coordinates (s, phi) about the Sun's centre. Each boundary is A cos s + B sin s > C, i.e.
    |s - delta| < acos(C / R) with R = hypot(A, B), delta = atan2(B, A), so every ray's visible s-intervals are
    closed form. The radial integral of I(mu(s)) sin s uses Gauss-Legendre with s = a + (b - a)(1 - cos t)/2
    (square-root end at the limb). The ray flux is smooth in phi except where an interval end meets 0, rho or
    another end: those phi are found (scan + bisection) and each smooth piece is integrated by Gauss-Legendre
    with a sine substitution. Independent of the engine's azimuth-strip integrator."""
    from lunaops.engine.limb_darkening import LD_COEFFS, full_disk_flux, intensity
    coeffs = LD_COEFFS if coeffs is None else coeffs
    rho, E = math.radians(sun["rho"]), math.radians(sun["el"])
    c = direction(sun["az"], sun["el"])
    up = U_AX - (U_AX @ c) * c
    up /= np.linalg.norm(up)
    east = np.cross(up, c)
    e = direction(earth["az"], earth["el"]) if earth is not None else None
    xs, ws = np.polynomial.legendre.leggauss(n_s)
    ts = 0.5 * math.pi * (xs + 1)

    def allowed(A, B, C):
        R = np.hypot(A, B)
        d = np.arctan2(B, A)
        w = np.arccos(np.clip(C / np.maximum(R, 1e-300), -1, 1))
        return d - w, d + w

    def ends(phi):
        a1, b1 = allowed(np.full(phi.shape, math.sin(E)), np.cos(phi) * math.cos(E), math.sin(math.radians(level_deg)))
        out = [a1, b1]
        if e is not None:
            A = np.full(phi.shape, c @ e)
            B = np.cos(phi) * (up @ e) + np.sin(phi) * (east @ e)
            out += list(allowed(A, B, math.cos(math.radians(earth["rho"]))))
        return out

    def segments(phi):
        en = ends(phi)
        lo, hi = np.maximum(0.0, en[0]), np.minimum(rho, en[1])
        if e is None:
            return [(lo, hi)]
        return [(lo, np.minimum(hi, en[2])), (np.maximum(lo, en[3]), hi)]

    def ray_flux(phi):
        tot = np.zeros(phi.shape)
        for a, b in segments(phi):
            b = np.maximum(a, b)
            sv = a[:, None] + (b - a)[:, None] * 0.5 * (1 - np.cos(ts))[None, :]
            ds = (b - a)[:, None] * 0.5 * np.sin(ts)[None, :] * 0.5 * math.pi
            mu = np.sqrt(np.maximum(0.0, 1.0 - np.sin(sv) ** 2 / math.sin(rho) ** 2))
            tot += np.sum(ws[None, :] * intensity(mu, coeffs) * np.sin(sv) * ds, axis=1)
        return tot

    def kinks(phi):                                  # functions whose zeros are the kinks of ray_flux
        en = ends(phi)
        f = []
        for x in en:
            f += [x, x - rho]
        for i in range(len(en)):
            for j in range(i + 1, len(en)):
                f.append(en[i] - en[j])
        return np.array(f)

    scan = np.linspace(0.0, 2 * math.pi, n_scan + 1)
    K = kinks(scan)
    bps = [0.0, 2 * math.pi]
    for k in range(K.shape[0]):
        idx = np.nonzero(np.sign(K[k, :-1]) != np.sign(K[k, 1:]))[0]
        for i in idx:
            lo, hi = scan[i], scan[i + 1]
            flo = K[k, i]
            for _ in range(60):
                mid = 0.5 * (lo + hi)
                fm = kinks(np.array([mid]))[k, 0]
                if np.sign(fm) == np.sign(flo):
                    lo, flo = mid, fm
                else:
                    hi = mid
            bps.append(0.5 * (lo + hi))
    bps = np.unique(bps)
    xp, wp = np.polynomial.legendre.leggauss(n_phi)
    th = 0.5 * math.pi * xp
    total = 0.0
    for a, b in zip(bps[:-1], bps[1:]):
        m, h = 0.5 * (a + b), 0.5 * (b - a)
        phi = m + h * np.sin(th)
        total += float(np.sum(wp * np.cos(th) * ray_flux(phi)) * h * 0.5 * math.pi)
    return total / full_disk_flux(rho, coeffs)


def test_segments_from_slivers_to_almost_full_match_the_reference():
    """Level horizons cutting 0.1 % to 99 % of the disk, at several solar elevations: |f_I - reference| < 1e-9."""
    from lunaops.engine.limb_darkening import visible_flux_fraction
    from lunaops.engine.visibility import disk_state
    worst = 0.0
    for el in (0.0, 5.0, 25.0):
        sun = {"az": 140.0, "el": el, "rho": 0.2666}
        for depth in (-0.98, -0.9, -0.5, 0.0, 0.4, 0.8, 0.95):
            level = el + depth * 0.2666
            hp = horizon("flat", 140.0, level)
            f = disk_state(hp, 140.0, el, 0.2666)["f"]
            assert 0.0005 < f < 0.9995
            fi, err, _ = visible_flux_fraction(hp, sun)
            ref = polar_reference(sun, level)
            worst = max(worst, abs(fi - ref))
            assert abs(fi - ref) < 1e-9, (el, depth, fi, ref)
    print(f"f_I vs polar reference: worst {worst:.1e}")


def test_full_disk_and_centre_chord():
    """The integrator itself (no short-circuit): a fully visible disk gives 1 to 1e-12; with the Sun's centre on
    the astronomical horizon (el = 0, level 0, a great circle through the centre) exactly half the flux."""
    from lunaops.engine.limb_darkening import visible_flux_fraction
    fi, _, _ = visible_flux_fraction(horizon("flat", 10.0, -5.0), {"az": 10.0, "el": 8.0, "rho": 0.2666})
    assert abs(fi - 1.0) < 1e-12
    fi, _, _ = visible_flux_fraction(horizon("flat", 10.0, 0.0), {"az": 10.0, "el": 0.0, "rho": 0.2666})
    assert abs(fi - 0.5) < 1e-12


def test_uniform_law_reproduces_the_visible_fraction():
    """With I = 1 the visible-flux fraction is the visible solid-angle fraction: equal to disk_state's f to 1e-10
    on random flat, sloped, notched and two-notch horizons."""
    from lunaops.engine.limb_darkening import visible_flux_fraction
    from lunaops.engine.visibility import disk_state
    rng = np.random.default_rng(21)
    for k in range(80):
        az, el = rng.uniform(0, 360), rng.uniform(-3, 40)
        hp = horizon(("flat", "sloped", "notched", "two_notch")[k % 4], az, el + rng.uniform(-0.3, 0.3),
                     rng.uniform(-2, 2), rng.uniform(0, 0.5), rng.uniform(0.05, 1), az + rng.uniform(-0.3, 0.3))
        f = disk_state(hp, az, el, 0.2666)["f"]
        fu, _, _ = visible_flux_fraction(hp, {"az": az, "el": el, "rho": 0.2666}, coeffs=(1, 0, 0, 0, 0, 0))
        assert abs(fu - f) < 1e-10, (k, fu, f)


def test_limb_sliver_tends_to_the_limb_intensity_ratio():
    """A thin hidden sliver at the bottom limb carries less flux than its area share. For a sliver of fractional
    depth d its mean mu is (3 pi / (8 sqrt 2)) sqrt(d) to leading order, so the flux/area ratio is
    A0 / (F/I) + A1 (3 pi / (8 sqrt 2)) / (F/I) sqrt(d) + O(d): decreasing with d, above the limit
    A0 / (F/I) = 0.3259, and with the analytic sqrt(d) slope 1.3266 at small d."""
    from lunaops.engine.limb_darkening import LD_COEFFS, planar_f_over_i, visible_flux_fraction
    from lunaops.engine.visibility import disk_state
    sun = {"az": 200.0, "el": 6.0, "rho": 0.2666}
    depths = (0.2, 0.05, 0.01, 0.002, 0.0005)
    ratios = []
    for d in depths:
        level = 6.0 - 0.2666 * (1 - d)
        hp = horizon("flat", 200.0, level)
        f = disk_state(hp, 200.0, 6.0, 0.2666)["f"]
        fi, _, _ = visible_flux_fraction(hp, dict(sun))
        ratios.append((1 - fi) / (1 - f))
    fi_ = planar_f_over_i()
    limit = LD_COEFFS[0] / fi_
    slope = LD_COEFFS[1] * 3 * math.pi / (8 * math.sqrt(2)) / fi_
    assert all(a > b > limit for a, b in zip(ratios, ratios[1:])), ratios
    measured = (ratios[-1] - limit) / math.sqrt(depths[-1])
    assert abs(measured / slope - 1) < 0.05, (measured, slope)
    print("hidden-limb-sliver flux/area ratios:", [round(r, 4) for r in ratios], f"limit {limit:.4f}; "
          f"sqrt(d) slope measured {measured:.4f}, analytic {slope:.4f}")


def test_earth_occultation_matches_the_reference():
    """Earth (circular) in front of the Sun, with and without terrain: f_I within 1e-9 of the polar reference;
    with the uniform law it equals the Item 4 joint fraction to 1e-10."""
    from lunaops.engine.limb_darkening import visible_flux_fraction
    from lunaops.engine.visibility import disk_state, sun_joint_state
    sun = {"az": 120.0, "el": 8.0, "rho": 0.2666}
    c = direction(120.0, 8.0)
    up = U_AX - (U_AX @ c) * c
    up /= np.linalg.norm(up)
    east = np.cross(up, c)
    for gamma, pa, level in ((0.9, 30.0, -40.0), (0.75, 200.0, 8.05), (1.1, 95.0, 7.9), (0.3, 0.0, -40.0)):
        g, p = math.radians(gamma), math.radians(pa)
        ev = math.cos(g) * c + math.sin(g) * (math.cos(p) * up + math.sin(p) * east)
        earth = {"az": math.degrees(math.atan2(ev[0], ev[1])) % 360, "el": math.degrees(math.asin(ev[2])), "rho": 0.95}
        s = {**sun, "gamma": gamma}
        hp = horizon("flat", 120.0, level)
        fi, _, _ = visible_flux_fraction(hp, s, earth)
        ref = polar_reference(s, level, earth)
        assert abs(fi - ref) < 1e-9, (gamma, pa, level, fi, ref)
        fu, _, _ = visible_flux_fraction(hp, s, earth, coeffs=(1, 0, 0, 0, 0, 0))
        js = sun_joint_state(hp, s, earth, disk_state(hp, 120.0, 8.0, 0.2666))
        assert abs(fu - js["f"]) < 1e-10, (gamma, fu, js)


def test_short_circuits_are_exact():
    from lunaops.engine.limb_darkening import limb_darkened_fraction
    hp = horizon("flat", 0.0, 0.0)
    sun = {"az": 0.0, "el": 5.0, "rho": 0.2666, "gamma": 50.0}
    assert limb_darkened_fraction(hp, sun, None, 1.0)["f_I"] == 1.0
    assert limb_darkened_fraction(hp, sun, None, 0.0)["f_I"] == 0.0
    assert math.isnan(limb_darkened_fraction(hp, sun, None, float("nan"))["f_I"])


# ------------------------------------------------------------------ analysis integration
@needs_kernels
def test_analysis_keeps_p_rel_and_adds_the_limb_darkened_series(kernels, synthetic_crater):
    """Golden window: P_rel_LD equals P_rel bitwise wherever the Sun is fully visible or hidden; the uniform
    series is still the product f (1 au / r)^2 k of the unchanged visible fraction; the label, citation and
    coefficients are in the parameters, and the adaptive error estimate is below the tolerance."""
    from lunaops.engine.analysis import AnalysisRequest, analyze
    from lunaops.engine.limb_darkening import LD_COEFFS, LD_LABEL, LD_TOL
    from test_phase2_golden import SNAP
    res = analyze(AnalysisRequest(**SNAP["request"]))
    f = np.array([np.nan if v is None else v for v in res["series"]["sun"]["f"]])
    fl = np.array([np.nan if v is None else v for v in res["series"]["sun"]["f_ld"]])
    whole = np.isfinite(f) & ((f == 0.0) | (f == 1.0))
    assert whole.sum() > 200 and np.array_equal(fl[whole], f[whole])
    for m, v in res["series"]["power"].items():
        p = np.array([np.nan if x is None else x for x in v["series"]])
        pl = np.array([np.nan if x is None else x for x in v["series_ld"]])
        assert np.array_equal(p[whole], pl[whole], equal_nan=True), m
        assert set(v["metrics_ld"]) == set(v["metrics"])
    assert res["summary"]["power_ld"]["vertical_tracking"] == res["series"]["power"]["vertical_tracking"]["metrics_ld"]
    ld = res["provenance"]["parameters"]["limb_darkening"]
    assert ld["label"] == LD_LABEL and ld["coefficients"] == list(LD_COEFFS) and ld["wavelength_nm"] == 541.760
    assert ld["max_adaptive_error"] < LD_TOL


@needs_kernels
def test_limb_darkening_parameters_are_in_the_result_key(monkeypatch, kernels, synthetic_crater):
    from lunaops.engine import limb_darkening
    from lunaops.engine.analysis import AnalysisRequest, result_id
    req = AnalysisRequest(lat=-89.0, lon=45.0, start_utc="2026-11-14T00:00:00Z", end_utc="2026-11-15T00:00:00Z")
    rid = result_id(req)
    for name, value in (("LD_COEFFS", (0.26892, 1.34319, -1.58427, 1.91271, -1.31350, 0.37295)),
                        ("LD_WAVELENGTH_NM", 559.950), ("LD_TOL", 1e-9), ("LD_ORDERS", (32, 256)),
                        ("LD_METHOD_VERSION", "x"), ("LD_CITATION", "x")):
        old = getattr(limb_darkening, name)
        monkeypatch.setattr(limb_darkening, name, value)
        assert result_id(req) != rid, name
        monkeypatch.setattr(limb_darkening, name, old)
        assert result_id(req) == rid, name
