"""Simulation service and HTTP routes on a synthetic analysis result built in memory (no engine run, no cache writes).
Needs the installed kernels for time conversion and the relay's frame transformations (read only)."""
from __future__ import annotations

import json
import math
import re

import numpy as np
import pytest

from lunaops import settings
from lunaops.engine.timeutil import parse_utc

HAVE_KERNELS = (settings.KERNEL_DIR / "lock.json").exists()
pytestmark = pytest.mark.skipif(not HAVE_KERNELS, reason="no kernel lock")
FORBIDDEN = re.compile(r"score|probabilit|rank|recommend|reliab|guarantee|certif", re.I)
FULL = {"pt_w": 10.0, "gt_dbi": 6.0, "ltx_db": 1.0, "gr_dbi": 34.0, "lrx_db": 0.5, "lother_db": 2.0, "ts_k": 200.0,
        "freq_hz": 2.25e9, "rb_bps": 1000.0, "ebn0_req_db": 3.0}


def synthetic_result(horizon_deg=0.0, incomplete=False) -> dict:
    et0 = parse_utc("2026-11-13T00:00:00Z")
    et1 = et0 + 2 * 86400.0
    step = 1800.0
    ets = et0 + step * np.arange(int(2 * 86400 / step) + 1)
    # Earth elevation: a slow sinusoid; distance 384,400 km +- 20,000 km; clearance = el - horizon
    el = 3.0 * np.sin(2 * math.pi * (ets - et0) / 86400.0)
    dist = 384_400.0 + 20_000.0 * np.cos(2 * math.pi * (ets - et0) / 172800.0)
    c = el - horizon_deg
    # engine-style visibility intervals (centre rule): open where c > 0 (exact crossings of the sinusoid)
    ivs, t, state = [], et0, bool(c[1] > 0)
    for k in range(1, ets.size):
        if (c[k] > 0) != state:
            tz = ets[k - 1] + step * (c[k - 1] / (c[k - 1] - c[k]))
            ivs.append({"start_et": t, "end_et": tz, "state": state, "uncertain": False})
            t, state = tz, not state
    ivs.append({"start_et": t, "end_et": et1, "state": state, "uncertain": False})
    utc = ["2026-11-13T00:00:00Z"] * ets.size
    return {
        "id": "synthetic0001", "site": {"lat": -89.0, "lon": 0.0, "name": None, "ground_h_m": 0.0, "terrain_level_at_site": "20m",
                                         "coverage": {"covered": True}},
        "window": {"start_et": et0, "end_et": et1, "start_utc": "2026-11-13T00:00:00Z", "end_utc": "2026-11-15T00:00:00Z"},
        "series": {"et": ets.tolist(), "utc": utc, "step_s": step,
                   "earth": {"el": el.tolist(), "az": [0.0] * ets.size, "dist_km": dist.tolist(), "c": c.tolist(),
                             "f": [1.0 if x > 0 else 0.0 for x in c], "light_time_s": (dist / 299792.458).tolist()}},
        "intervals": {"earth_centre": ivs},
        "horizon": {"h_deg": [horizon_deg] * 3600, "incomplete": [incomplete] * 3600, "sigma_deg": None, "incomplete_share": 1.0 if incomplete else 0.0,
                    "levels": [{"key": "synthetic"}]},
        "labels": {"sun_earth_azel": {"validation": "Validated"}, "horizon": {"validation": "Validated"},
                   "disk_visibility": {"validation": "Pending validation"}, "events": {"validation": "Pending validation"}},
        "provenance": {"parameters": {"observer": {"height_m": 0.0}, "rules": {"dte": "centre"},
                                      "earth_model": {"atmosphere": "not modelled"}},
                       "algorithm_version": "1.5.0", "code_fingerprint": "synthetic", "kernels": {"files": []}},
        "geometric_not_radio": "Earth above the terrain horizon is geometric line of sight.",
    }


