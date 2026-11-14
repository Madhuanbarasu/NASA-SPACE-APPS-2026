"""Terrain horizon (blueprint Section 8.4; tests V-06, V-07).

For each 0.1 deg azimuth bin a ray marches outward along the great circle
p(d) = cos(d/R) u + sin(d/R) t_alpha, samples the finest DEM product covering
each point (bilinear; any nodata neighbour -> nodata; finer products first,
then coarser ones), and keeps the largest exact 3D elevation angle. Curvature
is included by construction.

Stopping is exact and conservative. With r_p = R0 + h_max (h_max is the highest
value in every loaded window, which also bounds every bilinear sample) and
r_s the observer radius, the highest elevation any terrain at arc angle delta
can reach is

    e_max(delta) = atan2(r_p cos(delta) - r_s, r_p sin(delta)),

which decreases for delta > delta* = acos(min(1, r_p / r_s)) and increases
before it. A ray stops at delta when e_max(max(delta, delta*)) < its current
maximum: no farther sample can beat it. A ray that meets nodata or leaves all
coverage first marks its bin incomplete; its stored value is then a lower
bound. Sampling between ray steps can still miss sub-step peaks (V-07).

Uncertainty (sigma, Phase 2). For each bin the blocking sample's product is the window index the
kernel reports (never a level, since several products can share one). With the observer at
P_s = (R0 + h_s + H) u and the blocker at P_b = (R0 + h_b) p, v = P_b - P_s and sin e = v.u/|v|,
the exact first-order sensitivities of the horizon elevation to the two height errors are

    g_b = de/dh_b = (p.u - sin e (v^.p)) / (|v| cos e),     g_s = de/dh_s = -cos e / |v|,

and Var(e) = g_b^2 s_b^2 + g_s^2 s_s^2 + 2 g_b g_s C + g_b^2 s_x^2, where s_b and s_s come from the
error maps of the blocker's and the site's products. Within one product C = rho(d) s_b s_s with
rho(d) = exp(-d^2 / (2 L^2)); L = 250 m is an UNCALIBRATED ASSUMPTION (see l_corr_label). Between
products C = 0 (conservative: shared LOLA tracks make the true correlation positive) and s_x is the
cross-product discrepancy allowance, the RMS of finer-minus-coarser heights where the two products
overlap around the site: a conservative allowance that includes measured bias, not a calibrated
random 1-sigma. With too few overlapping samples the allowance is unknown, never zero: those bins get
no sigma and force "uncertain" flags. Bins above SIGMA_NONLINEAR_DEG are outside the range where
first-order propagation is trusted and also force "uncertain". None of this changes the horizon
elevations themselves.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .. import ALGORITHM_VERSION, settings
from ..fingerprint import code_fingerprint
from .dem import (LevelWindow, error_map_for, load_pyramid, products_digest, read_registry,
                  expand_into_new_buffer, resolve_dem_path, site_height_window, window_hmax)
from .frames import enu_basis

from numba import njit, prange   # a pinned dependency (requirements.txt)

STOP_EPS = 1e-12  # floating-point guard only; the bound itself is exact


NOT_LOADED = math.inf   # _sample: inside the nominal window but outside the loaded block (never a height)


@njit(cache=True)
def _sample(flat, off, nr, nc, rof, cof, nrl, ncl, x0, y0, dx, dy, w, x, y):
    """Bilinear height of window w at (x, y). The nominal-window test and the interpolation weights use the
    nominal origin exactly as before; the four pixels are read from the loaded block at offset (rof, cof).
    NaN: outside the nominal window or a nodata neighbour. NOT_LOADED: needs a block not yet loaded."""
    fc = (x - x0[w]) / dx[w]
    fr = (y - y0[w]) / dy[w]
    c0 = int(math.floor(fc))
    r0 = int(math.floor(fr))
    if c0 < 0 or r0 < 0 or c0 + 1 >= nc[w] or r0 + 1 >= nr[w]:
        return np.nan
    lc = c0 - cof[w]
    lr = r0 - rof[w]
    if lc < 0 or lr < 0 or lc + 1 >= ncl[w] or lr + 1 >= nrl[w]:
        return NOT_LOADED
    base = off[w] + lr * ncl[w] + lc
    a = flat[base]
    b = flat[base + 1]
    c = flat[base + ncl[w]]
    d = flat[base + ncl[w] + 1]
    if not (np.isfinite(a) and np.isfinite(b) and np.isfinite(c) and np.isfinite(d)):
        return np.nan
    tc = fc - c0
    tr = fr - r0
    return (a * (1.0 - tc) + b * tc) * (1.0 - tr) + (c * (1.0 - tc) + d * tc) * tr


@njit(cache=True, parallel=True)
def _horizon_kernel(nbins, ux, uy, uz, nx_, ny_, nz_, ex, ey, ez, r_site,
                    d_arr, start_w, cosd, sind,
                    flat, off, nr, nc, rof, cof, nrl, ncl, x0, y0, dx, dy, nwin,
                    R0, r_p, delta_star, e_at_star, use_stop, mask, az_off=0.0):
    """Rays for the bins where mask is True (other entries are left unset). stop_step: the step index at which
    each ray stopped (bound), broke (no data) or ended; need: the window whose not-yet-loaded block a ray
    reached (-1: none), in which case that ray's other outputs are to be recomputed after loading it."""
    H = np.empty(nbins)
    D = np.empty(nbins)
    W = np.full(nbins, -1, dtype=np.int64)   # window (product) that supplied the blocking sample
    HB = np.full(nbins, np.nan)               # height of the blocking sample (m above the sphere)
    inc = np.zeros(nbins, dtype=np.bool_)
    stop_step = np.full(nbins, -1, dtype=np.int64)
    need = np.full(nbins, -1, dtype=np.int64)
    sx = r_site * ux
    sy = r_site * uy
    sz = r_site * uz
    nsteps = d_arr.shape[0]
    for k in prange(nbins):
        if not mask[k]:
            continue
        a = 2.0 * math.pi * k / nbins + az_off       # az_off = 0: node rays, bitwise as before
        ca = math.cos(a)
        sa = math.sin(a)
        tx = ca * nx_ + sa * ex
        ty = ca * ny_ + sa * ey
        tz = ca * nz_ + sa * ez
        best = -1.0
        best_d = 0.0
        best_w = -1
        best_h = np.nan
        complete = False
        incomplete = False
        last = nsteps
        for j in range(nsteps):
            if use_stop and j > 0:
                delta = d_arr[j] / R0
                if delta <= delta_star:
                    bound = e_at_star
                else:
                    bound = math.atan2(r_p * cosd[j] - r_site, r_p * sind[j])
                if bound < math.asin(best) - 1e-12:
                    complete = True
                    last = j
                    break
            px = cosd[j] * ux + sind[j] * tx
            py = cosd[j] * uy + sind[j] * ty
            pz = cosd[j] * uz + sind[j] * tz
            den = 1.0 - pz
            X = 2.0 * R0 * py / den
            Y = 2.0 * R0 * px / den
            h = np.nan
            w = start_w[j]
            while w < nwin:
                h = _sample(flat, off, nr, nc, rof, cof, nrl, ncl, x0, y0, dx, dy, w, X, Y)
                if h == NOT_LOADED or np.isfinite(h):
                    break
                w += 1
            if h == NOT_LOADED:
                need[k] = w
                last = j
                break
            if not np.isfinite(h):
                incomplete = True
                last = j
                break
            rr = R0 + h
            vx = rr * px - sx
            vy = rr * py - sy
            vz = rr * pz - sz
            vn = math.sqrt(vx * vx + vy * vy + vz * vz)
            s = (vx * ux + vy * uy + vz * uz) / vn
            if s > best:
                best = s
                best_d = d_arr[j]
                best_w = w
                best_h = h
        if not complete:
            incomplete = True
        H[k] = math.degrees(math.asin(best))
        D[k] = best_d
        W[k] = best_w
        HB[k] = best_h
        inc[k] = incomplete
        stop_step[k] = last
    return H, D, inc, W, HB, stop_step, need


