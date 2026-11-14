"""Basemap tiles rendered from the registered LOLA DEMs (blueprint Section 6.2 step 6).

The shading is cartographic (fixed light from the upper left), not the
computed lunar Sun; it exists only to make terrain legible on the map.
"""
from __future__ import annotations

import io
import json
import math
from functools import lru_cache

import numpy as np

from ..engine.dem import products_digest, resolve_dem_path, usable_levels

TILE = 256
STEREO_PROJ4 = ("+proj=stere +lat_0=-90 +lat_ts=-90 +lon_0=0 +k=1 +x_0=0 +y_0=0 "
                "+R=1737400 +units=m +no_defs")


def tile_meta() -> dict | None:
    return _tile_meta(json.dumps(products_digest()))


@lru_cache(maxsize=4)
def _tile_meta(_digest: str) -> dict | None:
    levels = usable_levels()
    if not levels:
        return None
    coarse = levels[-1]
    fine = levels[0]
    a, _, c, _, e, f = coarse["transform"]
    extent = [c, f + e * coarse["height"], c + a * coarse["width"], f]
    size = max(extent[2] - extent[0], extent[3] - extent[1])
    r0 = size / TILE
    res = []
    r = r0
    while r > fine["pixel_m"] / 2 and len(res) < 20:
        res.append(r)
        r /= 2
    res.append(r)
    return {"extent": extent, "origin": [extent[0], extent[3]], "resolutions": res, "tile_size": TILE,
            "proj4": STEREO_PROJ4, "code": "LUNAOPS:SPS",
            "levels": [{"level": lv["level"], "product": lv.get("product"), "synthetic": bool(lv.get("synthetic"))}
                       for lv in levels],
            "note": "Cartographic hillshade from LOLA heights (fixed light direction); not the lunar Sun."}


def render_tile(z: int, x: int, y: int) -> bytes:
    import rasterio
    from PIL import Image
    from rasterio.enums import Resampling
    from rasterio.windows import from_bounds

    meta = tile_meta()
    if meta is None or z < 0 or z >= len(meta["resolutions"]):
        return _empty()
    res = meta["resolutions"][z]
    x0 = meta["origin"][0] + x * TILE * res
    y1 = meta["origin"][1] - y * TILE * res
    x1, y0 = x0 + TILE * res, y1 - TILE * res
    levels = usable_levels()
    arr = np.full((TILE, TILE), np.nan, dtype=np.float32)
    for lv in reversed(levels):  # coarse first, finer levels overwrite where they have data
        if lv["pixel_m"] > res * 4 and lv is not levels[-1]:
            continue
        a, _, c, _, e, f = lv["transform"]
        lx0, lx1, ly0, ly1 = c, c + a * lv["width"], f + e * lv["height"], f
        if x1 < lx0 or x0 > lx1 or y1 < ly0 or y0 > ly1:
            continue
        # Read only the tile pixels this product covers (aligned to the tile's own pixel grid) and resample them to
        # exactly those pixels. A boundless read of the whole tile window made GDAL build a virtual raster as large as
        # the tile at the product's resolution: for the 16 km 5 m Site01 product inside a 931 km zoom-1 tile that is
        # about 186,000 x 186,000 pixels, which took minutes and gigabytes. Every overlapping product still contributes
        # at the tile's resolution (nothing is skipped); for a product covering the whole tile the read is unchanged.
        c0, c1 = max(0, math.floor((lx0 - x0) / res)), min(TILE, math.ceil((lx1 - x0) / res))
        r0, r1 = max(0, math.floor((y1 - ly1) / res)), min(TILE, math.ceil((y1 - ly0) / res))
        if c1 <= c0 or r1 <= r0:
            continue
        with rasterio.open(resolve_dem_path(lv["path"])) as src:
            win = from_bounds(x0 + c0 * res, y1 - r1 * res, x0 + c1 * res, y1 - r0 * res, src.transform)
            nod = lv.get("nodata")
            part = src.read(1, window=win, out_shape=(r1 - r0, c1 - c0), boundless=True,
                            fill_value=nod if nod is not None else np.nan,
                            resampling=Resampling.bilinear).astype(np.float32)
        if nod is not None:
            part[part == np.float32(nod)] = np.nan
        ok = np.isfinite(part)
        arr[r0:r1, c0:c1][ok] = part[ok]
    if not np.isfinite(arr).any():
        return _empty()
    gy, gx = np.gradient(np.nan_to_num(arr, nan=np.nanmean(arr)), res)
    slope = np.arctan(np.hypot(gx, gy))
    aspect = np.arctan2(-gx, gy)
    az, alt = math.radians(315.0), math.radians(40.0)
    shade = np.sin(alt) * np.cos(slope) + np.cos(alt) * np.sin(slope) * np.cos(az - aspect)
    shade = np.clip(shade, 0, 1)
    v = (40 + 190 * shade).astype(np.uint8)
    alpha = np.where(np.isfinite(arr), 255, 0).astype(np.uint8)
    rgba = np.dstack([v, v, (v * 1.02).clip(0, 255).astype(np.uint8), alpha])
    buf = io.BytesIO()
    Image.fromarray(rgba, "RGBA").save(buf, "PNG", optimize=True)
    return buf.getvalue()


@lru_cache(maxsize=1)
def _empty() -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGBA", (TILE, TILE), (0, 0, 0, 0)).save(buf, "PNG")
    return buf.getvalue()