@pytest.fixture()
def client(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from lunaops_comms import service as SV
    from lunaops_comms.api import install
    store = {"synthetic0001": synthetic_result(), "walled0001": {**synthetic_result(horizon_deg=10.0), "id": "walled0001"},
             "incomplete001": {**synthetic_result(incomplete=True), "id": "incomplete001"}}
    monkeypatch.setattr(SV, "load_result", lambda rid: store.get(rid))
    app = FastAPI()

    @app.get("/{path:path}")
    def spa(path: str):          # stands in for the real app's single-page-app catch-all
        return {"spa": path}

    install(app)
    return TestClient(app)


RELAY = {"a_km": 1737.4 + 3000.0, "e": 0.0, "i_deg": 90.0, "raan_deg": 0.0, "argp_deg": 0.0, "m0_deg": 0.0,
         "epoch_utc": "2026-11-13T00:00:00Z", "frame": "LME_EPOCH", "step_s": 120.0}


def test_meta_precedes_catch_all_and_reports_gm(client):
    m = client.get("/api/comms/meta").json()
    assert m["comms_version"] == "0.1.0" and m["status"] == "Preliminary simulation, not part of the validated engine"
    assert m["gm"]["gm_km3_s2"] == 4902.8001184575496 and "none" in m["defaults"]


def test_direct_windows_are_the_engine_intervals_and_labels_pass_through(client):
    r = client.post("/api/comms/simulate", json={"result_id": "synthetic0001"}).json()
    vis = [s for s in r["timeline"]["earth_visible"] if s["state"]]
    assert len(vis) == 2 and r["direct"]["stats"]["windows"] == 2
    assert r["engine_labels"] == {"sun_earth_azel": "Validated", "horizon": "Validated",
                                  "disk_visibility": "Pending validation", "events": "Pending validation"}
    assert r["comms_status"].startswith("Preliminary simulation")
    assert set(r["engine_label_reasons"]) == set(r["engine_labels"])
    assert r["timeline"]["direct_rf"] is None                  # no link budget: nothing is called feasible
    assert r["direct"]["link"]["complete"] is False


def test_terrain_blocks_earth(client):
    r = client.post("/api/comms/simulate", json={"result_id": "walled0001"}).json()
    assert r["direct"]["stats"]["windows"] == 0                # a 10 deg wall hides an Earth that rises to 3 deg
    assert r["direct"]["terrain_blocked_stats"]["open_h"] > 20  # above 0 deg about half the time, all of it blocked


def test_rf_feasible_needs_margin_and_geometry(client):
    ok = client.post("/api/comms/simulate", json={"result_id": "synthetic0001", "direct_link": {**FULL, "rb_bps": 1.0}}).json()
    geo = ok["comparison"]["direct_geometric"]["open_h"]
    assert ok["comparison"]["direct_rf"]["open_h"] == pytest.approx(geo, rel=1e-6)   # margin positive everywhere
    bad = client.post("/api/comms/simulate", json={"result_id": "synthetic0001", "direct_link": {**FULL, "rb_bps": 1e12}}).json()
    assert bad["comparison"]["direct_rf"]["open_h"] == 0.0 and bad["comparison"]["direct_geometric"]["open_h"] == geo
    mm = bad["direct"]["link"]["margin_db"]
    assert mm["max"] < 0


def test_relay_two_legs_and_assisted_contacts(client):
    r = client.post("/api/comms/simulate", json={"result_id": "synthetic0001", "relay": RELAY}).json()
    rl = r["relay"]
    assert rl["label"].startswith("Hypothetical relay")
    assert rl["orbit"]["period_h"] == pytest.approx(2 * math.pi * math.sqrt(4737.4 ** 3 / 4902.8001184575496) / 3600, abs=1e-4)
    leg1, leg2, both = r["timeline"]["relay_leg1"], r["timeline"]["relay_leg2"], r["timeline"]["relay_geometric"]
    assert any(s["state"] for s in leg1) and any(not s["state"] for s in leg1)
    # relay-assisted only where BOTH legs are open
    def open_at(tl, t):
        return next(s["state"] for s in tl if s["start_et"] <= t < s["end_et"])
    for s in both:
        mid = 0.5 * (s["start_et"] + s["end_et"])
        assert s["state"] == (open_at(leg1, mid) and open_at(leg2, mid))
    assert r["comparison"]["relay_adds_geometric_h"] >= 0
    assert r["timeline"]["relay_rf"] is None and r["comparison"]["any_rf"] is None   # no relay link budgets
    full = client.post("/api/comms/simulate", json={"result_id": "synthetic0001", "relay": RELAY, "direct_link": FULL,
                                                   "relay_up_link": FULL, "relay_down_link": FULL}).json()
    assert full["timeline"]["relay_rf"] is not None and full["relay"]["leg1"]["link"]["complete"]


def test_incomplete_horizon_gives_unknown_not_open(client):
    r = client.post("/api/comms/simulate", json={"result_id": "incomplete001", "relay": RELAY}).json()
    states = {s["state"] for s in r["timeline"]["relay_leg1"]}
    assert None in states and r["relay"]["leg1"]["unknown_share"] > 0


def test_store_and_forward(client):
    body = {"result_id": "synthetic0001", "direct_link": {**FULL, "rb_bps": 1.0},
            "dtn": {"volume_mbit": 36.0, "rate_kbps": 1.0, "path": "direct_rf"}}
    d = client.post("/api/comms/simulate", json=body).json()["dtn"]
    assert d["evaluated"] and d["transmit_time_h"] == pytest.approx(10.0)       # 36 Mbit at 1 kbit/s = 36,000 s
    assert d["complete"] and sum(p["sent_mbit"] for p in d["plan"]) == pytest.approx(36.0)
    big = client.post("/api/comms/simulate", json={**body, "dtn": {**body["dtn"], "volume_mbit": 1e6}}).json()["dtn"]
    assert not big["complete"] and big["remaining_mbit"] > 0
    none = client.post("/api/comms/simulate", json={"result_id": "synthetic0001", "dtn": {"volume_mbit": 1, "rate_kbps": 1}}).json()["dtn"]
    assert none["evaluated"] is False                                           # direct RF not evaluated without a link budget


def test_errors(client):
    assert client.post("/api/comms/simulate", json={"result_id": "nope00000"}).status_code == 404
    r = client.post("/api/comms/simulate", json={"result_id": "synthetic0001", "relay": {**RELAY, "e": 1.5}})
    assert r.status_code == 422 and "Eccentricity" in r.json()["detail"]
    assert client.post("/api/comms/simulate", json={"result_id": "synthetic0001", "relay": {**RELAY, "a_km": None}}).status_code == 422
    assert client.post("/api/comms/linkbudget", json={"link": {}, "distance_km": 384400}).json()["complete"] is False


def test_no_reliability_or_ranking_vocabulary(client):
    r = client.post("/api/comms/simulate", json={"result_id": "synthetic0001", "relay": RELAY, "direct_link": FULL}).json()
    keys = []

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                keys.append(k)
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(r)
    assert not FORBIDDEN.search(" ".join(keys))
    assert "Hypothetical" in json.dumps(r["relay"]) and "not an actual NASA satellite" in r["relay"]["label"]
