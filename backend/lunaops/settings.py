"""Paths, physical constants and engine parameters (blueprint Sections 4-8).

Every parameter that affects a result is recorded in each result's
provenance record, so a run can be reproduced exactly.
"""
from __future__ import annotations

import math
import os

import numpy as np
from pathlib import Path

# ---------------------------------------------------------------- paths
REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.environ.get("LUNAOPS_DATA_DIR", REPO_ROOT / "data")).resolve()
# Production NAIF kernels and demo/test kernels live in separate folders, each with its own
# lock.json, so neither can overwrite or mix with the other. LUNAOPS_KERNEL_SET selects the one
# loaded by this process: "production" (default) or "demo" (set by `start.py --demo`).
PRODUCTION_KERNEL_DIR = DATA_DIR / "kernels"
DEMO_KERNEL_DIR = DATA_DIR / "kernels_demo"
KERNEL_SET = os.environ.get("LUNAOPS_KERNEL_SET", "production").strip().lower()
if KERNEL_SET not in ("production", "demo"):
    raise ValueError(f"LUNAOPS_KERNEL_SET must be 'production' or 'demo', not {KERNEL_SET!r}")
KERNEL_DIR = DEMO_KERNEL_DIR if KERNEL_SET == "demo" else PRODUCTION_KERNEL_DIR
# Terrain registry folder. `start.py --demo` points LUNAOPS_DEM_DIR at data/dem_demo so synthetic demo
# terrain gets its own registry and never mixes with (or is blocked by) the real LOLA registry in data/dem.
DEM_DIR = Path(os.environ.get("LUNAOPS_DEM_DIR", DATA_DIR / "dem")).resolve()
BASE_DEM_DIR = (REPO_ROOT / "data" / "dem").resolve()
# Extra folders searched for a registered DEM path that is not under DEM_DIR, in order. Empty by default:
# a file is never picked up from another data folder unless that folder is listed here explicitly (C08).
DEM_FALLBACK_DIRS = [Path(p).resolve() for p in os.environ.get("LUNAOPS_DEM_FALLBACK_DIRS", "").split(os.pathsep)
                     if p.strip()]
CATALOG_DIR = DATA_DIR / "catalog"
CACHE_DIR = DATA_DIR / "cache"
VALIDATION_REPORT = REPO_ROOT / "backend" / "validation" / "report.json"
FRONTEND_DIST = REPO_ROOT / "frontend" / "dist"



def ensure_dirs() -> None:
    """Create the data folders (kernels, terrain registry, catalogue, cache). Called by the API at startup, by
    start.py and the acquire CLI, and by the writers that need a folder; importing settings has no side
    effects (Phase 3 item 8)."""
    for d in (PRODUCTION_KERNEL_DIR, DEMO_KERNEL_DIR, DEM_DIR, CATALOG_DIR, CACHE_DIR):
        d.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------- physical constants
R_MOON_M = 1_737_400.0          # LOLA reference sphere (Section 7.2)
R_SUN_KM = 695_700.0            # IAU 2015 nominal solar radius (Section 8.2)
R_EARTH_KM = 6_378.137          # Earth equatorial radius (pre-Phase-3 circular disk; kept for reference only)
# Phase 3: Earth as an oblate spheroid, IERS Conventions 2010 (IERS TN 36, Table 1.1):
# a = 6378136.6 m, 1/f = 298.25642 -> b = a (1 - f) = 6356751.9 m.
EARTH_RADII_KM = (6378.1366, 6378.1366, 6378.1366 * (1.0 - 1.0 / 298.25642))
# Phase 4: Earth's spin axis is the CIP of date (engine.earth_orientation), replacing the frozen J2000 pole.
EARTH_POLE_MODEL = "CIP-IAU2006-precession-IAU2000B-nutation"
EARTH_POLE_LABEL = ("pole of date (Celestial Intermediate Pole): IAU 2006 precession (Fukushima-Williams angles, "
                    "IERS Conventions 2010) with IAU 2000B nutation (77 luni-solar terms), as SOFA/ERFA pn06 + "
                    "nut00b, about 1 mas; polar motion and free-core nutation neglected; SPICE J2000 taken as "
                    "the ICRF/GCRS axes; deviation from IAU_EARTH (pck00011) measured per epoch")
EARTH_LIMB_TOL_DEG = 1e-6       # circular-cap shortcut only if delta_max and E_g are within this
EARTH_F_TOL = 5e-6              # ... and the area-fraction bound E_f is below half a unit in the 5th decimal
EARTH_SOLVER = {"bracket": 64, "tol": 1e-14, "maxiter": 60}
AU_KM = 149_597_870.7           # IAU 2012 astronomical unit

# ------------------------------------------------------ engine parameters
HORIZON_BINS = 3600             # 0.1 deg azimuth bins (Section 8.4)


def validate_subbin_rays(value) -> int:
    """SUBBIN_RAYS (Phase 3 item 7): rays per azimuth bin interval [az_k, az_k+1), counting the node ray; the
    extra rays are at az_k + j * bin / M, j = 1 .. M - 1. An integer 1 <= M <= 16 (1 disables sub-bin rays).
    Anything else (0, 17, 2.5, '4x', True) is rejected."""
    if isinstance(value, bool):
        raise ValueError(f"SUBBIN_RAYS must be an integer 1..16, not {value!r}")
    if isinstance(value, str):
        v = value.strip()
        if not v.isdigit():
            raise ValueError(f"SUBBIN_RAYS must be an integer 1..16, not {value!r}")
        value = int(v)
    if not isinstance(value, (int, np.integer)) or not 1 <= int(value) <= 16:
        raise ValueError(f"SUBBIN_RAYS must be an integer 1..16, not {value!r}")
    return int(value)


