"""Relay propagation, frames and the two legs. Uses the installed production kernels read-only (skipped without them)."""
from __future__ import annotations

import math

import numpy as np
import pytest

from lunaops import settings
from lunaops.engine.ephem import Site
from lunaops.engine.timeutil import parse_utc
from lunaops.engine.visibility import HorizonProfile
from lunaops_comms import relay as RL
from lunaops_comms.constants import R_MOON_KM, moon_gm, parse_text_kernel_value

HAVE_KERNELS = (settings.KERNEL_DIR / "lock.json").exists()
needs_kernels = pytest.mark.skipif(not HAVE_KERNELS, reason="no kernel lock")
EPOCH = "2026-11-13T00:00:00Z"


def elems(**kw):
    base = {"a_km": 1837.4 + 300.0, "e": 0.0, "i_deg": 90.0, "raan_deg": 0.0, "argp_deg": 0.0, "m0_deg": 0.0,
            "epoch_utc": EPOCH, "frame": "LME_EPOCH"}
    base.update(kw)
    el, probs = RL.validate_elements(base, parse_utc)
    assert el is not None, probs
    return el


def test_gm_read_from_verified_naif_file():
    gm = moon_gm()
    assert gm["gm_km3_s2"] == 4902.8001184575496 and gm["name"] == "BODY301_GM" and not gm["loaded_into_spice_pool"]
    assert gm["sha256"] == "924ddf4fb9ead9fe8a1aa55780bcabde40b09d00065d58226e24b68d8092f140"
    txt = "\\begintext\nBODY301_GM = ( 1.0 )\n\\begindata\n  BODY301_GM     = ( 4.9028001184575496D+03 )\n"
    assert parse_text_kernel_value(txt, "BODY301_GM") == 4902.8001184575496      # only data blocks count


def test_kepler_solver():
    for e in (0.0, 0.3, 0.7, 0.95):
        M = np.linspace(-7, 7, 101)
        E = RL.kepler_E(M, e)
        assert np.max(np.abs(np.mod(E - e * np.sin(E) - np.mod(M, 2 * math.pi) + math.pi, 2 * math.pi) - math.pi)) < 1e-12


@needs_kernels
def test_circular_orbit_radius_period_and_energy():
    gm = moon_gm()["gm_km3_s2"]
    el = elems(frame="J2000")
    T = 2 * math.pi * math.sqrt(el.a_km ** 3 / gm)
    ets = el.epoch_et + np.linspace(0, T, 9)
    r, v = RL.propagate(el, ets, gm)
    assert np.allclose(np.linalg.norm(r, axis=1), el.a_km, rtol=1e-12)
    assert np.allclose(r[0], r[-1], atol=1e-6)                               # back after one period
    assert np.allclose(np.linalg.norm(v, axis=1), math.sqrt(gm / el.a_km), rtol=1e-12)


@needs_kernels
def test_elliptic_vis_viva_and_apsides():
    gm = moon_gm()["gm_km3_s2"]
    el = elems(a_km=5000.0, e=0.6, frame="J2000", m0_deg=0.0)
    ets = el.epoch_et + np.linspace(0, 40000, 400)
    r, v = RL.propagate(el, ets, gm)
    rn, vn = np.linalg.norm(r, axis=1), np.linalg.norm(v, axis=1)
    assert np.allclose(vn ** 2 / 2 - gm / rn, -gm / (2 * el.a_km), rtol=1e-10)
    assert rn[0] == pytest.approx(5000.0 * 0.4)                                # periapsis at M0 = 0
    h = np.cross(r, v)
    assert np.allclose(h, h[0], rtol=1e-10)                                   # angular momentum conserved


@needs_kernels
def test_lunar_equator_frame_at_epoch():
    from lunaops.engine.kernels import load
    import spiceypy as sp
    ks = load()
    gm = moon_gm()["gm_km3_s2"]
    eq = elems(i_deg=0.0)
    r, _ = RL.propagate(eq, np.array([eq.epoch_et]), gm)
    rj = r @ RL.element_to_j2000(eq).T
    rbf = np.array(sp.pxform("J2000", ks.frame, eq.epoch_et)) @ rj[0]
    assert abs(rbf[2]) < 1e-6                                                 # in the lunar equator at the epoch
    pol = elems(i_deg=90.0, argp_deg=90.0)                                    # over the north pole at epoch
    r, _ = RL.propagate(pol, np.array([pol.epoch_et]), gm)
    rbf = np.array(sp.pxform("J2000", ks.frame, pol.epoch_et)) @ (RL.element_to_j2000(pol) @ r[0])
    assert rbf[2] == pytest.approx(pol.a_km, rel=1e-9)
    assert not np.allclose(RL.element_to_j2000(pol), np.eye(3))                # the frames differ
    assert np.allclose(RL.element_to_j2000(elems(frame="J2000")), np.eye(3))


