"""Phase 4 A6: the shared, hash-bound terrain acceptance gate for the final V-09, V-10, V-11 and V-12 runs.

A run is final only if the 20 m and 240 m levels are registered and present, every registered non-synthetic product
and its error map are present as registered, and every pair of overlapping products is accepted in
validation/reference/terrain_acceptance.json for the exact DEM and error-map SHA-256. Synthetic scenes stand in for
registered products (flagged non-synthetic in their temporary registry only).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
REPO_REGISTRY = ROOT / "data" / "dem" / "registry.json"
A6_REPORT = ROOT / "docs" / "validation_evidence" / "terrain_a6_2026-11-10" / "terrain_validation_report.json"
FLAT = (lambda DX, DY: DX * 0.0)


def _gate():
    from validation import terrain_gate
    return terrain_gate


def _scene(tmp_path, monkeypatch, levels=("5m", "20m", "80m")):
    """Registered non-synthetic stand-ins (with error maps) for the given levels, all overlapping the site."""
    from lunaops.engine.dem import write_registry
    from scene_helpers import Scene

    sc = Scene(tmp_path, monkeypatch)
    size = {"5m": (5.0, 1000.0), "20m": (20.0, 2000.0), "80m": (80.0, 8000.0), "240m": (240.0, 24000.0)}
    recs = {}
    for lv in levels:
        px, half = size[lv]
        recs[lv] = sc.add(lv.upper(), px, half, FLAT, err=0.5)
    for rec in sc.reg["products"]:
        rec["synthetic"] = False                     # stands in for a registered NASA product (temp registry only)
    write_registry(sc.reg)
    return sc, recs


def _side(sc, rec):
    from lunaops.engine.dem import product_key
    k = product_key(rec)
    return {"key": k, "dem_sha256": rec["sha256"], "error_map_sha256": sc.reg["error_maps"][k]["sha256"]}


def _acceptance(tmp_path, sc, recs, pairs, **over):
    entries = [{"fine": _side(sc, recs[a]), "coarse": _side(sc, recs[b]), "scope": "test", "evidence": "test",
                "source": "test", "approver": "Test Approver", "approved_date": "2026-11-10", **over}
               for a, b in pairs]
    p = tmp_path / "acceptance.json"
    p.write_text(json.dumps({"schema": 1, "accepted_pairs": entries, "pending_pairs": []}))
    return p


A6_PAIRS = (("5m", "20m"), ("5m", "80m"), ("20m", "80m"))
ALL_PAIRS = A6_PAIRS + (("5m", "240m"), ("20m", "240m"), ("80m", "240m"))


# ------------------------------------------------------------------ the gate
def test_scoped_acceptance_without_240m_is_not_final(tmp_path, monkeypatch):
    G = _gate()
    sc, recs = _scene(tmp_path, monkeypatch)
    g = G.evaluate(acceptance_path=_acceptance(tmp_path, sc, recs, A6_PAIRS))
    assert not g["ok"] and g["missing_pairs"] == [] and len(g["accepted_pairs"]) == 3
    assert g["reasons"] == ["terrain levels not registered and present here: 240m (A5 20 m; wider 240 m)"]


def test_registered_240m_needs_all_three_240m_pairs(tmp_path, monkeypatch):
    """The 5 m / 20 m / 80 m acceptance never covers a 240 m level: registering it blocks every final run until
    5m/240m, 20m/240m and 80m/240m are accepted for the exact bytes."""
    G = _gate()
    sc, recs = _scene(tmp_path, monkeypatch, ("5m", "20m", "80m", "240m"))
    g = G.evaluate(acceptance_path=_acceptance(tmp_path, sc, recs, A6_PAIRS))
    assert not g["ok"] and len(g["required_pairs"]) == 6 and len(g["accepted_pairs"]) == 3
    assert sorted(m.split(" / ")[0].split(":")[0] for m in g["missing_pairs"]) == ["20m", "5m", "80m"]
    assert all(m.split(" / ")[1].startswith("240m:") for m in g["missing_pairs"])
    assert len(g["reasons"]) == 1 and g["reasons"][0].startswith("A6 acceptance missing")
    for partial in (ALL_PAIRS[:4], ALL_PAIRS[:5]):                       # any 240 m pair still missing: not final
        assert not G.evaluate(acceptance_path=_acceptance(tmp_path, sc, recs, partial))["ok"]


def test_all_six_overlapping_pairs_accepted_meet_the_gate(tmp_path, monkeypatch):
    G = _gate()
    sc, recs = _scene(tmp_path, monkeypatch, ("5m", "20m", "80m", "240m"))
    p = _acceptance(tmp_path, sc, recs, tuple((b, a) for a, b in ALL_PAIRS))   # order within a pair does not matter
    g = G.evaluate(acceptance_path=p)
    assert g["ok"] and g["reasons"] == [] and g["missing_pairs"] == [] and len(g["accepted_pairs"]) == 6
    assert g["acceptance_digest"] == G.acceptance_digest(p) and g["levels_present"] == ["20m", "240m", "5m", "80m"]


@pytest.mark.parametrize("what", ["dem", "error_map"])
def test_a_changed_hash_ends_the_acceptance(tmp_path, monkeypatch, what):
    """Acceptance is bound to the registered bytes: a DEM or error map registered with other bytes than the
    accepted ones leaves every pair of that product unaccepted."""
    from lunaops.engine.dem import product_key, write_registry
    G = _gate()
    sc, recs = _scene(tmp_path, monkeypatch, ("5m", "20m", "80m", "240m"))
    p = _acceptance(tmp_path, sc, recs, ALL_PAIRS)
    k80 = product_key(recs["80m"])
    if what == "dem":
        recs["80m"]["sha256"] = "0" * 64
        sc.reg["error_maps"][k80]["dem_sha256"] = "0" * 64             # keep the error-map link consistent
    else:
        sc.reg["error_maps"][k80]["sha256"] = "1" * 64
    write_registry(sc.reg)
    g = G.evaluate(acceptance_path=p)
    assert not g["ok"] and sorted(g["missing_pairs"]) == sorted(m for m in g["required_pairs"] if k80 in m)
    assert len(g["missing_pairs"]) == 3


def test_missing_or_stale_error_map_and_missing_files_block(tmp_path, monkeypatch):
    from lunaops.engine.dem import product_key, resolve_dem_path, write_registry
    G = _gate()
    sc, recs = _scene(tmp_path, monkeypatch, ("5m", "20m", "80m", "240m"))
    p = _acceptance(tmp_path, sc, recs, ALL_PAIRS)
    assert G.evaluate(acceptance_path=p)["ok"]
    k5 = product_key(recs["5m"])
    em = sc.reg["error_maps"].pop(k5)
    write_registry(sc.reg)
    g = G.evaluate(acceptance_path=p)
    assert not g["ok"] and any("has no registered error map" in r for r in g["reasons"])
    sc.reg["error_maps"][k5] = em
    write_registry(sc.reg)
    resolve_dem_path(em["path"]).unlink()                               # error map file gone
    g = G.evaluate(acceptance_path=p)
    assert not g["ok"] and any("error map of 5m" in r and "missing" in r for r in g["reasons"])
    resolve_dem_path(recs["5m"]["path"]).unlink()                       # a registered DEM file gone: never final,
    g = G.evaluate(acceptance_path=p)                                   # even though 20 m and 240 m are present
    assert not g["ok"] and "5m" not in g["levels_present"] and any("registered but missing" in r for r in g["reasons"])


def test_synthetic_products_are_neither_required_nor_accepted(tmp_path, monkeypatch):
    from lunaops.engine.dem import write_registry
    G = _gate()
    sc, recs = _scene(tmp_path, monkeypatch, ("5m", "20m", "80m", "240m"))
    p = _acceptance(tmp_path, sc, recs, ALL_PAIRS)
    syn = sc.add("SYN10", 10.0, 1500.0, FLAT, err=0.5)                  # overlapping, but synthetic
    assert syn["synthetic"] is True
    write_registry(sc.reg)
    g = G.evaluate(acceptance_path=p)
    assert g["ok"] and len(g["required_pairs"]) == 6 and not any("SYN10" in m for m in g["required_pairs"])


def test_required_pairs_are_the_overlapping_ones():
    G = _gate()
    prods = [{"key": "5m:a", "pixel_m": 5.0, "bounds": (0, 0, 10, 10)},
             {"key": "5m:b", "pixel_m": 5.0, "bounds": (5, 5, 15, 15)},       # same resolution, overlapping
             {"key": "5m:c", "pixel_m": 5.0, "bounds": (100, 100, 110, 110)},  # disjoint from a and b
             {"key": "5m:d", "pixel_m": 5.0, "bounds": (10, 0, 20, 10)},       # touches a along an edge only
             {"key": "20m:e", "pixel_m": 20.0, "bounds": (-50, -50, 50, 50)}]
    got = {(a["key"], b["key"]) for a, b in G.required_pairs(prods)}
    assert got == {("5m:a", "5m:b"), ("5m:b", "5m:d"), ("5m:a", "20m:e"), ("5m:b", "20m:e"), ("5m:d", "20m:e")}


# ------------------------------------------------------------------ the acceptance record
def test_recorded_acceptance_is_the_final_a6_acceptance():
    """The repository record accepts all six pairs across 5 m, 20 m, 80 m and 240 m, for the registered bytes,
    approved by Thilakhaesh K on 2026-11-10; pending_pairs is empty."""
    G = _gate()
    acc = G.load_acceptance()
    reg = json.loads(REPO_REGISTRY.read_text())
    sha = {f"{p['level']}:{Path(p['path']).name}": p["sha256"] for p in reg["products"]}
    em = {k: v["sha256"] for k, v in reg["error_maps"].items()}
    pairs = set()
    for e in acc["accepted_pairs"]:
        assert e["approver"] == "Thilakhaesh K" and e["approved_date"] == "2026-11-10"
        assert (ROOT / e["evidence"]).is_dir()
        for side in ("fine", "coarse"):
            s = e[side]
            assert s["dem_sha256"] == sha[s["key"]]
            assert s["error_map_sha256"] == em[s["key"]]
        pairs.add((e["fine"]["key"].split(":")[0], e["coarse"]["key"].split(":")[0]))
    assert pairs == set(ALL_PAIRS)
    assert acc["pending_pairs"] == []


def test_recorded_acceptance_covers_every_pair_of_the_registered_terrain():
    """Over the repository registry (5 m Site01, 20 m, 80 m and 240 m PGDA 90) every required pair is accepted;
    the gate is met when all registered files are present on disk."""
    G = _gate()
    g = G.evaluate(reg=json.loads(REPO_REGISTRY.read_text()))
    assert len(g["required_pairs"]) == 6 and g["missing_pairs"] == [] and len(g["accepted_pairs"]) == 6
    assert g["ok"]


@pytest.mark.parametrize("patch,msg", [
    ({"approver": " "}, "'approver' is required"),
    ({"approved_date": "10/11/2026"}, "YYYY-MM-DD"),
    ({"evidence": ""}, "'evidence' is required"),
])
def test_acceptance_record_is_checked(tmp_path, patch, msg):
    G = _gate()
    acc = json.loads(G.ACCEPTANCE_FILE.read_text())
    acc["accepted_pairs"][0].update(patch)
    p = tmp_path / "a.json"
    p.write_text(json.dumps(acc))
    with pytest.raises(ValueError, match=re.escape(msg)):
        G.load_acceptance(p)
    g = G.evaluate(acceptance_path=p)
    assert not g["ok"] and g["acceptance_digest"] is None and "unusable" in g["reasons"][0]


def test_acceptance_record_refuses_bad_hashes_and_self_pairs(tmp_path):
    G = _gate()
    acc = json.loads(G.ACCEPTANCE_FILE.read_text())
    bad = json.loads(json.dumps(acc))
    bad["accepted_pairs"][0]["fine"]["dem_sha256"] = "abc"
    selfp = json.loads(json.dumps(acc))
    selfp["accepted_pairs"][0]["coarse"] = selfp["accepted_pairs"][0]["fine"]
    for rec, msg in ((bad, "dem_sha256"), (selfp, "paired with itself"), ({"schema": 2}, "unknown schema")):
        p = tmp_path / "a.json"
        p.write_text(json.dumps(rec))
        with pytest.raises(ValueError, match=msg):
            G.load_acceptance(p)


def test_acceptance_digest_ignores_formatting_but_not_content(tmp_path):
    G = _gate()
    acc = json.loads(G.ACCEPTANCE_FILE.read_text())
    p = tmp_path / "a.json"
    p.write_text(json.dumps(acc, indent=7))
    assert G.acceptance_digest(p) == G.acceptance_digest()
    acc["accepted_pairs"][0]["approved_date"] = "2026-11-11"
    p.write_text(json.dumps(acc))
    assert G.acceptance_digest(p) != G.acceptance_digest()


def test_there_is_no_switch_that_bypasses_the_gate():
    """No validation script keeps a hand-set A6 flag; the gate module has no boolean constants."""
    vdir = ROOT / "backend" / "validation"
    for f in vdir.glob("*.py"):
        assert "a6_complete" not in f.read_text(), f.name
        assert "FINAL_PREREQUISITES" not in f.read_text(), f.name
    G = _gate()
    assert not [k for k, v in vars(G).items() if k.isupper() and isinstance(v, bool)]


def test_gate_never_reads_raster_contents(tmp_path, monkeypatch):
    import rasterio
    G = _gate()
    sc, recs = _scene(tmp_path, monkeypatch, ("5m", "20m", "80m", "240m"))
    p = _acceptance(tmp_path, sc, recs, ALL_PAIRS)

    def refuse(*a, **k):
        raise AssertionError("the gate must not open rasters")
    monkeypatch.setattr(rasterio, "open", refuse)
    assert G.evaluate(acceptance_path=p)["ok"]


# ------------------------------------------------------------------ merge guard
def test_run_metadata_carries_the_acceptance_digest(kernels):
    from validation.common import run_meta
    assert run_meta("x")["terrain_acceptance_digest"] == _gate().acceptance_digest()


@pytest.mark.parametrize("tid,script", [("V-09", "v09_v10_avgvisib"), ("V-10", "v09_v10_avgvisib"),
                                        ("V-11", "v11_psr"), ("V-12", "v12_lroc")])
def test_merge_requires_the_gate_for_every_gated_test(tid, script):
    from validation.common import merge_external
    now = {"code_fingerprint": "c", "suite_fingerprint": "s", "kernel_profile": "production", "kernels": ["k"],
           "terrain_acceptance_digest": "d"}
    meta = {**now, "script": script, "terrain_gate": {"ok": True, "acceptance_digest": "d"}}
    for status in ("passed", "failed", "inconclusive"):
        assert merge_external({}, {"meta": meta, "tests": {tid: {"status": status}}}, now) == []
        unmet = {**meta, "terrain_gate": {"ok": False, "acceptance_digest": "d"}}
        assert merge_external({}, {"meta": unmet, "tests": {tid: {"status": status}}}, now)
        stale = {**meta, "terrain_acceptance_digest": "old", "terrain_gate": {"ok": True, "acceptance_digest": "old"}}
        assert any("different terrain acceptance" in w
                   for w in merge_external({}, {"meta": stale, "tests": {tid: {"status": status}}}, now))
    bare = {k: v for k, v in meta.items() if k != "terrain_gate"}
    assert merge_external({}, {"meta": bare, "tests": {tid: {"status": "not run"}}}, now) == []   # preliminary files


def test_ungated_tests_are_unaffected():
    from validation.common import merge_external
    now = {"code_fingerprint": "c", "suite_fingerprint": "s", "kernel_profile": "production", "kernels": ["k"]}
    meta = {**now, "script": "v13_eclipse"}
    assert merge_external({}, {"meta": meta, "tests": {"V-13": {"status": "passed"}}}, now) == []

