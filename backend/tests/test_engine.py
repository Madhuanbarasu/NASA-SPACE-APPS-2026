"""Engine tests named after the blueprint validation matrix (Section 10.1).

Test function names start with the test ID (test_V01_..., test_V02a_...), which
run_validation.py maps into backend/validation/report.json.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from conftest import needs_kernels


# ------------------------------------------------------------------ V-01
@needs_kernels
def test_V01_utc_tdb_roundtrip(kernels):
    import spiceypy as sp
    from lunaops.engine.timeutil import parse_utc, to_utc

    for t in ["2026-11-14T09:00:00Z", "2027-03-20T12:34:56.250Z", "2030-01-01T00:00:00Z"]:
        et = parse_utc(t)
        back = parse_utc(to_utc(et, 6))
        assert abs(back - et) < 1e-3                        # round trip within 1 ms
    # agreement with SPICE for a plain ISO string
    assert parse_utc("2026-11-14T09:00:00Z") == sp.str2et("2026-11-14T09:00:00")


# ------------------------------------------------------------------ V-02
@needs_kernels
def test_V02a_frame_definitions(kernels):
    import spiceypy as sp

    code = sp.namfrm(kernels.frame)
    assert code != 0
    cent, frclss, clssid = sp.frinfo(code)
    assert cent == 301                                      # centred on the Moon
    if kernels.profile == "production":
        assert kernels.frame == "MOON_ME_DE440_ME421"


@needs_kernels
def test_V02b_rotation_matrices(kernels):
    import spiceypy as sp
    from lunaops.engine.timeutil import parse_utc

    et = parse_utc("2026-11-14T00:00:00Z")
    pa = kernels.pa_frame
    m = np.array(sp.pxform(pa, kernels.frame, et))
    assert np.allclose(m @ m.T, np.eye(3), atol=1e-12)
    assert abs(np.linalg.det(m) - 1.0) < 1e-12
    ang = math.degrees(math.acos(max(-1.0, min(1.0, (np.trace(m) - 1) / 2))))
    if kernels.profile == "production":
        assert abs(ang - 0.02886) < 5e-5                     # FK-documented PA-ME offset
    else:
        assert 0.02 < ang < 0.04                             # DE421 PA-ME offset is of the same order


@needs_kernels
def test_V02c_transformation_direction(kernels):
    import spiceypy as sp
    from lunaops.engine.timeutil import parse_utc

    et = parse_utc("2026-11-14T00:00:00Z")
    v = np.array([0.3, -0.4, 0.866])
    fwd = np.array(sp.pxform(kernels.pa_frame, kernels.frame, et)) @ v
    back = np.array(sp.pxform(kernels.frame, kernels.pa_frame, et)) @ fwd
    assert np.allclose(back, v, atol=1e-12)


def test_V02d_site_roundtrip():
    from lunaops.engine.frames import latlon_to_xyz_m, xyz_to_latlon

    for lat, lon, h in [(-89.9, 12.0, 1500.0), (-85.4, 359.99, -2500.0), (0.0, 180.0, 0.0), (89.0, 45.0, 10.0)]:
        la, lo, hh = xyz_to_latlon(latlon_to_xyz_m(lat, lon, h))
        p1 = latlon_to_xyz_m(lat, lon, h)
        p2 = latlon_to_xyz_m(la, lo, hh)
        assert np.linalg.norm(p1 - p2) < 1e-3              # within 1 mm


@needs_kernels
def test_V02e_de421_de440_residual(kernels):
    if kernels.profile != "production" or not kernels.de421_available:
        pytest.skip("needs production DE440 kernels plus the DE421 lunar PCK/FK")
    import spiceypy as sp
    from lunaops import settings
    from lunaops.engine.timeutil import parse_utc

    worst = 0.0
    for year in range(2026, 2037):
        et = parse_utc(f"{year}-06-01T00:00:00Z")
        m = np.array(sp.pxform("MOON_ME_DE421", kernels.frame, et))
        ang = math.acos(max(-1.0, min(1.0, (np.trace(m) - 1) / 2)))
        worst = max(worst, ang * settings.R_MOON_M)
    print(f"V-02e d_max = {worst:.3f} m")
    assert worst <= 1.0, f"d_max {worst:.3f} m exceeds the 1 m rule; apply R(t) per Section 7.4"


# ------------------------------------------------------------------ V-03
@needs_kernels
@pytest.mark.parametrize("lat,lon", [(-89.5, 0.0), (-85.3, 210.0), (-60.0, 33.0), (0.0, 0.0), (45.0, 300.0), (90.0, 0.0)])
def test_V03_azel_vs_azlcpo(kernels, lat, lon):
    import spiceypy as sp
    from lunaops.engine.ephem import Site, sample_target
    from lunaops.engine.timeutil import parse_utc

    et0 = parse_utc("2026-11-14T00:00:00Z")
    site = Site(lat, lon, 0.0, 0.0)
    for tgt, name in (("sun", "SUN"), ("earth", "EARTH")):
        for k in range(6):
            et = et0 + k * 17_000.0
            s = sample_target(site, tgt, [et])
            st, _ = sp.azlcpo("ELLIPSOID", name, et, "CN+S", False, True, site.pos_km, "MOON", kernels.frame)
            daz = (s.az[0] - math.degrees(st[1]) + 180.0) % 360.0 - 180.0
            if abs(s.el[0]) < 89.9:
                assert abs(daz) < 1e-6
            assert abs(s.el[0] - math.degrees(st[2])) < 1e-6


@needs_kernels
def test_V03_south_pole_recorded(kernels):
    """AZLCPO documents no frame at the south pole (VT-10): record its output beside ours."""
    import spiceypy as sp
    from lunaops.engine.ephem import Site, sample_target
    from lunaops.engine.timeutil import parse_utc

    et = parse_utc("2026-11-14T00:00:00Z")
    site = Site(-90.0, 0.0, 0.0, 0.0)
    s = sample_target(site, "sun", [et])
    try:
        st, _ = sp.azlcpo("ELLIPSOID", "SUN", et, "CN+S", False, True, site.pos_km, "MOON", kernels.frame)
        print(f"VT-10 south pole: LUNA-OPS az {s.az[0]:.6f} el {s.el[0]:.6f}; AZLCPO az {math.degrees(st[1]):.6f} "
              f"el {math.degrees(st[2]):.6f}")
    except Exception as exc:
        print(f"VT-10 south pole: AZLCPO raised {type(exc).__name__}")
    assert np.isfinite(s.az[0]) and np.isfinite(s.el[0])


# ------------------------------------------------------------------ V-06
@needs_kernels
def test_V06_sphere_dip(kernels, tmp_path):
    from lunaops.engine.dem import LevelWindow
    from lunaops.engine.horizon import compute_horizon, sphere_dip_deg

    n = 1601
    data = np.zeros((n, n), dtype=np.float32)
    for obs in (2.0, 10.0):
        # a flat synthetic window centred on a site (heights 0 everywhere)
        from lunaops.engine.frames import south_polar_stereo_xy, unit_from_latlon
        lat, lon = -88.0, 40.0
        cx, cy = south_polar_stereo_xy(unit_from_latlon(math.radians(lat), math.radians(lon)), 1_737_400.0)
        pix = 20.0
        w = LevelWindow("20m", data, cx - (n // 2) * pix, cy + (n // 2) * pix, pix, -pix, (n // 2 - 2) * pix, pix,
                        {"product": "synthetic flat", "synthetic": True})
        hz = compute_horizon(lat, lon, obs, pyramid=[w])
        assert not hz.incomplete.any()
        assert np.max(np.abs(hz.h_deg - sphere_dip_deg(obs))) < 1e-3


@needs_kernels
def test_V06_synthetic_crater(kernels, synthetic_crater):
    from lunaops.engine.horizon import compute_horizon
    from lunaops.testing import reference_horizon

    lat, lon, obs = -89.85, 75.0, 2.0
    hz = compute_horizon(lat, lon, obs)
    az = np.arange(0.0, 360.0, 7.5)
    ref = reference_horizon(lat, lon, obs, az, "crater", max_d=40_000.0)
    mine = hz.h_deg[np.round(az / 0.1).astype(int) % hz.nbins]
    assert np.max(np.abs(mine - ref)) < 0.01


# ------------------------------------------------------------------ V-07
@needs_kernels
def test_V07_exact_stopping_changes_nothing(kernels, synthetic_crater):
    """The stopping bound is conservative: stopping early must never change any bin."""
    from lunaops.engine.horizon import compute_horizon

    for lat, lon, obs in ((-89.85, 75.0, 2.0), (-89.2, 300.0, 0.0), (-88.0, 10.0, 50.0)):
        a = compute_horizon(lat, lon, obs, use_stop=True)
        b = compute_horizon(lat, lon, obs, use_stop=False)
        assert np.array_equal(a.h_deg, b.h_deg)


@needs_kernels
def test_V07_convergence_and_incomplete_flags(kernels, synthetic_crater):
    from lunaops.engine.horizon import compute_horizon

    lat, lon = -89.7, 200.0
    a = compute_horizon(lat, lon, 2.0, nbins=3600)
    b = compute_horizon(lat, lon, 2.0, nbins=7200)
    diff = np.abs(a.h_deg - b.h_deg[::2])
    assert np.percentile(diff, 95) <= 0.01
    # a site near the edge of the synthetic coverage must flag incomplete bins (lower bounds)
    edge = compute_horizon(-80.6, 0.0, 0.0)   # ~285 km from the pole, near the 300 km synthetic edge
    assert edge.incomplete.any()


# ------------------------------------------------------------------ V-08
def test_V08_disk_integrator_vs_circular_segment():
    from lunaops.engine.visibility import HorizonProfile, disk_state, segment_area_fraction

    for rho in (0.2617, 0.2717, 0.8986, 1.0254):
        el_c = 2.0
        for a in np.linspace(-rho * 0.999, rho * 0.999, 41):
            hp = HorizonProfile(np.full(3600, el_c - a), np.zeros(3600, bool))
            st = disk_state(hp, 123.4, el_c, rho)
            assert abs(st["f"] - segment_area_fraction(rho, a)) <= 1e-3


def test_V08_tangent_plane_vs_spherical_cap():
    """VT-8: exact spherical sampling of the disk at elevations up to 60 degrees."""
    from lunaops.engine.visibility import HorizonProfile, disk_state

    rng = np.random.default_rng(7)
    h = 1.0 + 0.8 * np.sin(np.radians(np.arange(3600) * 0.1 * 7)) + 0.3 * np.sin(np.radians(np.arange(3600) * 0.1 * 23))
    hp = HorizonProfile(h, np.zeros(3600, bool))
    for el in (1.5, 2.0, 2.5):
        for rho in (0.27, 1.0):
            az = 77.0
            st = disk_state(hp, az, el, rho)
            # exact: points uniform on the spherical cap around (az, el)
            c0 = math.cos(math.radians(rho))
            n = 200_000
            cz = rng.uniform(c0, 1.0, n)
            ph = rng.uniform(0, 2 * math.pi, n)
            sz = np.sqrt(1 - cz * cz)
            loc = np.stack([sz * np.cos(ph), sz * np.sin(ph), cz], axis=1)  # cap around +z
            A, E = math.radians(az), math.radians(el)
            centre = np.array([math.cos(E) * math.sin(A), math.cos(E) * math.cos(A), math.sin(E)])  # east, north, up
            east = np.array([math.cos(A), -math.sin(A), 0.0])
            north = np.cross(centre, east)
            pts = loc[:, :1] * east + loc[:, 1:2] * north + loc[:, 2:3] * centre
            pel = np.degrees(np.arcsin(pts[:, 2]))
            paz = np.degrees(np.arctan2(pts[:, 0], pts[:, 1])) % 360
            f_exact = float(np.mean(pel > hp.at(paz)))
            assert abs(st["f"] - f_exact) < 0.01   # Monte Carlo noise ~0.001; tangent-plane error is smaller


def test_V08_joint_terrain_and_earth():
    from lunaops.engine.visibility import HorizonProfile, disk_state, sun_fraction_with_earth

    hp = HorizonProfile(np.full(3600, 1.0), np.zeros(3600, bool))
    sun = {"az": 100.0, "el": 1.0, "rho": 0.27}
    st = disk_state(hp, sun["az"], sun["el"], sun["rho"])
    assert abs(st["f"] - 0.5) < 2e-3
    earth = {"az": 100.0, "el": 1.27, "rho": 0.95}
    sun["gamma"] = 0.27
    f, occ = sun_fraction_with_earth(hp, sun, earth, st)
    assert 0.0 <= f < 0.5 and occ > 0


def test_V08b_power_indicator_analytic():
    from lunaops import settings
    from lunaops.engine.power import p_rel

    au = settings.AU_KM
    assert abs(p_rel(1.0, au, 0.0, 0.0, "vertical_tracking")[()] - 1.0) < 1e-9
    assert abs(p_rel(1.0, au, 0.0, 30.0, "vertical_tracking")[()] - math.cos(math.radians(30))) < 1e-9
    assert abs(p_rel(1.0, au, 0.0, 30.0, "horizontal")[()] - 0.5) < 1e-9
    assert abs(p_rel(0.0, au, 0.0, 30.0, "horizontal")[()]) < 1e-12
    assert abs(p_rel(1.0, au / 2, 0.0, 0.0, "vertical_tracking")[()] - 4.0) < 1e-9
    assert abs(p_rel(1.0, au, 90.0, 0.0, "fixed_vertical", 0.0)[()]) < 1e-9


def test_V08_spherical_disk_near_zenith():
    """VT-8: disks at high elevation (including one touching the zenith) vs exact spherical Monte Carlo."""
    from lunaops.engine.visibility import HorizonProfile, disk_state

    rng = np.random.default_rng(11)
    cases = [(60.5, 0.27, 60.4), (75.0, 1.0, 75.3), (85.0, 0.27, 84.9), (89.7, 0.27, 89.6), (89.9, 1.0, 89.5)]
    for el, rho, hlev in cases:
        h = np.full(3600, -5.0)
        h[0:1800] = hlev                      # a high horizon over half the sky cuts the disk
        hp = HorizonProfile(h, np.zeros(3600, bool))
        az = 80.0
        st = disk_state(hp, az, el, rho)
        assert st.get("method") == "spherical"
        c0 = math.cos(math.radians(rho))
        n = 400_000
        cz = rng.uniform(c0, 1.0, n)
        ph = rng.uniform(0, 2 * math.pi, n)
        sz = np.sqrt(1 - cz * cz)
        A, E = math.radians(az), math.radians(el)
        centre = np.array([math.cos(E) * math.sin(A), math.cos(E) * math.cos(A), math.sin(E)])
        t1 = np.array([math.cos(A), -math.sin(A), 0.0])
        t2 = np.cross(centre, t1)
        pts = (sz * np.cos(ph))[:, None] * t1 + (sz * np.sin(ph))[:, None] * t2 + cz[:, None] * centre
        pel = np.degrees(np.arcsin(pts[:, 2]))
        paz = np.degrees(np.arctan2(pts[:, 0], pts[:, 1])) % 360
        f_exact = float(np.mean(pel > hp.at(paz)))
        assert abs(st["f"] - f_exact) < 0.003, (el, rho, st["f"], f_exact)


def test_dem_registry_migration_and_multi_product(tmp_path):
    """Several products may share a level; the old one-file-per-level registry migrates."""
    from lunaops.engine.dem import _migrate, product_key

    old = {"levels": {"20m": {"level": "20m", "path": "/x/A.tif", "pixel_m": 20.0, "sha256": "a"},
                      "240m": {"level": "240m", "path": "/x/B.tif", "pixel_m": 240.0, "sha256": "b"}},
           "error_maps": {"20m": {"path": "/x/A_ERR.tif"}}}
    new = _migrate(old)
    assert len(new["products"]) == 2
    assert product_key(new["products"][0]) in new["error_maps"]


@needs_kernels
def test_dem_multi_product_sampling(kernels, synthetic_crater, tmp_path):
    """A finer product registered beside coarser ones is used where it has data, and changes cache keys."""
    from lunaops import settings
    from lunaops.acquire import _basic_info
    from lunaops.engine.dem import coverage_check, load_pyramid, read_registry, write_registry
    from lunaops.engine.horizon import compute_horizon, horizon_key
    from lunaops.engine.kernels import sha256_of
    from lunaops.testing import write_synthetic_dem

    lat, lon = -89.85, 75.0
    key_before = horizon_key(lat, lon, 2.0, 3600)
    before = compute_horizon(lat, lon, 2.0)
    p = settings.DEM_DIR / "synthetic" / "SYNTH_CRATER_5m_extra.tif"
    write_synthetic_dem(p, 5.0, 6_000.0, kind="crater")
    reg = read_registry()
    reg["products"].append({"level": "5m", "product_id": "synthetic_5m", "path": str(p), "sha256": sha256_of(p),
                            "bytes": p.stat().st_size, "product": "SYNTHETIC TEST TERRAIN (crater)", "synthetic": True,
                            "pixel_m": 5.0, **_basic_info(p)})
    write_registry(reg)
    try:
        pyr = load_pyramid(lat, lon)
        assert [w.level for w in pyr][:1] == ["5m"] and len(pyr) == 3
        assert "5m" in coverage_check(-89.97, 0.0)["levels"]
        after = compute_horizon(lat, lon, 2.0)
        assert after.site_level == "5m"
        assert horizon_key(lat, lon, 2.0, 3600) != key_before
        assert np.max(np.abs(after.h_deg - before.h_deg)) < 0.05   # same analytic terrain, finer sampling
    finally:
        reg["products"] = [x for x in reg["products"] if x["path"] != str(p)]
        write_registry(reg)


@needs_kernels
def test_label_integrity(kernels, monkeypatch):
    """Validated only for the same code fingerprint, production kernels and identical kernel files."""
    import lunaops.engine.provenance as prov
    from lunaops.fingerprint import code_fingerprint, suite_fingerprint

    class FakeKS:
        profile = "production"
        files = [{"sha256": "k1"}, {"sha256": "k2"}]

    # every requirement passed: each quantity's tests plus the global ones (U-04, U-06; Phase 3 reconciliation)
    all_tests = {t: {"status": "passed"} for q in prov.QUANTITY_TESTS.values() for t in q}
    all_tests.update({t: {"status": "passed"} for t in prov.GLOBAL_TESTS})
    good = {"code_fingerprint": code_fingerprint(), "suite_fingerprint": suite_fingerprint(),
            "pytest_exit_code": 0, "kernel_profile": "production",
            "kernels": [{"sha256": "k2"}, {"sha256": "k1"}], "tests": all_tests}
    monkeypatch.setattr(prov, "load", lambda: FakeKS())
    monkeypatch.setattr(prov, "terrain_is_synthetic", lambda: False)
    monkeypatch.setattr(prov, "validation_report", lambda: good)
    assert all(v["validation"] == "Validated" for v in prov.labels().values())
    for bad in ({**good, "code_fingerprint": "other"}, {**good, "kernel_profile": "sandbox-test"},
                {**good, "kernels": [{"sha256": "k1"}]}, {**good, "suite_fingerprint": "edited-tests"},
                {**good, "pytest_exit_code": 1}, {**good, "pytest_exit_code": None},
                {**good, "tests": {**all_tests, "V-02e": {"status": "skipped"}}},
                {**good, "tests": {**all_tests, "U-04": {"status": "not run"}}}, None):
        monkeypatch.setattr(prov, "validation_report", lambda b=bad: b)
        labs = prov.labels()
        assert all(v["validation"] == "Pending validation" for v in labs.values())
        assert all(v["reasons"] for v in labs.values())


def test_external_merge_guard():
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from validation.common import merge_external

    now = {"code_fingerprint": "abc", "suite_fingerprint": "s1", "kernel_profile": "production", "kernels": ["k1", "k2"]}
    tests = {}
    meta = {**now, "kernels": ["k2", "k1"], "script": "horizons_compare"}
    assert merge_external(tests, {"meta": meta, "tests": {"V-04": {"status": "passed"}}}, now) == []
    assert tests["V-04"]["status"] == "passed"
    tests2 = {}
    why = merge_external(tests2, {"meta": {**meta, "code_fingerprint": "zzz"}, "tests": {"V-04": {"status": "passed"}}}, now)
    assert why and "V-04" not in tests2
