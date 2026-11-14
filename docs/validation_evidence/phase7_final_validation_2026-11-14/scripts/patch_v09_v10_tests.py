"""Phase 7: bring tests/test_phase4_v09_v10.py in line with the approved, frozen V-09/V-10 criteria (R1/R2/R3), and add
tests for the holdout additions (exclusion of the inspected benchmark, frozen points with a hash check, area weights).
Run once from backend/."""
from pathlib import Path

p = Path("tests/test_phase4_v09_v10.py")
s = p.read_text(encoding="utf-8")


def rep(old, new):
    global s
    assert old in s, old[:90]
    s = s.replace(old, new)


rep('''engine's own event detector ("any" rule, Sun with Earth occultation, oblate Earth), the scoring (the provisional
criteria can never produce a pass), and the end-to-end result with its merge.''',
'''engine's own event detector ("any" rule, Sun with Earth occultation, oblate Earth), the scoring under the approved
Phase 7 criteria (R1 smooth-region gate, R2 area-weighted gate, R3 diagnostic), the holdout additions (exclusion of the
previously inspected benchmark, frozen points with a hash check), and the end-to-end result with its merge.''')

rep('''    assert V.CRITERIA["approved"] is False and V.YEARS == 18.6 and V.STEP_S == 3600.0 and V.COVERAGE_LAT_DEG == -85.0''',
'''    assert V.CRITERIA["approved"] is True and V.YEARS == 18.6 and V.STEP_S == 3600.0 and V.COVERAGE_LAT_DEG == -85.0
    assert (V.CRITERIA["r1"]["rmse_pp"], V.CRITERIA["r1"]["abs_bias_pp"], V.CRITERIA["r1"]["smooth_range_max"]) == (2.0, 1.0, 0.05)
    assert (V.CRITERIA["r2"]["rmse_pp"], V.CRITERIA["r2"]["abs_bias_pp"]) == (5.0, 2.0) and V.HOLDOUT_SEED == 20261114''')