def l_corr_label(L: float | None = None) -> str:
    """The label every output carries wherever horizon sigma or an uncertain flag appears."""
    L = settings.HORIZON_CORR_LENGTH_M if L is None else L
    return (f"L_corr = {L:g} m is an uncalibrated assumption (no published source); "
            "horizon uncertainty and uncertain flags depend on it")


CROSS_PRODUCT_KIND = "conservative allowance (includes measured bias); not a calibrated random 1-sigma"


def uncertainty_settings() -> dict:
    """Every setting that changes horizon sigma, its flags or the near-field classification."""
    return {"correlation_model": settings.HORIZON_CORR_MODEL, "L_corr_m": settings.HORIZON_CORR_LENGTH_M,
            "L_corr_status": settings.L_CORR_STATUS, "sigma_nonlinear_deg": settings.SIGMA_NONLINEAR_DEG,
            "near_field_pixels": settings.HORIZON_NEAR_FIELD_PIXELS, "uncertain_sigma_k": settings.UNCERTAIN_SIGMA_K,
            "cross_product_sampling": dict(settings.CROSS_PRODUCT_SAMPLING),
            "variance_regularization": dict(settings.VARIANCE_REGULARIZATION)}


# per-bin arrays added in Phase 2 (all optional so older call sites keep working)
EXTRA_ARRAYS = ("near_field", "blocker_product", "cross_product", "discrepancy_unknown", "sigma_nonlinear",
                "sigma_lower_bound_deg", "sigma_block_m", "sigma_block_model_m", "block_h_m",
                "subbin_excess_deg", "subbin_unknown")


