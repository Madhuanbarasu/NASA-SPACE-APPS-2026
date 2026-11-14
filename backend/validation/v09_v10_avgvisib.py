"""V-09 / V-10: average Sun and Earth visibility against the LOLA AVGVISIB maps (PGDA 69, Mazarico).

    python -m validation.v09_v10_avgvisib --sun-img AVGVISIB_85S_060M_201608.IMG \
        --earth-img AVGVISIB_85S_060M_201608_EARTH.IMG --out v09_v10.json

Reference (documented facts; labels stored in validation/reference/avgvisib/, provenance in
validation/reference/avgvisib/provenance.json):
- Value: the fraction of hourly timesteps in which any part of the disc is visible, from the PDS3 label
  ("the percentage of timesteps where each pixel was sunlit (by any fraction of the solar disc)";
  AVERAGE_VISIBILITY = DN * SCALING_FACTOR + OFFSET = DN * 0.00004, DN 25000 = 1). The EARTH product is the same
  quantity for Earth's disc; PGDA 69: "the Earth is considered visible if any part of its disc is not obscured".
  So both use the "any" rule.
- Time sampling: PGDA 69: "averaged over hourly timesteps spanning 18.6 years" (one lunar nutation cycle).
- Terrain: LDEM_85S_060M (label), 1737.4 km sphere, polar stereographic, DE421 mean-Earth frame. LUNA-OPS uses its
  own registered terrain, so terrain resolution and version differences are part of what is compared.
- Two label defects are recorded, not relied on: the IMAGE description calls the values "binary" (contradicting the
  product description and the data), and the EARTH label gives MINIMUM_LATITUDE = 90.

Not documented anywhere available, so recorded as assumptions (provenance "assumptions"):
- Observer height: neither label nor PGDA 69 states it. PGDA 69 says assessing "height above the surface (for
  potential rovers or habitats)" needs further analysis, which implies surface-level maps; 0 m is used.
- The epoch of the 18.6-year span: not stated. The default start is 2026-01-01 (as V-11); --start changes it.
- Whether the solar maps count Earth occulting the Sun: not stated. LUNA-OPS's "any" rule includes it; the number of
  hours it changes is recorded per point.

Method (vectorised, identical to the engine's "any" rule by construction):
- The Sun and Earth apparent positions are computed once per hour from the Moon's centre (SPICE spkcpo, the
  engine's frame and aberration correction), and per site by subtracting the site vector; this agrees with the
  engine's per-site sample_target to ~1e-6 deg (tested).
- Sun: the visible-or-not verdict is the sign of the exact spherical-cap top-edge clearance (disk_edges_many).
  Hours in which Earth's outer circle touches the Sun's disc are evaluated by the engine itself (full_state), so
  Earth occultation is exact.
- Earth: the oblate Earth's silhouette lies between the circles of angular radius beta = asin(b/d) and
  alpha = asin(a/d) about its centre (nested spheres, nested silhouettes): visible if the inner circle is, hidden if
  the outer circle is not; only hours where the two disagree are evaluated by the engine (full_state).
- Hours whose deciding clearance lies within GUARD_DEG of zero are also evaluated by the engine, so the small
  geometric approximation can never change a verdict.
A point is scored only with a complete horizon (no incomplete or non-finite bin, as V-11); otherwise it is
inconclusive and never scored.

Sampling (defined here, A10): deterministic stratified sampling of each map's pixels inside its documented complete
coverage (85-90 deg S: a pixel is used only if all four corners lie at or south of 85 deg S), in five equal-width
strata of the reference value [0, 0.2), [0.2, 0.4), [0.4, 0.6), [0.6, 0.8), [0.8, 1.0], N_POINTS / 5 per stratum,
drawn with numpy's default_rng([seed, stratum]). A stratum with too few pixels gives all it has and the shortfall
goes, one point at a time, to the strata with spare pixels in ascending order (allocate), so N_POINTS are drawn
whenever the coverage holds that many (recorded per stratum).

Criteria (approved by the owner and frozen for Phase 7, see CRITERIA): R1, locally smooth points (reference range
over the 3 x 3 pixel neighbourhood <= 5 pp), unweighted RMSE <= 2 pp and |bias| <= 1 pp; R2, all scored points
area-weighted by inclusion probability (N_h / n_h), RMSE <= 5 pp and |bias| <= 2 pp; R3, equal-weight statistics and
outliers, reported only. A run passes only when R1 and R2 are both met. A run shorter than 18.6 years is "not run", and
so is a run whose terrain does not meet the shared terrain acceptance gate (validation/terrain_gate.py; Phase 4 A6) or
that has fewer than 20 scored smooth points. Any inconclusive point makes the run "inconclusive". The Phase 7 holdout
draws with seed 20261114, excludes every pixel of the earlier inspected benchmark (--exclude-from) and runs points
frozen beforehand (--select-only, then --use-points with --expect-sha256).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

TESTS = {"V-09": "sun", "V-10": "earth"}
COVERAGE_LAT_DEG = -85.0      # readme_illumination_2016.txt: "complete coverage from 65 or 85 degrees to the poles"
STRATA = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)
N_POINTS = 200
YEARS = 18.6                  # PGDA 69: hourly timesteps spanning 18.6 years
STEP_S = 3600.0
GUARD_DEG = 1e-3              # numerical guard band (not a tolerance): verdicts this close to zero go to the engine
                              # itself; the hourly-track geometry differs from the engine's by < 3e-5 deg (tested)
# Approved by the owner for Phase 7 (2026-11-14) and frozen before the holdout was drawn
# (docs/validation_evidence/phase7_final_validation_2026-11-14/scientific_criteria/FROZEN_CRITERIA.md):
#   R1  locally smooth points (reference range over the 3 x 3 pixel neighbourhood, +-60 m, <= 5 pp): unweighted
#       RMSE <= 2 pp and |bias| <= 1 pp, evaluable with at least 20 scored smooth points;
#   R2  all scored points, area-weighted (inclusion probabilities N_h / n_h per stratum): RMSE <= 5 pp, |bias| <= 2 pp;
#   R3  equal-weight RMSE / bias, max |d|, outliers: reported, never a gate.
# Before Phase 7 a single provisional rule (equal-weight RMSE <= 5, |bias| <= 2, unapproved) applied; it is replaced.
CRITERIA = {"approved": True, "approved_utc": "2026-11-14",
            "r1": {"rmse_pp": 2.0, "abs_bias_pp": 1.0, "smooth_range_max": 0.05, "min_points": 20,
                   "statistic": "unweighted, scored points whose reference 3 x 3 range <= 5 pp"},
            "r2": {"rmse_pp": 5.0, "abs_bias_pp": 2.0,
                   "statistic": "area-weighted (Horvitz-Thompson weights N_h / n_h), all scored points"},
            "r3": "equal-weight RMSE and bias, max |d|, outliers |d| > 10 pp: diagnostic, not a gate",
            "observer_height": "0 m project modelling assumption; NASA's observer height is not documented"}
SMOOTH_RANGE_MAX = 0.05
HOLDOUT_SEED = 20261114
REFERENCE_DIR = Path(__file__).resolve().parent / "reference" / "avgvisib"


# ------------------------------------------------------------------ PDS3 label and image
def parse_label(text: str) -> dict:
    """Minimal PDS3 label parser: KEY = VALUE pairs, nested OBJECT blocks, quoted (multi-line) strings,
    {...} lists and <unit> suffixes (returned as (number, unit))."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    root: dict = {}
    stack = [root]
    toks = re.finditer(r'(\^?[A-Z_][A-Z0-9_:]*)\s*=\s*("(?:[^"]*)"|\{[^}]*\}|\'[^\']*\'|[^\n]*)', text)
    for m in toks:
        key, raw = m.group(1), m.group(2).strip()
        if key == "OBJECT":
            child: dict = {}
            stack[-1][raw] = child
            stack.append(child)
            continue
        if key == "END_OBJECT":
            if len(stack) > 1:
                stack.pop()
            continue
        stack[-1][key] = _value(raw)
    return root


