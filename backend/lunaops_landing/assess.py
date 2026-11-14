"""Landing hazard screening of one analysis window and one circular footprint (landing 0.1.0).

Every number is computed from a registered NASA LOLA DEM window (or its registered error map, or an auxiliary
PGDA product tied to that DEM) and is returned with its basis: measured / interpolated / calculated / estimated /
product value / unavailable. Thresholds are user-defined assumptions: none has a default value, and LUNA-OPS does
not supply a "safe" slope or roughness. There is no combined score, ranking, probability or safe/unsafe verdict.
"""
from __future__ import annotations

import hashlib
import json
import math
import threading
from collections import OrderedDict
from dataclasses import dataclass, field

import numpy as np

from lunaops import settings
from lunaops.engine import dem as edem
from lunaops.engine.frames import CoordinateError, validate_latlon
from lunaops.fingerprint import code_fingerprint

from . import LANDING_VERSION, VALIDATION_STATUS, landing_code_hash
from . import kernels as K
from .sources import (R, Window, clamp_half, latlon_to_xy, point_scale, products_covering, read_window,
                      xy_to_latlon)

# ------------------------------------------------------------------ parameters (documented in the evidence README)
ROUGHNESS_WINDOWS_PX = (3, 5, 9, 15, 25)        # odd window sides offered; physical baseline = side x pixel size
MULTISCALE_PX = (3, 5, 9, 15)                   # windows summarised for the multi-scale roughness table
SLOPE_BINS_DEG = (0, 5, 10, 15, 20, 25, 30, 90)  # display bins of the slope distribution (not thresholds)
DEPTH_FLOOR_M = 0.01                            # numerical floor for "inside a filled depression"
MIN_CANDIDATE_PX = 9                            # a candidate needs at least 9 pixels (about 3 x 3) for a shape
MAX_CANDIDATES = 1000
FOOTPRINT_MIN_PX_ACROSS = 3.0                   # a footprint narrower than the 3 x 3 slope stencil is not resolved
# depression quality rules (a LUNA-OPS 0.1.0 screening convention, not a published criterion)
Q_DEFINED_SIGMA, Q_DEFINED_AXIS, Q_DEFINED_FILL = 3.0, 0.5, 0.6
CACHE_MAX = 3

STATUS_TEXT = {
    "hazard": "Potential hazard detected",
    "clear": "No configured threshold exceeded",
    "no_threshold": "No threshold configured (values shown)",
    "insufficient": "Insufficient terrain data",
    "higher_res": "Requires higher-resolution data",
    "manual": "Not available - manual review required",
    "none_detected": "No candidate detected at this resolution",
}


class LandingInputError(ValueError):
    pass


# ------------------------------------------------------------------ helpers
def _num(v, nd=3):
    if v is None:
        return None
    v = float(v)
    return None if not math.isfinite(v) else round(v, nd)


def _stats(a: np.ndarray, nd=3) -> dict:
    v = a[np.isfinite(a)]
    if v.size == 0:
        return {"n": 0, "min": None, "max": None, "mean": None, "median": None, "p95": None}
    return {"n": int(v.size), "min": _num(v.min(), nd), "max": _num(v.max(), nd), "mean": _num(v.mean(), nd),
            "median": _num(np.median(v), nd), "p95": _num(np.percentile(v, 95), nd)}


def _frame_of(rec: dict) -> str:
    try:
        m = json.loads((settings.REPO_ROOT / "backend" / "lunaops" / "manifests" / "datasets.json").read_text())
        for d in m.get("dem_levels", []):
            if d.get("id") == rec.get("product_id") and d.get("frame"):
                return d["frame"]
    except (OSError, ValueError):
        pass
    return "not recorded in the dataset manifest"


@dataclass
class Assessment:
    id: str
    config: dict
    win: Window
    xs: np.ndarray
    ys: np.ndarray
    k: np.ndarray
    slope: np.ndarray
    rough: np.ndarray
    rough_px: int
    tri: np.ndarray
    depth: np.ndarray
    labels: np.ndarray
    candidates: list
    summary: dict = field(default_factory=dict)


