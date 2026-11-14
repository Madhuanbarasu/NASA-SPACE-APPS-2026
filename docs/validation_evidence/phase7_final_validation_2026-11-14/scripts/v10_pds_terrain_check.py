"""V-10 failing patch: independent NASA terrain check (read only; nothing in the engine, criteria, holdout or NASA data
is changed).

Terrain:
  PDS  = NASA PDS LOLA GDR ldem_85s_40m (V2.0, 2017; 40 m; DN*0.5 m above 1737.4 km) and ldec_85s_40m (LOLA shots per
         pixel; 0 = no measurement, value interpolated), downloaded 2026-11-14 to data/reference_validation/pds_lola_gdr_2017.
  PGDA = the engine's production LDEM_80S_20MPP_ADJ (20 m) for comparison.
  (NASA's own source model LDEM_85S_060M is no longer distributed by the PDS; not available.)
Steps:
  1. registration: ground height at the point from both models;
  2. the 41-pixel NASA zero patch (60 m grid) and a ring 2-4 px around it: PDS minus PGDA height, LOLA shot counts;
  3. INDEPENDENT horizon (own ray-march, not the engine's horizon code): 720 azimuths, 10 m steps to 3 km then 1 %
     growth to 150 km, curvature drop s^2/2R, map-scale factor of the polar stereographic projection, bilinear heights;
     once with PDS 40 m everywhere, once with PGDA 20 m to 20 km and PDS beyond;
  4. Earth "any part of the disc visible" (el + asin(6371/d) > h(az)) hourly over the holdout's 18.6-year track
     (engine ephemeris, V-04/V-05 validated) at the point, 8 patch pixels and 8 ring pixels (the pixels of
     band_neighbours.json), against NASA's map and the engine's holdout-method values.
Usage (from backend/): python <this> <out json> <out txt>
"""
import json
import math
import os
import sys
from pathlib import Path

os.environ["LUNAOPS_WINDOW_MODE"] = "full"
sys.path.insert(0, str(Path.cwd()))
import numpy as np  # noqa: E402
import rasterio  # noqa: E402
from rasterio.windows import from_bounds  # noqa: E402

from lunaops.engine.ephem import Site  # noqa: E402
from validation.v09_v10_avgvisib import read_avgvisib, topocentric, track  # noqa: E402

R = 1737400.0
EV = Path(r"E:\LUNA-OPS\docs\validation_evidence\phase7_final_validation_2026-11-14")
PDSD = Path(r"E:\LUNA-OPS\data\reference_validation\pds_lola_gdr_2017")
LAT, LON = -85.33050, 285.21040
txt, out = [], {}


def say(s=""):
    print(s, flush=True); txt.append(s)


def ps_xy(lat, lon):
    k = 2 * R * math.tan(math.pi / 4 + math.radians(lat) / 2)
    return k * math.sin(math.radians(lon)), k * math.cos(math.radians(lon))


# ---- terrain readers
N40, S0 = 7584, 3791.5
dem40 = np.memmap(PDSD / "ldem_85s_40m.img", dtype="<i2", mode="r", shape=(N40, N40))
cnt40 = np.memmap(PDSD / "ldec_85s_40m.img", dtype="u1", mode="r", shape=(N40, N40))


def pds_rc(x, y):
    return S0 - np.asarray(y) / 40.0, np.asarray(x) / 40.0 + S0          # fractional (row, col) of pixel centres


def bilinear(arr, r, c, scale=1.0):
    r, c = np.asarray(r, float), np.asarray(c, float)
    r0, c0 = np.floor(r).astype(int), np.floor(c).astype(int)
    ok = (r0 >= 0) & (c0 >= 0) & (r0 < arr.shape[0] - 1) & (c0 < arr.shape[1] - 1)
    r0c, c0c = np.clip(r0, 0, arr.shape[0] - 2), np.clip(c0, 0, arr.shape[1] - 2)
    fr, fc = r - r0c, c - c0c
    v = (arr[r0c, c0c] * (1 - fr) * (1 - fc) + arr[r0c + 1, c0c] * fr * (1 - fc) + arr[r0c, c0c + 1] * (1 - fr) * fc
         + arr[r0c + 1, c0c + 1] * fr * fc) * scale
    return np.where(ok, v, np.nan)


def h_pds(x, y):
    r, c = pds_rc(x, y)
    return bilinear(dem40, r, c, 0.5)


x0, y0 = ps_xy(LAT, LON)
with rasterio.open(r"E:\LUNA-OPS\data\dem\pgda90_20m\LDEM_80S_20MPP_ADJ.TIF") as ds:
    W20 = 20500.0
    win = from_bounds(x0 - W20, y0 - W20, x0 + W20, y0 + W20, ds.transform)
    a20 = ds.read(1, window=win).astype(np.float64)
    t20 = ds.window_transform(win)
    crs20 = ds.crs.to_string()
