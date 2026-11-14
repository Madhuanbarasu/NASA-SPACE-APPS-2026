"""End-to-end landing screening on the isolated synthetic DEM (see conftest), through the HTTP routes."""
from __future__ import annotations

import io
import json
import math
import re

import numpy as np
import pytest

from .conftest import BOWL, CHECKER, HOLE, PIXEL, SIGMA_M, SLOPE_DEG, TRACK_EVERY

FORBIDDEN = re.compile(r"score|probabilit|rank|certif|\bsafe\b|validated\b", re.I)


@pytest.fixture(scope="module")
def client(synthetic_site):
    from fastapi.testclient import TestClient

    from lunaops.api.main import app
    from lunaops_landing.api import install
    if not any(getattr(r, "path", "").startswith("/api/landing") for r in app.router.routes):
        install(app)
    return TestClient(app)


def _ll(x, y):
    from lunaops_landing.sources import xy_to_latlon
    la, lo = xy_to_latlon(x, y)
    return float(la), float(lo)


def _assess(client, x, y, **kw):
    lat, lon = _ll(x, y)
    body = {"lat": lat, "lon": lon, "window_half_m": kw.pop("half", 1000.0), **kw}
    r = client.post("/api/landing/assess", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def test_routes_precede_the_spa_catch_all(client):
    r = client.get("/api/landing/meta")
    assert r.status_code == 200 and r.json()["landing_version"] == "0.1.0"
    assert "not part of the validated engine" in r.json()["validation_status"]


def test_slope_on_tilted_plane(client):
    a = _assess(client, 3000.0, 2500.0, half=600.0,
                footprint={"lat": _ll(3000.0, 2500.0)[0], "lon": _ll(3000.0, 2500.0)[1], "radius_m": 100.0,
                           "thresholds": {"slope_deg": 12.0}})
    s = a["summary"]["slope_deg"]
    assert s["median"] == pytest.approx(SLOPE_DEG, abs=0.02) and s["max"] < SLOPE_DEG + 0.05
    f = {x["key"]: x for x in a["footprint"]["findings"]}
    assert f["slope"]["status"] == "clear"
    assert f["obstacles"]["status"] == "manual"
    assert a["provenance"]["dem"]["synthetic"] is True
    fp = client.post(f"/api/landing/{a['id']}/footprint",
                     json={"lat": _ll(3000.0, 2500.0)[0], "lon": _ll(3000.0, 2500.0)[1], "radius_m": 100.0,
                           "thresholds": {"slope_deg": 8.0}}).json()
    sf = {x["key"]: x for x in fp["findings"]}["slope"]
    assert sf["status"] == "hazard" and sf["above_threshold_pct"] == pytest.approx(100.0)


def test_no_threshold_means_no_verdict(client):
    a = _assess(client, 3000.0, 2500.0, half=600.0)
    f = {x["key"]: x for x in a["footprint"]["findings"]}
    assert f["slope"]["status"] == "no_threshold" and f["roughness"]["status"] == "no_threshold"


def test_depression_candidate_matches_analytic_bowl(client):
    a = _assess(client, BOWL["x"], BOWL["y"], min_depth_m=1.0,
                footprint={"lat": _ll(BOWL["x"], BOWL["y"])[0], "lon": _ll(BOWL["x"], BOWL["y"])[1], "radius_m": 50.0})
    cands = a["candidates"]
    assert len(cands) == 1
    c = cands[0]
    assert c["diameter_m"] == pytest.approx(2 * BOWL["r"], rel=0.03)
    assert c["depth_m"] == pytest.approx(BOWL["depth"], abs=0.05)
    assert math.hypot(c["x"] - BOWL["x"], c["y"] - BOWL["y"]) < PIXEL
    assert c["sigma_m"] == pytest.approx(SIGMA_M) and c["quality"] == "defined"
    assert c["status"] == "unconfirmed_candidate"
    assert c["measured_share"] == pytest.approx(1 / TRACK_EVERY, abs=0.03)
    f = {x["key"]: x for x in a["footprint"]["findings"]}
    assert f["depressions"]["status"] == "hazard" and f["depressions"]["candidates"] == [1]


def test_depth_filter_and_size_range(client):
    assert _assess(client, BOWL["x"], BOWL["y"], min_depth_m=9.0)["candidates"] == []
    assert _assess(client, BOWL["x"], BOWL["y"], min_diameter_m=500.0)["candidates"] == []


def test_roughness_patch(client):
    a = _assess(client, CHECKER["x"], CHECKER["y"], half=400.0, roughness_baseline_m=30.0)
    assert a["config"]["roughness_window_px"] == 3
    rough = a["summary"]["roughness_m"]
    assert rough["max"] == pytest.approx(CHECKER["amp"] * math.sqrt(1 - 1 / 81), rel=0.01)
    assert rough["min"] == pytest.approx(0.0, abs=1e-4)          # flat ground around the patch
    multi = {m["window_px"]: m for m in a["summary"]["roughness_multiscale"]}
    assert set(multi) == {3, 5, 9, 15}


def test_missing_data_hole(client):
    lat, lon = _ll(HOLE["x"], HOLE["y"])
    a = _assess(client, HOLE["x"], HOLE["y"], footprint={"lat": lat, "lon": lon, "radius_m": 150.0})
    assert a["summary"]["valid_share"] < 1.0
    f = {x["key"]: x for x in a["footprint"]["findings"]}
    assert f["slope"]["status"] == "insufficient" and f["depressions"]["status"] == "insufficient"
    pt = client.get(f"/api/landing/{a['id']}/point", params={"lat": lat, "lon": lon}).json()
    assert pt["inside"] and pt["missing"] and pt["elevation_m"] is None and pt["slope_deg"] is None


def test_footprint_geometry_and_limits(client):
    a = _assess(client, 3000.0, 2500.0, half=600.0)
    lat, lon = _ll(3000.0, 2500.0)
    fp = client.post(f"/api/landing/{a['id']}/footprint", json={"lat": lat, "lon": lon, "radius_m": 200.0}).json()
    assert fp["pixels"] == pytest.approx(math.pi * 200.0 ** 2 / PIXEL ** 2, rel=0.02)
    assert fp["coverage"]["measured_pct"] == pytest.approx(100 / TRACK_EVERY, abs=2.0)
    far = _ll(3000.0 + 900.0, 2500.0)
    out = client.post(f"/api/landing/{a['id']}/footprint", json={"lat": far[0], "lon": far[1], "radius_m": 50.0}).json()
    assert not out["inside_window"] and all(x["status"] in ("insufficient", "manual") for x in out["findings"])
    tiny = client.post(f"/api/landing/{a['id']}/footprint", json={"lat": lat, "lon": lon, "radius_m": 8.0}).json()
    assert {x["key"]: x for x in tiny["findings"]}["slope"]["status"] == "higher_res"


def test_layers_align_with_window_grid(client):
    from PIL import Image
    a = _assess(client, 3000.0, 2500.0, half=600.0)
    n = a["provenance"]["window"]["pixels"]
    x0, y0, x1, y1 = a["extent_xy_m"]
    assert (x1 - x0) / PIXEL == n[1] and (y1 - y0) / PIXEL == n[0]
    assert (x0 / PIXEL).is_integer() and (y1 / PIXEL).is_integer()      # extent on the DEM's pixel edges
    for name in ("elevation", "slope", "roughness", "coverage", "uncertainty"):
        r = client.get(f"/api/landing/{a['id']}/layer/{name}.png")
        assert r.status_code == 200
        im = Image.open(io.BytesIO(r.content))
        assert im.size == (n[1], n[0]) and im.mode == "RGBA"
    assert client.get(f"/api/landing/{a['id']}/layer/nasa_slope.png").status_code == 404
    assert client.get(f"/api/landing/{a['id']}/layer/slope_exceed.png", params={"threshold": 5}).status_code == 200


def test_output_has_no_verdicts_scores_or_validated_claims(client):
    a = _assess(client, BOWL["x"], BOWL["y"])
    keys = json.dumps(_keys(a))
    assert not FORBIDDEN.search(keys)
    statuses = {f["status_text"] for f in a["footprint"]["findings"]}
    assert all(not FORBIDDEN.search(s) for s in statuses)
    assert a["provenance"]["validation_status"].startswith("Preliminary screening")


def _keys(o):
    if isinstance(o, dict):
        return [k for k in o] + [kk for v in o.values() for kk in _keys(v)]
    if isinstance(o, list):
        return [kk for v in o for kk in _keys(v)]
    return []


def test_unknown_assessment_and_bad_input(client):
    assert client.get("/api/landing/nope/point", params={"lat": -89, "lon": 0}).status_code == 404
    assert client.post("/api/landing/assess", json={"lat": -40, "lon": 0}).status_code == 422
    assert client.post("/api/landing/assess", json={"lat": -89.9, "lon": 0, "window_half_m": 50}).status_code == 422
