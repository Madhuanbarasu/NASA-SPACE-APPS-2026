"""Phase 4 A11: V-11 permanent-shadow validation (validation/v11_psr.py), on synthetic inputs.

The real reference (PGDA 90 LPSR_80S_20MPP_ADJ.TIF) is float32 with values exactly 0/1 and nodata NaN, but its
overview layers are resampled (fractional, even negative), so interior points must be chosen from the
full-resolution mask. These tests build small shadow maps in the same projection and check the encoding check,
interior sampling (margin, raster border, nodata, overviews, the documented 80-90 deg S coverage), the hourly
illumination test against the original loop, the scoring of incomplete horizons as inconclusive (never dark),
the merge of that status, and the end-to-end result. The 99% criterion is unchanged.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pytest

from conftest import needs_kernels

BACKEND = Path(__file__).resolve().parents[1]


def _V():
    sys.path.insert(0, str(BACKEND))
    from validation import v11_psr
    return v11_psr


def _write_map(path: Path, data: np.ndarray, px: float = 20.0, x0: float = -4000.0, y0: float = 4000.0,
               overviews: bool = False):
    import rasterio
    from rasterio.crs import CRS
    from rasterio.enums import Resampling
    from rasterio.transform import from_origin

    from lunaops.testing import STEREO_PROJ4
    with rasterio.open(path, "w", driver="GTiff", width=data.shape[1], height=data.shape[0], count=1,
                       dtype="float32", crs=CRS.from_proj4(STEREO_PROJ4), transform=from_origin(x0, y0, px, px),
                       nodata=float("nan"), tiled=True, blockxsize=64, blockysize=64) as dst:
        dst.write(data.astype(np.float32), 1)
        if overviews:
            dst.build_overviews([2, 4, 8], Resampling.average)


def _scene(n=400, px=20.0):
    """A shadowed disk of radius 2 km at the centre, a shadowed band touching the left border, a NaN patch inside
    the disk's edge region, and a lit 1-pixel hole inside the disk."""
    xs = (np.arange(n) + 0.5) * px - n * px / 2
    X, Y = np.meshgrid(xs, -xs)
    a = np.zeros((n, n), np.float32)
    a[np.hypot(X, Y) < 2000.0] = 1.0
    a[:, :30] = 1.0                                    # touches the raster border
    a[150:160, 250:262] = np.nan                       # nodata near the disk's edge
    a[200, 230] = 0.0                                  # a single lit pixel inside the disk
    return a, xs


def test_encoding_check(tmp_path):
    V = _V()
    a, _ = _scene()
    p = tmp_path / "m.tif"
    _write_map(p, a)
    enc = V.check_lpsr(str(p))
    assert enc["other"] == 0 and enc["nan"] == 120 and enc["shadow_1"] + enc["lit_0"] + enc["nan"] == a.size
    assert len(enc["sha256"]) == 64 and enc["dtype"] == "float32"
    b = a.copy()
    b[10, 10] = 0.5
    _write_map(tmp_path / "bad.tif", b)
    with pytest.raises(ValueError, match="neither 0, 1"):
        V.check_lpsr(str(tmp_path / "bad.tif"))


def test_interior_points_keep_the_margin_at_full_resolution(tmp_path):
    """Every sampled point is at least 2.5 cells (400 m) in each direction from any full-resolution pixel that is
    not 1 (lit or NaN), no point comes from the band touching the raster border, and sampling is deterministic."""
    V = _V()
    a, xs = _scene()
    p = tmp_path / "m.tif"
    _write_map(p, a)
    pts, info = V.interior_points(str(p), 50, seed=3)
    assert len(pts) == 50 and info["cell_m"] == 160.0 and info["cells_interior"] > 50
    bad_y, bad_x = np.nonzero(~(a == 1))
    bx, by = xs[bad_x], -xs[bad_y]
    for q in pts:
        cheb = np.min(np.maximum(np.abs(bx - q["x_m"]), np.abs(by - q["y_m"])))
        assert cheb >= 400.0 - 10.0 - 1e-6, (q, cheb)        # half a pixel: distances are to pixel centres
        assert q["x_m"] > -4000.0 + 30 * 20.0 + 2 * 160.0     # not taken from the border band
    assert V.interior_points(str(p), 50, seed=3)[0] == pts
    assert V.interior_points(str(p), 10_000, seed=3)[1]["cells_interior"] == len(V.interior_points(str(p), 10_000)[0])


