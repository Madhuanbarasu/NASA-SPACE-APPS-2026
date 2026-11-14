"""Regression tests for the 2026-11 audit: disk accuracy, terrain safeguards, DEM/error-map
association, validation-merge integrity and the V-14 checking helpers."""
from __future__ import annotations

import io
import json
import math
import tarfile
from argparse import Namespace
from pathlib import Path

import numpy as np
import pytest

from conftest import needs_kernels


# ------------------------------------------------------------ disk accuracy (V-08)
def _cap_column(az, el, rho, azs):
    """Independent reference: elevation range of the cap on each azimuth meridian (closed form)."""
    A, E, r = math.radians(az), math.radians(el), math.radians(rho)
    c = np.array([math.cos(E) * math.sin(A), math.cos(E) * math.cos(A), math.sin(E)])
    a = np.radians(azs)
    P = np.sin(a) * c[0] + np.cos(a) * c[1]
    K = np.hypot(P, c[2])
    phi = np.arctan2(c[2], P)
    ok = K >= math.cos(r)
    d = np.arccos(np.clip(math.cos(r) / K, -1, 1))
    return np.degrees(np.where(ok, phi - d, np.nan)), np.degrees(np.where(ok, phi + d, np.nan))


def _exact_reference(hp, az, el, rho, n=200001):
    """Edge clearances (max/min of el_p - H(az_p)) and visible solid-angle fraction by dense meridian
    integration, with every horizon node included so kinks are not missed."""
    hw = math.degrees(math.asin(math.sin(math.radians(rho)) / math.cos(math.radians(el))))
    nodes = np.arange(math.ceil((az - hw) / hp.bin), math.floor((az + hw) / hp.bin) + 1) * hp.bin
    azs = np.unique(np.concatenate([az + np.linspace(-hw, hw, n), nodes]))
    lo, hi = _cap_column(az, el, rho, azs)
    m = np.isfinite(lo)
    azs, lo, hi = azs[m], lo[m], hi[m]
    H = hp.at(azs)
    e1 = np.clip(H, lo, hi)
    vis = np.sin(np.radians(hi)) - np.sin(np.radians(e1))
    tot = np.sin(np.radians(hi)) - np.sin(np.radians(lo))
    da = np.gradient(np.radians(azs))
    return float(np.sum(vis * da) / np.sum(tot * da)), float(np.max(hi - H)), float(np.min(lo - H))


def test_V08_disk_exact_on_sphere_vs_independent_reference():
    """The closed-form cap solution matches an independent dense spherical integration at every
    elevation it is used for (the former tangent-plane model erred by up to 1.3e-2 deg at 60 deg)."""
    from lunaops.engine.visibility import HorizonProfile, disk_state

    rng = np.random.default_rng(5)
    az_n = np.arange(3600) * 0.1
    base = 0.8 * np.sin(np.radians(az_n * 7)) + 1.5 * np.sin(np.radians(az_n * 60)) + 0.15 * rng.standard_normal(3600)
    worst_f = worst_g = 0.0
    for rho in (0.2667, 0.95):
        for el in (1.0, 12.0, 37.0, 59.9):
            hp = HorizonProfile(el + base, np.zeros(3600, bool))
            for az in (13.3, 101.7, 222.2, 347.9):
                st = disk_state(hp, az, el, rho)
                f, gt, gb = _exact_reference(hp, az, el, rho)
                worst_f = max(worst_f, abs(st["f"] - f))
                worst_g = max(worst_g, abs(st["g_top"] - gt), abs(st["g_bot"] - gb))
    assert worst_f < 1e-6, worst_f
    assert worst_g < 1e-7, worst_g
    print(f"exact-sphere disk: worst |df| {worst_f:.1e}, worst |dg| {worst_g:.1e} deg")


