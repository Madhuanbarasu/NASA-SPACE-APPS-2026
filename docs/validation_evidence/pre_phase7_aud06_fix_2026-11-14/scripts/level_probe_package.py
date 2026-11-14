# The addendum's level_probe.py measurement (same tile, same score, same hillshade) applied to lunaops_tiles.read_level
# instead of the engine's boundless read. Read only; offline (no server). Usage: python level_probe_package.py
import math, sys
sys.path.insert(0, r"E:\LUNA-OPS\backend")
import numpy as np, rasterio
from lunaops.api import tiles
from lunaops.engine.dem import usable_levels, resolve_dem_path
from lunaops_tiles.render import read_level
meta = tiles.tile_meta(); z, tx, ty = 7, 63, 64; r = meta["resolutions"][z]
x0 = meta["origin"][0] + tx * 256 * r; y1 = meta["origin"][1] - ty * 256 * r
def shade(arr, res):   # level_probe.py's shade()
    gy, gx = np.gradient(np.nan_to_num(arr, nan=np.nanmean(arr)), res)
    s = np.arctan(np.hypot(gx, gy)); a = np.arctan2(-gx, gy); az, alt = math.radians(315), math.radians(40)
    return np.clip(np.sin(alt) * np.cos(s) + np.cos(alt) * np.sin(s) * np.cos(az - a), 0, 1)
def score(img):        # level_probe.py's score()
    hp = img - (np.roll(img, 1, 0) + np.roll(img, -1, 0) + np.roll(img, 1, 1) + np.roll(img, -1, 1)) / 4
    hp = hp[2:-2, 2:-2]; n = hp.std() + 1e-12
    return round(float(np.abs(hp.mean(axis=0)).mean() / n * math.sqrt(hp.shape[0])), 2), round(float(np.abs(hp.mean(axis=1)).mean() / n * math.sqrt(hp.shape[1])), 2)
for lv in usable_levels():
    with rasterio.open(resolve_dem_path(lv["path"])) as src:
        part = read_level(src, x0, y1, r, 256, 256, lv.get("nodata"))
    cov = float(np.isfinite(part).mean())
    if cov < 1:
        print(f"{lv['level']}: coverage {cov:.2f}  (partial; not scored, as in level_probe.py)"); continue
    print(f"{lv['level']}: coverage {cov:.2f}  line score cols/rows (z7, lunaops_tiles read) {score(shade(part, r))}")
