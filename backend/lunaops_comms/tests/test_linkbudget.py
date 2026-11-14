"""Link-budget equations against analytic values, and every missing or invalid input left unevaluated."""
from __future__ import annotations

import math

import pytest

from lunaops_comms import linkbudget as LB

C = 299_792_458.0
K = 1.380649e-23
FULL = {"pt_w": 10.0, "gt_dbi": 6.0, "ltx_db": 1.0, "gr_dbi": 34.0, "lrx_db": 0.5, "lother_db": 2.0, "ts_k": 200.0,
        "freq_hz": 2.25e9, "rb_bps": 1000.0, "ebn0_req_db": 3.0}


def test_fspl_matches_definition_and_handbook_form():
    d_km, f = 384_400.0, 2.2e9
    r = LB.evaluate({"freq_hz": f}, d_km)
    lam = C / f
    exact = 20 * math.log10(4 * math.pi * d_km * 1000 / lam)
    assert r["values"]["fspl_db"] == pytest.approx(exact, abs=1e-9)
    # handbook form FSPL = 20 log10(d_km) + 20 log10(f_MHz) + 20 log10(4 pi 1e9 / c) (= 32.4478 dB)
    hb = 20 * math.log10(d_km) + 20 * math.log10(f / 1e6) + 20 * math.log10(4 * math.pi * 1e9 / C)
    assert r["values"]["fspl_db"] == pytest.approx(hb, abs=1e-9)
    assert 20 * math.log10(4 * math.pi * 1e9 / C) == pytest.approx(32.4478, abs=1e-4)
    assert r["values"]["fspl_db"] == pytest.approx(211.0, abs=0.1)


def test_full_chain_by_hand():
    d_km = 1000.0
    r = LB.evaluate(FULL, d_km)
    fspl = 20 * math.log10(4 * math.pi * d_km * 1000 * FULL["freq_hz"] / C)
    pt = 10.0                                            # 10 W = 10 dBW
    eirp = pt + 6.0 - 1.0
    pr = pt + 6.0 + 34.0 - 1.0 - 0.5 - 2.0 - fspl
    cn0 = pr - 10 * math.log10(K) - 10 * math.log10(200.0)
    ebn0 = cn0 - 30.0
    v = r["values"]
    assert v["eirp_dbw"] == pytest.approx(eirp)
    assert v["pr_dbw"] == pytest.approx(pr, abs=1e-9)
    assert v["cn0_dbhz"] == pytest.approx(cn0, abs=1e-9)
    assert v["ebn0_db"] == pytest.approx(ebn0, abs=1e-9)
    assert v["margin_db"] == pytest.approx(ebn0 - 3.0, abs=1e-9)
    assert r["complete"] and r["notes"][0].startswith("Pt = 10 log10(10 W) = 10.000 dBW")
    assert 10 * math.log10(K) == pytest.approx(-228.599, abs=1e-3)


def test_dbw_input_and_bandwidth():
    p = dict(FULL)
    p.pop("pt_w")
    p["pt_dbw"] = 10.0
    p["bandwidth_hz"] = 2000.0
    r = LB.evaluate(p, 1000.0)
    assert r["values"]["margin_db"] == pytest.approx(LB.evaluate(FULL, 1000.0)["values"]["margin_db"])
    assert r["cn_db"] == pytest.approx(r["values"]["cn0_dbhz"] - 10 * math.log10(2000.0))


def test_array_distances_follow_inverse_square():
    r = LB.evaluate(FULL, [1000.0, 2000.0])
    m = r["values"]["margin_db"]
    assert m[0] - m[1] == pytest.approx(20 * math.log10(2.0))


@pytest.mark.parametrize("drop, stage", [("ts_k", "cn0_dbhz"), ("gr_dbi", "pr_dbw"), ("gt_dbi", "eirp_dbw"),
                                         ("rb_bps", "ebn0_db"), ("ebn0_req_db", "margin_db"), ("freq_hz", "fspl_db"),
                                         ("pt_w", "eirp_dbw"), ("lother_db", "pr_dbw")])
def test_missing_input_leaves_stage_and_later_unevaluated(drop, stage):
    p = {k: v for k, v in FULL.items() if k != drop}
    r = LB.evaluate(p, 1000.0)
    keys = [s["key"] for s in r["stages"]]
    i = keys.index(stage)
    assert r["stages"][i]["evaluated"] is False and drop in r["stages"][i]["missing"]
    assert all(r["values"][k] is None for k in keys[i:]) and not r["complete"]
    assert all(r["values"][k] is not None for k in keys[:i] if k != "fspl_db" or drop != "freq_hz")


@pytest.mark.parametrize("field, value", [("pt_w", 0.0), ("pt_w", -5.0), ("freq_hz", 0.0), ("freq_hz", -1e9), ("rb_bps", 0.0),
                                          ("rb_bps", -10.0), ("ts_k", 0.0), ("ltx_db", -1.0), ("freq_hz", float("nan")),
                                          ("freq_hz", "abc")])
def test_invalid_values_are_reported_never_used(field, value):
    p = dict(FULL)
    p[field] = value
    r = LB.evaluate(p, 1000.0)
    assert field in r["problems"] and not r["complete"] and r["values"]["margin_db"] is None


def test_inconsistent_power_units_rejected_and_nothing_assumed():
    p = dict(FULL)
    p["pt_dbw"] = 20.0                    # 10 W is 10 dBW, not 20
    r = LB.evaluate(p, 1000.0)
    assert "pt_dbw" in r["problems"] and r["values"]["eirp_dbw"] is None
    empty = LB.evaluate({}, 1000.0)
    assert all(v is None for v in empty["values"].values()) and empty["inputs"] == {}


def test_breakdown_rows_and_basis():
    b = LB.breakdown({**FULL, "basis": "specification", "reference": "datasheet X rev B"}, 1000.0)
    assert [r["key"] for r in b["rows"]] == ["fspl_db", "eirp_dbw", "pr_dbw", "cn0_dbhz", "ebn0_db", "margin_db"]
    assert all(r["evaluated"] and r["unit"] for r in b["rows"]) and b["reference"] == "datasheet X rev B"
    assert b["basis"].startswith("Values the user attributes")
    assert LB.breakdown(FULL, 1000.0)["basis"].startswith("Illustrative")