@dataclass
class Horizon:
    lat: float
    lon: float
    obs_h_m: float
    ground_h_m: float
    site_level: str
    h_deg: np.ndarray          # horizon elevation per bin (deg); lower bound where incomplete
    block_dist_m: np.ndarray
    incomplete: np.ndarray     # bool
    sigma_deg: np.ndarray | None  # horizon uncertainty per bin (deg); NaN where unknown
    levels: list[dict]
    key: str
    params: dict
    near_field: np.ndarray | None = None           # bool: blocker within HORIZON_NEAR_FIELD_PIXELS site pixels
    blocker_product: np.ndarray | None = None      # int: index into levels of the blocking product (-1: none)
    cross_product: np.ndarray | None = None        # bool: blocker from a different product than the site
    discrepancy_unknown: np.ndarray | None = None  # bool: cross-product allowance could not be measured
    sigma_nonlinear: np.ndarray | None = None      # bool: sigma above SIGMA_NONLINEAR_DEG
    sigma_lower_bound_deg: np.ndarray | None = None  # error-map terms only, where sigma is unknown
    sigma_block_m: np.ndarray | None = None        # error-map value at the blocking sample (m), pointwise
    sigma_block_model_m: np.ndarray | None = None  # blocker sigma used in the model (regularized in the site product)
    block_h_m: np.ndarray | None = None            # height of the blocking sample above the sphere (m)
    subbin_excess_deg: np.ndarray | None = None    # Phase 3: largest sub-ray rise above the node interpolation (deg)
    subbin_unknown: np.ndarray | None = None       # Phase 3: a sub-ray or a node of the bin is incomplete
    stop_step: np.ndarray | None = None            # diagnostic: step index where each node ray stopped or broke

    @property
    def nbins(self) -> int:
        return self.h_deg.size

    def flag_arrays(self) -> dict:
        return {"near_field": self.near_field, "sigma_nonlinear": self.sigma_nonlinear,
                "discrepancy_unknown": self.discrepancy_unknown, "subbin_excess_deg": self.subbin_excess_deg,
                "subbin_unknown": self.subbin_unknown}

    def to_json(self, compact: bool = False) -> dict:
        d = {
            "lat": self.lat, "lon": self.lon, "obs_h_m": self.obs_h_m,
            "ground_h_m": round(self.ground_h_m, 3), "site_level": self.site_level,
            "nbins": self.nbins, "bin_deg": 360.0 / self.nbins,
            "h_deg": [round(float(v), 5) for v in self.h_deg],
            "incomplete": [bool(v) for v in self.incomplete],
            "incomplete_share": float(np.mean(self.incomplete)),
            "max_deg": float(np.max(self.h_deg)), "min_deg": float(np.min(self.h_deg)),
            "levels": self.levels, "key": self.key, "params": self.params,
        }
        if not compact:
            d["block_dist_m"] = [round(float(v), 1) for v in self.block_dist_m]
        d["sigma_deg"] = _opt_list(self.sigma_deg, 5)
        for name in ("near_field", "cross_product", "discrepancy_unknown", "sigma_nonlinear"):
            arr = getattr(self, name)
            d[name] = None if arr is None else [bool(v) for v in arr]
        d["near_field_share"] = None if self.near_field is None else float(np.mean(self.near_field))
        d["blocker_product"] = None if self.blocker_product is None else [int(v) for v in self.blocker_product]
        d["subbin_excess_deg"] = _opt_list(self.subbin_excess_deg, 5)
        d["subbin_unknown"] = None if self.subbin_unknown is None else [bool(v) for v in self.subbin_unknown]
        if not compact:
            d["sigma_lower_bound_deg"] = _opt_list(self.sigma_lower_bound_deg, 5)
            d["sigma_block_m"] = _opt_list(self.sigma_block_m, 4)
            d["sigma_block_model_m"] = _opt_list(self.sigma_block_model_m, 4)
            d["block_h_m"] = _opt_list(self.block_h_m, 3)
        return d


def _opt_list(a, nd):
    return None if a is None else [None if not np.isfinite(v) else round(float(v), nd) for v in a]


def horizon_key(lat: float, lon: float, obs_h_m: float, nbins: int) -> str:
    payload = json.dumps({"lat": round(lat, 7), "lon": round(lon, 7), "obs": round(obs_h_m, 4),
                          "nbins": nbins, "products": products_digest(), "alg": ALGORITHM_VERSION,
                          "code": code_fingerprint(), "windows": settings.DEM_WINDOW_HALF_M,
                          "uncertainty": uncertainty_settings(), "subbin": subbin_settings()}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:24]


def subbin_settings() -> dict:
    """Sub-bin ray settings (hashed into horizon keys); M is validated here as well as at startup."""
    m = settings.validate_subbin_rays(settings.SUBBIN_RAYS)
    return {"rays_per_bin": m, "definition": SUBBIN_DEFINITION}


SUBBIN_DEFINITION = ("excess_k = max_j (H(az_k + j bin/M) - [H_k + (j/M)(H_k+1 - H_k)])+, j = 1..M-1: how far "
                     "terrain between horizon nodes rises above the linear interpolation the disk model uses; "
                     "informational (never enters sigma or the uncertain flags)")


def subbin_excess(H: np.ndarray, inc: np.ndarray, H_sub: list, inc_sub: list) -> tuple[np.ndarray, np.ndarray]:
    """Per bin k (interval [az_k, az_k+1)): the largest rise of the M - 1 sub-rays above the linear interpolation
    between the node horizons, clipped at 0, and whether it is unknown (a sub-ray or either node incomplete:
    then the value is only what the incomplete rays saw). M = 1 (no sub-rays): 0 everywhere, known where the
    nodes are complete. The last bin wraps to node 0."""
    M = len(H_sub) + 1
    nxt = np.roll(H, -1)
    unknown = inc | np.roll(inc, -1)
    ex = np.zeros(H.size)
    for j, (hj, ij) in enumerate(zip(H_sub, inc_sub), start=1):
        lin = H + (j / M) * (nxt - H)
        ex = np.maximum(ex, hj - lin)
        unknown = unknown | ij
    return ex, unknown


def build_steps(pyr: list[LevelWindow], d_start: float) -> tuple[np.ndarray, np.ndarray]:
    """Distances (half-pixel steps per band) and, per step, the first window allowed to serve it."""
    ds, sw = [], []
    d = d_start
    for i, w in enumerate(pyr):
        step = 0.5 * w.pixel_m
        while d <= w.band_m:
            ds.append(d)
            sw.append(i)
            d += step
    return np.asarray(ds, dtype=np.float64), np.asarray(sw, dtype=np.int64)


