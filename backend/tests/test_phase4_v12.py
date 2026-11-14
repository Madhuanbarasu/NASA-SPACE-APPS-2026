"""Phase 4 A12: V-12 against the LROC WAC south-pole illumination maps (validation/v12_lroc.py).

The maps themselves (5.9 MB each) are not stored; their PDS4 labels, READMEs, attached PDS3 headers and provenance
are (validation/reference/lroc/). These tests check the documented facts and the image offset (9712, not the PDS4
label's 4856), the reader on the real headers, the deterministic sampling with its 3 x 3 neighbourhoods, that the
vectorised any/centre/full Sun visibility equals the engine's event detector (including an eclipse in the LROC year),
the criteria (C1 gating, C2 and C3 reported only) and that no run is final before A5/A6 and the 240 m terrain.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pytest

from conftest import needs_kernels

BACKEND = Path(__file__).resolve().parents[1]
REF = BACKEND / "validation" / "reference" / "lroc"
N = 1214


def _V():
    sys.path.insert(0, str(BACKEND))
    from validation import v12_lroc
    return v12_lroc


# ------------------------------------------------------------------ reference fixtures and provenance
def test_fixtures_provenance_and_documented_facts():
    V = _V()
    prov = json.loads((REF / "provenance.json").read_text())
    for k, p in prov["products"].items():
        for key in ("pds4_label", "readme", "pds3_header"):
            assert hashlib.sha256((REF / p[key]["file"]).read_bytes()).hexdigest() == p[key]["sha256"], (k, key)
        xml = (REF / p["pds4_label"]["file"]).read_text()
        assert f"<md5_checksum>{p['img']['md5']}</md5_checksum>" in xml           # IMG hash recorded = label's MD5
        assert '<offset unit="byte">4856</offset>' in xml                      # the PDS4 label's (wrong) offset
        readme = (REF / p["readme"]["file"]).read_text()
        for fact in ("15 February 2010 to 5 February 2011", "3807", "229 observations", "conservative global threshold",
                     "close to, but not equal to zero", "30 m"):
            assert fact in readme, (k, fact)
    assert prov["products"]["TWI"]["role"] == "primary reference"
    assert prov["products"]["TWI"]["browse_geotiff_crosscheck"]["geotransform"] == [100.0, 0.0, -60700.0, 0.0, -100.0, 60700.0]
    assert any("byte 9712" in d for d in prov["label_defects"])
    assert prov["paper_access"]["result"].startswith("not obtained")
    assert V.PERIOD == ("2010-02-15T00:00:00Z", "2011-02-05T00:00:00Z") and V.OBS_H_M == 0.0
    assert V.C1_MAX_PCT == 1.0 and V.C2_SLACKS_PP == (0.0, 1.31, 3.0)
    assert not hasattr(V, "FINAL_PREREQUISITES")              # replaced by the shared terrain gate (Phase 4 A6)


def _write_img(tmp: Path, data: np.ndarray, kind="TWI", name=None) -> Path:
    """A map file made of the real attached PDS3 header followed by synthetic 32-bit floats."""
    head = (REF / f"WAC_POLE_ILL_{kind}_SOUTH_100M.pds3_header").read_bytes()
    p = tmp / (name or f"WAC_POLE_ILL_{kind}_SOUTH_100M.IMG")
    p.write_bytes(head + np.asarray(data, "<f4").tobytes())
    return p


def _disc(fill=lambda r: 10.0 + 0.0 * r):
    """The real 88-90 S disc: valid inside, CORE_NULL outside; values from fill(radius in m)."""
    x = (np.arange(N) - 606.5) * 100.0
    X, Y = np.meshgrid(x, -x)
    r = np.hypot(X, Y)
    a = fill(r).astype(np.float32)
    null = np.frombuffer(np.uint32(0xFF7FFFFB).tobytes(), "<f4")[0]
    a[r > 60650.0] = null
    return a


def test_reader_uses_the_pds3_offset_and_special_values(tmp_path):
    V = _V()
    lab, _text = V.read_header(str(REF / "WAC_POLE_ILL_TWI_SOUTH_100M.pds3_header"))
    assert (lab["^IMAGE"] - 1) * lab["RECORD_BYTES"] == V.IMAGE_OFFSET == 9712 != V.PDS4_LABEL_OFFSET
    a = _disc(lambda r: 70.0 * (1 - r / 61000.0))
    a[600, 600] = np.frombuffer(np.uint32(0xFF7FFFFE).tobytes(), "<f4")[0]      # high instrument saturation
    v, meta = V.read_lroc(str(_write_img(tmp_path, a)))
    assert meta["image_offset"] == 9712 and meta["geotransform"] == [100.0, 0.0, -60700.0, 0.0, -100.0, 60700.0]
    assert np.isnan(v[600, 600]) and np.isnan(v[0, 0]) and meta["missing_pixels"] == int(np.sum(~np.isfinite(v)))
    ok = np.isfinite(v)
    assert np.array_equal(v[ok], a[ok].astype(np.float64)) and meta["max"] <= 70.0
    bad = a.copy()
    bad[606, 606] = 1e19                                     # what a read at the PDS4 offset produces
    with pytest.raises(ValueError, match="0-100"):
        V.read_lroc(str(_write_img(tmp_path, bad, name="BAD.IMG")))
    short = _write_img(tmp_path, a, name="SHORT.IMG")
    short.write_bytes(short.read_bytes()[:-4])
    with pytest.raises(ValueError, match="bytes"):
        V.read_lroc(str(short))


def test_sampling_is_stratified_deterministic_with_full_3x3(tmp_path):
    V = _V()
    a = _disc(lambda r: np.clip(60.0 - r / 1000.0, 0, None))       # 60 % at the pole falling to 0 at ~60 km
    a[(a < 0.5) & (a > -1.0)] = -4.9e-6                             # the map's tiny negative zeros (not the nulls)
    twi, meta = V.read_lroc(str(_write_img(tmp_path, a)))
    pct, _ = V.read_lroc(str(_write_img(tmp_path, a, "PCT")))
    pts, info = V.sample_pixels(twi, meta, 120, seed=3, pct=pct)
    assert len(pts) == 120 and V.sample_pixels(twi, meta, 120, seed=3, pct=pct)[0] == pts
    assert info["strata"][0]["pixels"] > 0                          # negatives count as zeros
    for p in pts:
        nb = twi[p["row"] - 1:p["row"] + 2, p["col"] - 1:p["col"] + 2]
        assert np.isfinite(nb).all() and p["twi_3x3"]["min"] == float(nb.min()) and p["lat"] <= -88.0
        lo, hi = info["strata"][p["stratum"]]["range_pct"]
        assert lo <= max(p["twi"], 0.0) <= hi and p["pct"] == p["twi"]
    assert [s["sampled"] for s in info["strata"]] == V.allocate(120, [s["pixels"] for s in info["strata"]])


def test_avgvisib_block_mean():
    V = _V()
    meta = {"map_scale_m": 60.0, "sample_projection_offset": 4.5, "line_projection_offset": 4.5}
    av = np.arange(100, dtype=float).reshape(10, 10)
    # 100 m pixel centred on (30, -30) m covers the 60 m pixel centres at x = 30 (col 5) and y = -30 (row 5)
    assert V.avgvisib_block(av, meta, 30.0, -30.0) == av[5, 5]
    assert V.avgvisib_block(av, meta, 0.0, 0.0) == pytest.approx(av[4:6, 4:6].mean())


# ------------------------------------------------------------------ the vectorised rules equal the engine
def _detector_states(site, hp, ets):
    from lunaops.engine.events import EventConfig, EventDetector, build_intervals
    det = EventDetector(site, hp, EventConfig())
    e0, e1 = float(ets[0]) - 60.0, float(ets[-1]) + 60.0
    run = det.run(e0, e1)
    ivs = build_intervals(det, e0, e1, run["events"], run["samples"])
    out = {}
    for rule in ("any", "centre", "full"):
        iv = ivs[f"sun_{rule}"]
        starts = np.array([x["start_et"] for x in iv])
        out[rule] = [iv[np.searchsorted(starts, t, side="right") - 1]["state"] for t in ets]
    return out


@needs_kernels
def test_three_rules_equal_the_event_detector(kernels):
    """10 days of the LROC year every 20 minutes on the synthetic V-14 horizon: any, centre and full equal the
    detector's intervals at every epoch."""
    V = _V()
    from lunaops.engine.ephem import Site
    from lunaops.testing import v14_horizon
    from validation.v09_v10_avgvisib import track
    site = Site(-88.6, 120.0, 0.0, 0.0)
    trk = track("2010-09-01T00:00:00Z", 10 / 365.25, 1200.0)
    hp = v14_horizon(site, trk["ets"][0], 10.2)
    vis, _stats = V.rule_states(site, hp, trk)
    det = _detector_states(site, hp, trk["ets"])
    for rule in V.RULES:
        assert None not in det[rule] and [bool(s) for s in det[rule]] == [bool(v) for v in vis[rule]], rule
    assert vis["full"].sum() <= vis["centre"].sum() <= vis["any"].sum() and 0 < vis["full"].sum() < vis["any"].sum()