def _value(raw: str):
    if raw.startswith('"'):
        return " ".join(raw.strip('"').split())
    if raw.startswith("{"):
        return [" ".join(v.strip().strip('"').split()) for v in raw.strip("{}").split('","')]
    if raw.startswith("'"):
        return raw.strip("'")
    m = re.fullmatch(r"([-+0-9.eE]+)\s*<([^>]*)>", raw)
    if m:
        return (float(m.group(1)), m.group(2).strip())
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        return raw


def _num(v) -> float:
    return float(v[0] if isinstance(v, tuple) else v)


def read_avgvisib(img_path: str, label_path: str | None = None) -> tuple[np.ndarray, dict]:
    """The map as visibility fraction (float64) and its metadata, after checking the encoding against the label:
    16-bit LSB integers of the stated size, SCALING_FACTOR 0.00004, OFFSET 0, every DN in [0, 25000]; polar
    stereographic on the 1737.4 km sphere centred on the pole."""
    img = Path(img_path)
    lbl = Path(label_path) if label_path else _label_next_to(img)
    lab = parse_label(lbl.read_text(errors="replace"))
    im = lab["UNCOMPRESSED_FILE"]["IMAGE"]
    pr = lab["IMAGE_MAP_PROJECTION"]
    lines, samples = int(im["LINES"]), int(im["LINE_SAMPLES"])
    problems = []
    if im.get("SAMPLE_TYPE") != "LSB_INTEGER" or int(im.get("SAMPLE_BITS", 0)) != 16:
        problems.append(f"sample type {im.get('SAMPLE_TYPE')}/{im.get('SAMPLE_BITS')} is not 16-bit LSB_INTEGER")
    if img.stat().st_size != lines * samples * 2:
        problems.append(f"file has {img.stat().st_size} bytes, label implies {lines * samples * 2}")
    scale, offset = float(im["SCALING_FACTOR"]), float(im["OFFSET"])
    if scale != 0.00004 or offset != 0.0:
        problems.append(f"scaling {scale}/{offset} differs from the documented 0.00004/0")
    if pr.get("MAP_PROJECTION_TYPE") != "POLAR STEREOGRAPHIC" or _num(pr["A_AXIS_RADIUS"]) != 1737.4 \
            or _num(pr["CENTER_LATITUDE"]) != -90:
        problems.append("projection is not south polar stereographic on the 1737.4 km sphere")
    if problems:
        raise ValueError(f"{img.name}: " + "; ".join(problems))
    dn = np.fromfile(img, dtype="<i2").reshape(lines, samples)
    bad = int(np.sum((dn < 0) | (dn > 25000)))
    if bad:
        raise ValueError(f"{img.name}: {bad} DN values outside [0, 25000]")
    mscale, s0, l0, gt = projection(lab)
    meta = {"product_id": lab.get("PRODUCT_ID"), "file": img.name, "label": lbl.name,
            "lines": lines, "samples": samples, "scaling_factor": scale, "offset": offset,
            "map_scale_m": mscale, "sample_projection_offset": s0, "line_projection_offset": l0,
            "radius_km": _num(pr["A_AXIS_RADIUS"]), "frame": pr.get("COORDINATE_SYSTEM_NAME"),
            "derived_maximum_dn": im.get("DERIVED_MAXIMUM"), "start_time": lab.get("START_TIME"),
            "stop_time": lab.get("STOP_TIME"), "description": lab.get("DESCRIPTION"),
            "image_description": im.get("DESCRIPTION"), "dn_min": int(dn.min()), "dn_max": int(dn.max()),
            "sha256": _sha256(img), "label_sha256": _sha256(lbl), "geotransform": gt}
    return dn.astype(np.float64) * scale + offset, meta


