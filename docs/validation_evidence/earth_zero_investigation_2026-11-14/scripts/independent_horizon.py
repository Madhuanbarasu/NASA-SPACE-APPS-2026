"""Independent check (near field of 2 pixels excluded, as in the engine) of the engine's terrain horizon toward the Earth (read only; no engine code is used for the
horizon itself). For a site and azimuth, march along the great circle from the site, sample the registered LOLA DEMs
(nearest pixel, finest product containing each point), and take the maximum elevation angle of the terrain seen from
the site (observer at ground height + observer height above the 1737.4 km sphere). Compare with the engine result's
horizon h(az) at the same azimuth and at the opposite azimuth (a mirrored or rotated azimuth convention would show up).

Run from backend/:  python <this file> <result_id> [<result_id> ...]
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import rasterio

sys.path.insert(0, str(Path.cwd()))
from lunaops import settings  # noqa: E402
from lunaops.engine import dem as edem  # noqa: E402
from lunaops.engine.frames import enu_basis, south_polar_stereo_xy, unit_from_latlon  # noqa: E402

R = settings.R_MOON_M
levels = edem.usable_levels()                       # finest first
handles = [(lv, rasterio.open(edem.resolve_dem_path(lv["path"]))) for lv in levels]


def height_at(x, y):
    for lv, ds in handles:
        a, _, c, _, e, f = lv["transform"]
        col, row = int(math.floor((x - c) / a)), int(math.floor((y - f) / e))
        if 0 <= row < lv["height"] and 0 <= col < lv["width"]:
            v = ds.read(1, window=((row, row + 1), (col, col + 1)))[0, 0]
            if np.isfinite(v) and abs(v) < 20000 and (lv.get("nodata") is None or v != lv["nodata"]):
                return float(v), lv["level"]
    return None, None


def horizon(lat, lon, h0, az, max_km=150.0):
    u = unit_from_latlon(math.radians(lat), math.radians(lon))
    e, n, _ = enu_basis(lat, lon)
    t = math.sin(math.radians(az)) * e + math.cos(math.radians(az)) * n
    obs = (R + h0) * u
    best, best_d, best_lv = -90.0, None, None
    d = 20.0
    while d <= max_km * 1000.0:
        ang = d / R
        p = math.cos(ang) * u + math.sin(ang) * t
        x, y = south_polar_stereo_xy(p, R)
        hz, lv = height_at(x, y)
        pix = next((float(l["pixel_m"]) for l, _ in handles if l["level"] == lv), 0.0)
        # skip the near field (closer than 2 pixels of the sampled product): nearest-pixel sampling next to the site
        # compares a neighbouring pixel's height with the interpolated site height (the engine treats this zone separately)
        if hz is not None and d >= 2.0 * pix:
            v = (R + hz) * p - obs
            el = math.degrees(math.asin(float(np.dot(v, u)) / float(np.linalg.norm(v))))
            if el > best:
                best, best_d, best_lv = el, d, lv
        d += 20.0 if d < 5000 else (80.0 if d < 40000 else 240.0)
    return best, best_d, best_lv


out = []
for rid in sys.argv[1:]:
    r = json.load(open(settings.CACHE_DIR / f"result_{rid}.json"))
    lat, lon, gh = r["site"]["lat"], r["site"]["lon"], r["site"]["ground_h_m"]
    obs_h = r["provenance"]["parameters"]["observer"]["height_m"]
    h_eng = np.array(r["horizon"]["h_deg"], float)
    az_e = np.array([v for v in r["series"]["earth"]["az"] if v is not None], float)
    az_mid = float(np.degrees(np.arctan2(np.sin(np.radians(az_e)).mean(), np.cos(np.radians(az_e)).mean())) % 360)
    row = {"result": rid, "lat": lat, "lon": lon, "ground_h_m": gh, "earth_az_mid": round(az_mid, 2), "checks": []}
    for az in (az_mid, (az_mid + 180.0) % 360.0, (az_mid + 90.0) % 360.0):
        mine, dist, lv = horizon(lat, lon, gh + obs_h, az)
        eng = float(np.interp(az, np.arange(3600) * 0.1, h_eng, period=360.0))
        row["checks"].append({"az": round(az, 2), "independent_deg": round(mine, 3), "at_km": None if dist is None else round(dist / 1000, 2),
                              "product": lv, "engine_deg": round(eng, 3), "difference_deg": round(mine - eng, 3)})
    out.append(row)
    print(json.dumps(row))
