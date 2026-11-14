"""Phase 1 regression tests: startup and demo isolation, terrain paths, API hardening.

None of these touch a scientific algorithm; they guard the plumbing around it.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
REPO_REGISTRY = BACKEND.parent / "data" / "dem" / "registry.json"


def _sha(p: Path) -> str | None:
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from lunaops.api.main import app
    return TestClient(app)


@pytest.fixture
def isolated_dem(tmp_path, monkeypatch):
    """Point the terrain registry (and its fallback folder) at an empty temporary folder."""
    from lunaops import settings
    dem = tmp_path / "dem"
    dem.mkdir()
    monkeypatch.setattr(settings, "DEM_DIR", dem)
    monkeypatch.setattr(settings, "BASE_DEM_DIR", tmp_path / "no_base")
    monkeypatch.setattr(settings, "DEM_FALLBACK_DIRS", [])
    return dem


# ------------------------------------------------------------------ frontend route
def test_dist_file_refuses_paths_outside_dist(tmp_path, monkeypatch):
    from lunaops import settings
    from lunaops.api.main import _dist_file

    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html></html>")
    (dist / "assets" / "app.js").write_text("console.log(1)")
    (tmp_path / "secret.txt").write_text("secret")
    try:
        (dist / "link.txt").symlink_to(tmp_path / "secret.txt")
    except OSError:
        pass  # symlinks may need privileges on Windows
    monkeypatch.setattr(settings, "FRONTEND_DIST", dist)

    assert _dist_file("assets/app.js") == (dist / "assets" / "app.js").resolve()
    assert _dist_file("index.html") is not None
    for bad in ("", "../secret.txt", "assets/../../secret.txt", str(tmp_path / "secret.txt"), "link.txt",
                "missing.js", "assets"):
        assert _dist_file(bad) is None, bad


def test_spa_route_does_not_serve_files_outside_dist(client):
    from lunaops.api.main import app
    if not any(getattr(r, "path", "") == "/{path:path}" for r in app.routes):
        pytest.skip("frontend/dist not built, so the single-page route is not mounted")
    for url in ("/..%2F..%2Fbackend%2Flunaops%2Fsettings.py", "/%2E%2E/%2E%2E/backend/lunaops/settings.py",
                "/..%2F..%2F..%2Fbackend%2Flunaops%2Fsettings.py"):
        r = client.get(url)
        assert "SYNTHETIC_TERRAIN_ALLOWED" not in r.text, url


# ------------------------------------------------------------------ CORS
def test_cors_allows_only_local_origins(client):
    pre = {"Access-Control-Request-Method": "GET"}
    evil = client.options("/api/status", headers={"Origin": "https://evil.example", **pre})
    assert "access-control-allow-origin" not in evil.headers
    evil_get = client.get("/api/validation", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in evil_get.headers
    for origin in ("http://localhost:5173", "http://127.0.0.1:8000", "http://localhost"):
        ok = client.options("/api/status", headers={"Origin": origin, **pre})
        assert ok.headers.get("access-control-allow-origin") == origin, origin
    # look-alike hosts are not local
    for origin in ("http://localhost.evil.example", "http://127.0.0.1.evil.example:8000"):
        r = client.options("/api/status", headers={"Origin": origin, **pre})
        assert "access-control-allow-origin" not in r.headers, origin


# ------------------------------------------------------------------ input bounds
@pytest.mark.parametrize("radius", ["-1", "0", "1e6", "50.5"])
def test_terrain_radius_is_bounded(client, radius):
    r = client.get(f"/api/terrain?lat=-89.5&lon=0&radius_km={radius}")
    assert r.status_code == 422


# ------------------------------------------------------------------ terrain paths
def test_resolve_windows_absolute_path_on_any_os(isolated_dem):
    from lunaops.engine.dem import resolve_dem_path

    target = isolated_dem / "pgda90_80m" / "f.tif"
    target.parent.mkdir()
    target.write_bytes(b"x")
    rec = r"C:\Users\someone\luna-ops\data\dem\pgda90_80m\f.tif"
    assert resolve_dem_path(rec) == target
    # no "dem" folder in the recorded path: never matched by bare file name, so it is reported missing
    (isolated_dem / "g.tif").write_bytes(b"x")
    assert not resolve_dem_path(r"C:\Users\someone\elsewhere\g.tif").exists()
    # POSIX relative paths are unchanged
    assert resolve_dem_path("pgda90_80m/f.tif") == target


def _register_relative_synthetic(dem: Path) -> dict:
    from lunaops.acquire import _basic_info
    from lunaops.engine.dem import write_registry
    from lunaops.engine.kernels import sha256_of
    from lunaops.testing import write_synthetic_dem

    rel = Path("synthetic_rel") / "SYNTH_REL_240m.tif"
    (dem / rel.parent).mkdir()
    write_synthetic_dem(dem / rel, 240.0, 60_000.0, kind="hills")
    rec = {"level": "240m", "product_id": "synthetic_240m", "path": rel.as_posix(), "sha256": sha256_of(dem / rel),
           "bytes": (dem / rel).stat().st_size, "product": "SYNTHETIC TEST TERRAIN (hills)", "synthetic": True,
           "pixel_m": 240.0, **_basic_info(dem / rel)}
    write_registry({"products": [rec], "error_maps": {}})
    return rec


def test_tiles_render_from_relative_registry_paths(isolated_dem, monkeypatch, tmp_path):
    from lunaops.api.tiles import _empty, render_tile, tile_meta

    _register_relative_synthetic(isolated_dem)
    monkeypatch.chdir(tmp_path)  # a relative path must not depend on the working directory
    meta = tile_meta()
    assert meta is not None
    png = render_tile(len(meta["resolutions"]) - 1, 0, 0)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    centre = len(meta["resolutions"]) // 2
    n = 2 ** centre
    tiles = [render_tile(centre, x, y) for x in (n // 2 - 1, n // 2) for y in (n // 2 - 1, n // 2)]
    assert any(t != _empty() for t in tiles), "terrain around the pole should render"


def test_no_terrain_reason_names_missing_files(isolated_dem):
    from lunaops.engine.dem import TerrainError, coverage_check, load_pyramid, no_terrain_reason, write_registry

    assert no_terrain_reason().startswith("No terrain data are registered")
    write_registry({"products": [{"level": "80m", "path": "pgda90_80m/LDEM_MISSING.tif", "bytes": 10,
                                  "pixel_m": 80.0, "transform": [80.0, 0, -1000.0, 0, -80.0, 1000.0],
                                  "width": 25, "height": 25, "synthetic": False}],
                    "error_maps": {}})
    why = no_terrain_reason()
    assert "LDEM_MISSING.tif" in why and "missing" in why
    with pytest.raises(TerrainError, match="LDEM_MISSING.tif"):
        load_pyramid(-89.9, 0.0)
    assert "LDEM_MISSING.tif" in coverage_check(-89.9, 0.0)["reason"]


# ------------------------------------------------------------------ demo isolation
def test_dem_dir_override_keeps_demo_terrain_out_of_the_lola_registry(tmp_path):
    """start.py --demo sets LUNAOPS_DEM_DIR=data/dem_demo; synthetic terrain must land there only."""
    before = _sha(REPO_REGISTRY)
    env = {**os.environ, "LUNAOPS_DATA_DIR": str(tmp_path), "LUNAOPS_DEM_DIR": str(tmp_path / "dem_demo"),
           "LUNAOPS_ALLOW_SYNTHETIC": "1"}
    code = ("from lunaops import settings; from lunaops.engine.dem import registry_path; "
            "print(settings.DEM_DIR); print(registry_path())")
    out = subprocess.run([sys.executable, "-c", code], cwd=BACKEND, env=env, capture_output=True, text=True,
                         check=True).stdout.split()
    assert Path(out[0]) == (tmp_path / "dem_demo").resolve()
    assert Path(out[1]) == (tmp_path / "dem_demo" / "registry.json").resolve()

    # default (no override) is unchanged: <data>/dem
    env2 = {k: v for k, v in env.items() if k != "LUNAOPS_DEM_DIR"}
    out2 = subprocess.run([sys.executable, "-c", code], cwd=BACKEND, env=env2, capture_output=True, text=True,
                          check=True).stdout.split()
    assert Path(out2[0]) == (tmp_path / "dem").resolve()

    # the committed LOLA registry is never written by any of the above (or by this test session)
    assert _sha(REPO_REGISTRY) == before
    if before is not None:
        reg = json.loads(REPO_REGISTRY.read_text())
        assert not any(p.get("synthetic") for p in reg.get("products", []))