def test_V08_switch_to_sampled_cap_at_60_deg_is_small():
    """Above 60 deg the cap is sampled; measure the step in clearances across the switch."""
    from lunaops.engine.visibility import HorizonProfile, disk_state

    az_n = np.arange(3600) * 0.1
    worst = 0.0
    for rho in (0.2667, 0.95):
        hp = HorizonProfile(60.0 + 0.9 * np.sin(np.radians(az_n * 40)), np.zeros(3600, bool))
        for az in (20.0, 140.0, 260.0):
            a = disk_state(hp, az, 60.0 - 1e-9, rho)
            b = disk_state(hp, az, 60.0 + 1e-9, rho)
            assert a["method"] == "sphere-exact" and b["method"] == "spherical"
            worst = max(worst, abs(a["g_top"] - b["g_top"]), abs(a["g_bot"] - b["g_bot"]))
    assert worst < 2e-3, worst
    print(f"clearance step at the 60 deg switch: {worst:.1e} deg")


def test_V08_occultation_clearance_exact():
    """With terrain far below, the combined clearance equals gamma + rho_sun - rho_earth exactly."""
    from lunaops.engine.visibility import HorizonProfile, disk_state, sun_visibility_with_earth

    hp = HorizonProfile(np.full(3600, -30.0), np.zeros(3600, bool))
    for gamma in (0.10, 0.6, 0.68, 0.70, 1.1):
        sun = {"az": 40.0, "el": 10.0, "rho": 0.2667, "gamma": gamma}
        # Earth placed gamma away along the vertical through the Sun
        earth = {"az": 40.0, "el": 10.0 + gamma, "rho": 0.95}
        st = disk_state(hp, sun["az"], sun["el"], sun["rho"])
        _f, _occ, g = sun_visibility_with_earth(hp, sun, earth, st)
        if gamma < sun["rho"] + earth["rho"]:
            assert abs(g - (gamma + sun["rho"] - earth["rho"])) < 1e-9, (gamma, g)


# --------------------------------------------------------------- terrain safeguards
@needs_kernels
def test_terrain_missing_or_changed_file_is_refused_not_skipped(kernels, synthetic_crater):
    from lunaops.engine.dem import (TerrainError, coverage_check, load_pyramid, products_digest, read_registry,
                                    write_registry)

    reg = read_registry()
    saved = json.loads(json.dumps(reg))
    try:
        before = products_digest()
        fine = next(p for p in reg["products"] if p["level"] == "20m")
        fine["path"] = fine["path"] + ".moved"           # simulate a deleted/moved file
        write_registry(reg)
        assert products_digest() != before                # cache keys can no longer collide
        with pytest.raises(TerrainError, match="missing"):
            load_pyramid(-89.9, 10.0)
        cov = coverage_check(-89.9, 10.0)
        assert not cov["covered"] and "missing" in cov["reason"]
        reg = json.loads(json.dumps(saved))
        next(p for p in reg["products"] if p["level"] == "20m")["bytes"] += 1   # size no longer matches
        write_registry(reg)
        with pytest.raises(TerrainError, match="changed on disk"):
            load_pyramid(-89.9, 10.0)
    finally:
        write_registry(saved)


@needs_kernels
def test_terrain_digest_follows_synthetic_permission(kernels, synthetic_crater, monkeypatch):
    from lunaops import settings
    from lunaops.engine.dem import products_digest

    on = products_digest()
    monkeypatch.setattr(settings, "SYNTHETIC_TERRAIN_ALLOWED", False)
    assert products_digest() != on and products_digest() == []


def test_dem_rejects_implausible_values_and_accepts_error_maps(tmp_path):
    """Undeclared nodata (e.g. -32768) is refused; an error map in metres (< 20) is not mistaken for km."""
    import rasterio
    from rasterio.crs import CRS
    from rasterio.transform import from_origin

    from lunaops.engine.dem import TerrainError, inspect_raster
    from lunaops.testing import STEREO_PROJ4

    def write(path, arr):
        with rasterio.open(path, "w", driver="GTiff", width=arr.shape[1], height=arr.shape[0], count=1,
                           dtype="float32", crs=CRS.from_proj4(STEREO_PROJ4),
                           transform=from_origin(-2560, 2560, 20, 20)) as dst:
            dst.write(arr.astype(np.float32), 1)

    z = np.full((256, 256), 500.0)
    z[100:140, 100:140] = -32768.0
    write(tmp_path / "bad.tif", z)
    with pytest.raises(TerrainError, match="undeclared nodata"):
        inspect_raster(tmp_path / "bad.tif")
    err = np.full((256, 256), 0.4)
    write(tmp_path / "err.tif", err)
    with pytest.raises(TerrainError):                 # the height heuristic would refuse it ...
        inspect_raster(tmp_path / "err.tif")
    assert inspect_raster(tmp_path / "err.tif", kind="error_map")["pixel_m"] == 20.0   # ... the error-map check does not
    write(tmp_path / "neg.tif", -err)
    with pytest.raises(TerrainError, match="negative"):
        inspect_raster(tmp_path / "neg.tif", kind="error_map")


