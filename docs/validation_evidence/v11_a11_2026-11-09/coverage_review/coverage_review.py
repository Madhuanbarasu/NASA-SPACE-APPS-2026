"""A11 review: sampled V-11 latitude range against the LPSR product's coverage (read-only, scratch only).

Inputs: the LPSR map and the 80 m PGDA 90 DEM (both SHA-verified, in scratch) and the committed seed-1 points.
"""
import json
import math
import sys

import numpy as np
import rasterio

LPSR, DEM, POINTS = sys.argv[1], sys.argv[2], sys.argv[3]
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[4] / "backend"))
from validation import v11_psr as V  # noqa: E402

R = 1737.4e3
HALF = 304_000.0
WIN = 250_000.0


def lat_of_r(r):
    return -(90.0 - math.degrees(2 * math.atan(r / (2 * R))))


def scale(r):                      # stereographic point scale factor on the sphere
    return 1.0 + (r / (2 * R)) ** 2


out = []
p = out.append
r80 = 2 * R * math.tan(math.radians(5.0))
p("## Geometry (south polar stereographic, sphere R = 1737.4 km, map extent +-304 km)")
p(f"radius of the 80S circle in the map plane: {r80 / 1e3:.3f} km (half-width of the map: {HALF / 1e3:.0f} km)")
p(f"edge midpoints: {lat_of_r(HALF):.3f} deg; corners: {lat_of_r(HALF * math.sqrt(2)):.3f} deg")
area_sq, area_circ = (2 * HALF) ** 2, math.pi * r80 ** 2
p(f"map-plane share of the square outside the 80S circle (the four corners): {1 - area_circ / area_sq:.4f}")

# shadow and interior cells, exactly as the validator builds them
with rasterio.open(LPSR) as src:
    cells, t = V.shadow_cells(LPSR, V.CELL_PX)
core = V.erode(cells, V.MARGIN_CELLS)
rows, cols = np.indices(cells.shape)
cx = t.c + (cols + 0.5) * t.a
cy = t.f + (rows + 0.5) * t.e
rr = np.hypot(cx, cy)
inside = rr <= r80
p("")
p("## LPSR cells (160 m), full resolution, as sampled by the validator")
for name, m in (("shadow cells", cells), ("interior cells", core)):
    n, no = int(m.sum()), int((m & ~inside).sum())
    p(f"{name}: {n:,}; beyond 80S (corners): {no:,} ({100 * no / n:.2f}%)")
p("interior-cell share by latitude band:")
lat = -(90.0 - np.degrees(2 * np.arctan(rr / (2 * R))))
edges = [-90, -88, -86, -84, -82, -80, -79, -78, -77, -76]
for a, b in zip(edges, edges[1:]):
    band = (lat >= a) & (lat < b)
    p(f"  {a:>4} to {b:>4}: cells {int(band.sum()):>9,}  shadow {int((cells & band).sum()):>8,} "
      f"({100 * (cells & band).sum() / max(band.sum(), 1):5.2f}% of band)  interior {int((core & band).sum()):>7,}")
# shadow density against distance to the raster edge, corners only (looks for edge artefacts)
dedge = HALF - np.maximum(np.abs(cx), np.abs(cy))
p("shadow share of corner cells (beyond 80S) by distance to the raster edge:")
for a, b in ((0, 2e3), (2e3, 5e3), (5e3, 10e3), (10e3, 20e3), (20e3, 40e3), (40e3, 90e3)):
    m = (~inside) & (dedge >= a) & (dedge < b)
    p(f"  {a / 1e3:>4.0f}-{b / 1e3:>3.0f} km: {int(m.sum()):>8,} cells, shadow {100 * cells[m].mean():5.2f}%")
with rasterio.open(LPSR) as src:
    w = src.width
    border = np.concatenate([src.read(1, window=((0, 1), (0, w))).ravel(), src.read(1, window=((w - 1, w), (0, w))).ravel(),
                             src.read(1, window=((0, w), (0, 1))).ravel(), src.read(1, window=((0, w), (w - 1, w))).ravel()])
p(f"outermost full-resolution pixel ring: {border.size:,} pixels, shadow {int((border == 1).sum()):,} "
  f"({100 * (border == 1).mean():.2f}%)")