_CACHE: "OrderedDict[str, Assessment]" = OrderedDict()
_LOCK = threading.Lock()


def get(aid: str) -> Assessment | None:
    a = _CACHE.get(aid)
    if a is not None:
        _CACHE.move_to_end(aid)
    return a


# ------------------------------------------------------------------ configuration
def normalise(cfg: dict) -> dict:
    try:
        lat, lon = validate_latlon(float(cfg["lat"]), float(cfg["lon"]))
    except (CoordinateError, KeyError, TypeError, ValueError) as exc:
        raise LandingInputError(str(exc))
    if lat > -60.0:
        raise LandingInputError("Landing screening uses the registered LOLA products, which cover 60-90 S only.")
    half = float(cfg.get("window_half_m") or 1500.0)
    if not (100.0 <= half <= 30_000.0):
        raise LandingInputError("The analysis window half-width must be between 100 m and 30 km.")
    out = {"lat": lat, "lon": lon, "window_half_m": half, "product": cfg.get("product") or "auto",
           "roughness_baseline_m": cfg.get("roughness_baseline_m"), "roughness_window_px": cfg.get("roughness_window_px"),
           "min_depth_m": float(cfg.get("min_depth_m") if cfg.get("min_depth_m") is not None else 1.0),
           "min_diameter_m": cfg.get("min_diameter_m"), "max_diameter_m": cfg.get("max_diameter_m")}
    if out["min_depth_m"] <= 0:
        raise LandingInputError("The minimum depression depth must be positive.")
    return out


def _choose(cfg: dict, x: float, y: float) -> dict:
    cands = products_covering(x, y, cfg["window_half_m"])
    if cfg["product"] != "auto":
        for lv in cands:
            if edem.product_key(lv) == cfg["product"]:
                return lv
        raise LandingInputError(f"Terrain product {cfg['product']} does not fully cover this analysis window.")
    if not cands:
        if not edem.usable_levels():
            raise LandingInputError(edem.no_terrain_reason())
        raise LandingInputError("No registered terrain product fully covers this analysis window. Choose a smaller "
                                "window or a site inside the products' coverage.")
    return cands[0]


def _rough_px(cfg: dict, pixel: float) -> int:
    if cfg.get("roughness_window_px") in ROUGHNESS_WINDOWS_PX:
        return int(cfg["roughness_window_px"])
    b = cfg.get("roughness_baseline_m")
    if b is None:
        return 5
    return min(ROUGHNESS_WINDOWS_PX, key=lambda w: abs(w * pixel - float(b)))