# ------------------------------------------------------------- error-map association
def _write_like(path, rec, value):
    import rasterio
    from rasterio.crs import CRS

    from lunaops.testing import STEREO_PROJ4
    a, b, c, d, e, f = rec["transform"]
    with rasterio.open(path, "w", driver="GTiff", width=rec["width"], height=rec["height"], count=1,
                       dtype="float32", crs=CRS.from_proj4(STEREO_PROJ4), transform=rasterio.Affine(a, b, c, d, e, f),
                       compress="deflate") as dst:
        dst.write(np.full((rec["height"], rec["width"]), value, np.float32), 1)


@needs_kernels
def test_sigma_uses_the_error_map_of_the_product_that_was_sampled(kernels, synthetic_crater, monkeypatch, tmp_path):
    """A finer product's error map must not be applied to terrain sampled from a coarser product, even
    where the finer product's error map has data (the former code took the finest map with data)."""
    from lunaops import settings
    from lunaops.acquire import _error_map_record
    from lunaops.engine.dem import error_map_for, product_key, products_digest, read_registry, write_registry
    from lunaops.engine.horizon import compute_horizon, horizon_key

    reg = read_registry()
    saved = json.loads(json.dumps(reg))
    fine = next(p for p in reg["products"] if p["level"] == "20m")
    coarse = next(p for p in reg["products"] if p["level"] == "240m")
    _write_like(tmp_path / "fine_err.tif", fine, 0.5)
    _write_like(tmp_path / "coarse_err.tif", coarse, 7.0)
    key_before = horizon_key(-89.9, 30.0, 2.0, 3600)
    try:
        reg["error_maps"][product_key(fine)] = _error_map_record(tmp_path / "fine_err.tif", fine, {})
        reg["error_maps"][product_key(coarse)] = _error_map_record(tmp_path / "coarse_err.tif", coarse, {})
        write_registry(reg)
        assert horizon_key(-89.9, 30.0, 2.0, 3600) != key_before          # error maps are part of the cache key
        # the 20 m product covers 45 km, but serve it only to 8 km: the crater rim (9-15 km away) is then
        # sampled from the 240 m product although the 20 m error map has data there
        monkeypatch.setitem(settings.DEM_WINDOW_HALF_M, "20m", 8_000.0)
        hz = compute_horizon(-89.9, 30.0, 2.0)
        ok = np.isfinite(hz.sigma_deg) & (hz.block_dist_m > 0)
        band = next(lv["band_m"] for lv in hz.levels if lv["level"] == "20m")
        near, far = ok & (hz.block_dist_m <= band), ok & (hz.block_dist_m > band)
        # each bin reads the error map of the product that supplied its blocking sample (Phase 2: checked on
        # the per-bin value itself, independent of the propagation model)
        assert far.sum() > 100 and np.allclose(hz.sigma_block_m[far], 7.0, rtol=1e-5), \
            np.unique(np.round(hz.sigma_block_m[far], 3))
        if near.any():
            assert np.allclose(hz.sigma_block_m[near], 0.5, rtol=1e-5)
        i_coarse = next(i for i, lv in enumerate(hz.levels) if lv["level"] == "240m")
        assert np.all(hz.blocker_product[far] == i_coarse) and np.all(hz.cross_product[far])
        # and the final sigma is the exact first-order propagation of those values (site map 0.5 m,
        # blocker from another product -> rho = 0 plus the measured cross-product allowance)
        from lunaops.engine.frames import enu_basis
        from lunaops.engine.horizon import elevation_gradients, propagate_sigma
        e, n, u = enu_basis(-89.9, 30.0)
        a = 2 * np.pi * np.arange(hz.nbins) / hz.nbins
        t = np.outer(np.cos(a), n) + np.outer(np.sin(a), e)
        dlt = hz.block_dist_m / settings.R_MOON_M
        p = np.outer(np.cos(dlt), u) + np.sin(dlt)[:, None] * t
        g_b, g_s, _ = elevation_gradients(u, p[far], hz.block_h_m[far], settings.R_MOON_M + hz.ground_h_m + 2.0)
        note = hz.params["sigma"]
        assert note["site_sigma_m"] == pytest.approx(0.5)
        pair = next(v for v in note["cross_product_discrepancy_allowance"].values() if v["status"] == "measured")
        want = np.degrees(propagate_sigma(g_b, g_s, 7.0, 0.5, 0.0, pair["allowance_m"]))
        np.testing.assert_allclose(hz.sigma_deg[far], want, rtol=1e-4)
        # an error map registered for other bytes of its DEM is never used
        reg2 = read_registry()
        reg2["error_maps"][product_key(fine)]["dem_sha256"] = "0" * 64
        write_registry(reg2)
        assert error_map_for(fine, read_registry()) is None
        assert [r for r in products_digest() if r[0] == product_key(fine)][0][2] is None
    finally:
        write_registry(saved)