@needs_kernels
def test_eclipse_in_the_lroc_year_matches_the_detector(kernels):
    """21 December 2010 total lunar eclipse, every 2 minutes, flat -10 deg horizon: Earth hides the Sun, the three
    rules differ, and every verdict equals the detector's."""
    V = _V()
    from lunaops.engine.ephem import Site
    from lunaops.engine.visibility import HorizonProfile
    from validation.v09_v10_avgvisib import track
    hp = HorizonProfile(np.full(3600, -10.0), np.zeros(3600, bool))
    site = Site(-89.0, 0.0, 0.0, 0.0)
    trk = track("2010-12-21T05:00:00Z", 8 / 24 / 365.25, 120.0)
    vis, stats = V.rule_states(site, hp, trk)
    det = _detector_states(site, hp, trk["ets"])
    for rule in V.RULES:
        assert [bool(s) for s in det[rule]] == [bool(v) for v in vis[rule]], rule
    assert vis["full"].sum() < vis["centre"].sum() < vis["any"].sum() < trk["ets"].size and stats["exact_samples"] > 0


@needs_kernels
def test_guard_band_only_routes_to_the_engine(kernels):
    V = _V()
    from lunaops.engine.ephem import Site
    from lunaops.testing import v14_horizon
    from validation.v09_v10_avgvisib import track
    site = Site(-89.5, 0.0, 0.0, 0.0)
    trk = track("2010-06-03T00:00:00Z", 2 / 365.25)
    hp = v14_horizon(site, trk["ets"][0], 2.2)
    fast, _ = V.rule_states(site, hp, trk)
    slow, s2 = V.rule_states(site, hp, trk, guard=90.0)
    assert s2["exact_samples"] == trk["ets"].size and all(np.array_equal(fast[r], slow[r]) for r in V.RULES)


