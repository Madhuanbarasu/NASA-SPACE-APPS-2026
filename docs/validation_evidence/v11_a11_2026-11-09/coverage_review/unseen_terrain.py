"""A11 review: could terrain beyond the horizon's data coverage still block the Sun at each sampled point?

For each point and each 0.1 deg azimuth bin the real 18.6-year hourly Sun crosses, take the top of the disk
(el + rho_max) at its lowest in that bin, and the ground distance s_cov at which the engine's horizon stops seeing
terrain: the edge of the 80 m DEM (the only wide product registered) or the 80 m window (250 km), whichever is
nearer. Terrain at s >= s_cov blocks that Sun position only if it rises to
    H_req = min_{s >= s_cov} [ (R + h0) / (cos x - sin x tan e) - R ],  x = s / R,
(sphere R = 1737.4 km, observer at the surface, height h0). The minimum is at x = max(x_cov, -e). If H_req exceeds
any lunar relief, unseen terrain cannot block there, so a "lit" verdict in that bin cannot be a coverage artefact.
Conservative choices: the largest map scale factor (corner) turns map distance into the shortest ground distance;
each hour's azimuth arc is dilated by the largest hourly step. Missing terrain only ever lowers the computed horizon,
so it can cause false failures, never a false pass.
"""
import json
import math
import sys

import numpy as np
import rasterio
from pyproj import Transformer

DEM, POINTS = sys.argv[1], sys.argv[2]
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[4] / "backend"))
from lunaops.engine.frames import enu_basis  # noqa: E402
from lunaops.engine.kernels import load  # noqa: E402
from lunaops.testing import STEREO_PROJ4  # noqa: E402
from validation import v11_psr as V  # noqa: E402

R = 1737.4e3
HALF = 304_000.0
WIN = 250_000.0
LDEM4_MAX = 10_504.0          # PDS LOLA LDEM_4 label: MAXIMUM = 21008 DN x 0.5 m above 1737.4 km
BOUNDS = (LDEM4_MAX, 12_000.0)
K_MAX = 1.0 + (HALF * math.sqrt(2) / (2 * R)) ** 2

load()
ets, unit, rho = V.sun_track("2026-01-01T00:00:00Z")
pts = json.load(open(POINTS))["new_points"]
geo = Transformer.from_crs("+proj=longlat +R=1737400 +no_defs", STEREO_PROJ4, always_xy=True)
dem = rasterio.open(DEM)
nb = 3600
A = np.radians((np.arange(nb) + 0.5) * 0.1)
rows = []
for q in pts:
    lat, lon, x, y = q["lat"], q["lon"], q["x_m"], q["y_m"]
    h0 = float(next(dem.sample([(x, y)]))[0])
    # local north/east unit vectors in the map plane (conformal: angles preserved)
    xn, yn = geo.transform(lon, lat + 1e-4); xe, ye = geo.transform(lon + 1e-4, lat)
    n_ = np.array([xn - x, yn - y]); n_ /= np.hypot(*n_)
    e_ = np.array([xe - x, ye - y]); e_ /= np.hypot(*e_)
    d = np.outer(np.cos(A), n_) + np.outer(np.sin(A), e_)
    with np.errstate(divide="ignore", invalid="ignore"):
        tx = np.where(d[:, 0] > 0, (HALF - x) / d[:, 0], np.where(d[:, 0] < 0, (-HALF - x) / d[:, 0], np.inf))
        ty = np.where(d[:, 1] > 0, (HALF - y) / d[:, 1], np.where(d[:, 1] < 0, (-HALF - y) / d[:, 1], np.inf))
    s_cov = np.minimum(np.minimum(tx, ty) / K_MAX, WIN)
    # Sun: lowest disk top per azimuth bin, over the hour arcs (dilated by the largest hourly step)
    e, nn, u = enu_basis(lat, lon)
    el = np.degrees(np.arcsin(np.clip(unit @ u, -1, 1)))
    az = np.degrees(np.arctan2(unit @ e, unit @ nn)) % 360
    top = el + rho
    step = np.abs((np.diff(az) + 180) % 360 - 180).max()
    dil = int(math.ceil(step / 0.1)) + 1
    b = np.floor(az / 0.1).astype(int) % nb
    lo = np.full(nb, np.inf); hi = np.full(nb, -np.inf)
    np.minimum.at(lo, b, top); np.maximum.at(hi, b, top)
    lo_d = np.min([np.roll(lo, k) for k in range(-dil, dil + 1)], axis=0)
    hi_d = np.max([np.roll(hi, k) for k in range(-dil, dil + 1)], axis=0)
    seen = np.isfinite(lo_d)

    x_cov = s_cov / R
    row = {"lat": lat, "lon": lon, "h0_m": h0, "sun_bins": int(seen.sum()), "max_hourly_step_deg": float(step),
           "min_s_cov_km": float(s_cov[seen].min() / 1e3), "max_top_deg": float(top.max())}
    for B in BOUNDS:
        # highest disk top that terrain up to B beyond s_cov could still hide (closed form, optimum at s_cov)
        elim = np.degrees(np.arctan((np.cos(x_cov) - (R + h0) / (R + B)) / np.sin(x_cov)))
        k = f"{B:.0f}"
        row["robust_share_" + k] = float((seen & (lo_d > elim)).sum() / seen.sum())
        row["exposed_share_" + k] = float((seen & (hi_d <= elim)).sum() / seen.sum())
        row["elim_max_deg_" + k] = float(elim[seen].max())
        row["elim_at_highest_sun_deg_" + k] = float(elim[b[int(np.argmax(top))]])
    rows.append(row)

