"""Phase 3, item 5: validation labels and the V-09 to V-13 reconciliation.

Before Phase 3 the README required V-04, V-05, V-09 to V-13, U-04 and U-06 for a Validated label, but the
code gated nothing on V-09 to V-12 or on U-04/U-06, V-12 had no owner script (so it could never pass),
events did not require the horizon and disk tests (V-06 to V-08), and a Validated label did not say which
terrain it covered. These tests pin the reconciled rules.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TERRAIN_Q = {"horizon", "disk_visibility", "events", "power_indicator"}
# the agreed mapping (plan and docs/TRACEABILITY.md)
EXTERNAL_GATES = {
    "V-09": {"disk_visibility", "events", "power_indicator"},
    "V-10": {"disk_visibility", "events"},
    "V-11": {"horizon", "disk_visibility", "events", "power_indicator"},
    "V-12": {"horizon", "disk_visibility", "events"},
    "V-13": {"disk_visibility", "events", "power_indicator"},
}


def _all_ids():
    from validation.run_validation import ALL_IDS
    return ALL_IDS


def _passing_report():
    return {t: {"status": "passed"} for t in _all_ids()}


def _labels(tests, used=None, covered=None, blockers=(), synthetic=False, l_corr=None):
    from lunaops.engine.provenance import compute_labels
    return compute_labels(tests, list(blockers), synthetic, l_corr, used, covered)


PRODUCT = {"key": "80m:LDEM_80S_80MPP_ADJ.tiff", "sha256": "a" * 64, "error_map_sha256": "b" * 64, "synthetic": False}


# ------------------------------------------------------------------ ownership
def test_every_blueprint_id_is_automated_or_owned():
    from validation.common import OWNERS
    from validation.run_validation import test_id

    automated = set()
    for f in (ROOT / "backend" / "tests").glob("test_*.py"):
        for name in re.findall(r"^def (test_[VU]\d\d[a-f]?\w*)", f.read_text(), flags=re.M):
            automated.add(test_id(name))
    owners: dict[str, list[str]] = {}
    for script, ids in OWNERS.items():
        for t in ids:
            owners.setdefault(t, []).append(script)
    for t in _all_ids():
        assert t in automated or t in owners, f"{t} is neither automated nor owned by a validation script"
        assert len(owners.get(t, [])) <= 1, f"{t} is owned by several scripts: {owners[t]}"
    assert owners["V-12"] == ["v12_lroc"]
    assert (ROOT / "backend" / "validation" / "v12_lroc.py").exists()


def test_v12_owner_may_report_only_v12():
    from validation.common import merge_external

    now = {"code_fingerprint": "c", "suite_fingerprint": "s", "kernel_profile": "production", "kernels": ["k"],
           "terrain_acceptance_digest": "d"}
    meta = {"script": "v12_lroc", "code_fingerprint": "c", "suite_fingerprint": "s", "kernel_profile": "production",
            "kernels": ["k"], "terrain_acceptance_digest": "d", "terrain_gate": {"ok": True, "acceptance_digest": "d"}}
    tests = {t: {"status": "not run"} for t in _all_ids()}
    assert merge_external(tests, {"meta": meta, "tests": {"V-12": {"status": "passed"}}}, now) == []
    assert tests["V-12"]["status"] == "passed"
    # Phase 4 A6: a V-12 status other than "not run" needs the terrain gate met under the current acceptance record
    for bad in ({**meta, "terrain_gate": {"ok": False, "acceptance_digest": "d"}},
                {**meta, "terrain_gate": {"ok": True, "acceptance_digest": "old"}, "terrain_acceptance_digest": "old"},
                {k: v for k, v in meta.items() if k != "terrain_gate"}):
        assert merge_external({"V-12": {"status": "not run"}}, {"meta": bad, "tests": {"V-12": {"status": "passed"}}},
                              now)
    why = merge_external(tests, {"meta": meta, "tests": {"V-13": {"status": "passed"}}}, now)
    assert any("may not report V-13" in w for w in why)


def test_v12_refuses_to_produce_a_result_without_its_reference(tmp_path):
    """Phase 4 A12 replaced the blocked stub with the LROC comparison; without the reference maps it still writes
    no result (and a run on the current terrain can never be final: tests/test_phase4_v12.py)."""
    import subprocess
    import sys
    out = tmp_path / "v12.json"
    r = subprocess.run([sys.executable, "-m", "validation.v12_lroc", "--out", str(out)], cwd=ROOT / "backend",
                       capture_output=True, text=True)
    assert r.returncode != 0 and "--twi-img" in r.stderr and not out.exists()


# ------------------------------------------------------------------ dependency matrix
def test_all_passing_with_covered_terrain_is_validated():
    out = _labels(_passing_report(), used=[PRODUCT], covered=[PRODUCT])
    assert all(v["validation"] == "Validated" and not v["reasons"] for v in out.values())


@pytest.mark.parametrize("missing_status", ["not run", "failed", "skipped"])
def test_each_test_gates_exactly_its_quantities(missing_status):
    from lunaops.engine.provenance import GLOBAL_TESTS, QUANTITY_TESTS

    for t in _all_ids():
        tests = _passing_report()
        tests[t] = {"status": missing_status}
        out = _labels(tests, used=[PRODUCT], covered=[PRODUCT])
        expected = set(out) if t in GLOBAL_TESTS else {q for q, req in QUANTITY_TESTS.items() if t in req}
        pending = {q for q, v in out.items() if v["validation"] != "Validated"}
        assert pending == expected, (t, pending, expected)
        for q in expected:
            assert any(r.startswith(f"{t}: {missing_status}") for r in out[q]["reasons"]), (t, q)


def test_external_validations_gate_the_agreed_quantities():
    from lunaops.engine.provenance import QUANTITY_TESTS

    for t, quantities in EXTERNAL_GATES.items():
        assert {q for q, req in QUANTITY_TESTS.items() if t in req} == quantities, t
    for t in ("V-06", "V-07", "V-08"):
        assert t in QUANTITY_TESTS["events"]
    for t in ("V-06", "V-07"):
        assert t in QUANTITY_TESTS["power_indicator"]


def test_u04_u06_block_every_label():
    for t in ("U-04", "U-06"):
        tests = _passing_report()
        tests[t] = {"status": "not run"}
        out = _labels(tests, used=[PRODUCT], covered=[PRODUCT])
        assert all(v["validation"] == "Pending validation" for v in out.values())
        assert all(any(t in r and "every Validated label" in r for r in v["reasons"]) for v in out.values())


# ------------------------------------------------------------------ README and TRACEABILITY consistency
def _readme_block():
    text = (ROOT / "README.md").read_text()
    block = text.split("<!-- validated-requirements:start -->")[1].split("<!-- validated-requirements:end -->")[0]
    rows = {}
    for line in block.strip().splitlines():
        m = re.match(r"- (`(\w+)`|every quantity): (.+)$", line.strip())
        assert m, line
        rows[m.group(2) or "*"] = [x.strip() for x in m.group(3).split(",")]
    return rows


def test_readme_requirements_match_the_code():
    from lunaops.engine.provenance import GLOBAL_TESTS, QUANTITY_TESTS

    rows = _readme_block()
    assert rows.pop("*") == GLOBAL_TESTS
    assert rows == QUANTITY_TESTS
    text = (ROOT / "README.md").read_text()
    assert "V-04, V-05, V-09 to V-13, U-04 and U-06 must also pass" in text   # the README's summary sentence
    union = {t for req in QUANTITY_TESTS.values() for t in req} | set(GLOBAL_TESTS)
    for t in ("V-04", "V-05", "V-09", "V-10", "V-11", "V-12", "V-13", "U-04", "U-06"):
        assert t in union


def test_traceability_table_matches_the_code():
    from lunaops.engine.provenance import QUANTITY_TESTS

    text = (ROOT / "docs" / "TRACEABILITY.md").read_text()
    for t, quantities in EXTERNAL_GATES.items():
        row = next(line for line in text.splitlines() if line.startswith(f"| {t} |"))
        listed = {q.strip() for q in row.rstrip(" |").split("|")[-1].split(",")}
        assert listed == quantities == {q for q, req in QUANTITY_TESTS.items() if t in req}, t


# ------------------------------------------------------------------ terrain pin
def test_uncovered_terrain_keeps_terrain_labels_pending():
    out = _labels(_passing_report(), used=[PRODUCT], covered=[])
    for q, v in out.items():
        if q in TERRAIN_Q:
            assert v["validation"] == "Pending validation"
            assert f"terrain product not covered by validation report: {PRODUCT['key']}" in v["reasons"]
        else:
            assert v["validation"] == "Validated"


def test_error_map_change_breaks_coverage():
    other_em = {**PRODUCT, "error_map_sha256": "c" * 64}
    out = _labels(_passing_report(), used=[other_em], covered=[PRODUCT])
    assert out["horizon"]["validation"] == "Pending validation"


def test_synthetic_products_need_no_coverage_and_keep_their_label():
    synth = {"key": "20m:SYNTH.tif", "sha256": "d" * 64, "error_map_sha256": None, "synthetic": True}
    out = _labels(_passing_report(), used=[synth], covered=[], synthetic=True)
    assert out["horizon"]["validation"] == "Synthetic test terrain - not a lunar result"
    assert not any("not covered" in r for r in out["horizon"]["reasons"])


def test_status_page_without_a_result_has_no_terrain_reason():
    out = _labels(_passing_report(), used=None, covered=None)
    assert all(v["validation"] == "Validated" for v in out.values())


def test_report_records_the_terrain_it_covers(tmp_path, monkeypatch):
    from scene_helpers import Scene
    from lunaops.engine.dem import write_registry
    from lunaops.engine.provenance import terrain_products_record

    sc = Scene(tmp_path, monkeypatch)
    rec = sc.add("REAL", 20.0, 1000.0, lambda DX, DY: DX * 0.0, err=0.4)
    sc.add("SYN", 240.0, 6000.0, lambda DX, DY: DX * 0.0)
    rec["synthetic"] = False                        # stands in for a registered NASA product in this temp registry
    sc.reg["products"][0] = rec
    write_registry(sc.reg)
    recs = terrain_products_record()
    assert [r["key"] for r in recs] == [sc.keys["REAL"]]
    assert recs[0]["sha256"] == rec["sha256"] and recs[0]["error_map_sha256"]


# ------------------------------------------------------------------ frame text from metadata
def test_frame_text_comes_from_product_metadata():
    from lunaops.engine.provenance import terrain_frame

    wkt = 'PROJCS["x",GEOGCS["y",DATUM["z",SPHEROID["Moon (2015) - Sphere",1737400,0]]]]'
    real = terrain_frame([{"product_id": "pgda90_80m", "synthetic": False, "crs_wkt": wkt}])
    assert "MOON_ME" in real["frame"] and "DE421" in real["frame"]
    assert "1737400.0 m (from the product CRS)" in real["datum"]
    assert real["frame_alignment"] and "V-02e" in real["frame_alignment"]
    syn = terrain_frame([{"product_id": "synthetic_20m", "synthetic": True}])
    assert "synthetic test terrain" in syn["frame"] and syn["frame_alignment"] is None
    assert "no CRS recorded" in syn["datum"]
    unknown = terrain_frame([{"product_id": "not_in_manifest", "synthetic": False}])
    assert "not in the manifest" in unknown["frame"]


def test_label_rules_are_in_the_result_key(monkeypatch, kernels, synthetic_crater):
    from lunaops.engine import provenance
    from lunaops.engine.analysis import AnalysisRequest, result_id

    req = AnalysisRequest(lat=-89.0, lon=45.0, start_utc="2026-11-14T00:00:00Z", end_utc="2026-11-15T00:00:00Z")
    rid = result_id(req)
    monkeypatch.setitem(provenance.QUANTITY_TESTS, "horizon", provenance.QUANTITY_TESTS["horizon"] + ["V-14"])
    assert result_id(req) != rid
