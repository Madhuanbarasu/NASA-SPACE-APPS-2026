"""A12: analyses of the LROC reference maps behind the V-12 methodology (reproducible; reads only).

    python -I reference_analysis.py <TWI.IMG> <PCT.IMG> <LPSR_80S_20MPP_ADJ.TIF> <AVGVISIB_85S_060M_201608.IMG> \
        <wac_movie_south_epochs.json> > reference_analysis.txt

1. TWI vs PCT (the reference's processing-variant spread: the C2 slacks 1.31 pp RMS and 3.0 pp p95).
2. Scattered light: LROC values at PGDA 90 permanent-shadow interior points (2-cell margin) inside 88-90 S (C1 basis).
3. Co-registration with the PGDA 90 frame: LROC zero pixels vs LPSR fully shadowed 100 m pixels, LROC shifted by
   up to +-2 pixels.
4. LROC vs LOLA AVGVISIB (18.6-year modelled, 'any' rule) on the LROC grid (100 m block mean): the C3 benchmark scale.
5. WAC frame cadence in the map's year from the WAC_POLE_MOVIE_SOUTH file names (epochs only; no frames downloaded).
"""
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import rasterio

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "backend"))
from validation import v11_psr as V11  # noqa: E402
from validation import v12_lroc as V  # noqa: E402
from validation.v09_v10_avgvisib import read_avgvisib  # noqa: E402

twi_p, pct_p, lpsr_p, av_p, ep_p = sys.argv[1:6]
twi, tm = V.read_lroc(twi_p)
pct, _ = V.read_lroc(pct_p)
print(f"# LROC maps: image offset {tm['image_offset']}, valid {tm['valid_pixels']:,}, missing {tm['missing_pixels']:,}")

both = np.isfinite(twi) & np.isfinite(pct)
d = twi[both] - pct[both]
print(f"1. TWI - PCT over {both.sum():,} px: mean {d.mean():.3f}, RMS {np.sqrt(np.mean(d * d)):.3f}, median |d| "
      f"{np.median(np.abs(d)):.3f}, p95 |d| {np.percentile(np.abs(d), 95):.3f}, max |d| {np.abs(d).max():.2f} pp")

pts, info = V11.interior_points(lpsr_p, 10 ** 6, seed=1, lat_limit=-88.0)
x = np.array([p["x_m"] for p in pts]); y = np.array([p["y_m"] for p in pts])
col = np.round(x / 100.0 + 606.5).astype(int); row = np.round(606.5 - y / 100.0).astype(int)
for name, a in (("TWI", twi), ("PCT", pct)):
    v = a[row, col]; v = v[np.isfinite(v)]
    print(f"2. {name} at {v.size:,} LPSR interior points: == 0 {np.mean(v <= 0):.3f}; > 1 % {np.mean(v > 1):.5f}; "
          f"p99.9 {np.percentile(v, 99.9):.3f}; max {v.max():.2f} %")

with rasterio.open(lpsr_p) as src:
    c0 = int(round((-60700 - src.transform.c) / 20.0)); r0 = int(round((src.transform.f - 60700) / 20.0))
    a = src.read(1, window=((r0, r0 + 1214 * 5), (c0, c0 + 1214 * 5)))
share = (a == 1).reshape(1214, 5, 1214, 5).mean(axis=(1, 3))
valid = np.isfinite(twi)
res = []
for dr in range(-2, 3):
    for dc in range(-2, 3):
        t = np.roll(np.roll(twi, dr, 0), dc, 1)
        v = valid & np.roll(np.roll(valid, dr, 0), dc, 1)
        v[:3, :] = v[-3:, :] = False; v[:, :3] = v[:, -3:] = False
        lz, full = t[v] <= 0.0, share[v] >= 1.0
        res.append((np.sum(lz & full) / np.sum(lz | full), dr, dc))
best = max(res)
print(f"3. co-registration: IoU at zero shift {dict(((r, c), i) for i, r, c in res)[(0, 0)]:.4f}; best {best[0]:.4f} at shift "
      f"({best[1]:+d},{best[2]:+d}); one-pixel shifts {min(i for i, r, c in res if abs(r) + abs(c) == 1):.4f}-"
      f"{max(i for i, r, c in res if abs(r) + abs(c) == 1):.4f}")

av, am = read_avgvisib(av_p)
av = av * 100.0
rows, cols = np.nonzero(np.isfinite(twi))
xs = (np.arange(1214) - 606.5) * 100.0
blk = np.array([V.avgvisib_block(av, am, xs[c], -xs[r]) for r, c in zip(rows, cols)])
for name, a in (("TWI", twi), ("PCT", pct)):
    dd = a[rows, cols] - blk
    print(f"4. {name} - AVGVISIB (100 m block mean): mean {dd.mean():.2f} pp, RMSE {np.sqrt(np.mean(dd * dd)):.2f}, "
          f"corr {np.corrcoef(a[rows, cols], blk)[0, 1]:.3f}")

ep = [datetime.strptime(e, "%Y%m%dT%H%M") for e in json.load(open(ep_p))]
a_, b_ = datetime(2010, 2, 15), datetime(2011, 2, 5)
t = np.array([(e - a_).total_seconds() / 3600 for e in ep if a_ <= e <= b_])
dt = np.diff(t)
print(f"5. WAC frames in 2010-02-15..2011-02-05: {t.size} (README: 3807 + 229); interval median {np.median(dt):.2f} h, "
      f"p99 {np.percentile(dt, 99):.1f} h, max {dt.max():.1f} h; gaps > 6 h: {int(np.sum(dt > 6))} totalling {dt[dt > 6].sum():.0f} h")
