"""AUD-05: do the edges of the lighter rectangle in the audit screenshot fall on the backdrop's tile edges?

Read only. Input: the audit screenshot (pre_phase7_audit_2026-11-14/browser_run2/screenshots/layout-1920-landing.png).
1. Measures the strongest brightness steps inside the hazard raster (column and row means).
2. Predicts the screen position of the zoom-11 and zoom-10 tile edges of the hillshade backdrop from:
   - the tile grid of /api/tiles/meta: origin (-931200, 931200) m, resolutions 7.104 (z10) and 3.552 (z11) m/px, 256 px tiles;
   - the screening window extent_xy_m [-12500, -13500, -9495, -10495] m (minx, miny, maxx, maxy; before/corrections-before.json);
   - the map's fit (LandingMap.tsx: view.fit(extent, padding 16)) in the 1920 px layout, read from the screenshot: the
     window outline's left edge at x = 1160 and top edge at y = 499, 588 px across for 3005 m (5.1105 m/px).
Usage: python aud05_tile_alignment.py <layout-1920-landing.png>
"""
import sys

import numpy as np
from PIL import Image

im = np.asarray(Image.open(sys.argv[1]).convert("L"), dtype=float)
x0, x1, y0, y1 = 1166, 1742, 505, 1075          # inside the raster window, clear of its outline
sub = im[y0:y1, x0:x1]


def steps(p, off, k=6):
    s = np.convolve(p, np.ones(8) / 8, mode="same")
    d = s[8:] - s[:-8]
    picked = []
    for i in np.argsort(-np.abs(d)):
        if all(abs(i - j) > 20 for j in picked):
            picked.append(i)
        if len(picked) == k:
            break
    return sorted((int(i + 4 + off), round(float(d[i]), 1)) for i in picked)


print("measured column steps (x, brightness change):", steps(sub[300:, :].mean(axis=0), x0))
print("measured row steps (y, brightness change):   ", steps(sub[:, 160:460].mean(axis=1), y0))
print("(the steps at about x 1170/1737 and y 509/1067 are the averaging window's own edges)")

ORIGIN_X, ORIGIN_Y = -931200.0, 931200.0
EXT = (-12500.0, -13500.0, -9495.0, -10495.0)
SX0, SY0 = 1160.0, 499.0                         # screen position of (minx, maxy)
RES_VIEW = (EXT[2] - EXT[0]) / 588.0             # m per screen pixel
for z, res in ((10, 7.1044921875), (11, 3.55224609375)):
    tile_m = 256 * res
    cols = range(int((EXT[0] - ORIGIN_X) // tile_m), int((EXT[2] - ORIGIN_X) // tile_m) + 2)
    rows = range(int((ORIGIN_Y - EXT[3]) // tile_m), int((ORIGIN_Y - EXT[1]) // tile_m) + 2)
    xs = [(c, round(SX0 + (ORIGIN_X + c * tile_m - EXT[0]) / RES_VIEW, 1)) for c in cols]
    ys = [(r, round(SY0 + (EXT[3] - (ORIGIN_Y - r * tile_m)) / RES_VIEW, 1)) for r in rows]
    print(f"zoom {z} ({res:.3f} m/px, tile {tile_m:.2f} m = {tile_m / RES_VIEW:.1f} screen px): column edges (index, x) {xs}")
    print(f"zoom {z}: row edges (index, y) {ys}")