class _FakeHorizon:
    def __init__(self, h, incomplete=()):
        self.h_deg = np.full(3600, h, dtype=float)
        self.incomplete = np.zeros(3600, bool)
        self.incomplete[list(incomplete)] = True
        self.ground_h_m = 0.0
        self.sigma_deg = None


@needs_kernels
def test_incomplete_or_missing_terrain_is_inconclusive(kernels):
    V = _V()
    from lunaops.engine.dem import TerrainError
    from validation.v09_v10_avgvisib import track
    trk = track("2010-06-01T00:00:00Z", 1 / 365.25)
    assert V.evaluate_point(-89.0, 10.0, trk, horizon_fn=lambda *a: _FakeHorizon(-5.0, [3]))["outcome"] == "inconclusive"

    def none(*_a):
        raise TerrainError("no registered terrain")
    assert "no terrain" in V.evaluate_point(-89.0, 10.0, trk, horizon_fn=none)["reason"]
    dark = V.evaluate_point(-89.0, 10.0, trk, horizon_fn=lambda *a: _FakeHorizon(20.0))
    assert dark["outcome"] == "scored" and dark["any"] == dark["centre"] == dark["full"] == 0.0


# ------------------------------------------------------------------ criteria and status
def _p(twi, any_, full, centre=None, pct=None, scored=True, nb=None):
    p = {"twi": twi, "pct": twi if pct is None else pct, "twi_3x3": nb or {"min": twi, "max": twi, "mean": twi, "std": 0.0}}
    if scored:
        p.update({"outcome": "scored", "any": any_, "full": full, "centre": (any_ + full) / 2 if centre is None else centre})
    else:
        p["outcome"] = "inconclusive"
    return p


