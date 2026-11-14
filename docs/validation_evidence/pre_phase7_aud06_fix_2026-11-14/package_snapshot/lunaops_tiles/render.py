"""Hillshade tile rendering with a corrected terrain read (AUD-06).

Same tile grid, tile size, level order, hillshade and RGBA encoding as lunaops.api.tiles.render_tile; only the way each
product is read into the tile differs (read_level). Display only; see the package docstring.
"""
from __future__ import annotations

import io
import math

import numpy as np

from lunaops.api.tiles import TILE, _empty, tile_meta          # the engine's tile grid and empty tile (read only)
from lunaops.engine.dem import resolve_dem_path, usable_levels  # the engine's terrain registry and file lookup

# a destination pixel counts as inside a product when its edges are within this fraction of a pixel of the product's
# edges (absorbs floating-point noise where the tile grid and a product grid are aligned)
_EDGE_TOL = 1e-6


def read_level(src, bx0: float, by1: float, res: float, ncols: int, nrows: int, nodata=None) -> np.ndarray:
    """Heights of one product on a block of the tile's pixel grid, NaN where the product does not cover a whole pixel.

    The block's upper-left corner is (bx0, by1) in the projected frame, with square pixels of `res` metres, ncols by
    nrows pixels. Only destination pixels lying entirely inside the product are read, with a normal windowed read
    (fractional window, no boundless VRT). Pixels the product covers only partly, or not at all, stay NaN, so a coarser
    level drawn earlier shows there. The product's nodata value becomes NaN.

    Resampling: bilinear when the product is reduced (GDAL then also uses the product's overviews); cubic when it is
    enlarged (product pixels larger than the tile's), because a bilinear surface has a crease at every product pixel
    edge that the hillshade draws as a grid (measured on 240 m tiles at zoom 7: line score 2.05-2.70 bilinear, 1.02-1.03
    cubic; docs/validation_evidence/pre_phase7_aud06_fix_2026-11-14). Cubic interpolates the product's own heights; a
    cubic B-spline would smooth them and Lanczos rings, so neither is used.
    """
    from rasterio.enums import Resampling
    from rasterio.windows import from_bounds

    out = np.full((nrows, ncols), np.nan, dtype=np.float32)
    t = src.transform
    if t.b != 0 or t.d != 0 or t.e >= 0:
        raise ValueError("only north-up products without rotation are supported (the registered LOLA products are)")
    resampling = Resampling.cubic if abs(t.a) > res * (1 + _EDGE_TOL) else Resampling.bilinear
    left, bottom, right, top = src.bounds
    c0 = max(0, math.ceil((left - bx0) / res - _EDGE_TOL))
    c1 = min(ncols, math.floor((right - bx0) / res + _EDGE_TOL))
    r0 = max(0, math.ceil((by1 - top) / res - _EDGE_TOL))
    r1 = min(nrows, math.floor((by1 - bottom) / res + _EDGE_TOL))
    if c1 <= c0 or r1 <= r0:
        return out
    win = from_bounds(bx0 + c0 * res, by1 - r1 * res, bx0 + c1 * res, by1 - r0 * res, t)
    part = src.read(1, window=win, out_shape=(r1 - r0, c1 - c0), boundless=False,
                    resampling=resampling).astype(np.float32)
    if nodata is not None and not (isinstance(nodata, float) and math.isnan(nodata)):
        part[part == np.float32(nodata)] = np.nan
    out[r0:r1, c0:c1] = part
    return out


def hillshade_rgba(arr: np.ndarray, res: float) -> np.ndarray:
    """The engine's cartographic hillshade and colours (lunaops.api.tiles.render_tile), unchanged.

    Fixed light from azimuth 315 deg at 40 deg altitude; grey 40 + 190 * shade, blue channel x 1.02; transparent where
    there is no height. Cartographic only, not the lunar Sun.
    """
    gy, gx = np.gradient(np.nan_to_num(arr, nan=np.nanmean(arr)), res)
    slope = np.arctan(np.hypot(gx, gy))
    aspect = np.arctan2(-gx, gy)
    az, alt = math.radians(315.0), math.radians(40.0)
    shade = np.sin(alt) * np.cos(slope) + np.cos(alt) * np.sin(slope) * np.cos(az - aspect)
    shade = np.clip(shade, 0, 1)
    v = (40 + 190 * shade).astype(np.uint8)
    alpha = np.where(np.isfinite(arr), 255, 0).astype(np.uint8)
    return np.dstack([v, v, (v * 1.02).clip(0, 255).astype(np.uint8), alpha])


def render_heights(z: int, x: int, y: int) -> tuple[np.ndarray, float] | None:
    """The composed heights of tile z/x/y (finer levels over coarser ones) and its pixel size, or None."""
    import rasterio

    meta = tile_meta()
    if meta is None or z < 0 or z >= len(meta["resolutions"]):
        return None
    res = meta["resolutions"][z]
    x0 = meta["origin"][0] + x * TILE * res
    y1 = meta["origin"][1] - y * TILE * res
    x1, y0 = x0 + TILE * res, y1 - TILE * res
    levels = usable_levels()
    arr = np.full((TILE, TILE), np.nan, dtype=np.float32)
    for lv in reversed(levels):  # coarse first, finer levels overwrite where they have data (as the engine)
        if lv["pixel_m"] > res * 4 and lv is not levels[-1]:
            continue
        a, _, c, _, e, f = lv["transform"]
        lx0, lx1, ly0, ly1 = c, c + a * lv["width"], f + e * lv["height"], f
        if x1 < lx0 or x0 > lx1 or y1 < ly0 or y0 > ly1:
            continue
        with rasterio.open(resolve_dem_path(lv["path"])) as src:
            part = read_level(src, x0, y1, res, TILE, TILE, lv.get("nodata"))
        ok = np.isfinite(part)
        arr[ok] = part[ok]
    return arr, res


def render_tile(z: int, x: int, y: int) -> bytes:
    """PNG bytes of tile z/x/y: the same size, grid and colours as the engine's tiles, read without the grid artefact."""
    from PIL import Image

    got = render_heights(z, x, y)
    if got is None:
        return _empty()
    arr, res = got
    if not np.isfinite(arr).any():
        return _empty()
    buf = io.BytesIO()
    Image.fromarray(hillshade_rgba(arr, res), "RGBA").save(buf, "PNG", optimize=True)
    return buf.getvalue()