def _flatten(pyr: list[LevelWindow]):
    """Kernel arrays for the windows: the flat height buffer with each window's offset, the nominal shape, the
    loaded block's offset and shape, and the geometry. Windows read into one shared buffer (adaptive loader)
    are used in place; otherwise their blocks are concatenated (one copy)."""
    base = pyr[0].data.base if pyr and pyr[0].data.size else None
    shared = base is not None and base.ndim == 1 and base.dtype == np.float32 and all(
        w.data.size == 0 or (w.data.base is base and w.data.flags.c_contiguous) for w in pyr)
    if shared:
        flat = base
        off = np.array([0 if w.data.size == 0 else
                        (w.data.__array_interface__["data"][0] - base.__array_interface__["data"][0]) // 4
                        for w in pyr], dtype=np.int64)
    else:
        sizes = [w.data.size for w in pyr]
        off = np.zeros(len(pyr), dtype=np.int64)
        off[1:] = np.cumsum(sizes)[:-1]
        flat = np.concatenate([np.ascontiguousarray(w.data, dtype=np.float32).ravel() for w in pyr])
    nr = np.array([w.shape[0] for w in pyr], dtype=np.int64)
    nc = np.array([w.shape[1] for w in pyr], dtype=np.int64)
    rof = np.array([w.row_off for w in pyr], dtype=np.int64)
    cof = np.array([w.col_off for w in pyr], dtype=np.int64)
    nrl = np.array([w.data.shape[0] for w in pyr], dtype=np.int64)
    ncl = np.array([w.data.shape[1] for w in pyr], dtype=np.int64)
    x0 = np.array([w.x0 for w in pyr], dtype=np.float64)
    y0 = np.array([w.y0 for w in pyr], dtype=np.float64)
    dx = np.array([w.dx for w in pyr], dtype=np.float64)
    dy = np.array([w.dy for w in pyr], dtype=np.float64)
    return flat, off, nr, nc, rof, cof, nrl, ncl, x0, y0, dx, dy


def _run_rays(pyr, nbins, pre: tuple, post: tuple, az_off: float, log: list) -> tuple:
    """Run the kernel for every bin; whenever rays reach a window's not-yet-loaded block, load that window's
    whole nominal block (repacking the windows into a new shared buffer) and re-run only those bins (rays are independent per bin and see the same pixels, so
    the result is bitwise the one a fully loaded pyramid gives). Returns H, D, inc, W, HB, stop_step."""
    mask = np.ones(nbins, dtype=np.bool_)
    out = None
    while True:
        res = _horizon_kernel(nbins, *pre, *_flatten(pyr), len(pyr), *post, mask, az_off)
        H, D, inc, W, HB, stop, need = res
        if out is None:
            out = [H, D, inc, W, HB, stop]
        else:
            for dst, src in zip(out, (H, D, inc, W, HB, stop)):
                dst[mask] = src[mask]
        redo = mask & (need >= 0)
        if not redo.any():
            return tuple(out)
        expand_into_new_buffer(pyr, {int(wi) for wi in np.unique(need[redo])})
        for wi in np.unique(need[redo]):
            log.append({"window": int(wi), "key": pyr[int(wi)].meta.get("key"), "rays": int(np.sum(need[redo] == wi)),
                        "az_off": az_off})
        mask = redo


def compute_horizon(lat: float, lon: float, obs_h_m: float = 0.0,
                    nbins: int = settings.HORIZON_BINS,
                    pyramid: list[LevelWindow] | None = None, use_stop: bool = True) -> Horizon:
    pyr = pyramid if pyramid is not None else load_pyramid(lat, lon)
    ground, site_wi = site_height_window(pyr, lat, lon)
    site_level = pyr[site_wi].level
    site_pix = pyr[site_wi].pixel_m
    d_arr, start_w = build_steps(pyr, 0.5 * site_pix)
    R0 = settings.R_MOON_M
    delta = d_arr / R0
    e, n, u = enu_basis(lat, lon)
    h_max = max(v for v in (window_hmax(w) for w in pyr) if v is not None)   # over the nominal windows
    r_site = R0 + ground + obs_h_m
    r_p = R0 + h_max
    delta_star = math.acos(min(1.0, r_p / r_site))
    e_at_star = math.atan2(r_p * math.cos(delta_star) - r_site, r_p * math.sin(delta_star)) if delta_star > 0 else math.pi / 2
    pre = (u[0], u[1], u[2], n[0], n[1], n[2], e[0], e[1], e[2], r_site, d_arr, start_w, np.cos(delta), np.sin(delta))
    post = (R0, r_p, delta_star, e_at_star, use_stop)
    expansions: list = []
    H, D, inc, W, HB, stop_step = _run_rays(pyr, nbins, pre, post, 0.0, expansions)
    # sub-bin rays (Phase 3 item 7): the same kernel at az_k + j bin / M; node values above are untouched
    M = subbin_settings()["rays_per_bin"]
    H_sub, inc_sub = [], []
    for j in range(1, M):
        Hj, _Dj, incj, _Wj, _HBj, _st = _run_rays(pyr, nbins, pre, post, 2.0 * math.pi * j / (M * nbins), expansions)
        H_sub.append(Hj)
        inc_sub.append(incj)
    sub_ex, sub_unk = subbin_excess(H, inc, H_sub, inc_sub)
    unc = horizon_uncertainty(pyr, n, e, u, D, W, HB, r_site, site_wi)
    near_m = settings.HORIZON_NEAR_FIELD_PIXELS * site_pix
    near_field = (W >= 0) & (D > 0) & (D <= near_m)
    levels = [{"level": w.level, "pixel_m": w.pixel_m, "band_m": round(w.band_m, 1),
               "product": w.meta.get("product"), "key": w.meta.get("key"), "sha256": w.meta.get("sha256"),
               "synthetic": bool(w.meta.get("synthetic")), "resolved_from": w.meta.get("resolved_from")}
              for w in pyr]
    params = {"nbins": nbins, "step_rule": "half pixel per product band", "start_m": 0.5 * site_pix,
              "stopping": "exact conservative bound e_max(max(delta, delta*)) with h_max over loaded windows",
              "h_max_m": h_max, "windows_half_m": settings.DEM_WINDOW_HALF_M,
              "interpolation": "bilinear; any nodata neighbour -> nodata; finer products first",
              "height_plausibility_m": [-20_000.0, 20_000.0],
              "site_product": {"index": site_wi, "key": pyr[site_wi].meta.get("key"), "level": site_level},
              "near_field": {"pixels": settings.HORIZON_NEAR_FIELD_PIXELS, "distance_m": near_m,
                             "bins": int(near_field.sum()),
                             "meaning": "blocking terrain within this distance: the horizon there is the DEM's "
                                        "local slope at its resolution"},
              "sigma": unc["note"],
              "performance_settings": {**settings.performance_settings(), "expansions": expansions,
                                       "windows": [{"key": w.meta.get("key"), "complete": w.complete,
                                                    "nominal_px": int(w.shape[0] * w.shape[1]),
                                                    "loaded_px": int(w.data.size)} for w in pyr]},
              "stopping_diagnostics": {"rays_stopped_by_bound": int(np.sum(~inc)),
                                       "max_stop_step": int(stop_step.max()), "steps": int(d_arr.size)},
              "subbin": {**subbin_settings(), "spacing_deg": 360.0 / nbins / M,
                         "max_excess_deg": float(np.max(sub_ex)), "bins_with_excess": int(np.sum(sub_ex > 0)),
                         "unknown_bins": int(np.sum(sub_unk))},
              "algorithm_version": ALGORITHM_VERSION}
    return Horizon(lat, lon, obs_h_m, ground, site_level, H, D, inc, unc["sigma_deg"], levels,
                   horizon_key(lat, lon, obs_h_m, nbins), params,
                   near_field=near_field, blocker_product=W.astype(np.int64), cross_product=unc["cross_product"],
                   discrepancy_unknown=unc["discrepancy_unknown"], sigma_nonlinear=unc["sigma_nonlinear"],
                   sigma_lower_bound_deg=unc["sigma_lower_bound_deg"], sigma_block_m=unc["sigma_block_m"],
                   sigma_block_model_m=unc["sigma_block_model_m"],
                   block_h_m=HB, subbin_excess_deg=sub_ex, subbin_unknown=sub_unk, stop_step=stop_step)