# sampled points
pts = json.load(open(POINTS))["new_points"]
x = np.array([q["x_m"] for q in pts]); y = np.array([q["y_m"] for q in pts]); la = np.array([q["lat"] for q in pts])
r = np.hypot(x, y)
beyond = r > r80
frac = (core & ~inside).sum() / core.sum()
n = len(pts)
k = int(beyond.sum())
mean, sd = n * frac, math.sqrt(n * frac * (1 - frac))
p("")
p(f"## Sampled points (seed 1, n = {n})")
p(f"latitude range: {la.min():.3f} to {la.max():.3f} deg; beyond 80S: {k} (expected {mean:.1f} +- {sd:.1f} "
  f"from the interior-cell share {100 * frac:.2f}%)")

# terrain at every point (local, SHA-verified 80 m DEM)
with rasterio.open(DEM) as d:
    vals = np.array([v[0] for v in d.sample(zip(x, y))])
    win = []
    for xi, yi in zip(x, y):
        rr0, cc0 = d.index(xi, yi)
        a = d.read(1, window=((rr0 - 31, rr0 + 32), (cc0 - 31, cc0 + 32)), boundless=True, fill_value=np.nan)
        win.append(np.isfinite(a).mean())
    full = d.read(1)
    dem_finite = float(np.isfinite(full).mean())
p(f"80 m DEM: finite share of the whole raster {dem_finite:.6f}; finite height at the point: {int(np.isfinite(vals).sum())}/{n}; "
  f"5 km x 5 km neighbourhood fully finite: {int(sum(w_ == 1.0 for w_ in win))}/{n}")

# horizon reach: share of the 3600 azimuths whose 250 km ray leaves the 80 m DEM (no coarser product registered)
th = (np.arange(3600) + 0.5) * 2 * math.pi / 3600
dx, dy = np.cos(th), np.sin(th)
inc, reach_out = [], []
for xi, yi, ri in zip(x, y, r):
    with np.errstate(divide="ignore"):
        tx = np.where(dx > 0, (HALF - xi) / dx, np.where(dx < 0, (-HALF - xi) / dx, np.inf))
        ty = np.where(dy > 0, (HALF - yi) / dy, np.where(dy < 0, (-HALF - yi) / dy, np.inf))
    texit = np.minimum(tx, ty) / scale(ri)          # approximate ground distance to the data edge
    inc.append(float((texit < WIN).mean()))
    ux, uy = xi / ri, yi / ri                       # equatorward direction = radially outward in the map
    tox = (HALF - abs(xi)) / abs(ux) if ux else np.inf
    toy = (HALF - abs(yi)) / abs(uy) if uy else np.inf
    reach_out.append(min(tox, toy) / scale(ri))
inc, reach_out = np.array(inc), np.array(reach_out)
p("share of azimuths whose 250 km horizon ray runs off the 80 m DEM (horizon there is a lower bound):")
for lo, hi in ((-90, -88), (-88, -85), (-85, -82), (-82, -80), (-80, -76)):
    m = (la >= lo) & (la < hi)
    if m.any():
        p(f"  {lo} to {hi}: {int(m.sum()):>3} points, incomplete azimuths median {100 * np.median(inc[m]):5.1f}%, "
          f"max {100 * inc[m].max():5.1f}%; equatorward data reach min {reach_out[m].min() / 1e3:6.1f} km")
p(f"points with any incomplete azimuth: {int((inc > 0).sum())}/{n}; with no incomplete azimuth: {int((inc == 0).sum())}/{n}")
for lim in (10e3, 20e3, 50e3, 100e3):
    p(f"points whose equatorward data reach is under {lim / 1e3:.0f} km: {int((reach_out < lim).sum())}/{n}")
p("the 8 points beyond 80S:")
for i in np.argsort(-la)[:k]:
    p(f"  lat {la[i]:8.3f} lon {pts[i]['lon']:8.3f}  r {r[i] / 1e3:6.1f} km  "
      f"to raster edge {(HALF - max(abs(x[i]), abs(y[i]))) / 1e3:5.1f} km, equatorward data reach "
      f"{reach_out[i] / 1e3:5.1f} km, incomplete azimuths {100 * inc[i]:4.1f}%")
print("\n".join(out))
