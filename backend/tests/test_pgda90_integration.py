"""Regression tests for NASA PGDA90 80m regional terrain dataset integration.

Verifies:
- PGDA90 80m dataset manifest, settings, and registration
- 5m Site01 priority with 80m regional fallback
- Coordinate frames, stereographic projection compatibility, and grid alignment
- SHA-256 checksums and error map associations
- NoData handling and coverage refusal
- Horizon computation with combined error-map uncertainties
- 3D terrain grid availability at multiple resolutions
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

from conftest import needs_kernels

DEM_DIR = Path(__file__).resolve().parents[2] / "data" / "dem"
PGDA90_DEM = DEM_DIR / "pgda90_80m" / "LDEM_80S_80MPP_ADJ.tiff"
PGDA90_ERR = DEM_DIR / "pgda90_80m" / "LDEM_80S_80MPP_ADJ_ERR.tiff"
PGDA90_20M_DEM = DEM_DIR / "pgda90_20m" / "LDEM_80S_20MPP_ADJ.TIF"
PGDA90_20M_ERR = DEM_DIR / "pgda90_20m" / "LDEM_80S_20MPP_ADJ_ERR.TIF"
SITE01_DEM = DEM_DIR / "pgda78_site01" / "Site01_final_adj_5mpp_surf.tif"
SITE01_ERR = DEM_DIR / "pgda78_site01" / "Site01_final_adj_5mpp_toterr.tif"

EXPECTED_DEM_SHA256 = "82030dcbdd7c4bb0c7d858e9b4b293b9f2cda5a543ba31ec0f42784bd6beee5a"
EXPECTED_ERR_SHA256 = "e89306914bb209143f61ba66d341703d75221339424b774c6a1eb3c6c370ffc6"
EXPECTED_20M_DEM_SHA256 = "09b7ca80f9e6a146f970225d18af72fc02787669b3ef51b888e347d2b6845649"
EXPECTED_20M_ERR_SHA256 = "d64045b8aa58a24010f009ab5667ae02cc06cffa7796784dd5e2d48b3059d8cf"

# These tests read the real NASA files named in data/dem/registry.json. The files are not in git
# (each user downloads them, README step 3), so the tests skip when they are not on disk.
REAL_DEMS = all(p.exists() for p in (PGDA90_DEM, PGDA90_ERR, SITE01_DEM, SITE01_ERR))
needs_real_dems = pytest.mark.skipif(
    not REAL_DEMS, reason="PGDA 78 Site01 / PGDA 90 80 m files not on disk (README step 3)")

REAL_20M_DEMS = PGDA90_20M_DEM.exists() and PGDA90_20M_ERR.exists()
needs_20m_dems = pytest.mark.skipif(
    not REAL_20M_DEMS, reason="PGDA 90 20 m files not on disk")


def test_manifest_and_settings_include_80m():
    from lunaops import settings
    from lunaops.engine.dem import LEVEL_ORDER

    manifest_path = Path(__file__).resolve().parents[1] / "lunaops" / "manifests" / "datasets.json"
    man = json.loads(manifest_path.read_text())
    dem_levels = {d["id"]: d for d in man["dem_levels"]}

    assert "pgda90_80m" in dem_levels, "pgda90_80m missing from datasets.json"
    spec = dem_levels["pgda90_80m"]
    assert spec["level"] == "80m"
    assert spec["pixel_m"] == 80.0
    assert spec["priority"] == 50
    assert spec["coverage"] == "80-90 S"
    assert spec["tier"] == "core"

    assert "80m" in settings.DEM_WINDOW_HALF_M, "80m missing from DEM_WINDOW_HALF_M"
    assert settings.DEM_WINDOW_HALF_M["80m"] >= 160_000.0
    assert "80m" in LEVEL_ORDER, "80m missing from LEVEL_ORDER"


def test_manifest_and_settings_include_20m():
    from lunaops import settings
    from lunaops.engine.dem import LEVEL_ORDER

    manifest_path = Path(__file__).resolve().parents[1] / "lunaops" / "manifests" / "datasets.json"
    man = json.loads(manifest_path.read_text())
    dem_levels = {d["id"]: d for d in man["dem_levels"]}

    assert "pgda90_20m" in dem_levels, "pgda90_20m missing from datasets.json"
    spec = dem_levels["pgda90_20m"]
    assert spec["level"] == "20m"
    assert spec["pixel_m"] == 20.0
    assert spec["priority"] == 50
    assert spec["coverage"] == "80-90 S"
    assert spec["tier"] == "core"

    assert "20m" in settings.DEM_WINDOW_HALF_M, "20m missing from DEM_WINDOW_HALF_M"
    assert settings.DEM_WINDOW_HALF_M["20m"] == 40_000.0
    assert "20m" in LEVEL_ORDER, "20m missing from LEVEL_ORDER"


def test_pgda90_file_integrity_and_geometry():
    if not PGDA90_DEM.exists() or not PGDA90_ERR.exists():
        pytest.skip("PGDA90 80m files not available on disk")

    from lunaops.engine.dem import inspect_raster
    from lunaops.engine.kernels import sha256_of

    assert sha256_of(PGDA90_DEM) == EXPECTED_DEM_SHA256
    assert sha256_of(PGDA90_ERR) == EXPECTED_ERR_SHA256

    dinfo = inspect_raster(PGDA90_DEM, kind="dem")
    einfo = inspect_raster(PGDA90_ERR, kind="error_map")

    assert dinfo["width"] == 7600 and dinfo["height"] == 7600
    assert einfo["width"] == 7600 and einfo["height"] == 7600
    assert dinfo["pixel_m"] == 80.0 and einfo["pixel_m"] == 80.0
    assert dinfo["transform"] == [80.0, 0.0, -304000.0, 0.0, -80.0, 304000.0]
    assert einfo["transform"] == dinfo["transform"]
    assert dinfo["stereo_check_max_m"] < 1e-3
    assert einfo["stereo_check_max_m"] < 1e-3

    # DEM height plausibility & non-negative errors
    assert -9500.0 <= dinfo["sample_abs_max"] <= 11000.0
    assert einfo["sample_abs_max"] >= 0.0


@needs_20m_dems
def test_pgda90_20m_file_integrity_and_geometry():
    from lunaops.engine.dem import inspect_raster
    from lunaops.engine.kernels import sha256_of

    assert sha256_of(PGDA90_20M_DEM) == EXPECTED_20M_DEM_SHA256
    assert sha256_of(PGDA90_20M_ERR) == EXPECTED_20M_ERR_SHA256

    dinfo = inspect_raster(PGDA90_20M_DEM, kind="dem")
    einfo = inspect_raster(PGDA90_20M_ERR, kind="error_map")

    assert dinfo["width"] == 30400 and dinfo["height"] == 30400
    assert einfo["width"] == 30400 and einfo["height"] == 30400
    assert dinfo["pixel_m"] == 20.0 and einfo["pixel_m"] == 20.0
    assert dinfo["transform"] == [20.0, 0.0, -304000.0, 0.0, -20.0, 304000.0]
    assert einfo["transform"] == dinfo["transform"]
    assert dinfo["stereo_check_max_m"] < 1e-3
    assert einfo["stereo_check_max_m"] < 1e-3

    # DEM height plausibility & non-negative errors
    assert -9500.0 <= dinfo["sample_abs_max"] <= 11000.0
    assert einfo["sample_abs_max"] >= 0.0
    assert einfo["sample_abs_max"] >= 0.0


@pytest.fixture(autouse=True)
def setup_real_dem():
    """Ensure tests in this module access the real registered DEMs and restore registry state on teardown."""
    from lunaops import settings
    real_reg = DEM_DIR / "registry.json"
    test_reg = settings.DEM_DIR / "registry.json"
    prev = test_reg.read_text() if test_reg.exists() else None
    if REAL_DEMS and real_reg.exists() and test_reg.resolve() != real_reg.resolve():
        test_reg.parent.mkdir(parents=True, exist_ok=True)
        test_reg.write_text(real_reg.read_text())
    try:
        yield
    finally:
        if test_reg.resolve() != real_reg.resolve():
            if prev is not None:
                test_reg.parent.mkdir(parents=True, exist_ok=True)
                test_reg.write_text(prev)
            elif test_reg.exists():
                test_reg.unlink()


@needs_real_dems
def test_registry_contains_both_5m_and_80m():
    from lunaops.engine.dem import error_map_for, product_key, read_registry, usable_levels

    reg = read_registry()
    prods = {p["level"]: p for p in reg["products"]}

    if "80m" not in prods:
        pytest.skip("80m DEM not yet registered in registry.json")

    assert "5m" in prods, "5m Site01 must be preserved alongside 80m"
    p5 = prods["5m"]
    p80 = prods["80m"]

    assert p5["pixel_m"] == 5.0
    assert p80["pixel_m"] == 80.0
    assert p5["priority"] < p80["priority"], "5m must have higher priority (lower number) than 80m"

    em5 = error_map_for(p5, reg)
    em80 = error_map_for(p80, reg)
    assert em5 is not None, "5m Site01 error map must be linked"
    assert em80 is not None, "80m PGDA90 error map must be linked"
    assert em80["dem_sha256"] == p80["sha256"]
    assert em80["same_grid_as_dem"] is True

    # Usable levels must be sorted finest first
    usable = usable_levels()
    levels_in_order = [u["level"] for u in usable if u["level"] in ("5m", "80m")]
    assert levels_in_order == ["5m", "80m"]


@needs_real_dems
def test_multi_resolution_sampling_and_5m_priority():
    from lunaops.engine.dem import coverage_check, load_pyramid, read_registry, site_height

    reg = read_registry()
    if not any(p["level"] == "80m" for p in reg["products"]):
        pytest.skip("80m DEM not registered")

    # Site01 coordinates
    s01_lat, s01_lon = -89.463163, 222.510447
    cov_s01 = coverage_check(s01_lat, s01_lon)
    assert cov_s01["covered"] is True
    assert cov_s01["finest"] == "5m"
    assert "5m" in cov_s01["levels"]
    assert "80m" in cov_s01["levels"]

    pyr_s01 = load_pyramid(s01_lat, s01_lon)
    h_s01, lvl_s01 = site_height(pyr_s01, s01_lat, s01_lon)
    assert lvl_s01 == "5m", "Site01 ground height must be sourced from 5m"
    assert 1900.0 < h_s01 < 2000.0

    # Regional site outside Site01: fallback to regional DEM (20m when registered, else 80m)
    reg_lat, reg_lon = -89.9, 0.0
    cov_reg = coverage_check(reg_lat, reg_lon)
    assert cov_reg["covered"] is True
    has_20m = any(p["level"] == "20m" and not p.get("synthetic") for p in reg["products"])
    expected_finest = "20m" if has_20m else "80m"
    assert cov_reg["finest"] == expected_finest
    if has_20m:
        assert "20m" in cov_reg["levels"]
        assert "80m" in cov_reg["levels"]
    else:
        assert "80m" in cov_reg["levels"]

    pyr_reg = load_pyramid(reg_lat, reg_lon)
    h_reg, lvl_reg = site_height(pyr_reg, reg_lat, reg_lon)
    assert lvl_reg == expected_finest, f"Outside Site01 ground height must fall back to {expected_finest}"
    assert math.isfinite(h_reg)

    # Outside registered coverage (north of 60S with 240m): no coverage invented
    out_lat, out_lon = -55.0, 0.0
    cov_out = coverage_check(out_lat, out_lon)
    assert cov_out["covered"] is False


@needs_real_dems
def test_three_tier_hierarchy_5m_20m_80m():
    from lunaops.engine.dem import error_map_for, product_key, read_registry, usable_levels

    reg = read_registry()
    prods = {p["level"]: p for p in reg["products"] if not p.get("synthetic")}

    if "20m" not in prods or "80m" not in prods:
        pytest.skip("20m and 80m DEMs not both registered")

    assert "5m" in prods, "5m Site01 must be preserved"
    p5 = prods["5m"]
    p20 = prods["20m"]
    p80 = prods["80m"]

    # Resolution hierarchy
    assert p5["pixel_m"] == 5.0
    assert p20["pixel_m"] == 20.0
    assert p80["pixel_m"] == 80.0

    # Priority ordering: 5m site DEM has highest priority (40), regional DEMs have 50
    assert p5.get("priority", 50) < p20.get("priority", 50)
    assert p20.get("priority", 50) <= p80.get("priority", 50)

    # Error maps must be linked for all 3 products
    em5 = error_map_for(p5, reg)
    em20 = error_map_for(p20, reg)
    em80 = error_map_for(p80, reg)

    assert em5 is not None, "5m Site01 error map must be linked"
    assert em20 is not None, "20m PGDA90 error map must be linked"
    assert em80 is not None, "80m PGDA90 error map must be linked"

    assert em20["dem_sha256"] == p20["sha256"]
    assert em20["same_grid_as_dem"] is True

    # Usable levels must be sorted finest first: 5m -> 20m -> 80m
    usable = usable_levels()
    levels_in_order = [u["level"] for u in usable if not u.get("synthetic") and u["level"] in ("5m", "20m", "80m")]
    assert levels_in_order == ["5m", "20m", "80m"]


@needs_real_dems
@needs_kernels
def test_horizon_coverage_completes_with_80m():
    from lunaops.engine.dem import read_registry
    from lunaops.engine.horizon import compute_horizon

    reg = read_registry()
    if not any(p["level"] == "80m" for p in reg["products"]):
        pytest.skip("80m DEM not registered")

    s01_lat, s01_lon = -89.463163, 222.510447
    hz = compute_horizon(s01_lat, s01_lon, 0.0)

    # With regional fallback, horizon is 100% complete
    assert hz.incomplete.sum() == 0, f"Expected 0 incomplete bins, got {hz.incomplete.sum()}"
    assert hz.params["sigma"]["bins_with_sigma"] == 3600
    assert len(hz.params["sigma"]["error_maps"]) >= 1

    # Levels used in the pyramid
    levels_used = [lv["level"] for lv in hz.levels]
    assert "5m" in levels_used
    assert "80m" in levels_used


@needs_real_dems
def test_3d_terrain_grid_multi_resolution():
    from lunaops.engine.dem import read_registry, terrain_grid

    reg = read_registry()
    if not any(p["level"] == "80m" for p in reg["products"]):
        pytest.skip("80m DEM not registered")

    s01_lat, s01_lon = -89.463163, 222.510447

    # Small radius (2 km) fits within Site01 5m extent
    g_small = terrain_grid(s01_lat, s01_lon, 2000.0)
    assert g_small["level"] == "5m"
    assert g_small["n"] == 160
    assert any(h is not None for h in g_small["heights"])

    # Large radius (15 km) exceeds Site01 (8 km), falls back to 20m if present, else 80m
    has_20m = any(p["level"] == "20m" for p in reg["products"])
    expected_level = "20m" if has_20m else "80m"
    g_large = terrain_grid(s01_lat, s01_lon, 15000.0)
    assert g_large["level"] == expected_level
    assert g_large["n"] == 160
    assert any(h is not None for h in g_large["heights"])

    # Regional site outside Site01
    g_reg = terrain_grid(-89.9, 0.0, 10000.0)
    assert g_reg["level"] == expected_level
    assert any(h is not None for h in g_reg["heights"])


@needs_real_dems
@needs_kernels
def test_horizon_uncertainty_uses_both_error_maps():
    from lunaops.engine.dem import read_registry
    from lunaops.engine.horizon import compute_horizon

    reg = read_registry()
    if not any(p["level"] == "80m" for p in reg["products"]):
        pytest.skip("80m DEM not registered")

    s01_lat, s01_lon = -89.463163, 222.510447
    hz = compute_horizon(s01_lat, s01_lon, 0.0)

    # Uncertainty must be present for all 3600 bins
    assert hz.sigma_deg is not None
    assert np.all(np.isfinite(hz.sigma_deg))
    assert np.all(hz.sigma_deg >= 0.0)

    # Error maps of both products recorded
    em_names = hz.params["sigma"]["error_maps"]
    assert "Site01_final_adj_5mpp_toterr.tif" in em_names
    assert "LDEM_80S_80MPP_ADJ_ERR.tiff" in em_names


def test_nodata_is_never_treated_as_valid_terrain():
    from lunaops.engine.dem import LevelWindow, bilinear

    # 2x2 window with one NaN
    data = np.array([[100.0, 105.0], [102.0, np.nan]], dtype=np.float32)
    win = LevelWindow(
        level="test",
        data=data,
        x0=0.0,
        y0=0.0,
        dx=10.0,
        dy=-10.0,
        band_m=100.0,
        pixel_m=10.0,
    )
    # Sampling in the cell containing the NaN must return NaN
    h = bilinear(win, 5.0, -5.0)
    assert math.isnan(h), "Bilinear interpolation must return NaN if any neighbor is nodata"

    # Fully valid cell
    data_valid = np.array([[100.0, 105.0], [102.0, 108.0]], dtype=np.float32)
    win_valid = LevelWindow(
        level="test",
        data=data_valid,
        x0=0.0,
        y0=0.0,
        dx=10.0,
        dy=-10.0,
        band_m=100.0,
        pixel_m=10.0,
    )
    h_valid = bilinear(win_valid, 5.0, -5.0)
    assert math.isfinite(h_valid)
    assert 100.0 < h_valid < 108.0


@needs_real_dems
def test_cli_verify_all_registered():
    from argparse import Namespace
    from lunaops.acquire import cmd_verify

    ret = cmd_verify(Namespace())
    assert ret == 0


@needs_real_dems
@needs_kernels
def test_near_field_uncertainty_correlation_eliminates_7_deg_artifact():
    from lunaops import settings
    from lunaops.engine.ephem import Site
    from lunaops.engine.events import EventConfig, EventDetector, build_intervals, summarize
    from lunaops.engine.horizon import compute_horizon
    from lunaops.engine.visibility import HorizonProfile

    s01_lat, s01_lon = -89.463163, 222.510447
    hz = compute_horizon(s01_lat, s01_lon, obs_h_m=0.0)

    # Near-field blockers at d = 2.5 m (first ray step on 5m DEM)
    near_bins = np.where(hz.block_dist_m <= 2.5)[0]
    assert near_bins.size > 1000, f"Expected >1000 near-field bins at obs_h=0, got {near_bins.size}"

    # Under the uncorrected model atan(sigma_h / 2.5), sigma was 7.3888 deg.
    # With spatial correlation within the 5m product, relative elevation uncertainty approaches 0 as d -> 0,
    # bounding angular uncertainty by local slope roughness (< 0.1 deg).
    max_near_sig = float(np.max(hz.sigma_deg[near_bins]))
    assert max_near_sig < 0.15, f"Near-field artifact detected: {max_near_sig} deg >= 0.15 deg (expected ~0.06 deg)"
    assert np.all(hz.sigma_deg[near_bins] > 0.0)

    # Verify that clear solar tracking windows are not falsely flagged as uncertain
    site = Site(lat=s01_lat, lon=s01_lon, obs_h_m=0.0, ground_h_m=hz.ground_h_m)
    hp = HorizonProfile(hz.h_deg, hz.incomplete, hz.sigma_deg)
    cfg = EventConfig()
    det = EventDetector(site, hp, cfg)
    et0 = 847281669.183
    et1 = et0 + 86400.0
    res = det.run(et0, et1)
    ivs = build_intervals(det, et0, et1, res["events"], res["samples"])
    stats = summarize(ivs["sun_any"], et0, et1)
    assert stats["windows"] > 0
    assert stats["uncertain_windows"] == 0, "Clear solar window must not be flagged uncertain by near-field artifact"


@needs_real_dems
def test_5m_footprint_and_overlap_elevation_offsets():
    """Overlap statistics reported in the 2026-11 audit: nearest 80 m pixel (rasterio sample) at every 16th
    Site01 pixel on the 4-8 km annulus. Not the cross-product allowance (bilinear over the window
    intersection, CROSS_PRODUCT_SAMPLING); nearest sampling adds grad(h) . (2.5, 37.5) m on these grids.
    See tests/test_phase2_cross_product_method.py and docs/AUDIT_2026-11.md."""
    import rasterio
    from lunaops import settings
    from lunaops.engine.dem import load_pyramid, resolve_dem_path

    assert settings.DEM_WINDOW_HALF_M["5m"] == 8_000.0, "5m window half-width must match valid 8 km footprint"

    s01_lat, s01_lon = -89.463163, 222.510447
    pyr = load_pyramid(s01_lat, s01_lon)
    w5 = next(w for w in pyr if w.level == "5m")
    assert w5.band_m >= 7990.0, f"5m band should serve up to 8 km, got {w5.band_m}"

    # Measure elevation offset in 4-8 km overlap ring
    cx, cy = -11000.0, -12000.0
    step = 16  # 80 m grid spacing
    rows = np.arange(0, w5.data.shape[0], step)
    cols = np.arange(0, w5.data.shape[1], step)
    grid_c, grid_r = np.meshgrid(cols, rows)
    xs = w5.x0 + grid_c.ravel() * w5.dx
    ys = w5.y0 + grid_r.ravel() * w5.dy

    dists = np.hypot(xs - cx, ys - cy)
    ring = (dists >= 4000.0) & (dists <= 8000.0)
    pts_x = xs[ring]
    pts_y = ys[ring]
    v5 = w5.data[grid_r.ravel()[ring], grid_c.ravel()[ring]]

    w80 = next(w for w in pyr if w.level == "80m")
    with rasterio.open(resolve_dem_path(w80.meta.get("path") or str(PGDA90_DEM))) as src:
        v80 = np.array([v[0] for v in src.sample(list(zip(pts_x, pts_y)))], dtype=float)

    valid = np.isfinite(v5) & np.isfinite(v80)
    diff = v5[valid] - v80[valid]
    assert len(diff) > 20000, f"Expected >20000 overlap points, got {len(diff)}"
    mean_diff = float(np.mean(diff))
    rms_diff = float(np.sqrt(np.mean(diff ** 2)))
    assert abs(mean_diff) < 3.0, f"Mean offset too high: {mean_diff} m"
    assert rms_diff < 10.0, f"RMS difference exceeds tolerance: {rms_diff} m"


@needs_real_dems
def test_registry_paths_are_portable():
    from lunaops import settings
    from lunaops.engine.dem import read_registry, resolve_dem_path

    reg = read_registry()
    for p in reg["products"]:
        path_str = p["path"]
        assert not Path(path_str).is_absolute() or not ("Users" in path_str and "\\" in path_str), \
            f"Absolute machine path found in product: {path_str}"
        resolved = resolve_dem_path(path_str)
        assert resolved.exists(), f"Could not resolve portable path: {path_str} -> {resolved}"

    for k, em in reg.get("error_maps", {}).items():
        path_str = em["path"]
        assert not Path(path_str).is_absolute() or not ("Users" in path_str and "\\" in path_str), \
            f"Absolute machine path found in error map: {path_str}"
        resolved = resolve_dem_path(path_str)
        assert resolved.exists(), f"Could not resolve portable path: {path_str} -> {resolved}"


@needs_20m_dems
def test_cross_product_discrepancy_all_resolution_pairs():
    """Phase 4 A6: Cross-product discrepancy allowances across all four registered resolution tiers (six pairs).
    Validates bilinear allowance over window intersection (CROSS_PRODUCT_SAMPLING):
    - 5 m vs 20 m (Site01): RMS ~ 0.53 m, mean within +/-0.1 m
    - 5 m vs 80 m (Site01): RMS ~ 1.22 m, mean within +/-0.1 m
    - 20 m vs 80 m (Site01 regional): RMS ~ 1.11 m, mean within +/-0.05 m
    - 5 m vs 240 m (Site01 4-8 km annulus): RMS ~ 4.31 m, mean within +/-0.20 m
    - 20 m vs 240 m (Site01 regional): RMS ~ 2.74 m, mean within +/-0.10 m
    - 80 m vs 240 m (Site01 regional): RMS ~ 2.62 m, mean within +/-0.05 m
    - 20 m strictly tightens discrepancy against 5 m Site01 compared to 80 m and 240 m."""
    from lunaops.engine.dem import load_pyramid
    from lunaops.engine.horizon import cross_product_discrepancy

    s01_lat, s01_lon = -89.463163, 222.510447
    pyr = load_pyramid(s01_lat, s01_lon)
    w5 = next(w for w in pyr if w.level == "5m")
    w20 = next(w for w in pyr if w.level == "20m")
    w80 = next(w for w in pyr if w.level == "80m")
    w240 = next(w for w in pyr if w.level == "240m")

    d5_20 = cross_product_discrepancy(w5, w20)
    d5_80 = cross_product_discrepancy(w5, w80)
    d20_80 = cross_product_discrepancy(w20, w80)
    d5_240 = cross_product_discrepancy(w5, w240)
    d20_240 = cross_product_discrepancy(w20, w240)
    d80_240 = cross_product_discrepancy(w80, w240)

    for d in (d5_20, d5_80, d20_80, d5_240, d20_240, d80_240):
        assert d["status"] == "measured"
        assert d["n"] >= 100
        assert d["allowance_m"] == d["rms_m"]

    # 5 m vs 20 m
    assert d5_20["n"] == 40000
    assert 0.45 < d5_20["rms_m"] < 0.65
    assert abs(d5_20["mean_m"]) < 0.15

    # 5 m vs 80 m
    assert d5_80["n"] == 40000
    assert 1.10 < d5_80["rms_m"] < 1.35
    assert abs(d5_80["mean_m"]) < 0.15

    # 20 m vs 80 m
    assert d20_80["n"] > 20000
    assert 1.00 < d20_80["rms_m"] < 1.25
    assert abs(d20_80["mean_m"]) < 0.05

    # 5 m vs 240 m (measured at Site01 4-8 km annulus: n=4,489, RMS=4.314 m)
    assert d5_240["n"] > 4000
    assert 3.8 < d5_240["rms_m"] < 4.8
    assert abs(d5_240["mean_m"]) < 0.20

    # 20 m vs 240 m (measured at Site01 regional: n=27,889, RMS=2.735 m)
    assert d20_240["n"] > 25000
    assert 2.3 < d20_240["rms_m"] < 3.2
    assert abs(d20_240["mean_m"]) < 0.10

    # 80 m vs 240 m (measured at Site01 regional: n=36,100, RMS=2.620 m)
    assert d80_240["n"] > 30000
    assert 2.2 < d80_240["rms_m"] < 3.1
    assert abs(d80_240["mean_m"]) < 0.05

    # 20 m intermediate tier tightens discrepancy over 80 m by > 50%
    assert d5_20["rms_m"] < 0.6 * d5_80["rms_m"]
    # 20 m and 80 m discrepancies to 240 m are substantially tighter than 5 m to 240 m
    assert d20_240["rms_m"] < d5_240["rms_m"]
    assert d80_240["rms_m"] < d5_240["rms_m"]


@needs_20m_dems
def test_5m_and_20m_overlap_elevation_offsets():
    """Phase 4 A6: Overlap statistics between Site01 (5 m) and PGDA90 (20 m) on the 4-8 km annulus.
    Compares nearest-pixel and bilinear sampling. Nearest-pixel offset is (-7.5, +7.5) m."""
    import rasterio
    from lunaops import settings
    from lunaops.engine.dem import load_pyramid, resolve_dem_path
    from lunaops.engine.horizon import bilinear_many

    s01_lat, s01_lon = -89.463163, 222.510447
    pyr = load_pyramid(s01_lat, s01_lon)
    w5 = next(w for w in pyr if w.level == "5m")
    w20 = next(w for w in pyr if w.level == "20m")

    cx, cy = -11000.0, -12000.0
    step = 4  # 20 m grid spacing
    rows = np.arange(0, w5.data.shape[0], step)
    cols = np.arange(0, w5.data.shape[1], step)
    grid_c, grid_r = np.meshgrid(cols, rows)
    xs = w5.x0 + grid_c.ravel() * w5.dx
    ys = w5.y0 + grid_r.ravel() * w5.dy

    dists = np.hypot(xs - cx, ys - cy)
    ring = (dists >= 4000.0) & (dists <= 8000.0)
    pts_x = xs[ring]
    pts_y = ys[ring]
    v5 = w5.data[grid_r.ravel()[ring], grid_c.ravel()[ring]].astype(float)

    # Bilinear on window
    hb = bilinear_many(w20, pts_x, pts_y)
    valid_b = np.isfinite(v5) & np.isfinite(hb)
    diff_b = v5[valid_b] - hb[valid_b]
    assert len(diff_b) > 300000
    rms_b = float(np.sqrt(np.mean(diff_b ** 2)))
    assert abs(float(np.mean(diff_b))) < 0.2
    assert rms_b < 0.6  # Measured 0.40 m

    # Nearest-pixel sampling via rasterio
    with rasterio.open(resolve_dem_path(w20.meta.get("path") or str(PGDA90_20M_DEM))) as src:
        # Sample every 10th point in ring to keep test fast (37,000+ points)
        sample_x = pts_x[::10]
        sample_y = pts_y[::10]
        sample_v5 = v5[::10]
        v20_near = np.array([v[0] for v in src.sample(list(zip(sample_x, sample_y)))], dtype=float)

    valid_n = np.isfinite(sample_v5) & np.isfinite(v20_near)
    diff_n = sample_v5[valid_n] - v20_near[valid_n]
    assert len(diff_n) > 30000
    rms_n = float(np.sqrt(np.mean(diff_n ** 2)))
    assert abs(float(np.mean(diff_n))) < 0.5
    assert rms_n < 2.5  # Measured 1.56 m (substantially better than 80m's 6.33 m)


@needs_20m_dems
def test_20m_and_80m_polar_wide_grid_and_elevation_alignment():
    """Phase 4 A6: Polar-wide (80-90 S) grid alignment and elevation cross-check between 20 m and 80 m DEMs."""
    import rasterio
    from lunaops.engine.dem import read_registry, resolve_dem_path

    reg = read_registry()
    p20 = next(p for p in reg["products"] if p["level"] == "20m")
    p80 = next(p for p in reg["products"] if p["level"] == "80m")

    with rasterio.open(resolve_dem_path(p80["path"])) as src80, \
         rasterio.open(resolve_dem_path(p20["path"])) as src20:
        # Bounding box & CRS identity
        assert src80.bounds == src20.bounds
        assert src80.crs == src20.crs
        assert src20.width == 4 * src80.width
        assert src20.height == 4 * src80.height

        # Regular polar lattice: sample every 50th pixel on 80m grid (152 x 152 = 23,104 points)
        stride = 50
        rows = np.arange(0, src80.height, stride)
        cols = np.arange(0, src80.width, stride)
        R, C = np.meshgrid(rows, cols, indexing="ij")
        xs = src80.transform[2] + (C.ravel() + 0.5) * src80.transform[0]
        ys = src80.transform[5] + (R.ravel() + 0.5) * src80.transform[4]

        v80 = src80.read(1)[R.ravel(), C.ravel()].astype(float)
        v20 = np.array([v[0] for v in src20.sample(list(zip(xs, ys)))], dtype=float)

    valid = np.isfinite(v80) & np.isfinite(v20)
    assert valid.sum() == xs.size, "Polar DEMs must have 100% valid data coverage in 80-90 S"
    diff = v20[valid] - v80[valid]
    mean_diff = float(np.mean(diff))
    rms_diff = float(np.sqrt(np.mean(diff ** 2)))

    # Zero-bias polar agreement within 15 cm, RMS within 3.0 m
    assert abs(mean_diff) < 0.15, f"Polar mean diff exceeded: {mean_diff} m"
    assert rms_diff < 3.0, f"Polar RMS diff exceeded: {rms_diff} m"


def test_bilinear_many_invariant_to_window_block_offsets():
    """Phase 4 A6 Regression Guard: bilinear_many must yield mathematically identical results
    regardless of window col_off and row_off buffer positions."""
    from lunaops.engine.dem import LevelWindow
    from lunaops.engine.horizon import bilinear_many

    # Construct test synthetic terrain
    rng = np.random.default_rng(42)
    grid = rng.uniform(100.0, 500.0, size=(100, 100)).astype(np.float32)
    x0, y0, dx, dy = -5000.0, 5000.0, 100.0, -100.0

    # Fully loaded window (col_off = row_off = 0)
    w_full = LevelWindow("test", grid.copy(), x0, y0, dx, dy, 5000.0, 100.0, {"key": "test:full"})

    # Partially loaded / offset window
    grid_sub = grid[20:60, 30:70].copy()
    w_sub = LevelWindow("test", grid_sub, x0, y0, dx, dy, 5000.0, 100.0, {"key": "test:sub"},
                        col_off=30, row_off=20, nom_shape=(100, 100))

    # Sample points inside the overlapping sub-block
    xs = np.linspace(x0 + 32 * dx, x0 + 68 * dx, 25)
    ys = np.linspace(y0 + 22 * dy, y0 + 58 * dy, 25)

    res_full = bilinear_many(w_full, xs, ys)
    res_sub = bilinear_many(w_sub, xs, ys)

    np.testing.assert_allclose(res_sub, res_full, rtol=1e-6, atol=1e-6)
