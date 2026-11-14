"""Compare cross-product (fine - coarse) height statistics by region and by sampling method.

    cd backend
    python ../scripts/compare_cross_product_statistics.py            # PGDA 78 Site01 vs PGDA 90 80 m

Explains why two measurements of "Site01 5 m vs PGDA 90 80 m" differ. Both use the same lattice: the
finer product's pixel centres every coarse/fine pixels (here 16, i.e. 80 m), over the 5 m window loaded
around the site. They differ in

  region:  "annulus" = 4-8 km from the 5 m footprint centre (the 2026-11 audit, 23,572 points);
           "window"  = intersection of the two windows (CROSS_PRODUCT_SAMPLING, 40,000 points);
  method:  "nearest" = value of the 80 m pixel containing the point (rasterio sample; the audit);
           "bilinear" = bilinear between 80 m pixel centres, any nodata neighbour excluded (approved).

On these grids every lattice point sits at the same offset o from its nearest 80 m pixel centre
((+2.5, +37.5) m for Site01), so nearest-neighbour sampling adds a systematic slope term
grad(h) . o. The script prints all four combinations, the offset, the slope statistics and the
nearest-neighbour statistics predicted from the bilinear ones plus grad(h) . o, and checks that the
production function (engine.horizon.cross_product_discrepancy) equals "window / bilinear".
Read-only: it changes no file, registry entry or cache.
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))


def stats(d: np.ndarray) -> str:
    d = d[np.isfinite(d)]
    if d.size == 0:
        return "n=0"
    return (f"n={d.size:6d} mean={d.mean():+8.4f} std={d.std():7.4f} rms={math.sqrt(np.mean(d * d)):7.4f} "
            f"median={np.median(d):+8.4f} p5={np.percentile(d, 5):+8.3f} p95={np.percentile(d, 95):+8.3f}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lat", type=float, default=-89.463163)
    ap.add_argument("--lon", type=float, default=222.510447)
    ap.add_argument("--fine-level", default="5m")
    ap.add_argument("--coarse-level", default="80m")
    ap.add_argument("--centre", type=float, nargs=2, default=(-11000.0, -12000.0),
                    help="annulus centre x y (m); default: the Site01 5 m footprint centre used by the audit")
    ap.add_argument("--annulus", type=float, nargs=2, default=(4000.0, 8000.0))
    a = ap.parse_args()

    import rasterio

    from lunaops.engine.dem import load_pyramid, resolve_dem_path
    from lunaops.engine.horizon import bilinear_many, cross_product_discrepancy

    pyr = load_pyramid(a.lat, a.lon)
    fine = next(w for w in pyr if w.level == a.fine_level)
    coarse = next(w for w in pyr if w.level == a.coarse_level)
    stride = max(1, int(round(coarse.pixel_m / fine.pixel_m)))
    rows = np.arange(0, fine.data.shape[0], stride)
    cols = np.arange(0, fine.data.shape[1], stride)
    R, C = np.meshgrid(rows, cols, indexing="ij")
    xs = fine.x0 + C.ravel() * fine.dx
    ys = fine.y0 + R.ravel() * fine.dy
    hf = fine.data[R.ravel(), C.ravel()].astype(float)

    # coarse values: bilinear on the loaded window (approved) and nearest pixel read from the file (audit)
    hb = bilinear_many(coarse, xs, ys)
    with rasterio.open(resolve_dem_path(coarse.meta["path"])) as src:
        hn = np.array([v[0] for v in src.sample(list(zip(xs, ys)))], dtype=float)
        nod = src.nodata
    if nod is not None and np.isfinite(nod):
        hn[hn == nod] = np.nan
    # nearest 80 m pixel centre of each point, and the offset point - centre
    cc = np.floor((xs - (coarse.x0 - 0.5 * coarse.dx)) / coarse.dx)
    rr = np.floor((ys - (coarse.y0 - 0.5 * coarse.dy)) / coarse.dy)
    ox = xs - (coarse.x0 + cc * coarse.dx)
    oy = ys - (coarse.y0 + rr * coarse.dy)
    # fine-DEM gradient (per metre) at the lattice points
    gy_img, gx_img = np.gradient(fine.data.astype(float), fine.dy, fine.dx)
    gx = gx_img[R.ravel(), C.ravel()]
    gy = gy_img[R.ravel(), C.ravel()]

    d = np.hypot(xs - a.centre[0], ys - a.centre[1])
    regions = {"window (approved)": np.ones(xs.size, bool),
               f"annulus {a.annulus[0]:g}-{a.annulus[1]:g} m (audit)": (d >= a.annulus[0]) & (d <= a.annulus[1])}
    print(f"site {a.lat}, {a.lon}; fine {fine.meta.get('key')} ({fine.data.shape}), coarse {coarse.meta.get('key')}")
    print(f"lattice: every {stride} fine pixels, {xs.size} points; fine nodata at {int((~np.isfinite(hf)).sum())}, "
          f"bilinear nodata at {int((~np.isfinite(hb)).sum())}, nearest nodata at {int((~np.isfinite(hn)).sum())}")
    uo = np.unique(np.round(np.c_[ox, oy], 3), axis=0)
    print(f"offsets point - nearest {coarse.level} centre (m): {uo[:5].tolist()}{' ...' if len(uo) > 5 else ''}")
    for name, m in regions.items():
        print(f"\n{name}:")
        print(f"  bilinear  {stats(hf[m] - hb[m])}")
        print(f"  nearest   {stats(hf[m] - hn[m])}")
        pred = (hf[m] - hb[m]) + gx[m] * ox[m] + gy[m] * oy[m]
        print(f"  predicted nearest = bilinear + grad(h).o   {stats(pred)}")
        print(f"  slope: mean dh/dx={np.nanmean(gx[m]):+.4f} dh/dy={np.nanmean(gy[m]):+.4f}; "
              f"std dh/dx={np.nanstd(gx[m]):.4f} dh/dy={np.nanstd(gy[m]):.4f}; "
              f"RMS slope={math.degrees(math.atan(math.sqrt(np.nanmean(gx[m]**2 + gy[m]**2)))):.2f} deg")
    st = cross_product_discrepancy(fine, coarse)
    from lunaops import settings
    cfg = settings.CROSS_PRODUCT_SAMPLING
    thin = max(1, int(math.ceil(math.sqrt(rows.size * cols.size / float(cfg["max_points"])))))
    rows_th = rows[::thin]
    cols_th = cols[::thin]
    R_th, C_th = np.meshgrid(rows_th, cols_th, indexing="ij")
    xs_th = fine.x0 + C_th.ravel() * fine.dx
    ys_th = fine.y0 + R_th.ravel() * fine.dy
    hf_th = fine.data[R_th.ravel(), C_th.ravel()].astype(float)
    hb_th = bilinear_many(coarse, xs_th, ys_th)
    ref = hf_th - hb_th
    ref = ref[np.isfinite(ref)]
    same = st["status"] == "measured" and st["n"] == ref.size and abs(st["rms_m"] - math.sqrt(np.mean(ref ** 2))) < 1e-9
    print(f"\nproduction cross_product_discrepancy (thin={thin}): n={st['n']} mean={st.get('mean_m')} std={st.get('std_m')} "
          f"rms={st.get('rms_m')} -> equals 'window / bilinear': {same}")
    return 0 if same else 1


if __name__ == "__main__":
    sys.exit(main())
