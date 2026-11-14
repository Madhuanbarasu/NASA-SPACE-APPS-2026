"""Phase 7: encode the frozen, owner-approved V-09/V-10 methodology in backend/validation/v09_v10_avgvisib.py
(R1/R2 gates, R3 diagnostics, inclusion-probability weights, exclusion of the inspected benchmark, frozen points).
Validation suite only; the engine (backend/lunaops) is not touched. Run once from backend/."""
from pathlib import Path

p = Path("validation/v09_v10_avgvisib.py")
s = p.read_text(encoding="utf-8")


def rep(old, new):
    global s
    assert old in s, old[:80]
    s = s.replace(old, new)


rep('''CRITERIA = {"rmse_pp": 5.0, "abs_bias_pp": 2.0, "approved": False,
            "note": "provisional thresholds (README/blueprint); require explicit approval before any pass"}''',
'''# Approved by the owner for Phase 7 (2026-11-14) and frozen before the holdout was drawn
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
HOLDOUT_SEED = 20261114''')

rep('''def stratified_points(frac: np.ndarray, meta: dict, n: int = N_POINTS, seed: int = 1,
                      strata=STRATA, lat_limit: float = COVERAGE_LAT_DEG) -> tuple[list[dict], dict]:
    """Deterministic stratified sample of pixels inside the documented coverage (all four pixel corners at or south
    of lat_limit), n / len(strata) - 1 per equal-width stratum of the reference value."""''',
'''def stratified_points(frac: np.ndarray, meta: dict, n: int = N_POINTS, seed: int = 1,
                      strata=STRATA, lat_limit: float = COVERAGE_LAT_DEG,
                      exclude: set | None = None) -> tuple[list[dict], dict]:
    """Deterministic stratified sample of pixels inside the documented coverage (all four pixel corners at or south
    of lat_limit), n / len(strata) - 1 per equal-width stratum of the reference value. exclude: (row, col) pixels
    that may not be drawn (Phase 7 holdout: every pixel of the previously inspected benchmark); each stratum's
    eligible pixel count is recorded as `pixels` (the N_h of the area weights)."""''')

rep('''        pools.append(np.flatnonzero(covered & (frac >= a) & ((frac < b) if j < k - 1 else (frac <= b))))''',
'''        pool = np.flatnonzero(covered & (frac >= a) & ((frac < b) if j < k - 1 else (frac <= b)))
        if exclude:
            ex = np.array([r_ * frac.shape[1] + c_ for r_, c_ in exclude], dtype=np.int64)
            pool = pool[~np.isin(pool, ex)]
        pools.append(pool)''')

rep('''                     "nominal_per_stratum": n // k, "seed": seed, "requested": n}''',
'''                     "nominal_per_stratum": n // k, "seed": seed, "requested": n,
                     "excluded_pixels": len(exclude or ())}''')

rep('''                        "reference_3x3_min": float(nb.min()), "reference_3x3_max": float(nb.max())})''',
'''                        "reference_3x3_min": float(nb.min()), "reference_3x3_max": float(nb.max()),
                        "smooth": bool(float(nb.max()) - float(nb.min()) <= SMOOTH_RANGE_MAX + 1e-12)})''')

a = s.index("def score(points: list[dict], years: float, criteria: dict = CRITERIA,")
b = s.index("def main():")
NEW_SCORE = '''def _rmse_bias(d: np.ndarray, w: np.ndarray | None = None) -> tuple[float | None, float | None]:
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


'''
s = s[:a] + NEW_SCORE + s[b:]

rep('''    ap.add_argument("--out", default="v09_v10.json")
    a = ap.parse_args()''',
'''    ap.add_argument("--out", default="v09_v10.json")
    ap.add_argument("--exclude-from", action="append", default=[],
                    help="earlier result JSON whose sampled pixels may not be drawn again (independent holdout)")
    ap.add_argument("--select-only", metavar="DIR", help="write the selected points per test to DIR and stop")
    ap.add_argument("--use-points", action="append", default=[], metavar="TEST=FILE",
                    help="run exactly these frozen points (written by --select-only)")
    ap.add_argument("--expect-sha256", action="append", default=[], metavar="TEST=HEX",
                    help="refuse to run unless the frozen points file has this SHA-256")
    a = ap.parse_args()''')

rep('''    trk = track(a.start, a.years)
    out = {"tests": {}, "criteria": CRITERIA, "assumptions": {''',
'''    exclude = set()
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
    out = {"tests": {}, "criteria": CRITERIA, "assumptions": {''')

rep('''        frac, meta = read_avgvisib(img)
        pts, sampling = stratified_points(frac, meta, a.points, a.seed)
        for p in pts:''',
'''        frac, meta = read_avgvisib(img)
        if tid in use:
            fp = Path(use[tid])
            if tid in expect and _sha256(fp) != expect[tid]:
                sys.exit(f"{tid}: frozen points file {fp} does not match the expected SHA-256; refusing to run")
            frozen = json.loads(fp.read_text())
            pts, sampling = frozen["points"], {**frozen["sampling"], "frozen_points_file": fp.name,
                                               "frozen_points_sha256": _sha256(fp)}
        else:
            pts, sampling = stratified_points(frac, meta, a.points, a.seed, exclude=exclude)
        for p in pts:''')

rep('''        status, metrics, detail = score(pts, a.years, CRITERIA, (gate["ok"], "; ".join(gate["reasons"])))''',
'''        npx = {k: st["pixels"] for k, st in enumerate(sampling["strata"])}
        status, metrics, detail = score(pts, a.years, CRITERIA, (gate["ok"], "; ".join(gate["reasons"])), npx)''')

p.write_text(s, encoding="utf-8")
print("patched", p)