if np.nanmax(np.abs(a20)) < 20:
    a20 *= 1000.0                                                     # km -> m


def h_pgda(x, y):
    c = (np.asarray(x) - t20.c) / t20.a - 0.5
    r = (np.asarray(y) - t20.f) / t20.e - 0.5
    return bilinear(a20, r, c)


g_pds, g_pgda = float(h_pds(x0, y0)), float(h_pgda(x0, y0))
out["registration"] = {"pgda_crs": crs20[:120], "ground_h_pds40_m": g_pds, "ground_h_pgda20_m": g_pgda}
say(f"1. ground height at the point: PDS 40 m {g_pds:.1f} m, PGDA 20 m {g_pgda:.1f} m (engine holdout ground_h -628 m)")

# ---- 2. the NASA zero patch and its ring on the PDS grid
earth, me = read_avgvisib(r"E:\LUNA-OPS\data\reference_validation\AVGVISIB_85S_060M_201608_EARTH.IMG")
A = me["geotransform"]; X0, DX, Y0, DY = A[2], A[0], A[5], A[4]
row, col = int((y0 - Y0) // DY), int((x0 - X0) // DX)
W = 12
E = earth[row - W:row + W + 1, col - W:col + W + 1]


def flood(mask, r, c):
    seen = np.zeros_like(mask); st = [(r, c)]
    while st:
        i, j = st.pop()
        if seen[i, j] or not mask[i, j]:
            continue
        seen[i, j] = True
        st += [(i + a, j + b) for a in (-1, 0, 1) for b in (-1, 0, 1) if 0 <= i + a < mask.shape[0] and 0 <= j + b < mask.shape[1]]
    return seen


def dilate(m, k):
    o = m.copy()
    for _ in range(k):
        q = o.copy(); q[1:] |= o[:-1]; q[:-1] |= o[1:]; q[:, 1:] |= o[:, :-1]; q[:, :-1] |= o[:, 1:]; o = q
    return o


blob = flood(E == 0, W, W)
ring = dilate(blob, 4) & ~dilate(blob, 1)
wide = dilate(blob, 12) & ~dilate(blob, 4)


def cells_xy(mask):
    ii, jj = np.nonzero(mask)
    return X0 + (col - W + jj + 0.5) * DX, Y0 + (row - W + ii + 0.5) * DY


def stats(mask, name):
    xs, ys = cells_xy(mask)
    hp, hg = h_pds(xs, ys), h_pgda(xs, ys)
    # LOLA shots: every 40 m PDS pixel whose centre falls in one of the 60 m cells (3x3 sub-samples per cell)
    sub = np.linspace(-20, 20, 3)
    sx = (xs[:, None, None] + sub[None, :, None]).ravel(); sy = (ys[:, None, None] + sub[None, None, :]).ravel()
    r_, c_ = pds_rc(sx, sy)
    k = np.unique(np.c_[np.round(r_).astype(int), np.round(c_).astype(int)], axis=0)
    n = cnt40[k[:, 0], k[:, 1]].astype(int)
    d = {"cells_60m": int(mask.sum()), "nasa_earth_mean_pct": float(earth[row - W:row + W + 1, col - W:col + W + 1][mask].mean() * 100),
         "h_pds40_mean_m": float(np.nanmean(hp)), "h_pgda20_mean_m": float(np.nanmean(hg)),
         "pds_minus_pgda_mean_m": float(np.nanmean(hp - hg)), "pds_minus_pgda_rms_m": float(np.sqrt(np.nanmean((hp - hg) ** 2))),
         "pds40_pixels": int(n.size), "lola_shots_per_pixel_mean": float(n.mean()), "share_pixels_without_shots": float(np.mean(n == 0))}
    say(f"2. {name:28s} NASA Earth {d['nasa_earth_mean_pct']:5.1f} %; height PDS {d['h_pds40_mean_m']:8.1f} m, PGDA "
        f"{d['h_pgda20_mean_m']:8.1f} m, PDS-PGDA {d['pds_minus_pgda_mean_m']:+.1f} m (rms {d['pds_minus_pgda_rms_m']:.1f}); "
        f"LOLA shots/40 m pixel {d['lola_shots_per_pixel_mean']:.2f}, pixels with no shot {d['share_pixels_without_shots'] * 100:.0f} %")
    return d


out["patch"] = {"zero_patch": stats(blob, "zero patch (41 px)"), "ring_2_4px": stats(ring, "ring 2-4 px"),
                "ring_5_12px": stats(wide, "ring 5-12 px")}

# ---- 3. independent horizon
AZ = np.arange(0.0, 360.0, 0.5)
s = np.concatenate([np.arange(10.0, 3000.0, 10.0), 3000.0 * 1.01 ** np.arange(1, 400)])
s = s[s <= 150000.0]


def horizon(x, y, lat, lon, near_pgda):
    e = np.array([math.cos(math.radians(lon)), -math.sin(math.radians(lon))])
    n = np.array([math.sin(math.radians(lon)), math.cos(math.radians(lon))])     # local north points AWAY from the south pole
    msf = 2.0 / (1.0 + math.sin(abs(math.radians(lat))))                # map distance per ground distance
    dirs = np.sin(np.radians(AZ))[:, None] * e + np.cos(np.radians(AZ))[:, None] * n
    px = x + dirs[:, 0:1] * s[None, :] * msf
    py = y + dirs[:, 1:2] * s[None, :] * msf
    hh = h_pds(px, py)
    g = float(h_pds(x, y))
    if near_pgda:
        near = s[None, :].repeat(AZ.size, 0) <= 20000.0
        hh = np.where(near, h_pgda(px, py), hh)
        g = float(h_pgda(x, y))
    ang = np.degrees(np.arctan2(hh - g - s[None, :] ** 2 / (2 * R), s[None, :]))
    return np.nanmax(ang, axis=1), g


print("track ...", flush=True)
trk = track(os.environ.get("TRK_START", "2026-01-01T00:00:00Z"), float(os.environ.get("TRK_YEARS", "18.6")))   # default: the holdout track


def earth_vis(lat, lon, hz, g):
    site = Site(lat, lon, g, 0.0)
    t = topocentric(site, trk["earth"])
    top = t["el"] + np.degrees(np.arcsin(6371.0 / t["d"]))
    hv = np.interp(t["az"], AZ, hz, period=360.0)
    return float(np.mean(top > hv) * 100), t


nb = json.loads((EV / "V10_investigation" / "band_neighbours_corrected.json").read_text(encoding="utf-8"))
pts = [{"kind": "point", "lat": LAT, "lon": LON, "nasa_pct": 0.0, "engine_pct": 39.80}] + \
      [{"kind": r["kind"], "lat": r["lat"], "lon": r["lon"], "nasa_pct": r["nasa_pct"], "engine_pct": r["engine_pct"]} for r in nb["rows"]]
for p in pts:
    x, y = ps_xy(p["lat"], p["lon"])
    hz40, g40 = horizon(x, y, p["lat"], p["lon"], False)
    hz20, g20 = horizon(x, y, p["lat"], p["lon"], True)
    p["indep_pds40_pct"], t = earth_vis(p["lat"], p["lon"], hz40, g40)
    p["indep_pgda20_pct"], _ = earth_vis(p["lat"], p["lon"], hz20, g20)
    em = (t["az"] > 0)                                             # Earth azimuth band
    lo_, hi_ = float(np.percentile(t["az"], 1)), float(np.percentile(t["az"], 99))
    sel = (AZ >= lo_ - 1) & (AZ <= hi_ + 1)
    p["earth_az_range_deg"] = [lo_, hi_]
    p["earth_el_max_deg"] = float(t["el"].max())
    p["horizon_toward_earth_pds40_deg"] = [float(hz40[sel].min()), float(hz40[sel].max())]
    p["horizon_toward_earth_pgda20_deg"] = [float(hz20[sel].min()), float(hz20[sel].max())]
    say(f"4. {p['kind']:6s} {p['lat']:.5f} {p['lon']:.5f}: NASA {p['nasa_pct']:5.1f} | engine {p['engine_pct']:5.1f} | "
        f"independent PGDA20 {p['indep_pgda20_pct']:5.1f} | independent PDS40 {p['indep_pds40_pct']:5.1f}  "
        f"(horizon toward Earth PDS40 {hz40[sel].min():.1f}-{hz40[sel].max():.1f} deg, PGDA20 {hz20[sel].min():.1f}-{hz20[sel].max():.1f}; "
        f"Earth el max {p['earth_el_max_deg']:.1f})")
out["points"] = pts
for kind in ("blob", "beside"):
    rr = [p for p in pts if p["kind"] == kind]
    out[f"summary_{kind}"] = {k: float(np.mean([p[k] for p in rr])) for k in ("nasa_pct", "engine_pct", "indep_pgda20_pct", "indep_pds40_pct")}
    say(f"   mean {kind}: " + json.dumps({k: round(v, 1) for k, v in out[f'summary_{kind}'].items()}))
Path(sys.argv[1]).write_text(json.dumps(out, indent=1, default=float), encoding="utf-8")
Path(sys.argv[2]).write_text("\n".join(txt) + "\n", encoding="utf-8")
