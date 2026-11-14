"""The /api/display/tiles routes on a minimal app with a single-page-app catch-all, as start.py attaches them."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient
    from lunaops_tiles.api import install
    app = FastAPI()

    @app.get("/{path:path}")
    def spa(path: str):           # stands in for the app's catch-all (frontend index.html)
        return PlainTextResponse("spa")

    install(app)
    return TestClient(app)


def test_info_states_what_the_tiles_are(client):
    from lunaops_tiles import STATUS, TILES_VERSION
    r = client.get("/api/display/tiles/info")
    assert r.status_code == 200
    j = r.json()
    assert j["version"] == TILES_VERSION and j["status"] == STATUS and "not scientifically validated" in STATUS
    assert len(j["code_hash"]) == 64


def test_tile_route_is_ahead_of_the_catch_all(client):
    r = client.get("/api/display/tiles/-1/0/0.png")      # an out-of-range zoom: the engine's empty tile
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    assert r.headers["cache-control"] == "public, max-age=86400"
    assert r.headers["x-lunaops-renderer"].startswith("lunaops_tiles ")
    from lunaops.api.tiles import _empty
    assert r.content == _empty()


def test_other_paths_still_reach_the_catch_all(client):
    assert client.get("/api/display/other").text == "spa"
