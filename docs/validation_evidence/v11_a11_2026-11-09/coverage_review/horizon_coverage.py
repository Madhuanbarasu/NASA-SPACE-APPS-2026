"""A11: engine horizon completeness at the formal V-11 points (coverage diagnostic; computes no sunlight).

    LUNAOPS_DEM_FALLBACK_DIRS=<folder holding pgda90_80m/LDEM_80S_80MPP_ADJ.tiff> \
        python -I horizon_coverage.py <formal_points.json> <out.json>

The registry and data/ are not touched: the registered 80 m file (SHA-256 verified against the registry by the
caller) is found through the engine's documented fallback-folder lookup. For every point the engine's own
compute_horizon gives the incomplete bins; for each incomplete bin this records where the ray broke (the engine's
step distance at stop_step) and why (left the registered data, or reached the end of the last window), and an
upper bound on the ray length that would close the bin with the engine's exact stopping bound,
    d_req = smallest d with e_max(d) < h_k,  e_max from h_max and the site radius as in the engine,
using the bin's current (lower-bound) horizon h_k: the true horizon is at least h_k, so less reach may suffice;
terrain higher than this h_max beyond the data would need more. The farthest point each such ray must reach gives
the terrain extent required.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "backend"))
from lunaops import settings  # noqa: E402
from lunaops.engine.dem import load_pyramid, site_height_window  # noqa: E402
from lunaops.engine.frames import enu_basis  # noqa: E402
from lunaops.engine.horizon import build_steps, compute_horizon  # noqa: E402

pts = json.load(open(sys.argv[1]))["points"]
R0 = settings.R_MOON_M
HALF = 304_000.0          # registered 80 m product: +-304 km (registry transform)
WIN = settings.DEM_WINDOW_HALF_M["80m"]


def ray_point(u, n, e, a, d):
    t = math.cos(a) * n + math.sin(a) * e
    return math.cos(d / R0) * u + math.sin(d / R0) * t


def lat_of(p):
    return math.degrees(math.asin(max(-1.0, min(1.0, p[2]))))


def xy_of(p):          # as the kernel: X = 2 R py / (1 - pz), Y = 2 R px / (1 - pz)
    den = 1.0 - p[2]
    return 2 * R0 * p[1] / den, 2 * R0 * p[0] / den


rows = []
for i, q in enumerate(pts):
    pyr = load_pyramid(q["lat"], q["lon"])
    hz = compute_horizon(q["lat"], q["lon"], 0.0, pyramid=pyr)
    ground, wi = site_height_window(pyr, q["lat"], q["lon"])
    d_arr, _ = build_steps(pyr, 0.5 * pyr[wi].pixel_m)
    inc = np.asarray(hz.incomplete, bool)
    h_max = hz.params["h_max_m"]
    r_s, r_p = R0 + ground, R0 + h_max
    dstar = math.acos(min(1.0, r_p / r_s))
    e_star = math.atan2(r_p * math.cos(dstar) - r_s, r_p * math.sin(dstar)) if dstar > 0 else math.pi / 2
    e, n, u = enu_basis(q["lat"], q["lon"])
    nb = inc.size
    row = {"lat": q["lat"], "lon": q["lon"], "ground_m": ground, "h_max_m": h_max,
           "incomplete_bins": int(inc.sum()), "levels": [lv.get("key") for lv in hz.levels]}
    if inc.any():
        ks = np.nonzero(inc)[0]
        brk = d_arr[np.minimum(hz.stop_step[ks], d_arr.size - 1)]
        why_edge = brk < d_arr[-1] - 1.0
        need, need_lat, need_r = [], [], []
        for k in ks:
            hk = math.radians(hz.h_deg[k])
            # smallest d beyond which e_max(d) < h_k (e_max is flat at e_star up to d*, then decreasing)
            if e_star < hk:
                dq = 0.0
            else:
                lo, hi = max(dstar, 0.0), math.pi / 2
                for _ in range(80):
                    mid = 0.5 * (lo + hi)
                    if math.atan2(r_p * math.cos(mid) - r_s, r_p * math.sin(mid)) < hk:
                        hi = mid
                    else:
                        lo = mid
                dq = hi * R0
            need.append(dq)
            pnt = ray_point(u, n, e, 2 * math.pi * k / nb, dq)
            need_lat.append(lat_of(pnt))
            x, y = xy_of(pnt)
            need_r.append(math.hypot(x, y))
        need = np.array(need)
        row.update({
            "broke_at_data_edge_bins": int(why_edge.sum()), "broke_at_window_end_bins": int((~why_edge).sum()),
            "break_km_min": float(brk.min() / 1e3), "break_km_max": float(brk.max() / 1e3),
            "required_reach_km_max": float(need.max() / 1e3),
            "required_reach_beyond_250km_bins": int((need > WIN).sum()),
            "required_northernmost_lat_deg": float(max(need_lat)),
            "required_max_map_radius_km": float(max(need_r) / 1e3),
            "required_beyond_80m_square": bool(any(max(abs(c) for c in xy_of(ray_point(u, n, e, 2 * math.pi * k / nb, dq)))
                                                   > HALF for k, dq in zip(ks, need))),
        })
    rows.append(row)
    print(f"{i + 1:3d}/{len(pts)} lat {q['lat']:8.3f} incomplete {row['incomplete_bins']:4d}", flush=True)
json.dump(rows, open(sys.argv[2], "w"), indent=1)