SUBBIN_RAYS = validate_subbin_rays(os.environ.get("LUNAOPS_SUBBIN_RAYS", "4"))   # checked at startup

# ---------------------------------------------- horizon uncertainty (Phase 2)
# Height errors of one DEM product are modelled as correlated with rho(d) = exp(-d^2 / (2 L^2)).
# L_corr = 250 m is an UNCALIBRATED ASSUMPTION: no published source gives a correlation length for
# LOLA DEM height errors. Horizon uncertainty and "uncertain" flags depend on it, and every output
# that uses it carries the label from engine.horizon.l_corr_label(). Calibration is planned (Phase 4).
HORIZON_CORR_MODEL = "gaussian"
HORIZON_CORR_LENGTH_M = 250.0
L_CORR_STATUS = "uncalibrated assumption"
SIGMA_NONLINEAR_DEG = 5.0       # first-order propagation is not trusted above this; such bins force "uncertain"
HORIZON_NEAR_FIELD_PIXELS = 2.0  # blockers within this many site-product pixels are "near field" (local slope)
UNCERTAIN_SIGMA_K = 1.0         # a window/gap is uncertain when its clearance is within k sigma of the horizon
# Variance-field regularization (Phase 2 correction). The correlated-error model above describes an error
# field that is continuous at scale L_corr, so its standard deviation must also vary on scales >= L_corr:
# within the site product sigma~^2 = G_L * sigma^2 (error-map variance smoothed with a Gaussian of std
# L_corr, NaN-aware, mean-preserving), evaluated on a coarse grid of cell max(pixel, cell_fraction_of_L * L).
# Pointwise (nearest-pixel) error-map values are kept for blockers from other products (rho = 0 there).
VARIANCE_REGULARIZATION = {
    "kernel": "gaussian, std = L_corr",
    "truncation_L": 3.0,
    "cell_fraction_of_L": 0.2,
    "applies_to": "site product: within-product correlated terms and the site sigma",
}
# Cross-product discrepancy allowance: RMS of (finer - coarser) heights where the site product and a
# blocker product overlap. A conservative allowance (it includes measured bias), not a calibrated 1-sigma.
CROSS_PRODUCT_SAMPLING = {
    "min_pairs": 100,
    "max_points": 40_000,
    "stride": "coarse_pixel / fine_pixel (>= 1)",
    "region": "intersection of the site-product window and the blocker-product window",
    "interpolation": "bilinear; any nodata neighbour excluded",
    "statistic": "mean, std, rms of fine - coarse",
}
# DEM pyramid windows: half-width (m) of the window loaded per level.
# Levels are used fine to coarse by distance band (Section 6.2 step 4).
DEM_WINDOW_HALF_M = {
    "5m": 8_000.0,
    "10m": 15_000.0,
    "20m": 40_000.0,
    "80m": 250_000.0,
    "240m": 600_000.0,
}
# Phase 3 item 6 (performance only; output-invariant, see tests/test_phase3_windows.py):
# LUNAOPS_WINDOW_MODE=full is the reference loader (whole nominal windows, as before); "adaptive" (default)
# reads windows into one buffer and loads products listed below only up to an initial reach, growing them on
# demand. Keys are a level or a product_id (product_id first); values must lie in (0, nominal half-width].
# The nominal windows above define the physics (coverage, distance bands, steps) and are not overridable.
WINDOW_MODE = os.environ.get("LUNAOPS_WINDOW_MODE", "adaptive").strip().lower()
if WINDOW_MODE not in ("adaptive", "full"):
    raise ValueError(f"LUNAOPS_WINDOW_MODE must be 'adaptive' or 'full', not {WINDOW_MODE!r}")
DEM_INITIAL_REACH_M = {
    "80m": 100_000.0,
    "240m": 200_000.0,
}


def validate_initial_reach(reach: dict | None = None) -> None:
    """Level keys must name a level with a nominal window and lie in (0, nominal half-width]; product_id keys
    are checked against their product's level when it is loaded (engine.dem.initial_reach_m)."""
    for k, v in (DEM_INITIAL_REACH_M if reach is None else reach).items():
        if not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(float(v)):
            raise ValueError(f"DEM_INITIAL_REACH_M[{k!r}] must be a number of metres, not {v!r}")
        if k in DEM_WINDOW_HALF_M and not 0.0 < float(v) <= DEM_WINDOW_HALF_M[k]:
            raise ValueError(f"DEM_INITIAL_REACH_M[{k!r}] must be in (0, {DEM_WINDOW_HALF_M[k]:g}] m, not {v!r}")
        if k not in DEM_WINDOW_HALF_M and float(v) <= 0.0:
            raise ValueError(f"DEM_INITIAL_REACH_M[{k!r}] must be positive, not {v!r}")


validate_initial_reach()


def performance_settings() -> dict:
    """Settings that change only how terrain is loaded, never an output (excluded from cache keys)."""
    return {"window_mode": WINDOW_MODE, "initial_reach_m": dict(DEM_INITIAL_REACH_M)}

EVENT_STEP_CAP_S = 600.0        # 10-minute cap (Section 8.6)
EVENT_STEP_FLOOR_S = 1.0        # 1 s floor
EVENT_TOL_S = 1.0               # bisection tolerance
CURVATURE_INFLATION = 1.5       # inflation of grid curvature estimates
BRIEF_WINDOW_S = 600.0          # windows under 10 min are flagged brief
ABCORR = "CN+S"                 # converged light time + stellar aberration

DEFAULT_SERIES_STEP_S = 900.0   # display series step (15 min)
MAX_WINDOW_DAYS = 400.0         # guard against runaway requests

SYNTHETIC_TERRAIN_ALLOWED = os.environ.get("LUNAOPS_ALLOW_SYNTHETIC") == "1"
