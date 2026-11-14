"""V-10 holdout: diagnosis of the dominant point (85.3305 S, 285.2104 E; reference 0.00 %, computed 39.80 %). Read only;
nothing here changes the frozen result or criteria.
  1. the reference map around the point at growing radii (is NASA's 0 % local or regional?);
  2. Earth's azimuth/elevation range over the 18.6-year track; the engine horizon over that azimuth range: height,
     blocker distance, blocker product, near-field and incomplete flags;
  3. how far the blocking terrain lies and whether it is inside the reference DEM's extent (LDEM_85S_060M, +-151.74 km);
  4. the same evaluation with the observer at 2 m and with a 60 m near field (as in the earlier experiment).
Usage: python v10_outlier_diagnosis.py <out json>
"""
import json, math, os, sys
os.environ["LUNAOPS_WINDOW_MODE"] = "full"
sys.path.insert(0, r"E:\LUNA-OPS\backend")
import numpy as np

from lunaops.engine.dem import LevelWindow, load_pyramid, south_polar_stereo_xy, unit_from_latlon
from lunaops.engine.ephem import Site
from lunaops.engine.horizon import compute_horizon
from validation.v09_v10_avgvisib import evaluate_point, read_avgvisib, topocentric, track

LAT, LON = -85.33050, 285.21040
out = {"point": {"lat": LAT, "lon": LON}}
frac, meta = read_avgvisib(r"E:\LUNA-OPS\data\reference_validation\AVGVISIB_85S_060M_201608_EARTH.IMG")
p = unit_from_latlon(math.radians(LAT), math.radians(LON))
x, y = south_polar_stereo_xy(p, 1737400.0)
s = meta["map_scale_m"]; x0 = -151740.0; y0 = 151740.0
col, row = int((x - x0) // s), int((y0 - y) // s)
ring = {}
for rad_px in (1, 5, 17, 50):                  # +-60 m, +-300 m, +-1 km, +-3 km
    blk = frac[max(row - rad_px, 0):row + rad_px + 1, max(col - rad_px, 0):col + rad_px + 1]
    ring[f"+-{rad_px * 60} m"] = {"min": float(blk.min()), "max": float(blk.max()), "mean": float(blk.mean()), "share_zero": float(np.mean(blk == 0))}
out["reference_neighbourhood"] = ring
out["xy_m"] = [float(x), float(y)]; out["reference_extent_m"] = 151740.0
print("reference around the point:", json.dumps(ring))

trk = track("2026-01-01T00:00:00Z", 18.6)
hz = compute_horizon(LAT, LON, 0.0)
site = Site(LAT, LON, float(hz.ground_h_m), 0.0)
ea = topocentric(site, trk["earth"])
az, el = ea["az"], ea["el"]
out["earth"] = {"az_range": [float(np.min(az)), float(np.max(az))], "el_range": [float(np.min(el)), float(np.max(el))],
                "hours_above_0deg_share": float(np.mean(el > 0))}
bins = np.unique((np.round(az / 0.1).astype(int)) % 3600)
H = np.asarray(hz.h_deg)[bins]; D = np.asarray(hz.block_dist_m)[bins]
W = np.asarray(hz.blocker_product)[bins] if hz.blocker_product is not None else None
levels = [lv["level"] for lv in hz.levels]
out["horizon_toward_earth"] = {"bins": int(bins.size), "h_min": float(H.min()), "h_max": float(H.max()), "h_median": float(np.median(H)),
                               "blocker_distance_km_min": float(np.nanmin(D) / 1000), "blocker_distance_km_max": float(np.nanmax(D) / 1000),
                               "blocker_products": sorted({levels[int(w)] for w in W if w >= 0}) if W is not None else None,
                               "incomplete_bins": int(np.asarray(hz.incomplete)[bins].sum()),
                               "near_field_bins": int(np.asarray(hz.near_field)[bins].sum()) if hz.near_field is not None else None,
                               "ground_h_m": float(hz.ground_h_m)}
# blocking points: projected position of the blocker for each Earth-direction bin, and whether it is inside the reference DEM
e_hat = np.array([-math.sin(math.radians(LON)), math.cos(math.radians(LON))])          # unused; azimuth handled below
bx = []
for b, dist in zip(bins, D):
    if not np.isfinite(dist):
        continue
    a = math.radians(b * 0.1)
    # local east/north at the site in the polar stereographic plane (south pole): north points toward the pole
    r = math.hypot(x, y); nx, ny = -x / r, -y / r; ex, ey = -ny, nx
    bx.append((x + dist * (math.sin(a) * ex + math.cos(a) * nx), y + dist * (math.sin(a) * ey + math.cos(a) * ny)))
bx = np.array(bx)
inside = np.all(np.abs(bx) <= 151740.0, axis=1) if bx.size else np.array([])
out["blockers_inside_reference_dem_share"] = float(np.mean(inside)) if inside.size else None
vis_share = float(np.mean(el > np.interp(az, np.arange(3600) * 0.1, np.asarray(hz.h_deg), period=360)))
out["earth_centre_above_engine_horizon_share"] = vis_share
print(json.dumps({k: out[k] for k in ("earth", "horizon_toward_earth", "blockers_inside_reference_dem_share", "earth_centre_above_engine_horizon_share")}, indent=1))


def pyramid_60m(lat, lon):
    pyr = load_pyramid(lat, lon)
    w20 = next(w for w in pyr if w.level == "20m")
    a = w20.data; nr, nc = (a.shape[0] // 3) * 3, (a.shape[1] // 3) * 3
    avg = a[:nr, :nc].reshape(nr // 3, 3, nc // 3, 3).mean(axis=(1, 3)).astype(np.float32)
    w60 = LevelWindow(level="60m", data=avg, x0=w20.x0 + w20.dx, y0=w20.y0 + w20.dy, dx=3 * w20.dx, dy=3 * w20.dy,
                      band_m=w20.band_m, pixel_m=60.0, meta={"key": "60m:block-average of the 20 m LOLA product"})
    return [w60] + [w for w in pyr if w.level not in ("5m", "10m", "20m")]


variants = {"engine_0m": (0.0, None), "engine_2m": (2.0, None),
            "near_field_60m_0m": (0.0, lambda la, lo, h: compute_horizon(la, lo, 0.0, pyramid=pyramid_60m(la, lo)))}
out["variants"] = {}
for name, (h, fn) in variants.items():
    r = evaluate_point(LAT, LON, "earth", trk, h, horizon_fn=fn)
    out["variants"][name] = {k: r.get(k) for k in ("outcome", "computed", "exact_hours")}
    print(name, out["variants"][name])
json.dump(out, open(sys.argv[1], "w"), indent=1, default=float)
