"""Check, on the terrain registered on this machine, that the adaptive DEM window loader (Phase 3 item 6) gives
bitwise the same horizon as the reference loader, and report the time and peak memory of each.

    cd backend
    python ../scripts/check_window_identity.py                         # PGDA 78 Site01 and a regional 80 m site
    python ../scripts/check_window_identity.py --lat -89.9 --lon 0 --reach 80m=50000 --reach 240m=100000

For each site the horizon is computed three times: with the reference loader (LUNAOPS_WINDOW_MODE=full, the
pre-Phase-3 code path), with the adaptive loader and the default initial reach, and with the adaptive loader
and the reaches given on the command line (if any). Every per-bin output (horizon, blocking distance and
product, blocking height, incomplete flags, sigma and its flags, sub-bin excess, stop step), the stopping
bound's h_max and the uncertainty statistics must be identical; the exit status is 1 otherwise. Read-only:
it changes no file, registry entry or cache (the horizon cache is bypassed).
"""
from __future__ import annotations

import argparse
import sys
import time
import tracemalloc
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

ARRAYS = ("h_deg", "block_dist_m", "incomplete", "sigma_deg", "near_field", "blocker_product", "cross_product",
          "discrepancy_unknown", "sigma_nonlinear", "sigma_lower_bound_deg", "sigma_block_m", "sigma_block_model_m",
          "block_h_m", "subbin_excess_deg", "subbin_unknown", "stop_step")
SITES = [(-89.463163, 222.510447, "PGDA 78 Site01"), (-89.9, 0.0, "regional (80 m)")]


def _run(lat, lon, obs, mode, reach):
    from lunaops import settings
    from lunaops.engine.horizon import compute_horizon
    settings.WINDOW_MODE = mode
    settings.DEM_INITIAL_REACH_M.clear()
    settings.DEM_INITIAL_REACH_M.update(reach)
    tracemalloc.start()
    t = time.perf_counter()
    hz = compute_horizon(lat, lon, obs)
    dt = time.perf_counter() - t
    peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    return hz, dt, peak


def _diff(a, b) -> list[str]:
    bad = [n for n in ARRAYS if not ((getattr(a, n) is None and getattr(b, n) is None)
                                      or np.array_equal(getattr(a, n), getattr(b, n), equal_nan=True))]
    if a.params["h_max_m"] != b.params["h_max_m"]:
        bad.append("h_max_m")
    if a.params["sigma"] != b.params["sigma"]:
        bad.append("sigma statistics")
    return bad


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lat", type=float)
    ap.add_argument("--lon", type=float)
    ap.add_argument("--obs", type=float, default=0.0)
    ap.add_argument("--reach", action="append", default=[], help="LEVEL_OR_PRODUCT=metres (repeatable)")
    a = ap.parse_args()
    from lunaops import settings
    default = dict(settings.DEM_INITIAL_REACH_M)
    custom = {k: float(v) for k, v in (r.split("=", 1) for r in a.reach)}
    if custom:
        settings.validate_initial_reach(custom)
    sites = [(a.lat, a.lon, "requested")] if a.lat is not None else SITES
    ok = True
    for lat, lon, name in sites:
        ref, t0, m0 = _run(lat, lon, a.obs, "full", default)
        print(f"{name} ({lat}, {lon}): reference loader {t0:.1f} s, peak {m0 / 1e6:.0f} MB")
        runs = [("adaptive, default reach", default)] + ([("adaptive, --reach", custom)] if custom else [])
        for label, reach in runs:
            hz, t, m = _run(lat, lon, a.obs, "adaptive", reach)
            bad = _diff(ref, hz)
            ps = hz.params["performance_settings"]
            print(f"  {label} {reach}: {t:.1f} s, peak {m / 1e6:.0f} MB ({100 * (1 - m / m0):.0f}% lower), "
                  f"{len(ps['expansions'])} expansions -> {'IDENTICAL' if not bad else 'DIFFERENT: ' + ', '.join(bad)}")
            ok = ok and not bad
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
