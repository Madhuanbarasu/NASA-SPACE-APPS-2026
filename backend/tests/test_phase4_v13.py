"""Phase 4 A13: V-13 against the NASA GSFC lunar eclipse catalogue (validation/v13_eclipse.py).

The reference contacts (validation/reference/gsfc_lunar_eclipses_2025_2026.json) were transcribed from GSFC's
per-eclipse figures; these tests check the transcription's internal consistency, the TD conversion, that the
Section 10.1 criterion is applied unchanged and actually discriminates, and the reporting path.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

from conftest import needs_kernels

BACKEND = Path(__file__).resolve().parents[1]
REF_PATH = BACKEND / "validation" / "reference" / "gsfc_lunar_eclipses_2025_2026.json"
REF = json.loads(REF_PATH.read_text())


def _V():
    sys.path.insert(0, str(BACKEND))
    from validation import v13_eclipse
    return v13_eclipse


def test_reference_provenance_and_consistency():
    V = _V()
    assert [e["id"] for e in REF["eclipses"]] == ["2025-03-14", "2025-09-07", "2026-03-03", "2026-08-28"]
    assert "eclipse.gsfc.nasa.gov" in REF["source"]["catalogue"] and "Danjon" in REF["source"]["method_stated_in_figures"]
    for e in REF["eclipses"]:
        assert len(e["figure_sha256"]) == 64 and e["figure"].endswith(".pdf")
        assert V.check_reference(e) == [], e["id"]
        keys = set(e["contacts_ut"])
        assert keys == ({"P1", "U1", "U2", "U3", "U4", "P4"} if e["type"] == "total" else {"P1", "U1", "U4", "P4"})


def test_reference_check_catches_transcription_errors():
    V = _V()
    e = copy.deepcopy(REF["eclipses"][0])
    e["contacts_ut"]["P4"] = "2025-03-14 10:00:04"           # 3 s off: breaks the stated penumbral duration
    assert any("penumbral" in p for p in V.check_reference(e))
    e = copy.deepcopy(REF["eclipses"][1])
    e["contacts_ut"]["U2"] = "2025-09-07 17:29:41"           # 1 min off: duration and text-page minute both fail
    probs = V.check_reference(e)
    assert any("total" in p for p in probs) and any("text page" in p for p in probs)
    e = copy.deepcopy(REF["eclipses"][3])
    e["contacts_ut"]["U1"], e["contacts_ut"]["U4"] = e["contacts_ut"]["U4"], e["contacts_ut"]["U1"]
    assert any("order" in p for p in V.check_reference(e))


@needs_kernels
def test_contacts_converted_with_gsfc_delta_t(kernels):
    """TD = UT + GSFC's own Delta T for each eclipse (TD - UT of greatest eclipse), not today's leap seconds."""
    import spiceypy as sp
    V = _V()
    want = {"2025-03-14": 74.5, "2025-09-07": 74.8, "2026-03-03": 75.1, "2026-08-28": 75.4}
    for e in REF["eclipses"]:
        c, dt = V.contacts_et(e)
        assert abs(dt - want[e["id"]]) < 1e-6
        p1_utc = float(sp.str2et(e["contacts_ut"]["P1"] + " UTC"))
        # GSFC's predicted Delta T (~75 s) exceeds the leap-second value (69.184 s) by about 6 s
        assert 5.0 < c["P1"] - p1_utc < 7.0


@needs_kernels
def test_criterion_holds_and_discriminates(kernels):
    """At the nearside centre during the 2026 Aug 28 partial eclipse the criterion passes; moving P1 to just after
    the detected start of partial occultation (or U4 to just before the end of totality) makes it fail."""
    V = _V()
    e = REF["eclipses"][3]
    c, _ = V.contacts_et(e)
    r = V.evaluate(0.0, 0.0, c)
    assert r["passed"] and r["estimate_failures"] == 0
    assert r["margin_partial_start_after_P1_s"] > 60 and r["margin_total_end_before_U4_s"] > 60
    start = c["P1"] + r["margin_partial_start_after_P1_s"]
    assert not V.evaluate(0.0, 0.0, {**c, "P1": start + 1.5})["passed"]       # beyond the 1 s slack
    assert V.evaluate(0.0, 0.0, {**c, "P1": start + 0.5})["passed"]           # within the slack
    end_tot = c["U4"] - r["margin_total_end_before_U4_s"]
    assert not V.evaluate(0.0, 0.0, {**c, "U4": end_tot - 1.5})["passed"]
    no_u = {k: v for k, v in c.items() if k not in ("U1", "U4")}
    assert not V.evaluate(0.0, 0.0, no_u)["passed"]                          # totality seen but no U1/U4 given


@needs_kernels
def test_reference_mode_end_to_end_and_merge(kernels, monkeypatch, tmp_path):
    V = _V()
    from validation.common import merge_external, run_meta

    out = tmp_path / "v13.json"
    monkeypatch.setattr(sys, "argv", ["v13_eclipse", "--reference", str(REF_PATH), "--lat", "0", "--lon", "0",
                                      "--out", str(out)])
    V.main()
    res = json.loads(out.read_text())
    assert res["tests"]["V-13"]["status"] == "passed" and len(res["results"]) == 4
    assert res["meta"]["script"] == "v13_eclipse" and "Section 10.1" in res["criterion"]
    tests = {"V-13": {"status": "not run"}}
    assert merge_external(tests, res, run_meta("run_validation")) == []
    assert tests["V-13"]["status"] == "passed" and tests["V-13"]["script"] == "v13_eclipse"


@needs_kernels
def test_inconsistent_reference_is_refused(kernels, monkeypatch, tmp_path):
    V = _V()
    bad = copy.deepcopy(REF)
    bad["eclipses"][0]["contacts_ut"]["P1"] = "2025-03-14 03:57:30"
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(bad))
    monkeypatch.setattr(sys, "argv", ["v13_eclipse", "--reference", str(p), "--out", str(tmp_path / "o.json")])
    with pytest.raises(SystemExit, match="inconsistent"):
        V.main()
    assert not (tmp_path / "o.json").exists()