def test_error_map_must_share_the_dem_grid(tmp_path):
    import rasterio
    from rasterio.crs import CRS
    from rasterio.transform import from_origin

    from lunaops.acquire import _error_map_record
    from lunaops.testing import STEREO_PROJ4

    dem = {"path": str(tmp_path / "dem.tif"), "sha256": "d" * 64, "pixel_m": 20.0, "width": 100, "height": 100,
           "transform": [20.0, 0.0, -1000.0, 0.0, -20.0, 1000.0]}

    def write(name, pix, x0):
        with rasterio.open(tmp_path / name, "w", driver="GTiff", width=100, height=100, count=1, dtype="float32",
                           crs=CRS.from_proj4(STEREO_PROJ4), transform=from_origin(x0, 1000.0, pix, pix)) as d:
            d.write(np.full((100, 100), 1.0, np.float32), 1)

    write("ok.tif", 20.0, -1000.0)
    assert _error_map_record(tmp_path / "ok.tif", dem, {})["dem_sha256"] == "d" * 64
    write("coarse.tif", 40.0, -1000.0)
    with pytest.raises(SystemExit, match="pixel size"):
        _error_map_record(tmp_path / "coarse.tif", dem, {})
    write("shifted.tif", 20.0, -990.0)
    with pytest.raises(SystemExit, match="fraction of a pixel"):
        _error_map_record(tmp_path / "shifted.tif", dem, {})


# ----------------------------------------------------------------- catalogue sources
def _tiny_shapefile(folder: Path, stem: str):
    import shapefile
    w = shapefile.Writer(str(folder / stem), shapeType=shapefile.POLYGON)
    w.field("name", "C")
    w.poly([[(-5000, -5000), (5000, -5000), (5000, 5000), (-5000, 5000), (-5000, -5000)]])
    w.record("roi")
    w.close()
    from lunaops.testing import STEREO_PROJ4
    from pyproj import CRS
    (folder / f"{stem}.prj").write_text(CRS.from_proj4(STEREO_PROJ4).to_wkt())