a = s.index("def test_provisional_criteria_never_pass():")
b = s.index("def test_approved_criteria_never_decide_without_the_terrain_gate():")
s = s[:a] + '''def _sp(diffs, smooth=True, stratum=0, inconclusive=0):
    out = [{"stratum": stratum, "outcome": "scored", "reference": 0.5, "computed": 0.5 + d / 100.0, "smooth": smooth}
           for d in diffs]
    return out + [{"stratum": stratum, "outcome": "inconclusive", "reference": 0.5, "smooth": smooth}] * inconclusive


def test_approved_gates_r1_and_r2():
    """Phase 7 (frozen criteria): passed only when R1 (smooth points, unweighted RMSE <= 2, |bias| <= 1) and R2
    (area-weighted RMSE <= 5, |bias| <= 2) are both met; R3 never decides; any inconclusive point -> inconclusive;
    fewer than 20 smooth points or a partial span -> not run."""
    V = _V()
    met = (True, "")
    good = _sp([1.0, -1.0] * 50) + _sp([3.0, -3.0] * 50, smooth=False)    # R1 1.0/0; R2 equal weights sqrt(5)=2.24/0
    st, m, detail = V.score(good, 18.6, V.CRITERIA, met)
    assert st == "passed" and m["gates"]["R1"]["met"] and m["gates"]["R2"]["met"] and "R3 (diagnostic)" in detail
    assert m["smooth"]["points"] == 100 and m["smooth"]["rmse_pp"] == pytest.approx(1.0)
    r1_bad = _sp([2.5, -2.5] * 50) + _sp([1.0] * 100, smooth=False)        # R1 RMSE 2.5 > 2
    assert V.score(r1_bad, 18.6, V.CRITERIA, met)[0] == "failed"
    r1_bias = _sp([1.5] * 100) + _sp([-1.5] * 100, smooth=False)           # R1 |bias| 1.5 > 1; R2 bias 0, RMSE 1.5
    st, m, _ = V.score(r1_bias, 18.6, V.CRITERIA, met)
    assert st == "failed" and not m["gates"]["R1"]["met"] and m["gates"]["R2"]["met"]
    r2_bad = _sp([0.5] * 50) + _sp([8.0] * 150, smooth=False)              # R1 met, R2 RMSE ~6.9 > 5
    st, m, _ = V.score(r2_bad, 18.6, V.CRITERIA, met)
    assert st == "failed" and m["gates"]["R1"]["met"] and not m["gates"]["R2"]["met"]
    outlier = _sp([0.2] * 199) + _sp([40.0], smooth=False)                 # one 40 pp outlier: R3 reports, gates decide
    st, m, _ = V.score(outlier, 18.6, V.CRITERIA, met)
    assert st == "passed" and m["max_abs_pp"] == pytest.approx(40.0) and len(m["outliers"]) == 1
    assert V.score(_sp([0.0] * 199, inconclusive=1), 18.6, V.CRITERIA, met)[0] == "inconclusive"
    few = _sp([0.0] * 19) + _sp([0.0] * 181, smooth=False)
    st, _m, detail = V.score(few, 18.6, V.CRITERIA, met)
    assert st == "not run" and "R1 not evaluable" in detail
    assert V.score(good, 1.0, V.CRITERIA, met)[0] == "not run" and "PARTIAL" in V.score(good, 1.0, V.CRITERIA, met)[2]
    assert V.score([], 18.6, V.CRITERIA, met)[0] == "not run"
    assert V.score(good, 18.6, {**V.CRITERIA, "approved": False}, met)[0] == "not run"


def test_area_weights_are_inclusion_probabilities():
    """R2 weights each scored point by N_h / n_h: a stratum of 1,000,000 pixels with 2 points outweighs one of 10 pixels
    with 2 points by 10^5, so the rare stratum's large errors barely move the area-weighted statistics."""
    V = _V()
    pts = _sp([1.0, 1.0], stratum=0) + _sp([30.0, 30.0], stratum=1)
    _st, m, _ = V.score(pts, 18.6, V.CRITERIA, (True, ""), {0: 1_000_000, 1: 10})
    w0, w1 = 1_000_000 / 2, 10 / 2
    assert m["area_weighted"]["bias_pp"] == pytest.approx((2 * w0 * 1.0 + 2 * w1 * 30.0) / (2 * w0 + 2 * w1))
    assert m["area_weighted"]["rmse_pp"] == pytest.approx(math.sqrt((2 * w0 * 1.0 + 2 * w1 * 900.0) / (2 * w0 + 2 * w1)))
    assert m["rmse_pp"] == pytest.approx(math.sqrt((1 + 1 + 900 + 900) / 4))     # equal weights (R3)


def test_holdout_excludes_the_inspected_pixels_and_freezes_points(tmp_path, monkeypatch):
    """The holdout never redraws an excluded pixel, records the eligible N_h, flags smooth points from the reference
    alone, and a run with a frozen points file refuses to start if the file's SHA-256 differs."""
    V = _V()
    rng = np.random.default_rng(5)
    dn = (rng.random((341, 341)) * 25000).astype(np.int16)
    img = _write_map(tmp_path, dn, 1000.0, "MAP.IMG")
    frac, meta = V.read_avgvisib(str(img))
    first, info1 = V.stratified_points(frac, meta, 50, 1)
    excl = {(p["row"], p["col"]) for p in first}
    second, info2 = V.stratified_points(frac, meta, 50, V.HOLDOUT_SEED, exclude=excl)
    assert not excl & {(p["row"], p["col"]) for p in second}
    assert sum(s["pixels"] for s in info2["strata"]) == sum(s["pixels"] for s in info1["strata"]) - len(excl)
    for p in second:
        assert p["smooth"] == ((p["reference_3x3_max"] - p["reference_3x3_min"]) <= 0.05 + 1e-12)
    prev = tmp_path / "prev.json"
    prev.write_text(json.dumps({"results": {"V-09": {"points": first}}}))
    sel = tmp_path / "sel"
    monkeypatch.setattr(sys, "argv", ["v", "--sun-img", str(img), "--points", "50", "--seed", str(V.HOLDOUT_SEED),
                                      "--exclude-from", str(prev), "--select-only", str(sel)])
    V.main()
    frozen = json.loads((sel / "V-09_points.json").read_text())
    assert [(p["row"], p["col"]) for p in frozen["points"]] == [(p["row"], p["col"]) for p in second]
    monkeypatch.setattr(sys, "argv", ["v", "--sun-img", str(img), "--use-points", f"V-09={sel / 'V-09_points.json'}",
                                      "--expect-sha256", "V-09=" + "0" * 64, "--years", "0.001", "--out", str(tmp_path / "o.json")])
    with pytest.raises(SystemExit) as e:
        V.main()
    assert "does not match the expected SHA-256" in str(e.value)


''' + s[b:]

rep('''        assert res["tests"][tid]["status"] == "not run" and "provisional" in res["tests"][tid]["detail"]''',
'''        assert res["tests"][tid]["status"] == "not run" and "PARTIAL" in res["tests"][tid]["detail"]''')
rep('''    """Synthetic Sun and Earth maps (value 1 everywhere) with a horizon far below: every scored point computes 1.0
    over a short span, the run reports metrics with status "not run" (provisional criteria, partial span), and the
    result merges through the guard."""''',
'''    """Synthetic Sun and Earth maps (value 1 everywhere) with a horizon far below: every scored point computes 1.0
    over a short span, the run reports metrics with status "not run" (partial span), and the result merges through
    the guard."""''')
p.write_text(s, encoding="utf-8")
print("patched", p)
