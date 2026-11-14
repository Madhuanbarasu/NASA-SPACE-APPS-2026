"""Phase 5: compare the landing package's slope (Horn 1981, lunaops_landing.kernels.slope_horn) with NASA's own
PGDA 78 Site01 slope product (Site01_final_adj_5mpp_slp.tif) over the whole 16 x 16 km Site01 grid.

Read only. Run from backend/:  python <this file>
The NASA README does not state the baseline or method of its slope product, so two of our estimators are compared:
Horn's 3 x 3 weighted differences (used by the app) and plain 2-pixel central differences. Differences are also split
by whether the pixel holds a LOLA return (LDEC count map) and compared with NASA's slope uncertainty (slperr).
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path.cwd()))
import rasterio  # noqa: E402
from rasterio.windows import Window  # noqa: E402

from lunaops.engine import dem as edem  # noqa: E402
from lunaops_landing import kernels as K  # noqa: E402
from lunaops_landing.sources import R, aux_for, landing_dir, point_scale  # noqa: E402

lv = next(p for p in edem.usable_levels() if p["level"] == "5m")
aux, notes = aux_for(lv)
assert {"count", "slope", "slope_error"} <= set(aux), notes
W, H = lv["width"], lv["height"]
a, _, c, _, e, f = lv["transform"]
STRIP = 400


def strip(path, r0, n):
    with rasterio.open(path) as s:
        return s.read(1, window=Window(0, r0, W, n)).astype(np.float64)


acc = {k: [] for k in ("horn", "central", "nasa", "err", "count")}
for r0 in range(0, H, STRIP):
    a0, a1 = max(r0 - 1, 0), min(r0 + STRIP + 1, H)
    z = edem._read_block(lv, 0, a0, W, a1 - a0).astype(np.float64)
    xs = c + a * (np.arange(W) + 0.5)
    ys = f + e * (np.arange(a0, a1) + 0.5)
    X, Y = np.meshgrid(xs, ys)
    k = point_scale(X, Y)
    g = (abs(a) / k) * ((R + np.nan_to_num(z)) / R)
    horn = K.slope_horn(z, g, g)
    cen = np.full(z.shape, np.nan)
    dzdx = (z[1:-1, 2:] - z[1:-1, :-2]) / (2 * g[1:-1, 1:-1])
    dzdy = (z[2:, 1:-1] - z[:-2, 1:-1]) / (2 * g[1:-1, 1:-1])
    cen[1:-1, 1:-1] = np.degrees(np.arctan(np.hypot(dzdx, dzdy)))
    lo, hi = r0 - a0, r0 - a0 + min(STRIP, H - r0)
    acc["horn"].append(horn[lo:hi]); acc["central"].append(cen[lo:hi])
    for kind, key in (("slope", "nasa"), ("slope_error", "err"), ("count", "count")):
        acc[key].append(strip(landing_dir() / aux[kind]["path"], r0, hi - lo))
A = {k: np.vstack(v) for k, v in acc.items()}
ok = np.isfinite(A["horn"]) & np.isfinite(A["nasa"]) & np.isfinite(A["central"])
out = {"site": "PGDA 78 Site01 (5 m, 3200 x 3200)", "pixels_compared": int(ok.sum()),
       "nasa_slope_product": aux["slope"]["product"], "nasa_slope_sha256": aux["slope"]["sha256"],
       "dem_sha256": lv["sha256"], "point_scale_range": [float(point_scale(c, f)), float(point_scale(c + a * W, f + e * H))]}


def summarise(name, ours, sel):
    d = (ours - A["nasa"])[sel]
    ad = np.abs(d)
    err = A["err"][sel]
    return {"estimator": name, "n": int(sel.sum()), "mean_diff_deg": round(float(d.mean()), 3),
            "median_diff_deg": round(float(np.median(d)), 3), "rms_diff_deg": round(float(np.sqrt((d ** 2).mean())), 3),
            "p95_abs_diff_deg": round(float(np.percentile(ad, 95)), 3),
            "correlation": round(float(np.corrcoef(ours[sel], A["nasa"][sel])[0, 1]), 4),
            "share_within_1x_nasa_slope_sigma": round(float((ad <= err).mean()), 4),
            "share_within_2x_nasa_slope_sigma": round(float((ad <= 2 * err).mean()), 4),
            "our_median_deg": round(float(np.median(ours[sel])), 3), "nasa_median_deg": round(float(np.median(A["nasa"][sel])), 3)}


meas = ok & (A["count"] > 0)
interp = ok & (A["count"] == 0)
out["all"] = [summarise("horn_3x3 (app)", A["horn"], ok), summarise("central_2px", A["central"], ok)]
out["measured_pixels"] = [summarise("horn_3x3 (app)", A["horn"], meas)]
out["interpolated_pixels"] = [summarise("horn_3x3 (app)", A["horn"], interp)]
out["measured_share"] = round(float((A["count"] > 0).mean()), 4)
out["nasa_slope_sigma_median_deg"] = round(float(np.median(A["err"])), 3)
print(json.dumps(out, indent=1))
