"""Per-bin breakdown of the horizon uncertainty at a site, on the terrain registered on this machine.

    cd backend
    python ../scripts/diagnose_horizon_sigma.py                     # PGDA 78 Site01, observer 0 m
    python ../scripts/diagnose_horizon_sigma.py --lat -89.46 --lon 222.5 --obs 0 --near-m 2.5 --top 15

For the bins with the largest sigma (optionally only those whose blocker is within --near-m metres) it
prints the site and blocker product identities, cross-product flag, pointwise and model (regularized)
error-map sigmas, correlation rho(d), cross-product allowance, the gradients g_b and g_s, the two
squared terms of the propagation and the resulting sigma - both with the model in use and with pointwise
error-map values (the pre-correction Phase 2 behaviour), so a large near-field sigma can be traced to its
source. Read-only: it changes no file, registry entry or cache.
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lat", type=float, default=-89.463163)
    ap.add_argument("--lon", type=float, default=222.510447)
    ap.add_argument("--obs", type=float, default=0.0, help="observer height above ground (m)")
    ap.add_argument("--near-m", type=float, default=None, help="only bins whose blocker is within this distance")
    ap.add_argument("--top", type=int, default=15)
    a = ap.parse_args()

    from lunaops import settings
    from lunaops.engine.frames import enu_basis
    from lunaops.engine.horizon import compute_horizon, correlation, elevation_gradients, propagate_sigma

    hz = compute_horizon(a.lat, a.lon, a.obs)
    note = hz.params["sigma"]
    print(f"site {a.lat}, {a.lon}  observer {a.obs} m  ground {hz.ground_h_m:.3f} m")
    print(f"site product: {hz.params['site_product']}")
    print(f"error maps: {note.get('error_maps')}  status: {note.get('status')}")
    if hz.sigma_deg is None:
        print("no sigma computed (no error maps for the products used)")
        return 0
    print(f"site sigma pointwise {note.get('site_sigma_m')} m, model {note.get('site_sigma_model_m')} m "
          f"({note.get('variance_model')})")
    print(f"L_corr {note['L_corr_m']} m ({note['L_corr_status']}); nonlinear above {note['sigma_nonlinear_deg']} deg")
    for k, v in (note.get("cross_product_discrepancy_allowance") or {}).items():
        print(f"pair {k}: {v}")
    e, n, u = enu_basis(a.lat, a.lon)
    nb = hz.nbins
    az = 2 * np.pi * np.arange(nb) / nb
    t = np.outer(np.cos(az), n) + np.outer(np.sin(az), e)
    dl = hz.block_dist_m / settings.R_MOON_M
    p = np.outer(np.cos(dl), u) + np.sin(dl)[:, None] * t
    rs = settings.R_MOON_M + hz.ground_h_m + a.obs
    ok = (hz.blocker_product >= 0) & np.isfinite(hz.block_h_m)
    gb = np.full(nb, np.nan)
    gs = np.full(nb, np.nan)
    gb[ok], gs[ok], _ = elevation_gradients(u, p[ok], hz.block_h_m[ok], rs)
    site_i = hz.params["site_product"]["index"]
    rho = np.where(hz.cross_product, 0.0, correlation(hz.block_dist_m))
    allow = np.zeros(nb)
    for k, v in (note.get("cross_product_discrepancy_allowance") or {}).items():
        blk = k.split(" | ")[1]
        j = next(i for i, lv in enumerate(hz.levels) if lv["key"] == blk)
        allow[hz.blocker_product == j] = v["allowance_m"] if v["status"] == "measured" else np.nan
    ss_pt, ss_mod = note.get("site_sigma_m") or np.nan, note.get("site_sigma_model_m") or np.nan
    sig_pt = np.degrees(propagate_sigma(gb, gs, hz.sigma_block_m, ss_pt, rho, np.nan_to_num(allow)))
    sel = ok & np.isfinite(hz.sigma_deg)
    if a.near_m is not None:
        sel &= hz.block_dist_m <= a.near_m
    idx = np.where(sel)[0]
    print(f"\nbins considered: {idx.size}; max sigma (model) {np.nanmax(hz.sigma_deg[idx]):.4f} deg; "
          f"max sigma (pointwise) {np.nanmax(sig_pt[idx]):.4f} deg; near_field bins {int(hz.near_field.sum())}")
    order = idx[np.argsort(-sig_pt[idx])][: a.top]
    hdr = ("bin", "az_deg", "d_m", "e_deg", "blocker", "cross", "sb_pt", "ss_pt", "sb_mod", "ss_mod", "rho",
           "allow", "g_b", "g_s", "T1_pt", "T2_pt", "sig_pt", "sig_model")
    print(" ".join(f"{h:>9}" for h in hdr))
    for k in order:
        sb, sm = hz.sigma_block_m[k], hz.sigma_block_model_m[k]
        t1 = (gb[k] * sb + rho[k] * gs[k] * ss_pt) ** 2
        t2 = (1 - rho[k] ** 2) * (gs[k] * ss_pt) ** 2
        row = (k, math.degrees(az[k]), hz.block_dist_m[k], hz.h_deg[k], hz.levels[hz.blocker_product[k]]["level"]
               + ("*" if hz.blocker_product[k] == site_i else ""), bool(hz.cross_product[k]), sb, ss_pt, sm, ss_mod,
               rho[k], allow[k], gb[k], gs[k], t1, t2, sig_pt[k], hz.sigma_deg[k])
        print(" ".join(f"{v:>9}" if isinstance(v, (str, bool, np.bool_)) else
                       (f"{v:>9d}" if isinstance(v, (int, np.integer)) else f"{v:>9.4g}") for v in row))
    print("\n* = blocker from the site product. T1 = (g_b s_b + rho g_s s_s)^2, T2 = (1 - rho^2) g_s^2 s_s^2 "
          "(rad^2, pointwise values). sig_model is what results report.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
