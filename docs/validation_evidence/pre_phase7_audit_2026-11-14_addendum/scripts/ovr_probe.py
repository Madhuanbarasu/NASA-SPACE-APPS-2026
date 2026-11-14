# Read-only: the same z7 tile area from the 20 m COG (a) via its built-in overview 1 (40 m) at native size,
# (b) via the tile read with overviews disabled (OVERVIEW_LEVEL=NONE), with bilinear and average resampling.
import math, sys
sys.path.insert(0, r"E:\LUNA-OPS\backend")
import numpy as np, rasterio
from rasterio.enums import Resampling
from rasterio.windows import from_bounds
from lunaops.api import tiles
from lunaops.engine.dem import usable_levels, resolve_dem_path
exec(open(sys.argv[1]).read().split("for lv in usable_levels():")[0].split("meta = tiles.tile_meta()")[1].join(["meta = tiles.tile_meta()", ""]) if False else "")
meta = tiles.tile_meta(); z, tx, ty = 7, 63, 64; r = meta["resolutions"][z]
x0 = meta["origin"][0] + tx * 256 * r; y1 = meta["origin"][1] - ty * 256 * r; x1, y0 = x0 + 256 * r, y1 - 256 * r
def shade(arr, res):
    gy, gx = np.gradient(arr, res); s = np.arctan(np.hypot(gx, gy)); a = np.arctan2(-gx, gy); az, alt = math.radians(315), math.radians(40)
    return np.clip(np.sin(alt) * np.cos(s) + np.cos(alt) * np.sin(s) * np.cos(az - a), 0, 1)
def score(img):
    hp = img - (np.roll(img, 1, 0) + np.roll(img, -1, 0) + np.roll(img, 1, 1) + np.roll(img, -1, 1)) / 4
    hp = hp[2:-2, 2:-2]; n = hp.std() + 1e-12
    return round(float(np.abs(hp.mean(axis=0)).mean() / n * math.sqrt(hp.shape[0])), 2), round(float(np.abs(hp.mean(axis=1)).mean() / n * math.sqrt(hp.shape[1])), 2)
lv = [l for l in usable_levels() if l["level"] == "20m"][0]; p = str(resolve_dem_path(lv["path"]))
with rasterio.open(p, overview_level=0) as o:   # first overview = 40 m
    w = from_bounds(x0, y0, x1, y1, o.transform); a = o.read(1, window=w).astype(np.float32)
    print("overview 40 m, native size", a.shape, "line score", score(shade(a, 40.0)))
for m in ("bilinear", "average"):
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR"), rasterio.open(p, OVERVIEW_LEVEL="NONE") as s:
        w = from_bounds(x0, y0, x1, y1, s.transform)
        a = s.read(1, window=w, out_shape=(256, 256), resampling=getattr(Resampling, m)).astype(np.float32)
        print(f"full-res 20 m -> 56.8 m, overviews disabled, {m}: line score", score(shade(a, r)))
# (c) the overview opened explicitly and resampled by RasterIO (out_shape) vs (d) by rasterio.warp.reproject
from rasterio.warp import reproject
from affine import Affine
with rasterio.open(p, overview_level=0) as o:
    w = from_bounds(x0, y0, x1, y1, o.transform)
    for m in ("bilinear", "average"):
        a = o.read(1, window=w, out_shape=(256, 256), resampling=getattr(Resampling, m)).astype(np.float32)
        print(f"overview 40 m read with out_shape, {m}: line score", score(shade(a, r)))
    nat = o.read(1, window=w).astype(np.float32); wt = o.window_transform(w)
    for m in ("bilinear", "average"):
        dst = np.zeros((256, 256), np.float32)
        reproject(nat, dst, src_transform=wt, src_crs=o.crs, dst_transform=Affine(r, 0, x0, 0, -r, y1), dst_crs=o.crs, resampling=getattr(Resampling, m))
        print(f"overview 40 m read natively, then warp {m}: line score", score(shade(dst, r)))
# (e) the default open (GDAL chooses the overview) exactly as api/tiles.py, boundless True vs False
with rasterio.open(p) as s:
    w = from_bounds(x0, y0, x1, y1, s.transform)
    for b in (True, False):
        for m in ("bilinear", "average"):
            kw = dict(boundless=True, fill_value=np.nan) if b else {}
            a = s.read(1, window=w, out_shape=(256, 256), resampling=getattr(Resampling, m), **kw).astype(np.float32)
            print(f"default open, boundless={b}, {m}: line score", score(shade(a, r)))
print("rasterio", rasterio.__version__, "GDAL", rasterio.__gdal_version__)