def test_criteria_and_status():
    V = _V()
    met, unmet = (True, ""), (False, "terrain levels not registered")
    psr_ok = [_p(0.0, 0.0, 0.0), _p(0.9, 0.0, 0.0)]
    other = [_p(10.0, 12.0, 8.0), _p(10.0, 9.0, 8.0), _p(20.0, 17.5, 16.0, nb={"min": 15.0, "max": 25.0, "mean": 20.0, "std": 1.0})]
    st, m, detail = V.score(psr_ok + other, met)
    assert st == "passed" and m["C1"]["result"] == "passed" and m["C1"]["predicted_permanent_shadow"] == 2
    c2 = m["C2"]["twi"]
    # 0.9 % needs the 1.31 pp slack, 10 % with any 9 % needs it too, 20 % with any 17.5 % needs the 3.0 pp slack
    assert (c2["slack_0pp"]["inside"], c2["slack_1.31pp"]["inside"], c2["slack_3pp"]["inside"]) == (2, 4, 5)
    assert m["C2"]["3x3_overlap"]["bracket_overlaps_twi_3x3_range"] == 3                  # reported separately
    assert set(m["C3"]) == {"any", "centre", "full"} and "not gating" in detail
    assert V.score(psr_ok + [_p(1.5, 0.0, 0.0)] + other, met)[0] == "failed"            # 1.5 % > 1 % where dark
    assert V.score(psr_ok + other + [_p(5.0, 0, 0, scored=False)], met)[0] == "inconclusive"
    assert V.score(other, met)[0] == "inconclusive"                                       # no permanent-shadow sample
    st, m, detail = V.score(psr_ok + [_p(1.5, 0.0, 0.0)] + other, unmet)
    assert st == "not run" and m["C1"]["result"] == "failed" and "PRELIMINARY" in detail  # never final before A5/A6
    assert V.score(psr_ok + other, unmet)[0] == "not run"
    bench = [dict(p, avgvisib_block_pct=p["twi"] + 2.0) for p in other]
    assert V.score(bench, met)[1]["C3"]["lola_avgvisib_block"]["bias_pp"] == pytest.approx(-2.0)


def test_current_terrain_does_not_meet_the_final_prerequisites():
    """V-12 uses the shared terrain gate; the registered terrain has no 240 m level, so no run can be final."""
    V = _V()
    from validation import terrain_gate
    ok, why = V.terrain_prerequisites()
    assert (ok, why) == terrain_gate.final_terrain_prerequisites()
    assert not ok and "240m" in why


# ------------------------------------------------------------------ end to end
@needs_kernels
def test_end_to_end_and_merge(kernels, monkeypatch, tmp_path):
    V = _V()
    from validation.common import merge_external, run_meta
    a = _disc(lambda r: np.clip(50.0 - r / 1200.0, 0, None))
    twi = _write_img(tmp_path, a)
    pct = _write_img(tmp_path, a, "PCT")
    real = V.evaluate_point
    monkeypatch.setattr(V, "evaluate_point", lambda lat, lon, trk, horizon_fn=None:
                        real(lat, lon, trk, horizon_fn=lambda *k: _FakeHorizon(-30.0)))
    out = tmp_path / "v12.json"
    monkeypatch.setattr(sys, "argv", ["v12_lroc", "--twi-img", str(twi), "--pct-img", str(pct), "--points", "6",
                                      "--step-s", "43200", "--out", str(out)])
    V.main()
    res = json.loads(out.read_text())
    assert res["tests"]["V-12"]["status"] == "not run" and "PRELIMINARY" in res["tests"]["V-12"]["detail"]
    gate = res["meta"]["terrain_gate"]
    assert gate["ok"] is False and res["method"]["prerequisites_met"] is False
    assert gate["acceptance_digest"] == res["meta"]["terrain_acceptance_digest"]
    assert res["method"]["period"] == list(V.PERIOD) and res["method"]["observer_height_m"] == 0.0
    assert res["reference"]["twi"]["image_offset"] == 9712 and res["metrics"]["scored"] == 6
    assert all(p["any"] >= p["centre"] >= p["full"] > 90.0 for p in res["points"])        # horizon far below
    tests = {"V-12": {"status": "not run"}}
    assert merge_external(tests, res, run_meta("run_validation")) == [] and tests["V-12"]["status"] == "not run"
