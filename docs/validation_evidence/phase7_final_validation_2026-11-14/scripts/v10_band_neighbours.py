"""V-10 failing point: the UNCHANGED engine on 8 pixels of NASA's zero-Earth blob and on 8 pixels 2-4 px beside it, against
NASA's Earth map at the same pixels (same 18.6-year track and observer height 0 m as the holdout). Read only: does the
engine disagree with NASA only on the blob (NASA's map is locally discontinuous) or around it as well (an engine
problem in this area)? Pixel centres are converted with the round-trip-checked polar stereographic formulas of
v10_band_investigation.py (0.3 m from the label grid).
Usage (from backend/): python <this> <out json>
"""
import json
import math
import os
import sys
from pathlib import Path

os.environ["LUNAOPS_WINDOW_MODE"] = "full"
sys.path.insert(0, str(Path.cwd()))
import numpy as np  # noqa: E402

from validation.v09_v10_avgvisib import evaluate_point, read_avgvisib, track  # noqa: E402

LAT, LON, R = -85.33050, 285.21040, 1737400.0
REF = Path(r"E:\LUNA-OPS\data\reference_validation")


def ps_xy(lat, lon):
    k = 2 * R * math.tan(math.pi / 4 + math.radians(lat) / 2)
    return k * math.sin(math.radians(lon)), k * math.cos(math.radians(lon))


def ps_latlon(x, y):
    return math.degrees(2 * math.atan(math.hypot(x, y) / (2 * R)) - math.pi / 2), math.degrees(math.atan2(x, y)) % 360


earth, me = read_avgvisib(str(REF / "AVGVISIB_85S_060M_201608_EARTH.IMG"))
A = me["geotransform"]; x0, dx, y0, dy = A[2], A[0], A[5], A[4]
x, y = ps_xy(LAT, LON); col, row = int((x - x0) // dx), int((y - y0) // dy)
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
beside = dilate(blob, 4) & ~dilate(blob, 1) & (E > 0)
rng = np.random.default_rng(20261114)
pick = lambda m, k: [tuple(p) for p in np.argwhere(m)[rng.choice(int(m.sum()), size=min(k, int(m.sum())), replace=False)]]
cells = [("blob", p) for p in pick(blob, 8)] + [("beside", p) for p in pick(beside, 8)]
trk = track("2026-01-01T00:00:00Z", 18.6)
rows = []
for kind, (i, j) in cells:
    r_, c_ = row - W + i, col - W + j
    la, lo = ps_latlon(x0 + (c_ + 0.5) * dx, y0 + (r_ + 0.5) * dy)
    res = evaluate_point(la, lo, "earth", trk, 0.0)
    ref = float(earth[r_, c_]) * 100
    rows.append({"kind": kind, "pixel": [int(r_), int(c_)], "lat": la, "lon": lo, "nasa_pct": ref, "engine_pct": res.get("computed"),
                 "outcome": res.get("outcome")})
    print(json.dumps(rows[-1]), flush=True)
summ = {}
for kind in ("blob", "beside"):
    d = [r["engine_pct"] - r["nasa_pct"] for r in rows if r["kind"] == kind and r["engine_pct"] is not None]
    summ[kind] = {"n": len(d), "mean_diff_pp": float(np.mean(d)), "rmse_pp": float(np.sqrt(np.mean(np.square(d)))),
                  "engine_mean": float(np.mean([r["engine_pct"] for r in rows if r["kind"] == kind])),
                  "nasa_mean": float(np.mean([r["nasa_pct"] for r in rows if r["kind"] == kind]))}
print(json.dumps(summ, indent=1))
Path(sys.argv[1]).write_text(json.dumps({"rows": rows, "summary": summ}, indent=1), encoding="utf-8")
