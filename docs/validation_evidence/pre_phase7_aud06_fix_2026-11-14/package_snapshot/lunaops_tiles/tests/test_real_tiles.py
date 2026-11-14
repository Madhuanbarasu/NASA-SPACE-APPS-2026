"""The corrected tiles against the engine's tiles on the registered LOLA products (read only; skipped without them).

Same tile size, grid, transparency and overall brightness as the engine; no grid lines where the engine has them.
"""
from __future__ import annotations

import io

import numpy as np
import pytest
from PIL import Image

from .helpers import line_score


def _levels():
    try:
        from lunaops.engine.dem import usable_levels
        return {lv["level"]: lv for lv in usable_levels() if not lv.get("synthetic")}
    except Exception:            # noqa: BLE001 - no terrain configured in this environment
        return {}


LEVELS = _levels()
needs_lola = pytest.mark.skipif(not {"20m", "240m"} <= set(LEVELS),
                                reason="the registered LOLA 20 m and 240 m products are not available here")
# zoom/x/y around Site01 and the pole: zoomed out (1, 3), the AUD-06 tiles (6, 7), fine (8, 11)
SAMPLES = [(1, 0, 0), (1, 1, 1), (3, 3, 4), (6, 31, 32), (7, 63, 64), (8, 126, 129), (11, 1011, 1036)]


def _rgba(png: bytes) -> np.ndarray:
    im = Image.open(io.BytesIO(png))
    assert im.size == (256, 256)
    return np.asarray(im.convert("RGBA"))


@needs_lola
@pytest.mark.parametrize("zxy", SAMPLES)
def test_same_footprint_and_brightness_as_the_engine(zxy):
    from lunaops.api.tiles import render_tile as engine_tile
    from lunaops_tiles.render import render_tile
    a, b = _rgba(engine_tile(*zxy)), _rgba(render_tile(*zxy))
    assert (a[..., 3] == b[..., 3]).all(), "the transparent (no terrain) area differs from the engine's"
    m = b[..., 3] > 0
    if m.any():
        assert abs(float(a[..., 0][m].mean()) - float(b[..., 0][m].mean())) < 1.0
        assert np.abs(a[..., 0][m].astype(int) - b[..., 0][m].astype(int)).mean() < 6.0


@needs_lola
@pytest.mark.parametrize("zxy", [(6, 31, 32), (7, 63, 64),          # 20 m product reduced (engine: up to 3.59)
                                 (6, 42, 31), (5, 15, 16),          # across the 20 m product edge; zoom 5
                                 (7, 94, 69), (7, 27, 42)])         # only 240 m, enlarged x 4.2 (engine: up to 3.0)
def test_no_grid_lines_where_the_engine_has_them(zxy):
    from lunaops_tiles.render import render_tile
    cols, rows = line_score(_rgba(render_tile(*zxy))[..., 0])
    assert cols < 1.3 and rows < 1.3, f"line score {cols}/{rows}"


@needs_lola
def test_twenty_metre_level_alone_has_no_grid():
    """The addendum's per-level case: zoom-7 tile 63/64 drawn from the 20 m product only (engine read: 3.23 / 2.50)."""
    import rasterio
    from lunaops.api.tiles import tile_meta
    from lunaops.engine.dem import resolve_dem_path
    from lunaops_tiles.render import hillshade_rgba, read_level
    meta = tile_meta()
    res = meta["resolutions"][7]
    x0, y1 = meta["origin"][0] + 63 * 256 * res, meta["origin"][1] - 64 * 256 * res
    with rasterio.open(resolve_dem_path(LEVELS["20m"]["path"])) as src:
        arr = read_level(src, x0, y1, res, 256, 256, LEVELS["20m"].get("nodata"))
    assert np.isfinite(arr).all()
    cols, rows = line_score(hillshade_rgba(arr, res)[..., 0])
    assert cols < 1.2 and rows < 1.2, f"line score {cols}/{rows}"


@needs_lola
def test_out_of_range_zoom_gives_the_engines_empty_tile():
    from lunaops.api.tiles import _empty, tile_meta
    from lunaops_tiles.render import render_tile
    assert render_tile(-1, 0, 0) == _empty()
    assert render_tile(len(tile_meta()["resolutions"]), 0, 0) == _empty()
