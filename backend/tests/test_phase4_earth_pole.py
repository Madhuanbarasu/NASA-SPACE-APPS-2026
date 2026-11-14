"""Phase 4: Earth's spin axis is the pole of date (CIP: IAU 2006 precession + IAU 2000B nutation).

Independent references:
  * ERFA's own published test values (liberfa/erfa/src/t_erfa_c.c, ERFA 2.0.1 = SOFA 2023-10-11) for nut00b,
    pfw06, obl06, fw2m and pn06, with ERFA's own tolerances;
  * ERFA-computed nutation, mean pole and CIP at 602 TT epochs over 2000-2049
    (tests/reference/erfa_cip_2000_2049.json, generator beside it; ERFA is not a LUNA-OPS dependency);
  * physical checks that need neither: the IERS 2010 frame-bias pole offset at J2000.0, the nutation amplitude,
    and the precession of the pole against the production IAU_EARTH PCK model.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

from conftest import needs_kernels

REF = json.loads((Path(__file__).resolve().parent / "reference" / "erfa_cip_2000_2049.json").read_text())
DJ00 = 2451545.0
AS = math.pi / (180.0 * 3600.0)


def _t(date1, date2):
    return ((date1 - DJ00) + date2) / 36525.0


def _ang(a, b):
    """Angle (rad) between unit vectors, stable for tiny angles."""
    a, b = np.atleast_2d(a), np.atleast_2d(b)
    return np.arctan2(np.linalg.norm(np.cross(a, b), axis=1), np.sum(a * b, axis=1))


# ------------------------------------------------------------------ ERFA published test values
def test_erfa_published_values():
    """t_erfa_c.c: t_nut00b, t_pfw06, t_obl06, t_fw2m and the CIP row of t_pn06, ERFA's tolerances."""
    from lunaops.engine import earth_orientation as eo

    dpsi, deps = eo.nut00b(_t(2400000.5, 53736.0))
    assert abs(dpsi - -0.9632552291148362783e-5) <= 1e-13
    assert abs(deps - 0.4063197106621159367e-4) <= 1e-13
    gamb, phib, psib, epsa = eo.pfw06(_t(2400000.5, 50123.9999))
    assert abs(gamb - -0.2243387670997995690e-5) <= 1e-16
    assert abs(phib - 0.4091014602391312808) <= 1e-12
    assert abs(psib - -0.9501954178013031895e-3) <= 1e-14
    assert abs(epsa - 0.4091014316587367491) <= 1e-12
    assert abs(eo.obl06(_t(2400000.5, 54388.0)) - 0.4090749229387258204) <= 1e-14
    r = eo.fw2m(-0.2243387670997992368e-5, 0.4091014602391312982, -0.9501954178013015092e-3,
                0.4091014316587367472)[0]
    ref = np.array([[0.9999995505176007047, 0.8695404617348192957e-3, 0.3779735201865582571e-3],
                    [-0.8695404723772016038e-3, 0.9999996219496027161, -0.1361752496887100026e-6],
                    [-0.3779734957034082790e-3, -0.1924880848087615651e-6, 0.9999999285679971958]])
    assert np.all(np.abs(r - ref) <= 1e-12)
    # t_pn06 (dpsi, deps as given there): rbpn row 3, the CIP; X, Y to 1e-14 as in t_fw2xy
    gamb, phib, psib, epsa = eo.pfw06(_t(2400000.5, 53736.0))
    z = eo.fw2m(gamb, phib, psib + -0.9632552291149335877e-5, epsa + 0.4063197106621141414e-4)[0][2]
    assert abs(z[0] - 0.5791301952321296716e-3) <= 1e-14
    assert abs(z[1] - 0.4020538796195230577e-4) <= 1e-14
    assert abs(z[2] - 0.9999998314958576778) <= 1e-12


def test_nutation_table_is_the_iau2000b_series():
    from lunaops.engine import earth_orientation as eo
    assert eo.NUT00B.shape == (77, 11)
    # cip_gcrs multiplies out the third row of fw2m; it must equal the full matrix product
    t = np.linspace(-0.1, 0.6, 50)
    gamb, phib, psib, epsa = eo.pfw06(t)
    dpsi, deps = eo.nut00b(t)
    row = eo.fw2m(gamb, phib, psib + dpsi, epsa + deps)[:, 2, :]
    assert np.max(_ang(eo.cip_gcrs(t), row)) <= 1e-15
    # the 18.6-year term (Om): -17.2064161" in longitude, 9.2052331" in obliquity (McCarthy & Luzum 2003)
    assert tuple(eo.NUT00B[0, :5]) == (0, 0, 0, 0, 1)
    assert eo.NUT00B[0, 5] == -172064161.0 and eo.NUT00B[0, 8] == 92052331.0
    assert abs(eo.DPPLAN / eo.DMAS2R - -0.135) < 1e-15 and abs(eo.DEPLAN / eo.DMAS2R - 0.388) < 1e-15


