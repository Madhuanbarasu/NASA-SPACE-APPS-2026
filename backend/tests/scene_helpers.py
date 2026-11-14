"""Small synthetic DEM scenes for the Phase 2 tests (synthetic, flagged, never lunar data).

Each scene gets its own registry: the test points settings.DEM_DIR at a temporary folder (and clears
the fallback folders), so the session's synthetic crater and the real LOLA registry are never touched.
Product grids are placed relative to the site's stereographic position and aligned to whole pixels.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np

SITE = (-89.5, 0.0)


def site_xy(lat: float = SITE[0], lon: float = SITE[1]) -> tuple[float, float]:
    from lunaops import settings
    from lunaops.engine.frames import south_polar_stereo_xy, unit_from_latlon

    return south_polar_stereo_xy(unit_from_latlon(math.radians(lat), math.radians(lon)), settings.R_MOON_M)


def _write(path: Path, arr: np.ndarray, x0: float, y0: float, pixel: float, nodata: float | None) -> None:
    import rasterio
    from rasterio.crs import CRS
    from rasterio.transform import from_origin

    from lunaops.testing import STEREO_PROJ4

    a = np.array(arr, dtype=np.float32)
    if nodata is not None:
        a[~np.isfinite(a)] = nodata
    with rasterio.open(path, "w", driver="GTiff", width=a.shape[1], height=a.shape[0], count=1, dtype="float32",
                       crs=CRS.from_proj4(STEREO_PROJ4), transform=from_origin(x0, y0, pixel, pixel),
                       nodata=nodata, compress="deflate") as dst:
        dst.write(a, 1)


class Scene:
    """Build and register synthetic products around a site in an isolated DEM folder."""

    def __init__(self, tmp_path: Path, monkeypatch, lat: float = SITE[0], lon: float = SITE[1]):
        from lunaops import settings

        self.dem = tmp_path / "dem_scene"
        self.dem.mkdir()
        monkeypatch.setattr(settings, "DEM_DIR", self.dem)
        monkeypatch.setattr(settings, "DEM_FALLBACK_DIRS", [])
        self.lat, self.lon = lat, lon
        self.xs, self.ys = site_xy(lat, lon)
        self.reg = {"products": [], "error_maps": {}}
        self.keys: dict[str, str] = {}

    def add(self, name: str, pixel: float, half_m: float, height, priority: int = 50, err=None) -> dict:
        """height(DX, DY) -> heights (m, NaN = nodata) with DX, DY metres from the site; err: float or callable."""
        from lunaops.acquire import _basic_info, _error_map_record
        from lunaops.engine.dem import product_key, write_registry
        from lunaops.engine.kernels import sha256_of

        n = int(round(2 * half_m / pixel))
        x0, y0 = self.xs - half_m, self.ys + half_m
        DX, DY = np.meshgrid(-half_m + pixel * (np.arange(n) + 0.5), half_m - pixel * (np.arange(n) + 0.5))
        p = self.dem / f"SYNTH_{name}.tif"
        _write(p, height(DX, DY), x0, y0, pixel, -9999.0)
        rec = {"level": f"{pixel:g}m", "product_id": f"synthetic_{name}", "path": str(p), "sha256": sha256_of(p),
               "bytes": p.stat().st_size, "product": f"SYNTHETIC TEST TERRAIN ({name})", "synthetic": True,
               "pixel_m": pixel, "priority": priority, **_basic_info(p)}
        self.reg["products"].append(rec)
        self.keys[name] = product_key(rec)
        if err is not None:
            ev = err(DX, DY) if callable(err) else np.full(DX.shape, float(err))
            ep = self.dem / f"SYNTH_{name}_ERR.tif"
            _write(ep, ev, x0, y0, pixel, None)
            self.reg["error_maps"][product_key(rec)] = _error_map_record(ep, rec, {})
        write_registry(self.reg)
        return rec

    def horizon(self, obs_h_m: float = 0.0):
        from lunaops.engine.horizon import compute_horizon

        return compute_horizon(self.lat, self.lon, obs_h_m)

    def level_index(self, hz, name: str) -> int:
        return next(i for i, lv in enumerate(hz.levels) if lv["key"] == self.keys[name])


def ring(radius: float, height: float, width: float):
    """Gaussian ring ridge around the site."""
    return lambda DX, DY: height * np.exp(-0.5 * ((np.hypot(DX, DY) - radius) / width) ** 2)


def hill(x: float, y: float, height: float, width: float):
    return lambda DX, DY: height * np.exp(-0.5 * (((DX - x) ** 2 + (DY - y) ** 2) / width ** 2))


def add_fns(*fns):
    return lambda DX, DY: sum(f(DX, DY) for f in fns)