@pytest.mark.parametrize("bad, msg", [({"e": 1.0}, "Eccentricity"), ({"a_km": 1700.0}, "intersects the Moon"),
                                      ({"a_km": 2000.0, "e": 0.2}, "intersects the Moon"), ({"frame": "ECLIPJ2000"}, "frame"),
                                      ({"i_deg": 200.0}, "Inclination"), ({"epoch_utc": "yesterday"}, "Epoch"),
                                      ({"a_km": None}, "Semi-major axis (km) is missing"), ({"a_km": 90000.0}, "66,000")])
def test_incomplete_or_invalid_elements_rejected(bad, msg):
    base = {"a_km": 2137.4, "e": 0.0, "i_deg": 90.0, "raan_deg": 0.0, "argp_deg": 0.0, "m0_deg": 0.0, "epoch_utc": EPOCH,
            "frame": "LME_EPOCH"}
    base.update(bad)
    el, probs = RL.validate_elements(base, parse_utc)
    assert el is None and any(msg in p for p in probs)
    assert RL.validate_elements(None, parse_utc)[0] is None


def test_relay_to_earth_occultation_geometry():
    earth = np.array([[384_400.0, 0.0, 0.0]] * 3)
    relay = np.array([[2000.0, 0.0, 0.0], [-2000.0, 0.0, 0.0], [0.0, 2000.0, 0.0]])
    c = RL.earth_limb_clearance_deg(relay, earth)
    assert c[0] > 0 and c[1] < 0                                               # same side open, far side behind the Moon
    # angle(Earth, Moon centre) from (0, 2000, 0) = acos(2000 / |(384400, -2000)|), minus the lunar angular radius
    ang = math.degrees(math.acos(2000.0 / math.hypot(384_400.0, 2000.0)))
    assert c[2] == pytest.approx(ang - math.degrees(math.asin(R_MOON_KM / 2000.0)), abs=1e-9)
    s = RL.sphere_clear_km(relay, earth, R_MOON_KM)
    assert s[0] > 0 and s[1] < 0 and s[2] > 0


def _site():
    return Site(-89.0, 0.0, 0.0, 0.0)


def test_lander_leg_horizon_wall_flat_and_incomplete():
    site = _site()
    e, n, u = site.basis
    p = site.pos_km
    overhead = p + 500.0 * u
    low = p + 1000.0 * (math.cos(math.radians(10)) * n + math.sin(math.radians(10)) * u)
    below = p + 1000.0 * (math.cos(math.radians(-5)) * n + math.sin(math.radians(-5)) * u)
    pts = np.array([overhead, low, below])
    flat = HorizonProfile(np.zeros(3600), np.zeros(3600, bool))
    wall = HorizonProfile(np.full(3600, 20.0), np.zeros(3600, bool))
    inc = HorizonProfile(np.zeros(3600), np.ones(3600, bool))
    f = RL.site_leg(p, site.basis, pts, flat)
    assert f["el_deg"][0] == pytest.approx(90.0, abs=1e-6) and f["el_deg"][1] == pytest.approx(10.0, abs=1e-6)
    assert (f["clearance_deg"] > 0).tolist() == [True, True, False]           # below the local horizon is blocked
    assert f["sphere_clear_km"][2] < 0 or f["clearance_deg"][2] < 0
    w = RL.site_leg(p, site.basis, pts, wall)
    assert (w["clearance_deg"] > 0).tolist() == [True, False, False]          # a 20 deg terrain wall blocks the 10 deg relay
    i = RL.site_leg(p, site.basis, pts, inc)
    assert i["unknown"][:2].all()                                             # incomplete horizon bins: unknown, not open
    assert f["range_km"][0] == pytest.approx(500.0)


def test_line_through_the_moon_is_blocked_even_if_dem_horizon_is_low():
    site = _site()
    p = site.pos_km
    far_side = -p * 3.0                                                       # straight through the Moon
    flat = HorizonProfile(np.full(3600, -90.0), np.zeros(3600, bool))
    r = RL.site_leg(p, site.basis, far_side[None, :], flat)
    assert r["clearance_deg"][0] < 0 and r["sphere_clear_km"][0] < 0


def test_site_below_the_reference_sphere_still_sees_overhead_relay():
    site = Site(-89.0, 0.0, -3000.0, 0.0)                                       # a crater floor 3 km below 1737.4 km
    e, n, u = site.basis
    p = site.pos_km
    flat = HorizonProfile(np.zeros(3600), np.zeros(3600, bool))
    r = RL.site_leg(p, site.basis, np.array([p + 800.0 * u, p - 800.0 * u]), flat)
    assert r["sphere_clear_km"][0] > 0 and r["clearance_deg"][0] > 0          # overhead: open
    assert r["clearance_deg"][1] < 0                                          # straight down: blocked