# ------------------------------------------------------------------ ERFA over 2000-2049
def test_matches_erfa_over_2000_2049():
    """602 TT epochs: nutation within 1e-15 rad, mean pole and CIP within 1e-14 rad (2e-9 arcsec) of ERFA."""
    from lunaops.engine import earth_orientation as eo

    rows = REF["rows"]
    assert REF["meta"]["sofa_release"] == "20231011" and len(rows) == 602
    t = np.array([r["tt_days_since_j2000"] for r in rows]) / 36525.0
    assert t.min() == 0.0 and t.max() * 100 >= 49.99
    dpsi, deps = eo.nut00b(t)
    assert np.max(np.abs(dpsi - [r["dpsi"] for r in rows])) <= 1e-15
    assert np.max(np.abs(deps - [r["deps"] for r in rows])) <= 1e-15
    for key, nut in (("cip", True), ("mean_pole", False)):
        got = eo.cip_gcrs(t, nutation=nut)
        want = np.array([r[key] for r in rows])
        err = _ang(got, want)
        assert np.max(err) <= 1e-14, (key, np.max(err))
    print("max CIP difference from ERFA (arcsec):", float(np.max(_ang(eo.cip_gcrs(t), [r["cip"] for r in rows])))
          / AS)


# ------------------------------------------------------------------ physical checks (no ERFA)
def test_frame_bias_and_nutation_amplitude():
    """At J2000.0 the IAU 2006 mean pole is offset from the GCRS Z axis by the frame bias
    (xi0, eta0) = (-16.617, -6.819) mas (IERS Conventions 2010 eq. 5.21), |.| = 17.962 mas. The CIP stays
    within the nutation amplitude of the mean pole: sqrt(9.21^2 + (17.21 sin 23.44)^2) < 10.0 arcsec plus
    the small terms (bounded here by 11 arcsec), and moves from it by more than 6 arcsec somewhere in an
    18.6-year cycle."""
    from lunaops.engine import earth_orientation as eo

    z0 = eo.cip_gcrs(0.0, nutation=False)[0]
    assert abs(z0[0] / eo.DMAS2R - -16.617) < 0.01 and abs(z0[1] / eo.DMAS2R - -6.819) < 0.01
    t = np.linspace(0.0, 0.5, 4000)
    off = _ang(eo.cip_gcrs(t), eo.cip_gcrs(t, nutation=False)) / AS
    assert off.max() < 11.0 and off.max() > 6.0
    # precession: the mean pole moves about 2004.19" per century (theta_A, IERS 2010 eq. 5.40)
    drift = _ang(eo.cip_gcrs(0.5, nutation=False), z0)[0] / AS
    assert abs(drift - 0.5 * 2004.19) < 1.0


def test_time_scale_and_derivative(kernels):
    """TT is used (SPICE unitim TDB->TT; TT-TDB < 2 ms, so a TDB argument would change the pole by < 1e-14 rad),
    and the CIP's own rate from the central difference agrees with a Richardson extrapolation."""
    import spiceypy as sp
    from lunaops.engine import earth_orientation as eo

    ets = np.linspace(sp.str2et("2000-01-02T00:00:00"), sp.str2et("2049-12-01T00:00:00"), 60)
    t = eo.tt_centuries(ets)
    assert np.max(np.abs(t * eo.SEC_PER_CENTURY - ets)) < 2e-3
    assert np.max(_ang(eo.cip_gcrs(t), eo.cip_gcrs(ets / eo.SEC_PER_CENTURY))) < 1e-14
    z, zd = eo.earth_pole_gcrs(ets)
    assert np.allclose(np.linalg.norm(z, axis=1), 1.0, atol=1e-15)
    for et, zdi in zip(ets[::6], zd[::6]):
        d = [(eo.earth_pole_gcrs([et + h])[0][0] - eo.earth_pole_gcrs([et - h])[0][0]) / (2 * h)
             for h in (7200.0, 3600.0)]
        rich = (4 * d[1] - d[0]) / 3
        assert np.linalg.norm(zdi - rich) <= 1e-3 * np.linalg.norm(rich) + 1e-20
        assert np.linalg.norm(zdi) < 1e-11                      # rad/s: precession + nutation only