# ------------------------------------------------------------------ uncertainty
def elevation_gradients(u, p_hat, h_b, r_site):
    """Exact first-order sensitivities (rad per metre) of the horizon elevation to the blocker's and the
    site's height errors. u: (3,) site unit vector; p_hat: (N, 3) blocker unit vectors; h_b: (N,) blocker
    heights above the sphere; r_site: observer radius R0 + h_s + H. Returns (g_b, g_s, e_rad)."""
    u = np.asarray(u, dtype=float)
    p_hat = np.atleast_2d(np.asarray(p_hat, dtype=float))
    P_b = (settings.R_MOON_M + np.asarray(h_b, dtype=float))[:, None] * p_hat
    v = P_b - r_site * u
    nv = np.linalg.norm(v, axis=1)
    vh = v / nv[:, None]
    sin_e = np.clip(vh @ u, -1.0, 1.0)
    cos_e = np.sqrt(1.0 - sin_e ** 2)
    g_b = (p_hat @ u - sin_e * np.einsum("ij,ij->i", vh, p_hat)) / (nv * cos_e)
    g_s = -cos_e / nv
    return g_b, g_s, np.arcsin(sin_e)


def propagate_sigma(g_b, g_s, sig_b, sig_s, rho, sig_x=0.0):
    """sqrt(Var e) in radians, Var e = g_b^2 s_b^2 + g_s^2 s_s^2 + 2 g_b g_s rho s_b s_s + g_b^2 s_x^2.

    Evaluated in the algebraically identical form
        (g_b s_b + rho g_s s_s)^2 + (1 - rho^2) g_s^2 s_s^2 + g_b^2 s_x^2,
    a sum of non-negative squares for rho in [0, 1], so the strong cancellation of the expanded form
    (equal sigmas, rho -> 1, g_b = -g_s) leaves no rounding residue and the variance is never negative."""
    g_b, g_s, sig_b, sig_s, rho, sig_x = (np.asarray(a, dtype=float) for a in (g_b, g_s, sig_b, sig_s, rho, sig_x))
    var = (g_b * sig_b + rho * g_s * sig_s) ** 2 + (1.0 - rho * rho) * (g_s * sig_s) ** 2 + (g_b * sig_x) ** 2
    return np.sqrt(np.maximum(var, 0.0))


def correlation(d_m, L_m: float | None = None, model: str | None = None):
    """Correlation of height errors within one product at separation d (Gaussian; L is an assumption)."""
    model = settings.HORIZON_CORR_MODEL if model is None else model
    L_m = settings.HORIZON_CORR_LENGTH_M if L_m is None else L_m
    if model != "gaussian":
        raise ValueError(f"Unknown horizon error correlation model {model!r}")
    return np.exp(-0.5 * (np.asarray(d_m, dtype=float) / L_m) ** 2)


