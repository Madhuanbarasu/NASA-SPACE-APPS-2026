"""V-12: Sun visibility against the LROC WAC south-pole illumination maps (observed, one lunar year).

    python -m validation.v12_lroc --twi-img WAC_POLE_ILL_TWI_SOUTH_100M.IMG --pct-img WAC_POLE_ILL_PCT_SOUTH_100M.IMG \
        [--avgvisib-img AVGVISIB_85S_060M_201608.IMG] --out v12.json

Reference (LROLRC_2001 BDR WAC_POLE, v1.3; fixtures and provenance in validation/reference/lroc/):
- WAC_POLE_ILL_TWI_SOUTH_100M (time-weighted: sparse periods weigh double, gaps linearly interpolated) is the primary
  reference; WAC_POLE_ILL_PCT_SOUTH_100M (plain lit/imaged ratio) is a secondary sensitivity comparison.
- Percent of observations in which the 100 m pixel was classified lit ("a series of spatial filters and a conservative
  global threshold"), from 3807 WAC images taken 2010-02-15 to 2011-02-05 (+229 gap fills), 88-90 deg S.
- Encoding: PC_REAL 32-bit, 1214 x 1214, image after the attached PDS3 header at byte 9712 (^IMAGE = 3 records of
  4856 bytes). The PDS4 label's Array offset (4856) is wrong: it points into the header (recorded in provenance).
  CORE_NULL and the saturation constants (0xFF7FFFFB-F) are missing data. Polar stereographic, 1737.4 km sphere,
  geotransform [100, 0, -60700, 0, -100, 60700], equal to LROC's own GeoTIFF browse product.
- The binary threshold is not quantified in the PDS documents; Speyerer & Robinson (2013) could not be obtained
  through an authorized route here (see provenance).

Comparison (approved methodology, A12):
- Period 2010-02-15T00:00:00Z to 2011-02-05T00:00:00Z, observer 0 m (LROC observes the surface itself), uniform
  time sampling (STEP_S) as the analogue of the time-weighted map.
- LUNA-OPS Sun visibility under the whole-disc ("full") and any-part ("any") rules bracket the unquantified threshold;
  the centre rule is reported for diagnosis. Each rule is computed exactly as the engine's rule_state, vectorised:
  the deciding clearance from the exact spherical cap (disk_edges_many), with hours within GUARD_DEG of zero and hours
  in which Earth's outer circle reaches the Sun's disc decided by the engine itself (full_state).
- The central LROC pixel is compared with the point at its centre; its 3 x 3 neighbourhood is reported separately.
- A point is scored only with a complete horizon (as V-10/V-11); otherwise it is inconclusive.
Criteria:
- C1 (gating): every scored sample that LUNA-OPS predicts permanently shadowed over the period (any-rule fraction 0)
  has LROC TWI <= C1_MAX_PCT (1 %). PCT is reported for the same samples.
- C2 (reported, non-gating): share of samples with TWI inside [full - s, any + s] for s = 0, 1.31 pp (TWI-PCT RMS) and
  3.0 pp (TWI-PCT p95). No pass share is defined.
- C3 (reported benchmark): RMSE of each LUNA-OPS rule against TWI beside the RMSE of LOLA AVGVISIB (100 m block mean)
  against TWI at the same samples.
Status: a run is final only if the shared terrain acceptance gate is met (validation/terrain_gate.py: the A5 20 m and
the wider 240 m terrain registered and present, and every overlapping product pair accepted in A6 for the exact
registered DEM and error-map bytes); otherwise it is "not run" (preliminary) with its metrics. With them: "failed" if C1 fails,
"inconclusive" if any sample is inconclusive or no predicted permanent-shadow sample exists, else "passed".
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
from validation.v09_v10_avgvisib import allocate, parse_label, topocentric, track, xy_to_latlon  # noqa: E402

PERIOD = ("2010-02-15T00:00:00Z", "2011-02-05T00:00:00Z")   # WAC_POLE_ILL README: the map's observation year
OBS_H_M = 0.0
STEP_S = 600.0               # uniform time sampling of the comparison (numerical; sensitivity in the evidence)
IMAGE_OFFSET = 9712          # verified: (^IMAGE - 1) * RECORD_BYTES of the attached PDS3 header
PDS4_LABEL_OFFSET = 4856     # what the PDS4 label states (defect)
SPECIAL_MIN = 0xFF7FFFFB     # CORE_NULL ... CORE_HIGH_REPR_SATURATION
STRATA = (0.0, 1.0, 10.0, 20.0, 30.0, 45.0, 100.0)          # TWI percent
N_POINTS = 200
C1_MAX_PCT = 1.0             # approved
C2_SLACKS_PP = (0.0, 1.31, 3.0)                            # approved for reporting: TWI-PCT RMS and p95 (measured)
GUARD_DEG = 1e-3
RULES = ("any", "centre", "full")
REFERENCE_DIR = Path(__file__).resolve().parent / "reference" / "lroc"


# ------------------------------------------------------------------ reader
def read_header(img_path: str) -> tuple[dict, str]:
    """The attached PDS3 header (text up to its standalone END line), parsed."""
    import re
    with open(img_path, "rb") as f:
        head = f.read(65536)
    m = re.search(rb"\r?\nEND[ \t]*\r?\n", head)
    if not m:
        raise ValueError(f"{img_path}: no PDS3 END line in the first 64 KiB")
    text = head[:m.end()].decode("ascii", errors="replace")
    return parse_label(text), text


def read_lroc(img_path: str) -> tuple[np.ndarray, dict]:
    """The map in percent (float64, NaN where missing) and its metadata, after checking the attached PDS3 header:
    image start, 32-bit PC_REAL, 1214 x 1214 (or as stated), file size, polar stereographic on the 1737.4 km sphere."""
    img = Path(img_path)
    lab, text = read_header(str(img))
    im, pr = lab["IMAGE"], lab["IMAGE_MAP_PROJECTION"]
    rb, nlab, ptr = int(lab["RECORD_BYTES"]), int(lab["LABEL_RECORDS"]), int(lab["^IMAGE"])
    lines, samples = int(im["LINES"]), int(im["LINE_SAMPLES"])
    offset = (ptr - 1) * rb
    problems = []
    if offset != nlab * rb:
        problems.append(f"^IMAGE record {ptr} is not right after the {nlab} label records")
    if im.get("SAMPLE_TYPE") != "PC_REAL" or int(im.get("SAMPLE_BITS", 0)) != 32:
        problems.append(f"sample type {im.get('SAMPLE_TYPE')}/{im.get('SAMPLE_BITS')} is not 32-bit PC_REAL")
    if img.stat().st_size != offset + lines * samples * 4:
        problems.append(f"file has {img.stat().st_size} bytes, header implies {offset + lines * samples * 4}")
    if pr.get("MAP_PROJECTION_TYPE") != "POLAR STEREOGRAPHIC" or float(pr["A_AXIS_RADIUS"][0]) != 1737.4 \
            or float(pr["CENTER_LATITUDE"][0]) != -90:
        problems.append("projection is not south polar stereographic on the 1737.4 km sphere")
    if problems:
        raise ValueError(f"{img.name}: " + "; ".join(problems))
    u = np.fromfile(img, dtype="<u4", offset=offset, count=lines * samples).reshape(lines, samples)
    special = u >= SPECIAL_MIN
    v = u.view("<f4").astype(np.float64)
    v[special] = np.nan
    if np.nanmax(v) > 100.0 + 1e-6 or np.nanmin(v) < -1e-3:
        raise ValueError(f"{img.name}: values outside 0-100 % (wrong image offset?)")
    scale = float(pr["MAP_SCALE"][0])
    s0, l0 = float(pr["SAMPLE_PROJECTION_OFFSET"][0]), float(pr["LINE_PROJECTION_OFFSET"][0])
    meta = {"product_id": lab.get("PRODUCT_ID"), "version": lab.get("PRODUCT_VERSION_ID"), "file": img.name,
            "image_offset": offset, "lines": lines, "samples": samples, "map_scale_m": scale,
            "sample_projection_offset": s0, "line_projection_offset": l0,
            "geotransform": [scale, 0.0, -(s0 + 0.5) * scale, 0.0, -scale, (l0 + 0.5) * scale],
            "missing_pixels": int(special.sum()), "valid_pixels": int(np.isfinite(v).sum()),
            "min": float(np.nanmin(v)), "max": float(np.nanmax(v)), "creation": lab.get("PRODUCT_CREATION_TIME"),
            "sha256": _hash(img, "sha256"), "md5": _hash(img, "md5")}
    return v, meta


def _hash(p: Path, algo: str) -> str:
    h = hashlib.new(algo)
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def pixel_xy(meta: dict, rows, cols):
    s = meta["map_scale_m"]
    return (np.asarray(cols) - meta["sample_projection_offset"]) * s, (meta["line_projection_offset"] - np.asarray(rows)) * s


# ------------------------------------------------------------------ sampling
def neighbourhood(a: np.ndarray, r: int, c: int) -> dict:
    nb = a[r - 1:r + 2, c - 1:c + 2]
    return {"min": float(np.min(nb)), "max": float(np.max(nb)), "mean": float(np.mean(nb)), "std": float(np.std(nb))}


def sample_pixels(twi: np.ndarray, meta: dict, n: int = N_POINTS, seed: int = 1, strata=STRATA,
                  pct: np.ndarray | None = None) -> tuple[list[dict], dict]:
    """Deterministic stratified sample of TWI pixels whose whole 3 x 3 neighbourhood is valid (inside the map's
    88-90 deg S disc), allocated as in V-09/V-10 (allocate) over TWI strata, drawn with default_rng([seed, stratum])."""
    ok = np.isfinite(twi)
    full = np.zeros_like(ok)
    full[1:-1, 1:-1] = np.all([ok[1 + dr:ok.shape[0] - 1 + dr, 1 + dc:ok.shape[1] - 1 + dc]
                               for dr in (-1, 0, 1) for dc in (-1, 0, 1)], axis=0)
    if pct is not None:
        okp = np.isfinite(pct)
        full[1:-1, 1:-1] &= np.all([okp[1 + dr:okp.shape[0] - 1 + dr, 1 + dc:okp.shape[1] - 1 + dc]
                                    for dr in (-1, 0, 1) for dc in (-1, 0, 1)], axis=0)
    t = np.where(ok, np.maximum(twi, 0.0), -1.0)     # the map's tiny negatives (>= -1e-5) are zeros for the strata
    k = len(strata) - 1
    pools = [np.flatnonzero(full & (t >= strata[j]) & ((t < strata[j + 1]) if j < k - 1 else (t <= strata[j + 1])))
             for j in range(k)]
    alloc = allocate(n, [p.size for p in pools])
    pts, info = [], {"strata": [], "seed": seed, "requested": n, "pixels_with_full_3x3": int(full.sum())}
    for j in range(k):
        rng = np.random.default_rng([seed, j])
        take = np.sort(rng.choice(pools[j].size, size=alloc[j], replace=False)) if alloc[j] else np.array([], int)
        info["strata"].append({"range_pct": [strata[j], strata[j + 1]], "pixels": int(pools[j].size),
                               "sampled": int(take.size)})
        for i in take:
            r, c = divmod(int(pools[j][i]), twi.shape[1])
            x, y = pixel_xy(meta, r, c)
            lat, lon = xy_to_latlon(np.array(x), np.array(y), 1737400.0)
            p = {"stratum": j, "row": r, "col": c, "x_m": float(x), "y_m": float(y), "lat": float(lat),
                 "lon": float(lon), "twi": float(twi[r, c]), "twi_3x3": neighbourhood(twi, r, c)}
            if pct is not None:
                p.update({"pct": float(pct[r, c]), "pct_3x3": neighbourhood(pct, r, c)})
            pts.append(p)
    info["points"] = len(pts)
    return pts, info


# ------------------------------------------------------------------ Sun visibility under the three rules
def rule_fractions(site, hp, trk: dict, guard: float = GUARD_DEG, exact=None) -> tuple[dict, dict]:
    """Fractions (percent) of the samples in which the Sun is visible under each rule, and counts."""
    states, stats = rule_states(site, hp, trk, guard, exact)
    stats["visible_samples"] = {r: int(np.sum(states[r])) for r in RULES}
    return {rule: 100.0 * float(np.mean(states[rule])) for rule in RULES}, stats


def rule_states(site, hp, trk: dict, guard: float = GUARD_DEG, exact=None) -> tuple[dict, dict]:
    """Per-sample Sun visibility under 'any', 'centre' and 'full', identical to the engine's rule_state with Earth
    occultation (full_state). exact(i) -> the engine's rules dict for sample i (default: full_state)."""
    from lunaops import settings
    from lunaops.engine.earth import intrinsic_radii
    from lunaops.engine.visibility import disk_edges_many
    ets = trk["ets"]
    if exact is None:
        exact = _engine_rules(site, hp, ets)
    sun = topocentric(site, trk["sun"])
    earth = topocentric(site, trk["earth"])
    alpha = np.degrees(intrinsic_radii(earth["d"])[0])
    rho = np.degrees(np.arcsin(settings.R_SUN_KM / sun["d"]))
    e = disk_edges_many(hp, sun["az"], sun["el"], rho)
    gamma = np.degrees(np.arccos(np.clip(np.sum(sun["unit"] * earth["unit"], axis=1), -1.0, 1.0)))
    touch = gamma < rho + alpha + guard
    out, amb_all = {}, np.zeros(ets.size, bool)
    for rule, g in (("any", e["g_top"]), ("centre", e["c"]), ("full", e["g_bot"])):
        vis = g > guard
        amb = (np.abs(g) <= guard) | (vis & touch)
        out[rule] = [vis & ~touch, amb]
        amb_all |= amb
    cache, unknown = {}, 0
    for i in np.flatnonzero(amb_all):
        rules = exact(int(i))
        cache[int(i)] = rules
    for rule in RULES:
        vis, amb = out[rule]
        for i in np.flatnonzero(amb):
            v = cache[int(i)][f"sun_{rule}"]
            if v is None:
                unknown += 1
                v = False
            vis[i] = bool(v)
        out[rule] = vis
    stats = {"samples": int(ets.size), "exact_samples": len(cache), "exact_unknown": unknown,
             "earth_touching_samples": int(np.sum(touch))}
    return out, stats