# ------------------------------------------------------------------ the engine's pole
def test_engine_pole_is_the_cip_and_kernel_independent(kernels, monkeypatch):
    """pole_in_frame returns R(t) * CIP with R from the J2000 -> body-fixed transformation only: no Earth
    orientation is read from the kernels, so the demo and production sets give the same pole."""
    import spiceypy as sp
    from lunaops.engine import earth
    from lunaops.engine import earth_orientation as eo

    ets = np.linspace(sp.str2et("2026-11-01T00:00:00"), sp.str2et("2036-11-01T00:00:00"), 25)
    calls = []
    real = sp.sxform

    def spy(a, b, et):
        calls.append((a, b))
        return real(a, b, et)
    monkeypatch.setattr(sp, "sxform", spy)
    p, pd = earth.pole_in_frame(ets, kernels.frame)
    monkeypatch.setattr(sp, "sxform", real)
    assert set(calls) == {("J2000", kernels.frame)}
    z, zd = eo.earth_pole_gcrs(ets)
    for i, et in enumerate(ets):
        x = np.asarray(real("J2000", kernels.frame, float(et)))
        assert np.allclose(p[i], x[:3, :3] @ z[i], atol=1e-15)
        assert np.allclose(pd[i], x[3:, :3] @ z[i] + x[:3, :3] @ zd[i], atol=1e-20)
        assert abs(np.linalg.norm(p[i]) - 1.0) < 1e-15


def test_engine_pole_rate_matches_finite_differences(kernels):
    """dp/dt in the rotating lunar frame (dominated by the Moon's rotation) against Richardson differences."""
    import spiceypy as sp
    from lunaops.engine.earth import pole_in_frame

    for et in np.linspace(sp.str2et("2001-01-01T00:00:00"), sp.str2et("2049-01-01T00:00:00"), 20):
        _, pd = pole_in_frame([et], kernels.frame)
        d = [(pole_in_frame([et + h], kernels.frame)[0][0] - pole_in_frame([et - h], kernels.frame)[0][0]) / (2 * h)
             for h in (120.0, 60.0)]
        rich = (4 * d[1] - d[0]) / 3
        assert np.linalg.norm(pd[0] - rich) <= 1e-6 * np.linalg.norm(rich)


@needs_kernels
def test_cip_against_iau_earth(kernels):
    """Production PCK only. IAU_EARTH (pck00011) is the IAU WGCCRE pole: linear precession, no nutation.
    Its pole must agree with the IAU 2006 mean pole to within the WGCCRE model's own limits over 2000-2049
    (coefficients rounded to 0.001 deg/century, i.e. up to 1.8" per century each, linear in T, plus the omitted
    T^2 terms of theta_A and zeta_A + z_A, under 0.4" at T = 0.5, plus the 0.018" frame bias): 1.5". The CIP
    then differs from IAU_EARTH by the nutation (< 11") plus that 1.5"."""
    import spiceypy as sp
    from lunaops.engine import earth_orientation as eo

    try:
        sp.pxform("IAU_EARTH", "J2000", 0.0)
    except Exception:  # noqa: BLE001 - SPICE raises when the PCK lacks BODY399 orientation
        pytest.skip("IAU_EARTH orientation not loaded (production pck00011.tpc not installed)")
    ets = np.linspace(sp.str2et("2000-01-01T12:00:00"), sp.str2et("2049-12-01T00:00:00"), 200)
    iau = np.array([np.asarray(sp.pxform("IAU_EARTH", "J2000", float(et)))[:, 2] for et in ets])
    t = eo.tt_centuries(ets)
    d_mean = _ang(eo.cip_gcrs(t, nutation=False), iau) / AS
    d_cip = _ang(eo.cip_gcrs(t), iau) / AS
    d_frozen = _ang(np.tile([0.0, 0.0, 1.0], (ets.size, 1)), iau) / AS
    print(f"IAU_EARTH vs mean pole max {d_mean.max():.3f}\", vs CIP max {d_cip.max():.3f}\", "
          f"vs frozen J2000 pole max {d_frozen.max():.1f}\"")
    assert d_mean.max() <= 1.5
    assert d_cip.max() <= 11.0 + 1.5
    assert d_frozen.max() > 900.0                              # what the frozen pole missed by 2049