# ------------------------------------------------------------------ assessment
def assess(raw_cfg: dict) -> Assessment:
    cfg = normalise(raw_cfg)
    x, y = latlon_to_xy(cfg["lat"], cfg["lon"])
    lv = _choose(cfg, x, y)
    cfg["product"] = edem.product_key(lv)
    pixel = abs(float(lv["transform"][0]))
    cfg["window_half_m_used"] = clamp_half(lv, cfg["window_half_m"])
    rpx = _rough_px(cfg, pixel)
    cfg["roughness_window_px"] = rpx
    key = json.dumps({**cfg, "sha": lv.get("sha256"), "landing": landing_code_hash()}, sort_keys=True)
    aid = hashlib.sha256(key.encode()).hexdigest()[:20]
    with _LOCK:
        hit = get(aid)
        if hit is not None:
            return hit
        win = read_window(lv, x, y, cfg["window_half_m"])
        xs, ys = win.centres()
        X, Y = np.meshgrid(xs, ys)
        k = point_scale(X, Y)
        del X, Y
        z = win.z
        h = np.where(np.isfinite(z), z, 0.0)
        ground = (pixel / k) * ((R + h) / R)                 # ground spacing between pixel centres (m)
        del h
        z64 = z.astype(np.float64)
        slope = K.slope_horn(z64, ground, ground)
        rough = K.detrended_rms(z64, rpx // 2)
        tri = K.tri_riley(z64)
        depth = K.fill_depth(z64)
        mask = np.isfinite(depth) & (depth > DEPTH_FLOOR_M)
        labels, n = K.label8(mask)
        del mask
        err = win.err if win.err is not None else np.full(z.shape, np.nan, np.float32)
        cnt = win.aux.get("count")
        cnt = cnt if cnt is not None else np.full(z.shape, np.nan, np.float32)
        mom = K.component_moments(labels, n, depth.astype(np.float64), err.astype(np.float64), cnt.astype(np.float64))
        a = Assessment(id=aid, config=cfg, win=win, xs=xs, ys=ys, k=k.astype(np.float32), slope=slope, rough=rough,
                       rough_px=rpx, tri=tri, depth=depth, labels=labels, candidates=[])
        a.candidates, keep = _candidates(a, mom, cfg)
        # labels of rejected components are cleared so footprint intersections use reported candidates only
        lut = np.zeros(n + 1, dtype=np.int32)
        for new_id, old in enumerate(keep, start=1):
            lut[old] = new_id
        a.labels = lut[labels]
        a.summary = _region_summary(a, z64)
        _CACHE[aid] = a
        while len(_CACHE) > CACHE_MAX:
            _CACHE.popitem(last=False)
        return a


def _candidates(a: Assessment, mom: np.ndarray, cfg: dict) -> tuple[list, list]:
    pixel = a.win.pixel_m
    dmin = float(cfg["min_diameter_m"]) if cfg.get("min_diameter_m") else 0.0
    dmax = float(cfg["max_diameter_m"]) if cfg.get("max_diameter_m") else math.inf
    out, keep = [], []
    have_err = a.win.err is not None
    have_cnt = "count" in a.win.aux
    for i in range(mom.shape[0]):
        npx, sr, sc, srr, scc, src, dmax_m, rmax, cmax, esum, en, meas, cn = mom[i]
        if npx < MIN_CANDIDATE_PX or dmax_m < cfg["min_depth_m"]:
            continue
        mr, mc = sr / npx, sc / npx
        vr = srr / npx - mr * mr + 1.0 / 12.0
        vc = scc / npx - mc * mc + 1.0 / 12.0
        cv = src / npx - mr * mc
        tr, det = vr + vc, vr * vc - cv * cv
        disc = math.sqrt(max(tr * tr / 4.0 - det, 0.0))
        l1, l2 = tr / 2.0 + disc, max(tr / 2.0 - disc, 1e-12)
        axis_ratio = math.sqrt(l2 / l1)
        fill_ratio = npx / (4.0 * math.pi * math.sqrt(l1 * l2))
        ri, ci = int(round(mr)), int(round(mc))
        kc = float(a.k[min(max(ri, 0), a.k.shape[0] - 1), min(max(ci, 0), a.k.shape[1] - 1)])
        gpx = pixel / kc
        area = npx * gpx * gpx
        diam = 2.0 * math.sqrt(area / math.pi)
        if diam < dmin or diam > dmax:
            continue
        if len(out) >= MAX_CANDIDATES:
            break
        a_, _, c_, _, e_, f_ = a.win.rec["transform"]
        cx = c_ + a_ * (a.win.col0 + mc + 0.5)
        cy = f_ + e_ * (a.win.row0 + mr + 0.5)
        lat, lon = xy_to_latlon(cx, cy)
        dx = c_ + a_ * (a.win.col0 + cmax + 0.5)
        dy = f_ + e_ * (a.win.row0 + rmax + 0.5)
        dlat, dlon = xy_to_latlon(dx, dy)
        sigma = esum / en if en > 0 else None
        ratio = dmax_m / sigma if sigma else None
        shape_ok = axis_ratio >= Q_DEFINED_AXIS and fill_ratio >= Q_DEFINED_FILL
        if ratio is None:
            quality = "shape_only"
        elif ratio < 1.0:
            quality = "within_uncertainty"
        elif ratio >= Q_DEFINED_SIGMA and shape_ok:
            quality = "defined"
        else:
            quality = "weak"
        keep.append(i + 1)
        out.append({
            "id": len(out) + 1, "lat": _num(lat, 6), "lon": _num(lon, 6), "x": _num(cx, 1), "y": _num(cy, 1),
            "diameter_m": _num(diam, 1), "depth_m": _num(dmax_m, 2), "deepest": {"lat": _num(dlat, 6), "lon": _num(dlon, 6)},
            "pixels": int(npx), "axis_ratio": _num(axis_ratio, 2), "fill_ratio": _num(fill_ratio, 2),
            "sigma_m": _num(sigma, 2) if have_err else None, "depth_to_sigma": _num(ratio, 1) if have_err else None,
            "measured_share": _num(meas / cn, 3) if (have_cnt and cn > 0) else None,
            "quality": quality, "status": "unconfirmed_candidate",
            "orientation_deg": _num(math.degrees(0.5 * math.atan2(2 * cv, vc - vr)), 1),
            "axes_m": [_num(4.0 * math.sqrt(l1) * gpx, 1), _num(4.0 * math.sqrt(l2) * gpx, 1)],
        })
    return out, keep


def _basis(a: Assessment) -> str:
    if a.win.rec.get("synthetic"):
        return "synthetic test terrain (not lunar data)"
    if "count" in a.win.aux:
        return "LOLA DEM: measured where the LDEC count map has >= 1 return, interpolated elsewhere"
    return "LOLA DEM: measured and interpolated pixels cannot be told apart (no count map for this product)"


def _region_summary(a: Assessment, z64: np.ndarray) -> dict:
    w = a.win
    n = w.z.size
    valid = np.isfinite(w.z)
    cnt = w.aux.get("count")
    s = a.slope
    sv = s[np.isfinite(s)]
    hist = np.histogram(sv, bins=SLOPE_BINS_DEG)[0] if sv.size else np.zeros(len(SLOPE_BINS_DEG) - 1, int)
    multi = []
    for wpx in MULTISCALE_PX:
        r = a.rough if wpx == a.rough_px else K.detrended_rms(z64, wpx // 2)
        multi.append({"window_px": wpx, "baseline_m": _num(wpx * w.pixel_m, 1), **_stats(r)})
    return {
        "pixels": int(n), "valid_share": _num(valid.mean(), 4),
        "measured_share": _num(((cnt > 0) & valid).sum() / n, 4) if cnt is not None else None,
        "elevation_m": _stats(w.z, 2), "slope_deg": _stats(s, 2),
        "slope_hist": {"edges_deg": list(SLOPE_BINS_DEG), "counts": [int(c) for c in hist]},
        "roughness_m": _stats(a.rough, 3), "tri_m": _stats(a.tri, 3), "roughness_multiscale": multi,
        "height_sigma_m": _stats(w.err, 3) if w.err is not None else None,
        "nasa_slope_deg": _stats(w.aux["slope"], 2) if "slope" in w.aux else None,
        "slope_sigma_deg": _stats(w.aux["slope_error"], 2) if "slope_error" in w.aux else None,
        "depressions": {"count": len(a.candidates),
                        "by_quality": {q: sum(1 for c in a.candidates if c["quality"] == q)
                                       for q in ("defined", "weak", "within_uncertainty", "shape_only")},
                        "truncated": len(a.candidates) >= MAX_CANDIDATES},
        "basis": _basis(a),
    }


# ------------------------------------------------------------------ footprint
def footprint(a: Assessment, lat: float, lon: float, radius_m: float, th: dict) -> dict:
    """Separate findings for a circular footprint of radius_m (metres on the 1737.4 km sphere)."""
    try:
        lat, lon = validate_latlon(float(lat), float(lon))
    except (CoordinateError, TypeError, ValueError) as exc:
        raise LandingInputError(str(exc))
    radius_m = float(radius_m)
    if not (1.0 <= radius_m <= 5000.0):
        raise LandingInputError("The footprint radius must be between 1 m and 5 km.")
    w = a.win
    x, y = latlon_to_xy(lat, lon)
    kc = float(point_scale(x, y))
    rmap = radius_m * kc
    x0, y0, x1, y1 = w.bounds
    inside = x - rmap >= x0 and x + rmap <= x1 and y - rmap >= y0 and y + rmap <= y1
    pixel_ground = w.pixel_m / kc
    px_across = 2.0 * radius_m / pixel_ground
    th = {k: (None if th.get(k) in (None, "") else float(th[k])) for k in ("slope_deg", "roughness_m", "relief_m")} | {
        "min_valid_pct": float(th.get("min_valid_pct") if th.get("min_valid_pct") not in (None, "") else 95.0)}
    base = {"center": {"lat": _num(lat, 6), "lon": _num(lon, 6), "x": _num(x, 1), "y": _num(y, 1)},
            "radius_m": radius_m, "pixel_m_ground": _num(pixel_ground, 3), "pixels_across": _num(px_across, 1),
            "inside_window": bool(inside), "thresholds": th,
            "threshold_basis": "user-defined assumptions entered in this session; LUNA-OPS supplies no default "
                               "and no published landing limit is implied"}
    if not inside:
        msg = "The footprint extends beyond the analysed window. Re-run the assessment centred on the footprint."
        return {**base, "pixels": 0, "findings": [
            {"key": k, "status": "insufficient", "status_text": STATUS_TEXT["insufficient"], "reason": msg}
            for k in ("slope", "roughness", "relief", "depressions")] + [_obstacles(w)], "coverage": None}
    xs, ys = a.xs, a.ys
    cols = np.nonzero(np.abs(xs - x) <= rmap)[0]
    rows = np.nonzero(np.abs(ys - y) <= rmap)[0]
    npx = 0
    if rows.size and cols.size:
        sub = (slice(rows.min(), rows.max() + 1), slice(cols.min(), cols.max() + 1))
        XX, YY = np.meshgrid(xs[sub[1]], ys[sub[0]])
        m = (XX - x) ** 2 + (YY - y) ** 2 <= rmap * rmap
        npx = int(m.sum())
    if npx == 0:
        return {**base, "pixels": 0, "findings": [
            {"key": k, "status": "higher_res", "status_text": STATUS_TEXT["higher_res"],
             "reason": "No DEM pixel centre lies inside the footprint."} for k in ("slope", "roughness", "relief", "depressions")]
            + [_obstacles(w)], "coverage": None}
    z = w.z[sub][m]
    valid_pct = 100.0 * np.isfinite(z).mean()
    cnt = w.aux.get("count")
    cov = {"pixels": npx, "valid_pct": _num(valid_pct, 2),
           "measured_pct": _num(100.0 * ((cnt[sub][m] > 0) & np.isfinite(z)).mean(), 2) if cnt is not None else None,
           "measured_basis": "LDEC count map (pixels with >= 1 LOLA return)" if cnt is not None
           else "unavailable: this product has no count map",
           "height_sigma_m": _stats(w.err[sub][m], 3) if w.err is not None else None,
           "slope_sigma_deg": _stats(w.aux["slope_error"][sub][m], 2) if "slope_error" in w.aux else None,
           "nasa_slope_deg": _stats(w.aux["slope"][sub][m], 2) if "slope" in w.aux else None}
    low_cov = valid_pct < th["min_valid_pct"]
    coarse = px_across < FOOTPRINT_MIN_PX_ACROSS
    findings = []

    def threshold_finding(key, vals, thr, unit, extra):
        shown = "°" if unit == "deg" else f" {unit}"
        st = _stats(vals, 3)
        f = {"key": key, "unit": unit, "stats": st, "threshold": thr, **extra}
        vv = vals[np.isfinite(vals)]
        if thr is not None and vv.size:
            f["above_threshold_pct"] = _num(100.0 * (vv > thr).mean(), 2)
        if low_cov or vv.size == 0:
            f["status"] = "insufficient"
            f["reason"] = (f"Valid terrain covers {valid_pct:.1f}% of the footprint, below the configured "
                           f"{th['min_valid_pct']:.0f}% minimum (user-defined assumption).")
        elif coarse:
            f["status"] = "higher_res"
            f["reason"] = (f"The footprint spans {px_across:.1f} DEM pixels; at least {FOOTPRINT_MIN_PX_ACROSS:.0f} "
                           "are needed to resolve it with a 3 x 3 stencil.")
        elif thr is None:
            f["status"] = "no_threshold"
        elif (vv > thr).any():
            f["status"] = "hazard"
            f["reason"] = (f"The footprint relief exceeds the configured {thr:g}{shown}." if key == "relief" else
                           f"{f['above_threshold_pct']}% of valid footprint pixels exceed the configured {thr:g}{shown}.")
        else:
            f["status"] = "clear"
        f["status_text"] = STATUS_TEXT[f["status"]]
        return f

    findings.append(threshold_finding("slope", a.slope[sub][m], th["slope_deg"], "deg",
                                      {"basis": "calculated (Horn 1981, 3 x 3) from the DEM",
                                       "baseline_m": _num(3 * pixel_ground, 1)}))
    findings.append(threshold_finding("roughness", a.rough[sub][m], th["roughness_m"], "m",
                                      {"basis": "calculated: RMS residual about a least-squares plane",
                                       "baseline_m": _num(a.rough_px * pixel_ground, 1), "window_px": a.rough_px}))
    zz = z[np.isfinite(z)]
    relief = np.array([zz.max() - zz.min()], dtype=np.float64) if zz.size else np.array([np.nan])
    rf = threshold_finding("relief", relief, th["relief_m"], "m",
                           {"basis": "calculated: maximum minus minimum DEM height inside the footprint",
                            "elevation_m": _stats(z, 2)})
    rf["stats"] = {"value": _num(relief[0], 2)}
    findings.append(rf)
    ids = sorted(int(i) for i in np.unique(a.labels[sub][m]) if i > 0)
    hit = [c for c in a.candidates if c["id"] in ids]
    df = {"key": "depressions", "candidates": [c["id"] for c in hit],
          "basis": "estimated: unconfirmed DEM depression candidates (priority-flood); no crater catalogue integrated",
          "detection_limits": {"min_depth_m": a.config["min_depth_m"],
                               "min_diameter_m": a.config.get("min_diameter_m"),
                               "min_pixels": MIN_CANDIDATE_PX, "pixel_m": w.pixel_m}}
    if low_cov:
        df["status"] = "insufficient"
        df["reason"] = f"Valid terrain covers {valid_pct:.1f}% of the footprint."
    elif hit:
        df["status"] = "hazard"
        df["reason"] = f"{len(hit)} unconfirmed depression candidate(s) intersect the footprint."
    elif coarse:
        df["status"] = "higher_res"
        df["reason"] = (f"The footprint spans {px_across:.1f} DEM pixels; depressions inside it cannot be resolved "
                        "at this resolution.")
    else:
        df["status"] = "none_detected"
        df["reason"] = ("No candidate intersects the footprint. Depressions smaller than about "
                        f"{math.sqrt(MIN_CANDIDATE_PX) * w.pixel_m:.0f} m or shallower than "
                        f"{a.config['min_depth_m']:g} m below their spill level are not detectable here.")
    df["status_text"] = STATUS_TEXT[df["status"]]
    findings.append(df)
    findings.append(_obstacles(w))
    return {**base, "pixels": npx, "coverage": cov, "findings": findings}


def _obstacles(w: Window) -> dict:
    return {"key": "obstacles", "status": "manual", "status_text": STATUS_TEXT["manual"], "basis": "unavailable",
            "reason": (f"No imagery-based obstacle product is registered. This screening uses {w.pixel_m:g} m DEM pixels, and "
                       "even the finest registered LOLA product (PGDA 78, 5 m pixels, about 90% of them interpolated "
                       "between laser tracks) cannot resolve boulders or other metre-scale obstacles. Orbital imagery "
                       "review is required; even then orbital data cannot guarantee that every landing hazard is found.")}


# ------------------------------------------------------------------ provenance and serialisation
def provenance(a: Assessment) -> dict:
    w, lv = a.win, a.win.rec
    em = w.error_map
    return {
        "landing_version": LANDING_VERSION, "landing_code_sha256": landing_code_hash(),
        "validation_status": VALIDATION_STATUS,
        "validation_note": ("The official LUNA-OPS validation report covers the science engine (backend/lunaops) "
                            "only. This screening package is outside that fingerprint and has not been validated."),
        "engine_code_fingerprint": code_fingerprint(),
        "dem": {"key": edem.product_key(lv), "product": lv.get("product"), "product_id": lv.get("product_id"),
                "file": lv.get("path"), "sha256": lv.get("sha256"), "pixel_m": lv.get("pixel_m"), "level": lv.get("level"),
                "page": lv.get("page"), "citation": lv.get("citation"), "frame": _frame_of(lv),
                "crs": "south polar stereographic on the 1737.4 km sphere (true scale at the pole), metres",
                "vertical": "height in metres above the 1737.4 km reference sphere",
                "synthetic": bool(lv.get("synthetic"))},
        "error_map": None if em is None else {"product": em.get("product"), "file": em.get("path"),
                                              "sha256": em.get("sha256"), "units": em.get("units")},
        "auxiliary": {k: {kk: e.get(kk) for kk in ("product", "path", "sha256", "units", "source_url", "citation", "frame")}
                      for k, e in w.aux_entries.items()},
        "window": {"bounds_xy_m": [_num(v, 1) for v in w.bounds], "pixels": [w.nrows, w.ncols],
                   "col0": w.col0, "row0": w.row0, "half_m_requested": a.config["window_half_m"],
                   "half_m_used": a.config["window_half_m_used"]},
        "config": a.config,
        "algorithms": {
            "slope": "Horn (1981) 3 x 3 weighted finite differences; spacing = pixel / k x (R + h) / R, k = projection "
                     "point scale; NaN if any of the 9 samples is missing",
            "roughness": f"RMS of residuals about the least-squares plane in a {a.rough_px} x {a.rough_px} window "
                         "(complete windows only)",
            "tri": "Terrain Ruggedness Index, Riley et al. (1999): sqrt of the sum of squared differences to the 8 neighbours",
            "depressions": "Priority-Flood depression filling (Barnes et al. 2014) seeded at the window edge and next to "
                           "missing data; 8-connected regions deeper than the configured minimum depth below their "
                           "spill level; size from area-equivalent diameter; shape from second moments",
            "depression_quality": {"defined": f"depth >= {Q_DEFINED_SIGMA:g} x mean RMS height uncertainty in the region, "
                                              f"axis ratio >= {Q_DEFINED_AXIS}, ellipse fill >= {Q_DEFINED_FILL}",
                                   "weak": "depth >= 1 x uncertainty but not 'defined'",
                                   "within_uncertainty": "depth < 1 x uncertainty",
                                   "shape_only": "no error map: depth cannot be compared with uncertainty",
                                   "note": "LUNA-OPS landing 0.1.0 screening convention, not a published criterion"},
            "obstacles": "not available (manual review required)",
        },
        "notes": w.notes,
        "limitations": [
            "Preliminary screening only: no result certifies a landing site as safe.",
            "Slope and roughness describe the DEM at its pixel scale; LOLA 5 m products are mostly interpolated "
            "between laser tracks, so their effective resolution is coarser than the pixel size.",
            "DEM roughness is not rock or boulder detection.",
            "Depression candidates are unconfirmed; they are not identified as impact craters. Depth is counted only "
            "below the level at which a hollow could drain to the window edge or to missing data, so hollows open to "
            "the edge or to a data gap, and depressions breached on slopes, are missed or measured shallower.",
            "Depth is measured below the spill level (lowest rim point), not from the rim crest.",
            "Thresholds are user-defined assumptions; no default or published landing limit is applied.",
        ],
    }


def to_json(a: Assessment) -> dict:
    return {"id": a.id, "config": a.config, "summary": a.summary, "candidates": a.candidates,
            "provenance": provenance(a), "status_text": STATUS_TEXT,
            "layers": layer_index(a)}


def layer_index(a: Assessment) -> list[dict]:
    w = a.win
    have = {"count": "count" in w.aux, "err": w.err is not None, "slope": "slope" in w.aux}
    L = [("elevation", "m", "measured/interpolated LOLA heights", True),
         ("slope", "deg", "calculated", True),
         ("roughness", "m", "calculated", True),
         ("coverage", "", "data coverage: missing, interpolated, measured", True),
         ("uncertainty", "m", "estimated: product-declared RMS height error", have["err"]),
         ("nasa_slope", "deg", "NASA PGDA slope product (cross-check)", have["slope"])]
    return [{"name": n, "unit": u, "basis": b, "available": ok} for n, u, b, ok in L]
