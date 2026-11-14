# Read-only: the same z7 tile, hillshaded from each LOLA level alone (same read call as api/tiles.py), plus the
# native-resolution 20 m hillshade, to see which product carries the grid. Grid score = power of 1-pixel-wide straight
# lines: mean along each column/row of the high-passed image, as a ratio to the image's high-pass noise.
import math, sys
sys.path.insert(0, r"E:\LUNA-OPS\backend")
import numpy as np, rasterio
from rasterio.enums import Resampling
from rasterio.windows import from_bounds
from PIL import Image
from lunaops.api import tiles
from lunaops.engine.dem import usable_levels, resolve_dem_path
meta = tiles.tile_meta(); z, tx, ty = 7, 63, 64; r = meta["resolutions"][z]
x0 = meta["origin"][0] + tx * 256 * r; y1 = meta["origin"][1] - ty * 256 * r; x1, y0 = x0 + 256 * r, y1 - 256 * r
def shade(arr, res):
    gy, gx = np.gradient(np.nan_to_num(arr, nan=np.nanmean(arr)), res)
    s = np.arctan(np.hypot(gx, gy)); a = np.arctan2(-gx, gy); az, alt = math.radians(315), math.radians(40)
    return np.clip(np.sin(alt) * np.cos(s) + np.cos(alt) * np.sin(s) * np.cos(az - a), 0, 1)
def score(img):
    hp = img - (np.roll(img, 1, 0) + np.roll(img, -1, 0) + np.roll(img, 1, 1) + np.roll(img, -1, 1)) / 4
    hp = hp[2:-2, 2:-2]; n = hp.std() + 1e-12
    return round(float(np.abs(hp.mean(axis=0)).mean() / n * math.sqrt(hp.shape[0])), 2), round(float(np.abs(hp.mean(axis=1)).mean() / n * math.sqrt(hp.shape[1])), 2)
for lv in usable_levels():
    with rasterio.open(resolve_dem_path(lv["path"])) as src:
        win = from_bounds(x0, y0, x1, y1, src.transform)
        part = src.read(1, window=win, out_shape=(256, 256), boundless=True, fill_value=np.nan, resampling=Resampling.bilinear).astype(np.float32)
        nod = lv.get("nodata")
        if nod is not None: part[part == np.float32(nod)] = np.nan
        cov = np.isfinite(part).mean()
        if cov == 0: print(lv["level"], "no data in tile"); continue
        img = shade(part, r); img[~np.isfinite(part)] = np.nan
        sub = img[np.isfinite(part).all(axis=1)][:, np.isfinite(part).all(axis=0)] if cov < 1 else img
        print(f"{lv['level']}: coverage {cov:.2f}  line score cols/rows (z7, bilinear read) {score(sub) if sub.size > 400 else 'n/a'}")
        Image.fromarray((40 + 190 * np.nan_to_num(img, nan=0)).astype(np.uint8)).resize((768, 768), Image.NEAREST).save(sys.argv[1] + f"/lvl_{lv['level']}.png")
        if lv["level"] in ("20m", "80m"):
            # native resolution, same area (centre 1024 px crop only, to keep memory low)
            w = rasterio.windows.Window(int(win.col_off + win.width / 2 - 256), int(win.row_off + win.height / 2 - 256), 512, 512)
            nat = src.read(1, window=w).astype(np.float32)
            if nod is not None: nat[nat == np.float32(nod)] = np.nan
            ns = shade(nat, lv["pixel_m"]); print(f"   native {lv['level']} centre 512 px: line score {score(ns)}")
            Image.fromarray((40 + 190 * ns).astype(np.uint8)).save(sys.argv[1] + f"/native_{lv['level']}.png")