def _engine_rules(site, hp, ets):
    from lunaops.engine.events import EventConfig, EventDetector, full_state
    det = EventDetector(site, hp, EventConfig())
    return lambda i: full_state(det, float(ets[i]))["rules"]


def evaluate_point(lat: float, lon: float, trk: dict, horizon_fn=None) -> dict:
    from lunaops.engine.dem import TerrainError
    from lunaops.engine.ephem import Site
    from lunaops.engine.horizon import compute_horizon
    from lunaops.engine.visibility import HorizonProfile
    try:
        hz = (horizon_fn or compute_horizon)(lat, lon, OBS_H_M)
    except TerrainError as exc:
        return {"outcome": "inconclusive", "reason": f"no terrain horizon: {exc}"[:300]}
    h = np.asarray(hz.h_deg, dtype=float)
    inc = np.asarray(hz.incomplete, dtype=bool) | ~np.isfinite(h)
    rec = {"incomplete_bins": int(inc.sum()), "ground_h_m": float(getattr(hz, "ground_h_m", 0.0))}
    if inc.any():
        return {**rec, "outcome": "inconclusive", "reason": f"{int(inc.sum())} of {inc.size} horizon bins incomplete"}
    flags = hz.flag_arrays() if hasattr(hz, "flag_arrays") else None
    hp = HorizonProfile(h, inc, getattr(hz, "sigma_deg", None), flags=flags)
    fr, stats = rule_fractions(Site(lat, lon, rec["ground_h_m"], OBS_H_M), hp, trk)
    if stats["exact_unknown"]:
        return {**rec, **stats, "outcome": "inconclusive", "reason": "engine verdict unknown at some samples"}
    return {**rec, **stats, "outcome": "scored", **fr}


