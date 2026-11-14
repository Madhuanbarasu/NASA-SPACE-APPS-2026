"""Isolated fixtures for landing screening tests.

LUNAOPS_DATA_DIR points at a fresh temporary folder BEFORE lunaops is imported, so the synthetic test DEM, its
registry, error map and landing manifest live only there. The production registry (data/dem/registry.json) and
data/landing are never read or written by these tests. Synthetic terrain is flagged synthetic (not lunar data).
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path

import numpy as np
import pytest

_tmp = Path(tempfile.mkdtemp(prefix="lunaops_landing_test_"))
os.environ["LUNAOPS_DATA_DIR"] = str(_tmp)
os.environ["LUNAOPS_ALLOW_SYNTHETIC"] = "1"
os.environ.pop("LUNAOPS_DEM_DIR", None)

PIXEL = 10.0
HALF = 6000.0                      # synthetic DEM spans x, y in [-6 km, 6 km] around the pole
SLOPE_DEG = 10.0                   # east half: plane tilted 10 degrees along +x
BOWL = {"x": -3000.0, "y": 2000.0, "r": 200.0, "depth": 8.0}
CHECKER = {"x": -3000.0, "y": -3000.0, "half": 250.0, "amp": 0.5}
HOLE = {"x": 3000.0, "y": -3000.0, "r": 100.0}
SIGMA_M = 0.5
TRACK_EVERY = 5                    # synthetic count map: 1 return on every 5th column, 0 elsewhere


def synthetic_surface(X: np.ndarray, Y: np.ndarray) -> np.ndarray:
    z = np.where(X > 0, np.tan(np.radians(SLOPE_DEG)) * X, 0.0)
    r = np.hypot(X - BOWL["x"], Y - BOWL["y"])
    z = z - np.where(r < BOWL["r"], BOWL["depth"] * (1 - (r / BOWL["r"]) ** 2), 0.0)
    cx, cy = X - CHECKER["x"], Y - CHECKER["y"]
    patch = (np.abs(cx) <= CHECKER["half"]) & (np.abs(cy) <= CHECKER["half"])
    sign = np.where(((np.floor(cx / PIXEL) + np.floor(cy / PIXEL)) % 2) == 0, 1.0, -1.0)
    z = z + np.where(patch, CHECKER["amp"] * sign, 0.0)
    z = np.where(np.hypot(X - HOLE["x"], Y - HOLE["y"]) < HOLE["r"], np.nan, z)
    return z


def _write(path: Path, arr: np.ndarray, nodata) -> None:
    import rasterio
    from rasterio.crs import CRS
    from rasterio.transform import from_origin

    from lunaops.testing import STEREO_PROJ4

    with rasterio.open(path, "w", driver="GTiff", width=arr.shape[1], height=arr.shape[0], count=1,
                       dtype="float32", crs=CRS.from_proj4(STEREO_PROJ4), transform=from_origin(-HALF, HALF, PIXEL, PIXEL),
                       nodata=nodata, compress="deflate", tiled=True) as dst:
        dst.write(arr.astype(np.float32), 1)
        dst.update_tags(SYNTHETIC="TEST TERRAIN - NOT LUNAR DATA")


@pytest.fixture(scope="session")
def synthetic_site():
    from lunaops import settings
    from lunaops.acquire import _basic_info
    from lunaops.engine.dem import product_key, read_registry, write_registry
    from lunaops.engine.kernels import sha256_of

    n = int(2 * HALF / PIXEL)
    xs = -HALF + PIXEL * (np.arange(n) + 0.5)
    ys = HALF - PIXEL * (np.arange(n) + 0.5)
    X, Y = np.meshgrid(xs, ys)
    Z = synthetic_surface(X, Y)
    d = settings.DEM_DIR / "synthetic_landing"
    d.mkdir(parents=True, exist_ok=True)
    dem_p, err_p, cnt_p = d / "SYNTH_LANDING_10m.tif", d / "SYNTH_LANDING_10m_err.tif", d / "SYNTH_LANDING_10m_count.tif"
    _write(dem_p, np.where(np.isfinite(Z), Z, -9999.0), -9999.0)
    _write(err_p, np.full(Z.shape, SIGMA_M), None)
    cols = np.arange(n)[None, :].repeat(n, axis=0)
    _write(cnt_p, (cols % TRACK_EVERY == 0).astype(np.float32), None)
    rec = {"level": "10m", "product_id": "synthetic_landing_10m", "path": str(dem_p), "sha256": sha256_of(dem_p),
           "bytes": dem_p.stat().st_size, "product": "SYNTHETIC TEST TERRAIN (landing fixtures)", "synthetic": True,
           "pixel_m": PIXEL, **_basic_info(dem_p)}
    em = {"path": str(err_p), "sha256": sha256_of(err_p), "bytes": err_p.stat().st_size, "dem_sha256": rec["sha256"],
          "same_grid_as_dem": True, "product": "synthetic error map", "units": "m", "nodata": None, **{
              k: rec[k] for k in ("transform", "width", "height")}}
    reg = read_registry()
    reg["products"] = [rec]
    reg["error_maps"] = {product_key(rec): em}
    write_registry(reg)
    # landing manifest (temporary data folder only)
    from lunaops_landing.sources import _sha256, landing_dir, manifest_path
    landing_dir().mkdir(parents=True, exist_ok=True)
    shutil.copyfile(cnt_p, landing_dir() / cnt_p.name)
    man = {"products": [{"key": "synthetic#count", "kind": "count", "dem_product_key": product_key(rec),
                         "dem_sha256": rec["sha256"], "path": cnt_p.name, "bytes": cnt_p.stat().st_size,
                         "sha256": _sha256(landing_dir() / cnt_p.name), "product": "synthetic count map",
                         "units": "returns", "nodata": None,
                         **{k: rec[k] for k in ("transform", "width", "height")}}]}
    manifest_path().write_text(json.dumps(man))
    return rec


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(_tmp, ignore_errors=True)
