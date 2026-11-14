"""V-10 failing point (85.3305 S, 285.2104 E): is NASA's 0 % a real terrain effect or a DEM artifact? Read only.

Tests (none changes data, criteria, the frozen holdout or the engine):
  A. coordinate mapping: the holdout point -> reference pixel via the LABEL geotransform (as the validation does), and
     the pixel centre back to lat/lon (round trip);
  B. geometry of the zero region in the NASA Earth map: connected component containing the point, size, principal
     direction (PCA), length, width; is it straight (linear) like a DEM track artifact?
  C. NASA's SUN map (same DEM, same horizon method) on the band vs beside it: a real trench deep enough to hide the
     Earth (> ~8.4 deg horizon toward azimuth 66-83 deg) also lowers Sun visibility; an Earth-only zero band does not
     have to, but a DEM artifact usually marks both maps along the same line;
  D. LOLA terrain (the engine's 20 m and 80 m PGDA products) along a transect across the band through the point and
     along the band: is there a trench/ridge whose depth/height could give a > 8.4 deg horizon toward the Earth?
  E. the band direction against LOLA ground-track direction near 85 S (tracks are close to meridians there).
Usage (from backend/): python <this> <out json> <out txt>
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import rowcol

sys.path.insert(0, str(Path.cwd()))
from validation.v09_v10_avgvisib import read_avgvisib  # noqa: E402

LAT, LON = -85.33050, 285.21040
R = 1737400.0
REF = Path(r"E:\LUNA-OPS\data\reference_validation")
out, txt = {"point": {"lat": LAT, "lon": LON}}, []


def say(s=""):
    print(s); txt.append(s)


def ps_xy(lat, lon):
    """South polar stereographic on the 1737.4 km sphere, true scale at the pole (PDS: x = 2R tan(pi/4 + lat/2) sin(lon),
    y = 2R tan(pi/4 + lat/2) cos(lon), lat negative)."""
    k = 2 * R * math.tan(math.pi / 4 + math.radians(lat) / 2)
    return k * math.sin(math.radians(lon)), k * math.cos(math.radians(lon))


def ps_latlon(x, y):
    rho = math.hypot(x, y)
    lat = 2 * math.atan(rho / (2 * R)) - math.pi / 2
    return math.degrees(lat), math.degrees(math.atan2(x, y)) % 360


earth, me = read_avgvisib(str(REF / "AVGVISIB_85S_060M_201608_EARTH.IMG"))
sun, ms = read_avgvisib(str(REF / "AVGVISIB_85S_060M_201608.IMG"))
A = me["geotransform"]                                    # affine order [dx, 0, x0, 0, dy, y0] (pixel corners)
gt = [A[2], A[0], 0.0, A[5], 0.0, A[4]]                    # re-ordered to GDAL [x0, dx, 0, y0, 0, dy]
x, y = ps_xy(LAT, LON)
col, row = int((x - gt[0]) // gt[1]), int((y - gt[3]) // gt[5])
xc, yc = gt[0] + (col + 0.5) * gt[1], gt[3] + (row + 0.5) * gt[5]
la2, lo2 = ps_latlon(xc, yc)
out["A_mapping"] = {"geotransform": gt, "xy_m": [x, y], "pixel_row_col": [row, col], "pixel_centre_latlon": [la2, lo2],
                    "offset_from_pixel_centre_m": [x - xc, y - yc], "earth_value": float(earth[row, col]),
                    "sun_value": float(sun[row, col]), "same_grid_sun_earth": ms["geotransform"] == gt}
say(f"A. point -> pixel (row {row}, col {col}); pixel centre {la2:.5f}, {lo2:.5f}; offset from centre "
    f"({x - xc:.1f}, {y - yc:.1f}) m; NASA Earth {earth[row, col] * 100:.2f} %, NASA Sun {sun[row, col] * 100:.2f} %")

# B. zero component
W = 120
r0, c0 = row - W, col - W
E = earth[r0:row + W + 1, c0:col + W + 1]; S = sun[r0:row + W + 1, c0:col + W + 1]
def component(mask, r, c):                                  # 8-connected flood fill (no SciPy installed)
    seen = np.zeros_like(mask); stack = [(r, c)] if mask[r, c] else []
    while stack:
        i, j = stack.pop()
        if seen[i, j]:
            continue
        seen[i, j] = True
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                a, b = i + di, j + dj
                if 0 <= a < mask.shape[0] and 0 <= b < mask.shape[1] and mask[a, b] and not seen[a, b]:
                    stack.append((a, b))
    return seen


def dilate(m, k):
    o = m.copy()
    for _ in range(k):
        q = o.copy(); q[1:] |= o[:-1]; q[:-1] |= o[1:]; q[:, 1:] |= o[:, :-1]; q[:, :-1] |= o[:, 1:]; o = q
    return o


comp = component(E == 0, W, W)
n = -1
rr, cc = np.nonzero(comp)
pts = np.c_[(cc - W) * gt[1], -(rr - W) * gt[5] * -1]     # metres east(+x) / north(+y) in map plane
pts = np.c_[(cc - W) * gt[1], (rr - W) * gt[5]]          # x right, y up (gt[5] is negative)
ctr = pts.mean(axis=0); u, s_, vt = np.linalg.svd(pts - ctr, full_matrices=False)
d = vt[0]; along = (pts - ctr) @ d; across = (pts - ctr) @ vt[1]
touches = bool(rr.min() == 0 or cc.min() == 0 or rr.max() == 2 * W or cc.max() == 2 * W)
map_az = math.degrees(math.atan2(d[0], d[1])) % 180      # map-plane direction, degrees clockwise from map +y
out["B_zero_component"] = {"pixels": int(comp.sum()), "length_m": float(np.ptp(along)), "width_rms_m": float(across.std()),
                           "elongation": float(s_[0] / max(s_[1], 1e-9)), "map_direction_deg_from_plus_y": map_az,
                           "touches_window_edge_+-7.2km": touches, "zero_pixels_in_window": int((E == 0).sum()),
                           "components_in_window": int(n)}
say(f"B. zero component through the point: {comp.sum()} px, length {np.ptp(along):.0f} m, rms width {across.std():.0f} m, "
    f"elongation {s_[0] / max(s_[1], 1e-9):.1f}, map direction {map_az:.1f} deg; touches the +-7.2 km window edge: {touches}")

# C. Sun on the band vs beside it (pixels 2-4 px off the band, not zero in Earth)
beside = dilate(comp, 4) & ~dilate(comp, 1) & (E > 0)       # 2-4 px (city-block) beside the band
out["C_sun_on_vs_beside_band"] = {"sun_mean_on_band": float(S[comp].mean()), "sun_mean_beside": float(S[beside].mean()),
                                  "earth_mean_beside": float(E[beside].mean()), "n_on": int(comp.sum()), "n_beside": int(beside.sum())}
say(f"C. NASA Sun on the zero-Earth band {S[comp].mean() * 100:.1f} % vs 2-4 px beside it {S[beside].mean() * 100:.1f} % "
    f"(NASA Earth beside it {E[beside].mean() * 100:.1f} %)")

# D. LOLA terrain across and along the band
def sample(path, xs, ys):
    with rasterio.open(path) as ds:
        vals = []
        for xx, yy in zip(xs, ys):
            r_, c_ = rowcol(ds.transform, xx, yy)
            win = ds.read(1, window=((r_, r_ + 1), (c_, c_ + 1)))
            vals.append(float(win[0, 0]))
        return np.array(vals), ds.crs.to_string()[:80], ds.res


prof = {}
nrm = np.array([-d[1], d[0]])
ctr_xy = np.array([xc, yc]) + ctr                            # band centroid in map metres
for name, p in (("20m", r"E:\LUNA-OPS\data\dem\pgda90_20m\LDEM_80S_20MPP_ADJ.TIF"),
                ("80m", r"E:\LUNA-OPS\data\dem\pgda90_80m\LDEM_80S_80MPP_ADJ.tiff")):
    t = np.arange(-1500, 1501, 20.0)
    # across the band through the POINT, and along the band through the point
    ax_, ay_ = x + t * nrm[0], y + t * nrm[1]
    bx_, by_ = x + t * d[0], y + t * d[1]
    h_across, crs, res = sample(p, ax_, ay_)
    h_along, _, _ = sample(p, bx_, by_)
    if np.nanmax(np.abs(h_across)) > 20000:                  # products in km or m: normalise to metres
        pass
    scale = 1000.0 if np.nanmax(np.abs(h_across)) < 20 else 1.0
    h_across, h_along = h_across * scale, h_along * scale
    i0 = len(t) // 2
    # local depression test: elevation at the point vs the mean at +-120..300 m on both sides
    side = (np.abs(t) >= 120) & (np.abs(t) <= 300)
    prof[name] = {"crs": crs, "res": res, "unit_scale_to_m": scale, "t_m": t.tolist(),
                  "across_m": h_across.tolist(), "along_m": h_along.tolist(),
                  "point_minus_sides_across_m": float(h_across[i0] - h_across[side].mean()),
                  "across_slope_deg_max_within_200m": float(np.degrees(np.arctan(np.max(np.abs(np.diff(h_across[np.abs(t) <= 200]))) / 20.0))),
                  "along_detrended_rms_m": float(np.std(h_along - np.polyval(np.polyfit(t, h_along, 2), t)))}
    say(f"D. LOLA {name}: point minus mean of the band's sides (120-300 m) across the band "
        f"{prof[name]['point_minus_sides_across_m']:+.1f} m; steepest 20 m step within 200 m "
        f"{prof[name]['across_slope_deg_max_within_200m']:.1f} deg; along-band detrended rms {prof[name]['along_detrended_rms_m']:.1f} m")
out["D_lola_profiles"] = prof

# E. band direction vs the local meridian (LOLA ground tracks run close to meridians at 85 S)
mer = np.array([-x, -y]) / math.hypot(x, y)                 # toward the pole in the map plane
ang = math.degrees(math.acos(abs(float(np.dot(d, mer)))))
out["E_band_vs_meridian_deg"] = ang
say(f"E. band direction vs the local meridian (track direction): {ang:.1f} deg")

Path(sys.argv[1]).write_text(json.dumps(out, indent=1, default=float), encoding="utf-8")
Path(sys.argv[2]).write_text("\n".join(txt) + "\n", encoding="utf-8")