# ------------------------------------------------------------------ criteria and status
def terrain_prerequisites() -> tuple[bool, str]:
    """The shared terrain acceptance gate (validation/terrain_gate.py)."""
    from validation import terrain_gate
    return terrain_gate.final_terrain_prerequisites()


def score(points: list[dict], prerequisites: tuple[bool, str] = (False, "not checked"), avgvisib_rmse=None) -> tuple:
    sc = [p for p in points if p.get("outcome") == "scored"]
    inc = [p for p in points if p.get("outcome") != "scored"]
    psr = [p for p in sc if p["any"] == 0.0]
    c1_bad = [p for p in psr if not p["twi"] <= C1_MAX_PCT]
    c1 = {"threshold_pct": C1_MAX_PCT, "predicted_permanent_shadow": len(psr), "exceeding": len(c1_bad),
          "max_twi_pct": max((p["twi"] for p in psr), default=None),
          "pct_exceeding": sum(1 for p in psr if "pct" in p and not p["pct"] <= C1_MAX_PCT),
          "result": ("no samples" if not psr else ("failed" if c1_bad else "passed"))}
    c2 = {"twi": {}, "pct": {}, "3x3_overlap": None}
    for key in ("twi", "pct"):
        use = [p for p in sc if key in p]
        for s in C2_SLACKS_PP:
            inside = sum(1 for p in use if p["full"] - s <= p[key] <= p["any"] + s)
            c2[key][f"slack_{s:g}pp"] = {"inside": inside, "of": len(use), "share": inside / len(use) if use else None}
    ov = sum(1 for p in sc if p["any"] >= p["twi_3x3"]["min"] and p["full"] <= p["twi_3x3"]["max"])
    c2["3x3_overlap"] = {"bracket_overlaps_twi_3x3_range": ov, "of": len(sc)}
    c3 = {}
    for rule in RULES:
        d = np.array([p["twi"] - p[rule] for p in sc])
        c3[rule] = {"bias_pp": float(d.mean()) if d.size else None, "rmse_pp": float(np.sqrt(np.mean(d * d))) if d.size else None}
    ab = [p for p in sc if p.get("avgvisib_block_pct") is not None]
    if ab:
        d = np.array([p["twi"] - p["avgvisib_block_pct"] for p in ab])
        c3["lola_avgvisib_block"] = {"bias_pp": float(d.mean()), "rmse_pp": float(np.sqrt(np.mean(d * d))), "of": len(ab),
                                     "note": "18.6-year modelled 'any' rule, 100 m block mean; benchmark only"}
    ok, why = prerequisites
    if not ok:
        status = "not run"
    elif c1["result"] == "failed":
        status = "failed"
    elif inc or not psr:
        status = "inconclusive"
    else:
        status = "passed"
    detail = (f"{len(sc)}/{len(points)} samples scored ({len(inc)} inconclusive); C1 (TWI <= {C1_MAX_PCT:g} % where "
              f"LUNA-OPS predicts permanent shadow): {c1['result']} ({len(psr)} samples, {len(c1_bad)} above); "
              f"C2 TWI in [full, any] {c2['twi']['slack_0pp']['inside']}/{len(sc)}, with 1.31 pp "
              f"{c2['twi']['slack_1.31pp']['inside']}/{len(sc)}, with 3.0 pp {c2['twi']['slack_3pp']['inside']}/{len(sc)} "
              f"(reported, not gating)")
    if not ok:
        detail += f"; PRELIMINARY ({why}), not a V-12 result"
    return status, {"C1": c1, "C2": c2, "C3": c3, "scored": len(sc), "inconclusive": len(inc), "points": len(points)}, detail


