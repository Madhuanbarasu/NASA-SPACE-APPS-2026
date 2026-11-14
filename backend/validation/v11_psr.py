"""V-11: points inside PGDA permanently-shadowed regions must get zero sunlight over 18.6 years.

    python -m validation.v11_psr --lpsr LPSR_80S_20MPP_ADJ.TIF --points 200 --out v11.json

Uses the registered LOLA DEMs for horizons. The Sun's body-fixed direction is computed hourly over one
18.6-year cycle (site parallax under 0.001 deg is neglected) and a point is dark if El + rho stays below the
minimum horizon across each hour's azimuth sweep, a conservative test that cannot miss a sunlit hour.
Criterion (unchanged): at least 99% of the formal sample has zero sunlight.

Formal sample: `--points` (200) interior PSR points inside the map's documented coverage, 80-90 deg S (PGDA 90
product page: "LAT gives the latitude limit"; the 20 m products "cover 80 - 90 deg South"). The square raster
also holds values out to 75.9 deg S in its corners; those are outside the documented coverage and never sampled.

Scoring. A point is scored only if its horizon is complete: every one of its azimuth bins was closed by the
engine's exact stopping bound before the ray met nodata or left all registered terrain. Then it is "dark" (zero
sunlight) or "lit". A point with any incomplete bin, a non-finite horizon value, or no terrain horizon at all is
"inconclusive": it is not scored and is never counted as dark. With n formal points:
    passed        if dark / n >= 0.99                 (holds even if every inconclusive point were lit)
    failed        if (dark + inconclusive) / n < 0.99 (fails even if every inconclusive point were dark)
    inconclusive  otherwise.
Completeness follows the engine's stopping bound, which takes terrain beyond the loaded windows to be no higher
than their highest sample (h_max). Higher unseen terrain could only raise the true horizon, so it can turn a
lit verdict into a dark one, never the reverse: a dark verdict on a complete horizon stands either way.

Reference map (PGDA 90 LPSR_80S_20MPP_ADJ.TIF, checked 2026-11-09): float32, nodata NaN, full-resolution
values exactly 0 (not permanently shadowed) and 1 (permanently shadowed); 30400 x 30400 pixels of 20 m in
south polar stereographic (sphere 1737.4 km). Its overview layers are *resampled* (fractional and negative
values), so the map is always read at full resolution here, never through overviews.

Interior points: the map is reduced to cells of CELL_PX x CELL_PX full-resolution pixels, a cell being
permanent shadow only if every one of its pixels is 1 (NaN counts as not shadow) and all four of its corners lie
at or south of COVERAGE_LAT_DEG (the cell is wholly inside the documented coverage; in polar stereographic a
cell's northernmost point is a corner). Cells whose whole (2 * MARGIN_CELLS + 1)^2 neighbourhood is such shadow
are interior: at least MARGIN_CELLS cells (320 m with the defaults) from any non-shadow pixel, from the 80 deg S
coverage limit and from the raster border (not wrapped). Points are drawn from them at random with a fixed seed
and placed at the cell centres.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lunaops.engine.ephem import Site, sample_target  # noqa: E402
from lunaops.engine.frames import enu_basis  # noqa: E402
from lunaops.engine.horizon import compute_horizon  # noqa: E402
from lunaops.engine.timeutil import parse_utc  # noqa: E402

PASS_SHARE = 0.99
CELL_PX = 8              # cell size in full-resolution pixels (8 x 20 m = 160 m), as the original 1/8 reduction
MARGIN_CELLS = 2         # interior margin in cells, as the original 5 x 5 erosion
YEARS = 18.6
COVERAGE_LAT_DEG = -80.0  # documented coverage of the LPSR_80S product: 80-90 deg S (PGDA 90 product page)
COVERAGE_NOTE = ('PGDA 90 product page: "LAT gives the latitude limit (80S, ...)"; the 20 m products "cover '
                 '80 - 90 deg South"')
OUTCOMES = ("dark", "lit", "inconclusive")


# ------------------------------------------------------------------ reference map
def check_lpsr(path: str, rows_per_read: int = 512) -> dict:
    """Read the whole map at full resolution and confirm its encoding: every value is 0, 1 or NaN."""
    import rasterio
    from rasterio.windows import Window

    counts = {"shadow_1": 0, "lit_0": 0, "nan": 0, "other": 0}
    with rasterio.open(path) as src:
        meta = {"width": src.width, "height": src.height, "dtype": src.dtypes[0], "nodata": src.nodata,
                "crs": src.crs.to_proj4() if src.crs else None, "transform": list(src.transform)[:6],
                "overviews": src.overviews(1)}
        for r0 in range(0, src.height, rows_per_read):
            a = src.read(1, window=Window(0, r0, src.width, min(rows_per_read, src.height - r0)))
            nan = np.isnan(a) if np.issubdtype(a.dtype, np.floating) else np.zeros(a.shape, bool)
            if src.nodata is not None and not (isinstance(src.nodata, float) and math.isnan(src.nodata)):
                nan |= a == src.nodata
            v = a[~nan]
            counts["nan"] += int(nan.sum())
            counts["shadow_1"] += int((v == 1).sum())
            counts["lit_0"] += int((v == 0).sum())
            counts["other"] += int(((v != 0) & (v != 1)).sum())
    if counts["other"]:
        raise ValueError(f"{path}: {counts['other']} pixels are neither 0, 1 nor nodata; not a binary shadow map")
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return {**meta, **counts, "sha256": h.hexdigest(), "bytes": Path(path).stat().st_size}


def shadow_cells(path: str, cell: int = CELL_PX) -> tuple[np.ndarray, object]:
    """Boolean grid of cells (cell x cell full-resolution pixels) that are entirely permanent shadow, read at full
    resolution in strips (never through overviews), and the affine transform of that grid."""
    import rasterio
    from rasterio.windows import Window

    with rasterio.open(path) as src:
        nr, nc = src.height // cell, src.width // cell
        out = np.zeros((nr, nc), dtype=bool)
        step = max(1, 4096 // (cell * max(1, src.width // 4096)))      # cell-rows per read, bounded memory
        nodata = src.nodata
        for r in range(0, nr, step):
            k = min(step, nr - r)
            a = src.read(1, window=Window(0, r * cell, nc * cell, k * cell))
            ok = a == 1
            if nodata is not None and not (isinstance(nodata, float) and math.isnan(nodata)):
                ok &= a != nodata
            out[r:r + k] = ok.reshape(k, cell, nc, cell).all(axis=(1, 3))
        t = src.transform @ src.transform.scale(cell, cell)
    return out, t


def erode(mask: np.ndarray, margin: int = MARGIN_CELLS) -> np.ndarray:
    """Cells whose whole (2 margin + 1)^2 neighbourhood is True; outside the raster counts as False."""
    p = np.pad(mask, margin, constant_values=False)
    core = np.ones_like(mask)
    h, w = mask.shape
    for dy in range(2 * margin + 1):
        for dx in range(2 * margin + 1):
            core &= p[dy:dy + h, dx:dx + w]
    return core


def in_coverage(cells: np.ndarray, t, tr, lat_limit: float = COVERAGE_LAT_DEG) -> np.ndarray:
    """Of the True cells, those whose four corners all lie at or south of lat_limit (wholly inside coverage)."""
    rows, cols = np.nonzero(cells)
    ok = np.ones(rows.size, dtype=bool)
    for dr, dc in ((0, 0), (0, 1), (1, 0), (1, 1)):
        x = t.c + (cols + dc) * t.a + (rows + dr) * t.b
        y = t.f + (cols + dc) * t.d + (rows + dr) * t.e
        _lon, lat = tr.transform(x, y)
        ok &= np.asarray(lat) <= lat_limit
    out = np.zeros_like(cells)
    out[rows[ok], cols[ok]] = True
    return out


def interior_points(path: str, n: int, seed: int = 1, cell: int = CELL_PX, margin: int = MARGIN_CELLS,
                    lat_limit: float = COVERAGE_LAT_DEG):
    """Up to n (lat, lon east 0-360) points at the centres of interior shadow cells inside the documented
    coverage (south of lat_limit), plus the sampled x/y (m)."""
    import rasterio
    from pyproj import CRS, Transformer

    cells, t = shadow_cells(path, cell)
    with rasterio.open(path) as src:
        crs = CRS.from_wkt(src.crs.to_wkt())
    tr = Transformer.from_crs(crs, crs.geodetic_crs, always_xy=True)
    covered = in_coverage(cells, t, tr, lat_limit)
    core = erode(covered, margin)
    rows, cols = np.nonzero(core)
    rng = np.random.default_rng(seed)
    pick = rng.choice(rows.size, size=min(n, rows.size), replace=False) if rows.size else np.array([], int)
    pts = []
    for i in np.sort(pick):
        x, y = t @ (cols[i] + 0.5, rows[i] + 0.5)
        lon, lat = tr.transform(x, y)
        pts.append({"lat": float(lat), "lon": float(lon % 360), "x_m": float(x), "y_m": float(y)})
    return pts, {"cells_shadow": int(cells.sum()), "cells_shadow_in_coverage": int(covered.sum()),
                 "cells_interior": int(core.sum()),
                 "cells_interior_ignoring_coverage": int(erode(cells, margin).sum()),
                 "cell_m": float(abs(t.a)), "margin_cells": margin,
                 "coverage": {"lat_limit_deg": lat_limit, "source": COVERAGE_NOTE,
                              "rule": "a cell is used only if all four corners lie at or south of the limit; "
                                      "the interior margin then also applies from the limit"}}


# ------------------------------------------------------------------ hourly illumination test
def hour_ranges(az: np.ndarray, nbins: int) -> tuple[np.ndarray, np.ndarray]:
    """Inclusive horizon-bin index ranges [a, b] swept between consecutive azimuths (exactly as the original loop:
    the shorter arc, floor/ceil of az / bin width), as indices into the horizon repeated twice."""
    step = 360.0 / nbins
    lo = np.minimum(az[:-1], az[1:])
    hi = np.maximum(az[:-1], az[1:])
    wrap = hi - lo > 180
    lo2 = np.where(wrap, hi, lo)
    hi2 = np.where(wrap, lo + 360, hi)
    a = np.floor(lo2 / step).astype(np.int64)
    b = np.ceil(hi2 / step).astype(np.int64)
    return a, b


def range_min(h: np.ndarray, a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """min(h[i % n] for i in a..b) for every pair, exactly, with a sparse table over h repeated twice
    (requires 0 <= a and b - a < n, which hour_ranges guarantees for arcs up to 180 deg)."""
    n = h.size
    a = np.asarray(a, dtype=np.int64)
    b = np.asarray(b, dtype=np.int64)
    shift = (a // n) * n                        # move each range so that 0 <= a < n (same cells, "% h.size")
    a, b = a - shift, b - shift
    hh = np.concatenate([h, h, h])
    table = [hh]
    k = 1
    while (1 << k) <= hh.size:
        prev = table[-1]
        half = 1 << (k - 1)
        table.append(np.minimum(prev[:-half], prev[half:]))
        k += 1
    length = b - a + 1
    lev = np.floor(np.log2(length)).astype(np.int64)
    out = np.empty(a.size)
    for L in np.unique(lev):
        sel = lev == L
        t = table[L]
        out[sel] = np.minimum(t[a[sel]], t[b[sel] - (1 << L) + 1])
    return out


def first_lit_hour(el: np.ndarray, az: np.ndarray, h: np.ndarray, rho_max: float) -> tuple[int, float]:
    """Index of the first hour i in which max(el[i], el[i+1]) + rho_max reaches the minimum horizon over the
    azimuth swept from az[i] to az[i+1] (-1 if never), and the smallest clearance min_i(hmin_i - top_i) in deg
    (negative or zero means lit). Vectorised equivalent of the original per-hour loop."""
    h = np.where(np.isfinite(h), h, -90.0)
    a, b = hour_ranges(az, h.size)
    hmin = range_min(h, a, b)
    top = np.maximum(el[:-1], el[1:]) + rho_max
    lit = top >= hmin
    first = int(np.argmax(lit)) if lit.any() else -1
    return first, float(np.min(hmin - top))


def first_lit_hour_loop(el, az, h, rho_max) -> int:
    """The original per-hour loop (kept as the reference for the vectorised version)."""
    h = np.where(np.isfinite(h), h, -90.0)
    step = 360.0 / h.size
    for i in range(el.size - 1):
        lo, hi = sorted((az[i], az[i + 1]))
        if hi - lo > 180:
            lo, hi = hi, lo + 360
        idx = np.arange(int(math.floor(lo / step)), int(math.ceil(hi / step)) + 1) % h.size
        if max(el[i], el[i + 1]) + rho_max >= h[idx].min():
            return i
    return -1


# ------------------------------------------------------------------ run
def sun_track(start: str, years: float = YEARS):
    ets = parse_utc(start) + 3600.0 * np.arange(int(years * 365.25 * 24))
    s = sample_target(Site(-90.0, 0.0, 0.0, 0.0), "sun", ets)
    return ets, s.unit, float(s.rho.max())


def bin_runs(mask: np.ndarray) -> list[list[float]]:
    """Contiguous runs of True bins as [start, end] azimuths in deg (bin edges), merged across 0/360."""
    m = np.asarray(mask, dtype=bool)
    n = m.size
    if not m.any():
        return []
    step = 360.0 / n
    if m.all():
        return [[0.0, 360.0]]
    s = int(np.argmin(m))                    # start the scan at a False bin so no run is split at the seam
    runs, k = [], 0
    while k < n:
        i = (s + k) % n
        if m[i]:
            j = k
            while j < n and m[(s + j) % n]:
                j += 1
            a = i * step
            runs.append([round(a, 1), round(a + (j - k) * step, 1)])      # end may exceed 360: wraps the seam
            k = j
        else:
            k += 1
    return runs


def evaluate_point(lat: float, lon: float, unit: np.ndarray, rho_max: float, horizon_fn=None) -> dict:
    """Outcome "dark" or "lit" when the horizon is complete; otherwise "inconclusive" (never scored)."""
    from lunaops.engine.dem import TerrainError
    try:
        hz = (horizon_fn or compute_horizon)(lat, lon, 0.0)
    except TerrainError as exc:
        return {"outcome": "inconclusive", "zero_sunlight": None,
                "reason": f"no terrain horizon: {exc}"[:300]}
    h = np.asarray(hz.h_deg, dtype=float)
    inc = np.asarray(hz.incomplete, dtype=bool) | ~np.isfinite(h)
    e, n, u = enu_basis(lat, lon)
    el = np.degrees(np.arcsin(np.clip(unit @ u, -1.0, 1.0)))
    az = np.degrees(np.arctan2(unit @ e, unit @ n)) % 360
    first, clear = first_lit_hour(el, az, h, rho_max)
    levels = [lv.get("key") or lv.get("level") for lv in (getattr(hz, "levels", None) or []) if isinstance(lv, dict)]
    rec = {"incomplete_bins": int(inc.sum()), "terrain_levels": levels,
           "h_max_m": (getattr(hz, "params", None) or {}).get("h_max_m")}
    if inc.any():
        return {**rec, "outcome": "inconclusive", "zero_sunlight": None,
                "reason": f"{int(inc.sum())} of {inc.size} horizon bins incomplete: terrain coverage ends before "
                          "the horizon is proven",
                "incomplete_azimuths_deg": bin_runs(inc),
                # what the incomplete (lower-bound) horizon gives; recorded for review, never scored
                "unscored_lower_bound_first_lit_hour": first, "unscored_lower_bound_min_clearance_deg": clear}
    return {**rec, "outcome": "dark" if first < 0 else "lit", "zero_sunlight": first < 0,
            "first_lit_hour": first, "min_clearance_deg": clear}


def score(results: list[dict], prerequisites: tuple[bool, str] = (False, "not checked")) -> tuple[str, dict]:
    """Status from the per-point outcomes: passed only if the worst case (every inconclusive point lit) meets the
    criterion, failed only if the best case (every inconclusive point dark) misses it, otherwise inconclusive.
    prerequisites: (ok, reasons) of the shared terrain acceptance gate (validation/terrain_gate.py); unmet gives
    "not run" (preliminary) whatever the counts, which are still reported."""
    n = len(results)
    c = {k: sum(1 for r in results if r["outcome"] == k) for k in OUTCOMES}
    worst = c["dark"] / n
    best = (c["dark"] + c["inconclusive"]) / n
    status = "passed" if worst >= PASS_SHARE else ("failed" if best < PASS_SHARE else "inconclusive")
    ok, why = prerequisites
    counts = {"n": n, **c, "dark_share_worst_case": worst, "dark_share_best_case": best,
              "status_if_final": status, "prerequisites_met": bool(ok), "prerequisites_detail": why}
    return (status if ok else "not run"), counts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lpsr", required=True)
    ap.add_argument("--points", type=int, default=200)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--start", default="2026-01-01T00:00:00Z")
    ap.add_argument("--out", default="v11.json")
    a = ap.parse_args()
    enc = check_lpsr(a.lpsr)
    pts, sampling = interior_points(a.lpsr, a.points, a.seed)
    if len(pts) < a.points:
        sys.exit(f"V-11 needs a formal sample of {a.points} points, but only {len(pts)} interior PSR cells lie inside "
                 f"the documented coverage (south of {COVERAGE_LAT_DEG} deg); no result written")
    ets, unit, rho_max = sun_track(a.start)
    results = []
    for p in pts:
        results.append({**p, **evaluate_point(p["lat"], p["lon"], unit, rho_max)})
    from validation import terrain_gate
    gate = terrain_gate.evaluate()
    status, counts = score(results, (gate["ok"], "; ".join(gate["reasons"])))
    from lunaops.engine.dem import products_digest
    detail = (f"{counts['dark']}/{counts['n']} formal points dark with a complete horizon "
              f"({100 * counts['dark_share_worst_case']:.1f}%; criterion >= {100 * PASS_SHARE:.0f}%), "
              f"{counts['lit']} lit, {counts['inconclusive']} inconclusive (incomplete terrain coverage: not scored, "
              f"never counted as dark)")
    if not gate["ok"]:
        detail += f"; PRELIMINARY (terrain gate not met: {'; '.join(gate['reasons'])}), not a V-11 result"
    out = {"tests": {"V-11": {"status": status, "detail": detail}},
           "criterion": f"share of sampled interior PSR points with zero sunlight >= {PASS_SHARE}",
           "scoring": {"rule": "passed if dark/n >= 0.99; failed if (dark + inconclusive)/n < 0.99; otherwise "
                               "inconclusive. Only points with a complete horizon are scored.", **counts},
           "lpsr": {"path": a.lpsr, **enc}, "sampling": {**sampling, "seed": a.seed, "requested": a.points},
           "sun_track": {"start_utc": a.start, "hours": int(ets.size), "years": YEARS, "rho_max_deg": rho_max},
           "terrain_products": products_digest(), "points": results}
    from validation.common import run_meta
    out["meta"] = {**run_meta("v11_psr"), "terrain_gate": gate}
    Path(a.out).write_text(json.dumps(out, indent=2))
    print(json.dumps(out["tests"], indent=2))


if __name__ == "__main__":
    main()