def bilinear_many(w: LevelWindow, xs, ys) -> np.ndarray:
    """Vectorised dem.bilinear: NaN outside the window or when any of the four neighbours is nodata."""
    xs, ys = np.asarray(xs, dtype=float), np.asarray(ys, dtype=float)
    fc = (xs - w.x0) / w.dx
    fr = (ys - w.y0) / w.dy
    c0 = np.floor(fc).astype(np.int64)
    r0 = np.floor(fr).astype(np.int64)
    nr, nc = w.shape                                          # nominal window (Phase 3 item 6)
    ok = (c0 >= 0) & (r0 >= 0) & (c0 + 1 < nc) & (r0 + 1 < nr)
    out = np.full(xs.shape, np.nan)
    if ok.any():                                              # grow a partially loaded block to what is needed
        w.ensure(int(r0[ok].min()), int(r0[ok].max()) + 2, int(c0[ok].min()), int(c0[ok].max()) + 2)
    c, r = c0[ok] - w.col_off, r0[ok] - w.row_off
    tc, tr = fc[ok] - c0[ok], fr[ok] - r0[ok]
    a = w.data[r, c].astype(float)
    b = w.data[r, c + 1].astype(float)
    cc = w.data[r + 1, c].astype(float)
    d = w.data[r + 1, c + 1].astype(float)
    out[ok] = (a * (1 - tc) + b * tc) * (1 - tr) + (cc * (1 - tc) + d * tc) * tr   # NaN neighbour -> NaN
    return out


def cross_product_discrepancy(w_site: LevelWindow, w_blk: LevelWindow) -> dict:
    """Cross-product discrepancy allowance between the site product and a blocker product.

    Finer heights at pixel centres (every `stride` pixels, stride = coarse/fine pixel size, thinned to at
    most max_points) are compared with bilinear coarser heights at the same points, inside the overlap of
    the two windows loaded around the site. RMS(fine - coarse) = sqrt(mean^2 + std^2) is the allowance: a
    conservative allowance that includes the measured bias, not a calibrated random 1-sigma. Fewer than
    min_pairs valid pairs: status "unknown" (never zero).
    """
    cfg = settings.CROSS_PRODUCT_SAMPLING
    fine, coarse = (w_site, w_blk) if w_site.pixel_m <= w_blk.pixel_m else (w_blk, w_site)
    fine.ensure_full()          # every pixel of the finer nominal window is compared (Phase 2 definition)
    stride = max(1, int(round(coarse.pixel_m / fine.pixel_m)))
    rows = np.arange(0, fine.data.shape[0], stride)
    cols = np.arange(0, fine.data.shape[1], stride)
    thin = max(1, int(math.ceil(math.sqrt(rows.size * cols.size / float(cfg["max_points"])))))
    rows, cols = rows[::thin], cols[::thin]
    R, C = np.meshgrid(rows, cols, indexing="ij")
    xs = fine.x0 + C.ravel() * fine.dx
    ys = fine.y0 + R.ravel() * fine.dy
    hf = fine.data[R.ravel(), C.ravel()].astype(float)
    hc = bilinear_many(coarse, xs, ys)
    ok = np.isfinite(hf) & np.isfinite(hc)
    n = int(ok.sum())
    base = {"fine": fine.meta.get("key"), "coarse": coarse.meta.get("key"), "n": n,
            "min_pairs": int(cfg["min_pairs"]), "stride_px": stride * thin, "kind": CROSS_PRODUCT_KIND}
    if n < int(cfg["min_pairs"]):
        return {**base, "status": "unknown", "allowance_m": None}
    diff = hf[ok] - hc[ok]
    mean, std = float(np.mean(diff)), float(np.std(diff))
    rms = float(np.sqrt(np.mean(diff ** 2)))
    return {**base, "status": "measured", "mean_m": mean, "std_m": std, "rms_m": rms, "allowance_m": rms}


def _owner_error_maps(pyr: list[LevelWindow]) -> dict:
    """Window index -> error-map record registered for that window's own product (SHA-256 and file)."""
    reg = read_registry()
    owners = {}
    for wi, w in enumerate(pyr):
        rec = next((p for p in reg["products"] if p.get("sha256") == w.meta.get("sha256")
                    and Path(p["path"]).name == Path(w.meta.get("path") or "").name), None)
        em = error_map_for(rec, reg) if rec else None
        if em:
            owners[wi] = em
    return owners


def _sample_error_map(em: dict, xs, ys) -> np.ndarray:
    import rasterio

    xs, ys = np.asarray(xs, dtype=float), np.asarray(ys, dtype=float)
    out = np.full(xs.shape, np.nan)
    ta, _, tc, _, te, tf = em["transform"]
    cols = np.floor((xs - tc) / ta).astype(np.int64)
    rows = np.floor((ys - tf) / te).astype(np.int64)
    inside = (cols >= 0) & (rows >= 0) & (cols < em["width"]) & (rows < em["height"])
    if not inside.any():
        return out
    with rasterio.open(resolve_dem_path(em["path"])) as src:
        vals = np.array([v[0] for v in src.sample(list(zip(xs[inside], ys[inside])))], dtype=float)
    nod = em.get("nodata")
    if nod is not None and np.isfinite(nod):
        vals[vals == nod] = np.nan
    vals = vals * em.get("scale", 1.0) + em.get("offset", 0.0)
    vals[~(np.isfinite(vals) & (vals >= 0.0))] = np.nan
    out[inside] = vals
    return out


def _smooth_1d(a: np.ndarray, k: np.ndarray, axis: int) -> np.ndarray:
    return np.apply_along_axis(lambda r: np.convolve(r, k, mode="same"), axis, a)