def avgvisib_block(av_pct: np.ndarray, av_meta: dict, x: float, y: float) -> float:
    """Mean of the AVGVISIB 60 m pixels whose centres fall inside the 100 m LROC pixel centred at (x, y)."""
    s, c0, l0 = av_meta["map_scale_m"], av_meta["sample_projection_offset"], av_meta["line_projection_offset"]
    cr, rr = x / s + c0, l0 - y / s
    h = 50.0 / s
    cols = np.arange(math.ceil(cr - h), math.floor(cr + h) + 1)
    rows = np.arange(math.ceil(rr - h), math.floor(rr + h) + 1)
    return float(av_pct[np.ix_(rows, cols)].mean())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--twi-img", required=True)
    ap.add_argument("--pct-img", required=True)
    ap.add_argument("--avgvisib-img", help="optional LOLA AVGVISIB_85S_060M_201608.IMG for the C3 benchmark")
    ap.add_argument("--points", type=int, default=N_POINTS)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--step-s", type=float, default=STEP_S)
    ap.add_argument("--out", default="v12.json")
    a = ap.parse_args()
    twi, tmeta = read_lroc(a.twi_img)
    pct, pmeta = read_lroc(a.pct_img)
    if tmeta["geotransform"] != pmeta["geotransform"]:
        sys.exit("TWI and PCT grids differ")
    pts, sampling = sample_pixels(twi, tmeta, a.points, a.seed, pct=pct)
    av = None
    if a.avgvisib_img:
        from validation.v09_v10_avgvisib import read_avgvisib
        av_frac, av_meta = read_avgvisib(a.avgvisib_img)
        av = (av_frac * 100.0, av_meta)
    from lunaops.engine.timeutil import parse_utc
    days = (parse_utc(PERIOD[1]) - parse_utc(PERIOD[0])) / 86400.0
    trk = track(PERIOD[0], days / 365.25, a.step_s)
    for p in pts:
        if av is not None:
            p["avgvisib_block_pct"] = avgvisib_block(av[0], av[1], p["x_m"], p["y_m"])
        p.update(evaluate_point(p["lat"], p["lon"], trk))
        print(json.dumps({k: p.get(k) for k in ("lat", "lon", "twi", "any", "centre", "full", "outcome")}), flush=True)
    from validation import terrain_gate
    gate = terrain_gate.evaluate()
    prereq = (gate["ok"], "; ".join(gate["reasons"]))
    status, metrics, detail = score(pts, prereq)
    from lunaops.engine.dem import products_digest
    from validation.common import run_meta
    out = {"tests": {"V-12": {"status": status, "detail": detail}},
           "method": {"period": PERIOD, "observer_height_m": OBS_H_M, "step_s": a.step_s, "samples": int(trk["ets"].size),
                      "rules": "bracket [full, any]; centre for diagnosis", "c1_max_pct": C1_MAX_PCT,
                      "c2_slacks_pp": C2_SLACKS_PP, "prerequisites_met": prereq[0], "prerequisites_detail": prereq[1]},
           "reference": {"twi": tmeta, "pct": pmeta}, "sampling": sampling, "metrics": metrics, "points": pts,
           "terrain_products": products_digest(), "meta": {**run_meta("v12_lroc"), "terrain_gate": gate}}
    Path(a.out).write_text(json.dumps(out, indent=2, default=float))
    print(json.dumps(out["tests"], indent=2))


if __name__ == "__main__":
    main()