def test_overviews_are_not_used(tmp_path):
    """The same map with averaged overviews (as in the real product) gives exactly the same points; reading the
    overview the old way would mark partly lit cells as shadow."""
    import rasterio
    V = _V()
    a, _ = _scene()
    _write_map(tmp_path / "plain.tif", a)
    _write_map(tmp_path / "ov.tif", a, overviews=True)
    assert V.interior_points(str(tmp_path / "plain.tif"), 80, seed=5) == V.interior_points(str(tmp_path / "ov.tif"), 80, seed=5)
    with rasterio.open(tmp_path / "ov.tif") as src:
        ov = src.read(1, out_shape=(src.height // 8, src.width // 8))
    assert np.any((ov > 0) & (ov < 1))                         # what the old reduction saw


def test_border_is_not_wrapped():
    V = _V()
    m = np.zeros((20, 20), bool)
    m[:, :6] = True                       # touches the left border
    m[:, -6:] = True                      # and the right one: np.roll would join them across the edge
    core = V.erode(m, 2)
    assert not core[:, :2].any() and not core[:, -2:].any()
    assert core[2:-2, 2:4].all()


def test_vectorised_illumination_equals_the_original_loop():
    V = _V()
    rng = np.random.default_rng(11)
    for trial in range(200):
        n = int(rng.integers(3, 300))
        az = np.cumsum(rng.normal(0, rng.choice([0.3, 5, 90, 250]), n)) % 360
        el = rng.normal(rng.uniform(-5, 2), rng.uniform(0.05, 2), n)
        h = rng.normal(rng.uniform(-3, 3), rng.uniform(0.01, 3), 3600)
        if trial % 5 == 0:
            h[rng.integers(0, 3600, 30)] = np.nan
        assert V.first_lit_hour(el, az, h, 0.27)[0] == V.first_lit_hour_loop(el, az, h, 0.27), trial


def test_sun_track_illumination_on_a_flat_horizon():
    """Flat 1 deg horizon: a Sun whose top stays 0.001 deg below it is never lit (clearance 0.001); touching it
    exactly counts as lit; a non-finite horizon counts as -90 deg (lit); a crossing of the 0/360 azimuth seam
    uses the short arc."""
    V = _V()
    rho = 0.27
    t = np.arange(5000)
    az = (t * 0.51) % 360
    el = (1.0 - rho - 0.001) - 0.5 * (1 - np.cos(t / 300.0))
    h = np.full(3600, 1.0)
    first, clear = V.first_lit_hour(el, az, h, rho)
    assert first == -1 and abs(clear - 0.001) < 1e-9
    el2 = el.copy()
    el2[1234] = 1.0 - rho
    assert V.first_lit_hour(el2, az, h, rho)[0] == 1233
    h2 = h.copy()
    h2[100] = np.nan
    assert V.first_lit_hour(el, az, h2, rho)[0] >= 0
    seam = np.array([359.95, 0.05])
    h3 = np.full(3600, 5.0)
    h3[1800] = -10.0                                       # a gap on the far side must not be swept
    assert V.first_lit_hour(np.array([0.0, 0.0]), seam, h3, rho)[0] == -1


def test_point_without_terrain_is_inconclusive():
    """No terrain horizon at all: inconclusive, never scored (formerly counted as not passing)."""
    V = _V()
    from lunaops.engine.dem import TerrainError

    def no_terrain(*_a, **_k):
        raise TerrainError("no registered terrain covers this site")
    r = V.evaluate_point(-89.5, 0.0, np.array([[0.0, 0.0, -1.0]]), 0.27, horizon_fn=no_terrain)
    assert r["outcome"] == "inconclusive" and r["zero_sunlight"] is None and "no terrain horizon" in r["reason"]


class _FakeHorizon:
    def __init__(self, h, incomplete=()):
        self.h_deg = np.full(3600, h, dtype=float)
        self.incomplete = np.zeros(3600, bool)
        self.incomplete[list(incomplete)] = True
        self.levels = [{"level": "synthetic"}]
        self.params = {"h_max_m": 1000.0}


# ------------------------------------------------------------------ documented coverage: 80-90 deg S
def _r80_axis():
    """Map coordinates of 80 deg S on the lon 0 meridian, and the radius of the 80 deg S circle (sphere)."""
    from pyproj import Transformer
    from lunaops.testing import STEREO_PROJ4
    x, y = Transformer.from_crs("+proj=longlat +R=1737400 +no_defs", STEREO_PROJ4, always_xy=True).transform(0.0, -80.0)
    return x, y, math.hypot(x, y)


def test_sampling_stays_inside_the_80S_coverage(tmp_path):
    """A fully shadowed 8 km map straddling the 80 deg S circle: every sampled point lies south of 80 deg S with its
    whole 5 x 5-cell neighbourhood inside (centre at least 2.5 cells = 400 m inside the circle); the outermost
    interior row reaches the limit (not over-trimmed); without the limit the same map yields points north of 80 S."""
    V = _V()
    xc, yc, r80 = _r80_axis()
    p = tmp_path / "edge.tif"
    _write_map(p, np.ones((400, 400), np.float32), x0=xc - 4000.0, y0=yc + 4000.0)
    pts, info = V.interior_points(str(p), 100_000, seed=1)
    assert info["coverage"]["lat_limit_deg"] == -80.0 and "80 - 90 deg South" in info["coverage"]["source"]
    assert 0 < info["cells_shadow_in_coverage"] < info["cells_shadow"] == 2500
    assert len(pts) == info["cells_interior"] < info["cells_interior_ignoring_coverage"]
    inside = np.array([r80 - math.hypot(q["x_m"], q["y_m"]) for q in pts])
    assert all(q["lat"] <= -80.0 for q in pts)
    assert inside.min() >= 400.0 - 1.0, inside.min()                    # 2 cells + half a cell from the limit
    assert inside.min() < 400.0 + 2 * 160.0                              # the margin is not exceeded needlessly
    free, _ = V.interior_points(str(p), 100_000, seed=1, lat_limit=-75.0)
    assert any(q["lat"] > -80.0 for q in free)                           # the limit is what excludes them
    assert V.interior_points(str(p), 50, seed=7) == V.interior_points(str(p), 50, seed=7)


def test_map_outside_the_coverage_gives_no_formal_sample(tmp_path, monkeypatch):
    """Shadow only north of 80 deg S: no interior point, and the run refuses to write a result."""
    V = _V()
    xc, yc, r80 = _r80_axis()
    p = tmp_path / "north.tif"
    k = (r80 + 20_000.0) / r80                                           # 20 km beyond the 80 S circle
    _write_map(p, np.ones((200, 200), np.float32), x0=xc * k - 2000.0, y0=yc * k + 2000.0)
    pts, info = V.interior_points(str(p), 10, seed=1)
    assert pts == [] and info["cells_shadow_in_coverage"] == 0 and info["cells_interior_ignoring_coverage"] > 0
    out = tmp_path / "v11.json"
    monkeypatch.setattr(sys, "argv", ["v11_psr", "--lpsr", str(p), "--points", "5", "--out", str(out)])
    with pytest.raises(SystemExit, match="only 0 interior PSR cells"):
        V.main()
    assert not out.exists()


# ------------------------------------------------------------------ incomplete horizons are inconclusive
def _sun_ring(lat, lon, el_deg, n=720):
    """Unit Sun directions at a constant elevation sweeping all azimuths at the site (body-fixed frame)."""
    from lunaops.engine.frames import enu_basis
    e, nn, u = enu_basis(lat, lon)
    az = np.radians(np.arange(n) * 360.0 / n * 3.0)                       # three full turns
    ce = math.cos(math.radians(el_deg))
    return (ce * np.cos(az))[:, None] * nn + (ce * np.sin(az))[:, None] * e + math.sin(math.radians(el_deg)) * u


def test_incomplete_horizon_is_inconclusive_never_dark():
    """A horizon that would keep the point dark but has incomplete bins (or a non-finite value) is inconclusive,
    with zero_sunlight None; the lower-bound verdict is kept only as an unscored note. Complete horizons are
    scored dark or lit. Incomplete azimuths are reported as runs, merged across 0/360 deg."""
    V = _V()
    lat, lon, rho = -89.5, 0.0, 0.27
    unit = _sun_ring(lat, lon, 1.0)
    dark = V.evaluate_point(lat, lon, unit, rho, horizon_fn=lambda *a: _FakeHorizon(20.0))
    lit = V.evaluate_point(lat, lon, unit, rho, horizon_fn=lambda *a: _FakeHorizon(-10.0))
    assert dark["outcome"] == "dark" and dark["zero_sunlight"] is True and dark["incomplete_bins"] == 0
    assert lit["outcome"] == "lit" and lit["zero_sunlight"] is False
    seam = list(range(3595, 3600)) + list(range(0, 5)) + [1800]
    inc = V.evaluate_point(lat, lon, unit, rho, horizon_fn=lambda *a: _FakeHorizon(20.0, seam))
    assert inc["outcome"] == "inconclusive" and inc["zero_sunlight"] is None and inc["incomplete_bins"] == 11
    assert inc["incomplete_azimuths_deg"] == [[180.0, 180.1], [359.5, 360.5]] and "incomplete" in inc["reason"]
    assert inc["unscored_lower_bound_first_lit_hour"] == -1 and "first_lit_hour" not in inc
    one = V.evaluate_point(lat, lon, unit, rho, horizon_fn=lambda *a: _FakeHorizon(20.0, [42]))
    assert one["outcome"] == "inconclusive" and one["incomplete_bins"] == 1
    fake = _FakeHorizon(20.0)
    fake.h_deg[7] = np.nan
    nan = V.evaluate_point(lat, lon, unit, rho, horizon_fn=lambda *a: fake)
    assert nan["outcome"] == "inconclusive" and nan["incomplete_bins"] == 1
    assert V.bin_runs(np.zeros(3600, bool)) == [] and V.bin_runs(np.ones(3600, bool)) == [[0.0, 360.0]]


@pytest.mark.parametrize("dark,lit,inc,status", [
    (200, 0, 0, "passed"),
    (198, 0, 2, "passed"),          # holds even if both inconclusive points were lit
    (198, 2, 0, "passed"),
    (197, 0, 3, "inconclusive"),    # 98.5% demonstrated; 100% if all three were dark
    (196, 2, 2, "inconclusive"),    # best case exactly 99%
    (195, 3, 2, "failed"),          # best case 98.5%
    (197, 3, 0, "failed"),
    (0, 0, 200, "inconclusive"),    # nothing scored: never a pass
])
def test_scoring_never_counts_inconclusive_as_dark(dark, lit, inc, status):
    V = _V()
    res = [{"outcome": "dark"}] * dark + [{"outcome": "lit"}] * lit + [{"outcome": "inconclusive"}] * inc
    st, c = V.score(res, (True, ""))
    assert st == status and c["n"] == 200 and (c["dark"], c["lit"], c["inconclusive"]) == (dark, lit, inc)
    assert c["dark_share_worst_case"] == dark / 200 and V.PASS_SHARE == 0.99
    # Phase 4 A6: without the shared terrain gate the same counts are never decided (default: not checked)
    for prereq in ((False, "A6 acceptance missing for 20m / 240m"), None):
        st2, c2 = V.score(res, prereq) if prereq else V.score(res)
        assert st2 == "not run" and c2["status_if_final"] == status and c2["prerequisites_met"] is False


def test_inconclusive_status_merges_and_keeps_labels_pending():
    """merge accepts "inconclusive", never combines it into a pass, and every label gated by V-11 stays Pending."""
    sys.path.insert(0, str(BACKEND))
    from validation.common import STATUSES, combine
    from lunaops.engine.provenance import QUANTITY_TESTS, compute_labels
    assert "inconclusive" in STATUSES
    assert combine(None, "inconclusive") == "inconclusive"
    assert combine("passed", "inconclusive") == "inconclusive"
    assert combine("failed", "inconclusive") == "failed"
    allpass = {t: {"status": "passed"} for ts in QUANTITY_TESTS.values() for t in ts}
    allpass.update({"U-04": {"status": "passed"}, "U-06": {"status": "passed"}})
    labels = compute_labels({**allpass, "V-11": {"status": "inconclusive"}}, [], False)
    gated = [q for q, ts in QUANTITY_TESTS.items() if "V-11" in ts]
    assert gated and all(labels[q]["validation"] == "Pending validation" and "V-11: inconclusive" in labels[q]["reasons"]
                         for q in gated)
    assert all(labels[q]["validation"] == "Validated" for q in QUANTITY_TESTS if q not in gated)


def _met_gate():
    """A met terrain gate under the current acceptance record (stands in for registered, accepted terrain)."""
    from validation import terrain_gate
    return {"ok": True, "reasons": [], "acceptance_digest": terrain_gate.acceptance_digest(),
            "required_levels": list(terrain_gate.REQUIRED_LEVELS), "levels_present": ["20m", "240m"],
            "required_pairs": [], "accepted_pairs": [], "missing_pairs": []}


@needs_kernels
@pytest.mark.parametrize("h,incomplete,status", [(20.0, (), "passed"), (-10.0, (), "failed"),
                                                 (20.0, (100, 101), "inconclusive")])
def test_end_to_end_on_a_synthetic_map(kernels, monkeypatch, tmp_path, h, incomplete, status):
    """Real 18.6-year hourly Sun track (production or sandbox kernels) over points sampled from a synthetic map near
    the south pole; a horizon at +20 deg keeps every point dark (passed), one at -10 deg lights every point (failed),
    and a +20 deg horizon with two incomplete bins is inconclusive everywhere (never a pass). The terrain gate is
    stubbed as met here; test_end_to_end_without_the_terrain_gate covers the unmet case."""
    V = _V()
    from validation import terrain_gate
    from validation.common import merge_external, run_meta
    monkeypatch.setattr(terrain_gate, "evaluate", _met_gate)

    a, _ = _scene()
    p = tmp_path / "m.tif"
    _write_map(p, a)
    monkeypatch.setattr(V, "compute_horizon", lambda lat, lon, obs: _FakeHorizon(h, incomplete))
    out = tmp_path / "v11.json"
    monkeypatch.setattr(sys, "argv", ["v11_psr", "--lpsr", str(p), "--points", "12", "--out", str(out)])
    V.main()
    res = json.loads(out.read_text())
    assert res["tests"]["V-11"]["status"] == status and len(res["points"]) == 12
    assert res["criterion"].endswith(">= 0.99") and res["sun_track"]["hours"] == int(18.6 * 365.25 * 24)
    assert res["lpsr"]["other"] == 0 and len(res["lpsr"]["sha256"]) == 64
    assert res["sampling"]["coverage"]["lat_limit_deg"] == -80.0
    assert all(q["lat"] < -89.8 for q in res["points"])
    want = {"passed": "dark", "failed": "lit", "inconclusive": "inconclusive"}[status]
    assert all(q["outcome"] == want for q in res["points"]) and res["scoring"][want] == 12
    if status == "passed":
        assert all(q["zero_sunlight"] and q["min_clearance_deg"] > 0 for q in res["points"])
    if status == "inconclusive":
        assert all(q["zero_sunlight"] is None and q["incomplete_azimuths_deg"] == [[10.0, 10.2]]
                   for q in res["points"])
    assert res["meta"]["terrain_gate"]["ok"] is True
    tests = {"V-11": {"status": "not run"}}
    assert merge_external(tests, res, run_meta("run_validation")) == []
    assert tests["V-11"]["status"] == status


@needs_kernels
def test_end_to_end_without_the_terrain_gate(kernels, monkeypatch, tmp_path):
    """Phase 4 A6: with the real gate (no 240 m terrain, so unmet) an all-dark run is "not run" (preliminary), it
    records the gate, it merges as "not run", and a hand-edited "passed" is refused at merge."""
    V = _V()
    from validation.common import merge_external, run_meta

    a, _ = _scene()
    p = tmp_path / "m.tif"
    _write_map(p, a)
    monkeypatch.setattr(V, "compute_horizon", lambda lat, lon, obs: _FakeHorizon(20.0, ()))
    out = tmp_path / "v11.json"
    monkeypatch.setattr(sys, "argv", ["v11_psr", "--lpsr", str(p), "--points", "12", "--out", str(out)])
    V.main()
    res = json.loads(out.read_text())
    assert res["tests"]["V-11"]["status"] == "not run" and "PRELIMINARY" in res["tests"]["V-11"]["detail"]
    assert res["scoring"]["status_if_final"] == "passed" and res["meta"]["terrain_gate"]["ok"] is False
    tests = {"V-11": {"status": "not run"}}
    assert merge_external(tests, res, run_meta("run_validation")) == [] and tests["V-11"]["status"] == "not run"
    forged = {**res, "tests": {"V-11": {"status": "passed", "detail": "edited"}}}
    why = merge_external({"V-11": {"status": "not run"}}, forged, run_meta("run_validation"))
    assert any("without the terrain acceptance gate" in w for w in why)