def regularized_error_sigma(em: dict, xs, ys, L: float | None = None) -> np.ndarray:
    """sigma~ at the given points: sqrt of the error-map variance smoothed at the correlation length.

    sigma~^2 = (G_L * (m sigma^2)) / (G_L * m), with G_L a Gaussian of std L (truncated at
    VARIANCE_REGULARIZATION["truncation_L"] * L) and m the mask of valid error-map pixels, so nodata is
    excluded and the map's edges are not biased (normalized convolution). Smoothing a constant map returns
    it unchanged, and the mean of sigma^2 is preserved away from edges. The variance is first summed into
    cells of max(pixel, cell_fraction_of_L * L) (at most L/5, so the Gaussian stays resolved), then
    smoothed separably and interpolated bilinearly at the points. NaN where no valid pixel is in reach.
    """
    import rasterio
    from rasterio.windows import Window

    cfg = settings.VARIANCE_REGULARIZATION
    L = settings.HORIZON_CORR_LENGTH_M if L is None else L
    xs, ys = np.atleast_1d(np.asarray(xs, dtype=float)), np.atleast_1d(np.asarray(ys, dtype=float))
    out = np.full(xs.shape, np.nan)
    fin = np.isfinite(xs) & np.isfinite(ys)
    if not fin.any():
        return out
    ta, _, tc, _, te, tf = em["transform"]
    px = abs(ta)
    margin = float(cfg["truncation_L"]) * L
    x0, x1 = xs[fin].min() - margin, xs[fin].max() + margin
    y0, y1 = ys[fin].min() - margin, ys[fin].max() + margin
    cols = sorted(((x0 - tc) / ta, (x1 - tc) / ta))
    rows = sorted(((y0 - tf) / te, (y1 - tf) / te))
    c0, c1 = max(0, int(math.floor(cols[0]))), min(int(em["width"]), int(math.ceil(cols[1])) + 1)
    r0, r1 = max(0, int(math.floor(rows[0]))), min(int(em["height"]), int(math.ceil(rows[1])) + 1)
    if c1 <= c0 or r1 <= r0:
        return out
    with rasterio.open(resolve_dem_path(em["path"])) as src:
        arr = src.read(1, window=Window(c0, r0, c1 - c0, r1 - r0)).astype(np.float64)
    nod = em.get("nodata")
    if nod is not None and np.isfinite(nod):
        arr[arr == nod] = np.nan
    arr = arr * em.get("scale", 1.0) + em.get("offset", 0.0)
    arr[~(np.isfinite(arr) & (arr >= 0.0))] = np.nan
    f = max(1, int(round(float(cfg["cell_fraction_of_L"]) * L / px)))
    H, Wd = arr.shape
    Hc, Wc = -(-H // f), -(-Wd // f)
    pad = np.full((Hc * f, Wc * f), np.nan)
    pad[:H, :Wd] = arr
    m = np.isfinite(pad)
    var_sum = np.where(m, pad * pad, 0.0).reshape(Hc, f, Wc, f).sum(axis=(1, 3))
    cnt = m.reshape(Hc, f, Wc, f).sum(axis=(1, 3)).astype(np.float64)
    cell = f * px
    s = L / cell
    half = int(math.ceil(float(cfg["truncation_L"]) * s))
    k = np.exp(-0.5 * (np.arange(-half, half + 1) / s) ** 2)
    num = _smooth_1d(_smooth_1d(var_sum, k, 0), k, 1)
    den = _smooth_1d(_smooth_1d(cnt, k, 0), k, 1)
    with np.errstate(invalid="ignore", divide="ignore"):
        sig2 = np.where(den > 1e-12 * den.max(), num / den, np.nan)
    # cell (i, j) covers pixels [i f, (i+1) f) x [j f, (j+1) f) of the read window
    gx0 = tc + (c0 + 0.5 * f) * ta
    gy0 = tf + (r0 + 0.5 * f) * te
    v = sample_variance_grid(sig2, gx0, gy0, f * ta, f * te, xs, ys)
    out[fin] = np.sqrt(v[fin])
    return out


def sample_variance_grid(sig2: np.ndarray, gx0: float, gy0: float, dx: float, dy: float, xs, ys) -> np.ndarray:
    """Bilinear samples of a smoothed variance grid (cell centres at gx0 + j dx, gy0 + i dy).

    Inside the grid any NaN neighbour gives NaN: there is no valid error-map pixel within reach, and that
    uncertainty stays unknown rather than being borrowed from a neighbouring cell (C08). Only points within
    half a cell outside the bilinear interior (at the grid border) take the nearest cell, where the field
    smoothed at the correlation length is flat at that scale.
    """
    xs, ys = np.asarray(xs, dtype=float), np.asarray(ys, dtype=float)
    Hc, Wc = sig2.shape
    grid = LevelWindow("variance", sig2, gx0, gy0, dx, dy, 0.0, abs(dx))
    v = bilinear_many(grid, xs, ys)
    fc = (xs - gx0) / dx
    fr = (ys - gy0) / dy
    # complement of bilinear_many's interior (0 <= fc < Wc - 1 and 0 <= fr < Hc - 1), so every point is either
    # interpolated or, at the border only, given the nearest cell
    border = (fc < 0) | (fr < 0) | (fc >= Wc - 1) | (fr >= Hc - 1)
    miss = np.isfinite(xs) & np.isfinite(ys) & ~np.isfinite(v) & border
    if miss.any():
        ci = np.clip(np.round(fc[miss]).astype(np.int64), 0, Wc - 1)
        ri = np.clip(np.round(fr[miss]).astype(np.int64), 0, Hc - 1)
        v[miss] = sig2[ri, ci]
    return v


def horizon_uncertainty(pyr: list[LevelWindow], n, e, u, D, W, HB, r_site: float, site_wi: int) -> dict:
    """Per-bin horizon sigma and its flags (see the module docstring for the model)."""
    nb = D.size
    has_blk = (W >= 0) & (D > 0) & np.isfinite(HB)
    cross = has_blk & (W != site_wi)
    false = np.zeros(nb, dtype=bool)
    note = {"rule": "error map of the product that supplied each bin's blocking sample (by window index)",
            "model": "first-order exact-geometry propagation",
            **uncertainty_settings(), "L_corr_label": l_corr_label(),
            "site_window_index": int(site_wi), "site_product": pyr[site_wi].meta.get("key")}
    owners = _owner_error_maps(pyr)
    note["error_maps"] = sorted({Path(em["path"]).name for em in owners.values() if em.get("path")})
    if not owners:
        return {"sigma_deg": None, "sigma_lower_bound_deg": None, "sigma_block_m": None,
                "sigma_block_model_m": None, "cross_product": cross,
                "discrepancy_unknown": false, "sigma_nonlinear": false,
                "note": {**note, "status": "no error maps registered for the products used; sigma not computed",
                         "bins_with_sigma": 0}}
    a = 2 * np.pi * np.arange(nb) / nb
    t = np.outer(np.cos(a), n) + np.outer(np.sin(a), e)
    delta = D / settings.R_MOON_M
    p = np.outer(np.cos(delta), u) + np.sin(delta)[:, None] * t
    xs = 2 * settings.R_MOON_M * p[:, 1] / (1 - p[:, 2])
    ys = 2 * settings.R_MOON_M * p[:, 0] / (1 - p[:, 2])

    # error-map value at each bin's blocking sample, from that bin's own product only
    sig_b = np.full(nb, np.nan)
    for wi, em in owners.items():
        idx = np.where(has_blk & (W == wi))[0]
        if idx.size:
            sig_b[idx] = _sample_error_map(em, xs[idx], ys[idx])
    # error-map value at the site, from the site product's own map
    sig_s = np.nan
    if site_wi in owners:
        sx = 2.0 * settings.R_MOON_M * u[1] / (1.0 - u[2])
        sy = 2.0 * settings.R_MOON_M * u[0] / (1.0 - u[2])
        sig_s = float(_sample_error_map(owners[site_wi], [sx], [sy])[0])

    # model sigmas: within the site product the error field is sigma~(x) z(x) with sigma~ regularized at
    # L_corr (continuous at that scale, as the correlation model requires); other products keep their
    # pointwise values (rho = 0 with them, so their variance texture cannot create a spurious difference)
    sig_b_model = sig_b.copy()
    sig_s_model = np.nan
    same = has_blk & (W == site_wi)
    if site_wi in owners:
        idx = np.where(same)[0]
        reg = regularized_error_sigma(owners[site_wi], np.append(xs[idx], sx), np.append(ys[idx], sy))
        sig_b_model[idx] = reg[:-1]
        sig_s_model = float(reg[-1])

    # cross-product discrepancy allowance for every (site, blocker) product pair that occurs
    sig_x = np.zeros(nb)
    unknown = np.zeros(nb, dtype=bool)
    pairs = {}
    for wi in sorted({int(w) for w in W[cross]}):
        st = cross_product_discrepancy(pyr[site_wi], pyr[wi])
        pairs[f"{pyr[site_wi].meta.get('key')} | {pyr[wi].meta.get('key')}"] = st
        sel = cross & (W == wi)
        if st["status"] == "measured":
            sig_x[sel] = st["allowance_m"]
        else:
            unknown[sel] = True

    g_b = np.full(nb, np.nan)
    g_s = np.full(nb, np.nan)
    hb_idx = np.where(has_blk)[0]
    if hb_idx.size:
        g_b[hb_idx], g_s[hb_idx], _e = elevation_gradients(u, p[hb_idx], HB[hb_idx], r_site)
    rho = np.where(cross, 0.0, correlation(D))
    ok = has_blk & np.isfinite(sig_b_model) & np.isfinite(g_b)
    site_known = np.isfinite(sig_s_model)
    full = ok & site_known & ~unknown
    sigma = np.full(nb, np.nan)
    sigma[full] = np.degrees(propagate_sigma(g_b[full], g_s[full], sig_b_model[full], sig_s_model, rho[full],
                                             sig_x[full]))
    # lower bound from the terms that are known (never used for flags; reported for transparency)
    lb = np.full(nb, np.nan)
    part = ok & ~full
    lb[part] = np.degrees(propagate_sigma(g_b[part], g_s[part], sig_b_model[part],
                                          np.nan_to_num(sig_s_model, nan=0.0),
                                          np.where(site_known, rho[part], 0.0), 0.0))
    nonlinear = np.isfinite(sigma) & (sigma > settings.SIGMA_NONLINEAR_DEG)
    note.update({
        "status": "computed",
        "site_sigma_m": None if not np.isfinite(sig_s) else round(sig_s, 6),
        "site_sigma_model_m": None if not site_known else round(sig_s_model, 6),
        "variance_model": ("site product: error-map variance regularized at L_corr (sigma~^2 = G_L * sigma^2); "
                           "other products: pointwise error-map value"),
        "bins_with_sigma": int(np.isfinite(sigma).sum()),
        "bins_nonlinear": int(nonlinear.sum()),
        "bins_discrepancy_unknown": int(unknown.sum()),
        "bins_without_error_map": int((has_blk & ~np.isfinite(sig_b_model)).sum()),
        "bins_site_sigma_missing": int((ok & ~site_known).sum()),
        "cross_product_discrepancy_allowance": pairs,
    })
    return {"sigma_deg": sigma, "sigma_lower_bound_deg": lb, "sigma_block_m": sig_b,
            "sigma_block_model_m": sig_b_model, "cross_product": cross,
            "discrepancy_unknown": unknown, "sigma_nonlinear": nonlinear, "note": note}


def sphere_dip_deg(obs_h_m: float) -> float:
    """Analytic horizon dip of a bare sphere (V-06)."""
    R0 = settings.R_MOON_M
    return -math.degrees(math.acos(R0 / (R0 + obs_h_m)))