def test_pgda_roi_tgz_registers_with_unique_ids(tmp_path):
    from lunaops import settings
    from lunaops.acquire import cmd_register_catalog

    cat = settings.CATALOG_DIR / "sites.json"
    saved = cat.read_text() if cat.exists() else None
    try:
        for site in ("Site01", "Site04"):
            d = tmp_path / site
            d.mkdir()
            _tiny_shapefile(d, "ROI_1")                    # same stem in both archives
            with tarfile.open(tmp_path / f"{site}_ROIs.tgz", "w:gz") as tf:
                for f in d.iterdir():
                    tf.add(f, arcname=f.name)
            cmd_register_catalog(Namespace(usgs=None, pgda=str(tmp_path / f"{site}_ROIs.tgz")))
        sites = json.loads(cat.read_text())["sites"]
        ids = {s["id"] for s in sites if s["kind"] == "pgda_site"}
        assert {"pgda_site:Site01_ROIs/ROI_1", "pgda_site:Site04_ROIs/ROI_1"} <= ids
        s0 = next(s for s in sites if s["id"] == "pgda_site:Site01_ROIs/ROI_1")
        assert s0["lat"] < -89.0 and "Bounding box" in s0["extent_label"]
        # an archive member escaping the extraction folder is refused
        evil = tmp_path / "evil.tgz"
        with tarfile.open(evil, "w:gz") as tf:
            data = b"x"
            ti = tarfile.TarInfo("../escape.shp")
            ti.size = len(data)
            tf.addfile(ti, io.BytesIO(data))
        with pytest.raises(SystemExit, match="unsafe"):
            cmd_register_catalog(Namespace(usgs=None, pgda=str(evil)))
    finally:
        if saved is None:
            cat.unlink(missing_ok=True)
        else:
            cat.write_text(saved)


# --------------------------------------------------------------- validation integrity
def test_merge_guard_ownership_status_and_no_upgrade():
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from validation.common import merge_external

    now = {"code_fingerprint": "c", "suite_fingerprint": "s", "kernel_profile": "production", "kernels": ["k"]}
    meta = {**now, "script": "v14_month"}
    # a script may not report tests it does not own (e.g. the frame-alignment test)
    t = {"V-02e": {"status": "skipped"}}
    assert merge_external(t, {"meta": meta, "tests": {"V-02e": {"status": "passed"}}}, now)
    assert t["V-02e"]["status"] == "skipped"
    # a failed automated V-14 cannot be turned into a pass by an external file
    t = {"V-14": {"status": "failed", "detail": "pytest"}}
    assert merge_external(t, {"meta": meta, "tests": {"V-14": {"status": "passed"}}}, now) == []
    assert t["V-14"]["status"] == "failed"
    # and a passing automated V-14 is failed by a failing external run
    t = {"V-14": {"status": "passed"}}
    merge_external(t, {"meta": meta, "tests": {"V-14": {"status": "failed"}}}, now)
    assert t["V-14"]["status"] == "failed"
    # unknown status words, unknown scripts and edited suites are refused
    assert merge_external({}, {"meta": meta, "tests": {"V-14": {"status": "PASSED"}}}, now)
    assert merge_external({}, {"meta": {**now, "script": "mine"}, "tests": {"V-14": {"status": "passed"}}}, now)
    assert merge_external({}, {"meta": {**meta, "suite_fingerprint": "x"}, "tests": {"V-14": {"status": "passed"}}}, now)


def test_suite_fingerprint_tracks_tests():
    from lunaops.fingerprint import suite_fingerprint
    assert len(suite_fingerprint()) == 64


# ----------------------------------------------------------------- V-14 helpers
def test_V14_crossing_helpers_open_windows_and_direction():
    from lunaops.testing import CrossingAccumulator, match_events, required_crossings

    ets = np.arange(0.0, 100.0, 1.0)
    v = np.where((ets < 20) | ((ets > 40) & (ets < 41.5)) | (ets > 60), 1.0, -1.0) + 0.0
    acc = CrossingAccumulator()
    acc.add(ets[:50], v[:50])          # two chunks: the crossing set must not depend on the split
    acc.add(ets[50:], v[50:])
    one = CrossingAccumulator()
    one.add(ets, v)
    assert acc.crossings == one.crossings
    req = required_crossings(acc.crossings, acc.first_on, acc.t0, acc.t1, 2.0)
    # window open at t0 (only its end required), 1 s window ignored, window open at t1 (only its start)
    assert [d for _, d in req] == [-1, +1]
    # an event of the wrong direction at the right time does not count
    offs, missed, unmatched = match_events(req, acc.crossings, [19.5, 60.5], [+1, +1], 3.0)
    assert len(missed) == 1 and missed[0][1] == -1