out = []
p = out.append
p(f"Sun track: {len(ets)} hours from 2026-01-01, rho_max {rho:.4f} deg; map scale factor used {K_MAX:.5f}")
p("e_lim(az): highest Sun-disk top that unseen terrain (beyond the 80 m DEM edge or the 250 km window) no higher"
  " than the bound above 1737.4 km could still hide. A lit verdict with the disk top above e_lim cannot be a"
  " coverage artefact; below it, it may be.")
p("robust = share of the Sun's azimuth path where even the lowest Sun is above e_lim; exposed = share where even"
  " the highest Sun is at or below e_lim")
la = np.array([r["lat"] for r in rows])
for B in BOUNDS:
    k = f"{B:.0f}"
    p(f"bound {B / 1e3:.3f} km ({'LDEM_4 label maximum' if B == LDEM4_MAX else 'looser'}):")
    for lo_, hi_ in ((-90, -88), (-88, -85), (-85, -82), (-82, -80), (-80, -76)):
        sel = [r for r in rows if lo_ <= r["lat"] < hi_]
        rb = np.array([r["robust_share_" + k] for r in sel]); ex = np.array([r["exposed_share_" + k] for r in sel])
        eh = np.array([r["elim_at_highest_sun_deg_" + k] for r in sel]); mt = np.array([r["max_top_deg"] for r in sel])
        p(f"  {lo_:>4} to {hi_:>4}: {len(sel):>3} pts | robust median {100 * np.median(rb):5.1f}% min {100 * rb.min():5.1f}%"
          f" | exposed median {100 * np.median(ex):5.1f}% max {100 * ex.max():5.1f}%"
          f" | at the Sun's highest: e_lim median {np.median(eh):6.2f} max {eh.max():6.2f} deg vs top median"
          f" {np.median(mt):5.2f} deg; points with top <= e_lim there: {int((mt <= eh).sum())}")
k = f"{LDEM4_MAX:.0f}"
p("the 8 points beyond 80S (LDEM_4 bound):")
for r in sorted(rows, key=lambda r: -r["lat"])[:8]:
    p(f"  lat {r['lat']:8.3f} lon {r['lon']:8.3f} h0 {r['h0_m']:6.0f} m: nearest data edge {r['min_s_cov_km']:5.1f} km;"
      f" Sun top max {r['max_top_deg']:5.2f} deg, e_lim there {r['elim_at_highest_sun_deg_' + k]:6.2f} deg;"
      f" robust {100 * r['robust_share_' + k]:5.1f}%, exposed {100 * r['exposed_share_' + k]:5.1f}%")
near = [r for r in rows if r["lat"] < -88]
p(f"near-pole points (< -88): e_lim max over the Sun's path {max(r['elim_max_deg_' + k] for r in near):.2f} deg "
  "(the 250 km window, not the DEM edge, sets it)")
print("\n".join(out))
json.dump(rows, open(sys.argv[3], "w"), indent=1)