def projection(lab: dict) -> tuple[float, float, float, list[float]]:
    """Map scale (m), sample and line projection offsets, and the GDAL-style geotransform of the pixel grid.
    PDS polar stereographic (1-based sample s, line l): x = (s - S0 - 1) * scale, y = (L0 - l + 1) * scale, i.e. for
    0-based (col, row) pixel centres x = (col - S0) * scale, y = (L0 - row) * scale."""
    pr = lab["IMAGE_MAP_PROJECTION"]
    ms = pr["MAP_SCALE"]
    mscale = _num(ms) * (1000.0 if isinstance(ms, tuple) and ms[1].lower().startswith("km") else 1.0)
    s0, l0 = _num(pr["SAMPLE_PROJECTION_OFFSET"]), _num(pr["LINE_PROJECTION_OFFSET"])
    return mscale, s0, l0, [mscale, 0.0, -(s0 + 0.5) * mscale, 0.0, -mscale, (l0 + 0.5) * mscale]


def _label_next_to(img: Path) -> Path:
    for cand in (img.with_suffix(".lbl"), img.with_suffix(".LBL"), REFERENCE_DIR / (img.stem.lower() + ".lbl")):
        if cand.exists():
            return cand
    raise FileNotFoundError(f"no PDS label for {img}")


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def pixel_xy(meta: dict, rows: np.ndarray, cols: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    s = meta["map_scale_m"]
    return (cols - meta["sample_projection_offset"]) * s, (meta["line_projection_offset"] - rows) * s


def xy_to_latlon(x, y, radius_m: float = 1737400.0):
    """South polar stereographic (true scale at the pole, sphere) to planetocentric lat, east lon (deg)."""
    r = np.hypot(x, y)
    lat = -(90.0 - np.degrees(2.0 * np.arctan(r / (2.0 * radius_m))))
    lon = np.degrees(np.arctan2(x, y)) % 360.0
    return lat, lon


# ------------------------------------------------------------------ stratified sampling
def allocate(n: int, capacity: list[int]) -> list[int]:
    """Points per stratum: n // k each (n % k extra to the lowest strata), capped by each stratum's pixels; any
    shortfall is handed out one point at a time to the strata with spare pixels, in ascending order."""
    k = len(capacity)
    want = [n // k + (1 if j < n % k else 0) for j in range(k)]
    alloc = [min(w, c) for w, c in zip(want, capacity)]
    left = n - sum(alloc)
    while left > 0 and any(a < c for a, c in zip(alloc, capacity)):
        for j in range(k):
            if left and alloc[j] < capacity[j]:
                alloc[j] += 1
                left -= 1
    return alloc


def stratified_points(frac: np.ndarray, meta: dict, n: int = N_POINTS, seed: int = 1,
                      strata=STRATA, lat_limit: float = COVERAGE_LAT_DEG,
                      exclude: set | None = None) -> tuple[list[dict], dict]:
    """Deterministic stratified sample of pixels inside the documented coverage (all four pixel corners at or south
    of lat_limit), n / len(strata) - 1 per equal-width stratum of the reference value. exclude: (row, col) pixels
    that may not be drawn (Phase 7 holdout: every pixel of the previously inspected benchmark); each stratum's
    eligible pixel count is recorded as `pixels` (the N_h of the area weights)."""
    radius_m = meta["radius_km"] * 1000.0
    r_lim = 2.0 * radius_m * math.tan(math.radians(90.0 + lat_limit) / 2.0)
    s = meta["map_scale_m"]
    rows, cols = np.indices(frac.shape)
    x, y = pixel_xy(meta, rows, cols)
    far = np.hypot(np.abs(x) + s / 2.0, np.abs(y) + s / 2.0)        # farthest corner from the pole
    covered = far <= r_lim
    k = len(strata) - 1
    pools = []
    for j in range(k):
        a, b = strata[j], strata[j + 1]
        pool = np.flatnonzero(covered & (frac >= a) & ((frac < b) if j < k - 1 else (frac <= b)))
        if exclude:
            ex = np.array([r_ * frac.shape[1] + c_ for r_, c_ in exclude], dtype=np.int64)
            pool = pool[~np.isin(pool, ex)]
        pools.append(pool)
    alloc = allocate(n, [p.size for p in pools])
    pts, info = [], {"strata": [], "coverage_lat_limit_deg": lat_limit, "pixels_in_coverage": int(covered.sum()),
                     "nominal_per_stratum": n // k, "seed": seed, "requested": n,
                     "excluded_pixels": len(exclude or ())}
    for j in range(k):
        idx = pools[j]
        rng = np.random.default_rng([seed, j])
        take = np.sort(rng.choice(idx.size, size=alloc[j], replace=False)) if alloc[j] else np.array([], int)
        info["strata"].append({"range": [strata[j], strata[j + 1]], "pixels": int(idx.size), "sampled": int(take.size)})
        for t in take:
            r_, c_ = divmod(int(idx[t]), frac.shape[1])
            xx, yy = pixel_xy(meta, np.array(r_), np.array(c_))
            lat, lon = xy_to_latlon(xx, yy, radius_m)
            nb = frac[max(r_ - 1, 0):r_ + 2, max(c_ - 1, 0):c_ + 2]
            pts.append({"stratum": j, "row": r_, "col": c_, "x_m": float(xx), "y_m": float(yy), "lat": float(lat),
                        "lon": float(lon), "reference": float(frac[r_, c_]),
                        "reference_3x3_min": float(nb.min()), "reference_3x3_max": float(nb.max()),
                        "smooth": bool(float(nb.max()) - float(nb.min()) <= SMOOTH_RANGE_MAX + 1e-12)})
    info["points"] = len(pts)
    return pts, info


# ------------------------------------------------------------------ hourly track and visibility
def track(start: str, years: float = YEARS, step_s: float = STEP_S) -> dict:
    """Apparent Sun and Earth positions (km, Moon body-fixed frame) from the Moon's centre, hourly."""
    import spiceypy as sp
    from lunaops import settings
    from lunaops.engine.kernels import SPICE_LOCK, load
    from lunaops.engine.timeutil import parse_utc
    ks = load()
    ets = parse_utc(start) + step_s * np.arange(int(round(years * 365.25 * 86400.0 / step_s)))
    out = {"ets": ets, "start": start, "years": years, "step_s": step_s}
    for name, key in (("SUN", "sun"), ("EARTH", "earth")):
        pos = np.empty((ets.size, 3))
        with SPICE_LOCK:
            for i, et in enumerate(ets):
                st, _ = sp.spkcpo(name, float(et), ks.frame, "OBSERVER", settings.ABCORR, [0.0, 0.0, 0.0], "MOON",
                                  ks.frame)
                pos[i] = st[:3]
        out[key] = pos
    return out


def topocentric(site, pos_km: np.ndarray) -> dict:
    """Azimuth, elevation (deg), distance (km) and unit vector of a body seen from the site."""
    e, n, u = site.basis
    v = pos_km - site.pos_km
    d = np.linalg.norm(v, axis=1)
    rh = v / d[:, None]
    el = np.degrees(np.arcsin(np.clip(rh @ u, -1.0, 1.0)))
    az = np.degrees(np.arctan2(rh @ e, rh @ n)) % 360.0
    return {"az": az, "el": el, "d": d, "unit": rh}


def visible_any(site, hp, target: str, trk: dict, guard: float = GUARD_DEG, exact=None) -> tuple[np.ndarray, dict]:
    """Per-hour "any part of the disc visible" for target, identical to the engine's "any" rule.
    exact(i) -> bool | None gives the engine's own verdict for hour i (default: full_state on an EventDetector)."""
    from lunaops import settings
    from lunaops.engine.earth import intrinsic_radii
    from lunaops.engine.visibility import disk_edges_many
    ets = trk["ets"]
    if exact is None:
        exact = _engine_exact(site, hp, target, ets)
    sun = topocentric(site, trk["sun"])
    earth = topocentric(site, trk["earth"])
    alpha, beta = (np.degrees(x) for x in intrinsic_radii(earth["d"]))
    stats = {"hours": int(ets.size)}
    if target == "sun":
        rho = np.degrees(np.arcsin(settings.R_SUN_KM / sun["d"]))
        g = disk_edges_many(hp, sun["az"], sun["el"], rho)["g_top"]
        vis = g > guard
        amb = np.abs(g) <= guard
        gamma = np.degrees(np.arccos(np.clip(np.sum(sun["unit"] * earth["unit"], axis=1), -1.0, 1.0)))
        touch = gamma < rho + alpha + guard                   # Earth's outer circle reaches the Sun's disc
        stats["earth_touching_sun_hours"] = int(np.sum(touch))
        terrain_vis = vis.copy()
        amb |= vis & touch
        vis &= ~touch
    elif target == "earth":
        g_in = disk_edges_many(hp, earth["az"], earth["el"], beta)["g_top"]
        g_out = disk_edges_many(hp, earth["az"], earth["el"], alpha)["g_top"]
        vis = g_in > guard
        hidden = g_out < -guard
        amb = ~(vis | hidden)
    else:
        raise ValueError(target)
    idx = np.flatnonzero(amb)
    unknown = 0
    for i in idx:
        v = exact(int(i))
        if v is None:
            unknown += 1
            v = False
        vis[i] = bool(v)
    stats.update({"exact_hours": int(idx.size), "exact_unknown": unknown, "visible_hours": int(np.sum(vis))})
    if target == "sun":
        # hours whose terrain-only verdict was "visible" but the engine (with Earth) says hidden
        stats["hidden_by_earth_hours"] = int(np.sum(terrain_vis & ~vis))
    return vis, stats


def _engine_exact(site, hp, target: str, ets: np.ndarray):
    from lunaops.engine.events import EventConfig, EventDetector, full_state
    det = EventDetector(site, hp, EventConfig())
    key = f"{target}_any"
    return lambda i: full_state(det, float(ets[i]))["rules"][key]


# ------------------------------------------------------------------ per point and scoring
def evaluate_point(lat: float, lon: float, target: str, trk: dict, obs_h_m: float = 0.0, horizon_fn=None) -> dict:
    """Computed average visibility at one point (fraction of the track's hours), or inconclusive."""
    from lunaops.engine.dem import TerrainError
    from lunaops.engine.ephem import Site
    from lunaops.engine.horizon import compute_horizon
    from lunaops.engine.visibility import HorizonProfile
    try:
        hz = (horizon_fn or compute_horizon)(lat, lon, obs_h_m)
    except TerrainError as exc:
        return {"outcome": "inconclusive", "reason": f"no terrain horizon: {exc}"[:300]}
    h = np.asarray(hz.h_deg, dtype=float)
    inc = np.asarray(hz.incomplete, dtype=bool) | ~np.isfinite(h)
    rec = {"incomplete_bins": int(inc.sum()), "ground_h_m": float(getattr(hz, "ground_h_m", 0.0)),
           "h_max_m": (getattr(hz, "params", None) or {}).get("h_max_m")}
    if inc.any():
        return {**rec, "outcome": "inconclusive",
                "reason": f"{int(inc.sum())} of {inc.size} horizon bins incomplete"}
    flags = hz.flag_arrays() if hasattr(hz, "flag_arrays") else None
    hp = HorizonProfile(h, inc, getattr(hz, "sigma_deg", None), flags=flags)
    site = Site(lat, lon, rec["ground_h_m"], obs_h_m)
    vis, stats = visible_any(site, hp, target, trk)
    if stats["exact_unknown"]:
        return {**rec, **stats, "outcome": "inconclusive", "reason": "engine verdict unknown at some hours"}
    return {**rec, **stats, "outcome": "scored", "computed": float(vis.mean())}


def _rmse_bias(d: np.ndarray, w: np.ndarray | None = None) -> tuple[float | None, float | None]:
    if d.size == 0:
        return None, None
    w = np.ones_like(d) if w is None else w
    return float(np.sqrt(np.sum(w * d * d) / np.sum(w))), float(np.sum(w * d) / np.sum(w))


def _is_smooth(p: dict) -> bool:
    if "smooth" in p:
        return bool(p["smooth"])
    if "reference_3x3_max" in p and "reference_3x3_min" in p:
        return (p["reference_3x3_max"] - p["reference_3x3_min"]) <= SMOOTH_RANGE_MAX + 1e-12
    return False


def score(points: list[dict], years: float, criteria: dict = CRITERIA,
          prerequisites: tuple[bool, str] = (False, "not checked"),
          stratum_pixels: dict | None = None) -> tuple[str, dict, str]:
    """Metrics in percentage points and the status under the approved Phase 7 criteria (R1, R2 gates; R3 diagnostic).
    stratum_pixels: {stratum: eligible pixels N_h} for the area weights N_h / n_h (n_h = scored points of the stratum);
    without it every scored point weighs the same. prerequisites: (ok, reasons) of the shared terrain acceptance gate."""
    sc = [p for p in points if p.get("outcome") == "scored"]
    inc = [p for p in points if p.get("outcome") != "scored"]
    d = np.array([100.0 * (p["computed"] - p["reference"]) for p in sc])
    n_h: dict = {}
    for p in sc:
        n_h[p["stratum"]] = n_h.get(p["stratum"], 0) + 1
    if stratum_pixels:
        w = np.array([stratum_pixels[p["stratum"]] / n_h[p["stratum"]] for p in sc], dtype=float)
    else:
        w = np.ones(len(sc))
    smooth = np.array([_is_smooth(p) for p in sc], dtype=bool)
    eq_rmse, eq_bias = _rmse_bias(d)
    aw_rmse, aw_bias = _rmse_bias(d, w)
    r1_rmse, r1_bias = _rmse_bias(d[smooth]) if smooth.any() else (None, None)
    r1w_rmse, r1w_bias = _rmse_bias(d[smooth], w[smooth]) if smooth.any() else (None, None)
    m = {"points": len(points), "scored": len(sc), "inconclusive": len(inc),
         "rmse_pp": eq_rmse, "bias_pp": eq_bias, "max_abs_pp": float(np.max(np.abs(d))) if d.size else None,
         "area_weighted": {"rmse_pp": aw_rmse, "bias_pp": aw_bias, "weights": "N_h / n_h" if stratum_pixels else "equal"},
         "smooth": {"points": int(smooth.sum()), "rmse_pp": r1_rmse, "bias_pp": r1_bias,
                    "area_weighted_rmse_pp": r1w_rmse, "area_weighted_bias_pp": r1w_bias},
         "outliers": [{"lat": p.get("lat"), "lon": p.get("lon"), "stratum": p["stratum"], "reference": p["reference"],
                       "computed": p["computed"], "d_pp": float(di)} for p, di in zip(sc, d) if abs(di) > 10.0],
         "per_stratum": []}
    for j in sorted({p["stratum"] for p in points}):
        dj = np.array([100.0 * (p["computed"] - p["reference"]) for p in sc if p["stratum"] == j])
        rj, bj = _rmse_bias(dj)
        m["per_stratum"].append({"stratum": j, "scored": int(dj.size), "rmse_pp": rj, "bias_pp": bj,
                                 "eligible_pixels": (stratum_pixels or {}).get(j)})
    r1c, r2c = criteria.get("r1", {}), criteria.get("r2", {})
    r1_ok = bool(r1_rmse is not None and r1_rmse <= r1c.get("rmse_pp", -1) and abs(r1_bias) <= r1c.get("abs_bias_pp", -1))
    r2_ok = bool(aw_rmse is not None and aw_rmse <= r2c.get("rmse_pp", -1) and abs(aw_bias) <= r2c.get("abs_bias_pp", -1))
    r1_evaluable = int(smooth.sum()) >= r1c.get("min_points", 20)
    m["gates"] = {"R1": {"met": r1_ok, "evaluable": bool(r1_evaluable)}, "R2": {"met": r2_ok}}
    full = years >= YEARS - 1e-9
    gate_ok, gate_why = prerequisites
    if not criteria.get("approved") or not full or not sc or not gate_ok or not r1_evaluable:
        status = "not run"
    elif inc:
        status = "inconclusive"
    else:
        status = "passed" if (r1_ok and r2_ok) else "failed"
    fmt = (lambda v: "n/a" if v is None else f"{v:.2f}")
    detail = (f"{m['scored']}/{m['points']} points scored ({m['inconclusive']} inconclusive) over {years:g} years; "
              f"R1 smooth ({m['smooth']['points']} points): RMSE {fmt(r1_rmse)} pp, bias {fmt(r1_bias)} pp "
              f"(limits {r1c.get('rmse_pp')} / {r1c.get('abs_bias_pp')}: {'met' if r1_ok else 'not met'}); "
              f"R2 area-weighted: RMSE {fmt(aw_rmse)} pp, bias {fmt(aw_bias)} pp "
              f"(limits {r2c.get('rmse_pp')} / {r2c.get('abs_bias_pp')}: {'met' if r2_ok else 'not met'}); "
              f"R3 (diagnostic) equal-weight RMSE {fmt(eq_rmse)} pp, bias {fmt(eq_bias)} pp, max |d| {fmt(m['max_abs_pp'])} pp")
    if not criteria.get("approved"):
        detail += "; criteria not approved, so no pass/fail is reported"
    if not r1_evaluable:
        detail += f"; R1 not evaluable (fewer than {r1c.get('min_points', 20)} scored smooth points)"
    if not full:
        detail += f"; PARTIAL (needs {YEARS} years)"
    if not gate_ok:
        detail += f"; PRELIMINARY (terrain gate not met: {gate_why})"
    return status, m, detail


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sun-img", help="AVGVISIB_85S_060M_201608.IMG (V-09)")
    ap.add_argument("--earth-img", help="AVGVISIB_85S_060M_201608_EARTH.IMG (V-10)")
    ap.add_argument("--points", type=int, default=N_POINTS)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--start", default="2026-01-01T00:00:00Z")
    ap.add_argument("--years", type=float, default=YEARS)
    ap.add_argument("--observer-height-m", type=float, default=0.0)
    ap.add_argument("--out", default="v09_v10.json")
    ap.add_argument("--exclude-from", action="append", default=[],
                    help="earlier result JSON whose sampled pixels may not be drawn again (independent holdout)")
    ap.add_argument("--select-only", metavar="DIR", help="write the selected points per test to DIR and stop")
    ap.add_argument("--use-points", action="append", default=[], metavar="TEST=FILE",
                    help="run exactly these frozen points (written by --select-only)")
    ap.add_argument("--expect-sha256", action="append", default=[], metavar="TEST=HEX",
                    help="refuse to run unless the frozen points file has this SHA-256")
    a = ap.parse_args()
    if not (a.sun_img or a.earth_img):
        sys.exit("give --sun-img and/or --earth-img")
    exclude = set()
    for f in a.exclude_from:
        prev = json.loads(Path(f).read_text())
        for r in (prev.get("results") or {}).values():
            exclude |= {(int(p["row"]), int(p["col"])) for p in r.get("points", [])}
    use = dict(x.split("=", 1) for x in a.use_points)
    expect = dict(x.split("=", 1) for x in a.expect_sha256)
    if a.select_only:
        Path(a.select_only).mkdir(parents=True, exist_ok=True)
        for tid, img in (("V-09", a.sun_img), ("V-10", a.earth_img)):
            if img:
                frac, meta = read_avgvisib(img)
                pts, sampling = stratified_points(frac, meta, a.points, a.seed, exclude=exclude)
                f = Path(a.select_only) / f"{tid}_points.json"
                f.write_text(json.dumps({"test": tid, "seed": a.seed, "sampling": sampling, "reference": meta,
                                         "points": pts}, indent=1, default=float))
                print(tid, len(pts), "points ->", f, _sha256(f))
        return
    trk = track(a.start, a.years)
    out = {"tests": {}, "criteria": CRITERIA, "assumptions": {
               "observer_height_m": a.observer_height_m, "start_utc": a.start, "years": a.years,
               "earth_occults_sun": "included (engine 'any' rule)",
               "notes": "observer height and start epoch are not documented for AVGVISIB (see provenance.json)"},
           "results": {}}
    from lunaops.engine.dem import products_digest
    from validation import terrain_gate
    gate = terrain_gate.evaluate()
    for tid, img in (("V-09", a.sun_img), ("V-10", a.earth_img)):
        if not img:
            continue
        target = TESTS[tid]
        frac, meta = read_avgvisib(img)
        if tid in use:
            fp = Path(use[tid])
            if tid in expect and _sha256(fp) != expect[tid]:
                sys.exit(f"{tid}: frozen points file {fp} does not match the expected SHA-256; refusing to run")
            frozen = json.loads(fp.read_text())
            pts, sampling = frozen["points"], {**frozen["sampling"], "frozen_points_file": fp.name,
                                               "frozen_points_sha256": _sha256(fp)}
        else:
            pts, sampling = stratified_points(frac, meta, a.points, a.seed, exclude=exclude)
        for p in pts:
            p.update(evaluate_point(p["lat"], p["lon"], target, trk, a.observer_height_m))
            print(json.dumps({k: p.get(k) for k in ("lat", "lon", "reference", "computed", "outcome")}), flush=True)
        npx = {k: st["pixels"] for k, st in enumerate(sampling["strata"])}
        status, metrics, detail = score(pts, a.years, CRITERIA, (gate["ok"], "; ".join(gate["reasons"])), npx)
        out["tests"][tid] = {"status": status, "detail": detail}
        out["results"][tid] = {"target": target, "reference": meta, "sampling": sampling, "metrics": metrics,
                               "points": pts}
    out["terrain_products"] = products_digest()
    from validation.common import run_meta
    out["meta"] = {**run_meta("v09_v10_avgvisib"), "terrain_gate": gate}
    Path(a.out).write_text(json.dumps(out, indent=2, default=float))
    print(json.dumps(out["tests"], indent=2))


if __name__ == "__main__":
    main()
