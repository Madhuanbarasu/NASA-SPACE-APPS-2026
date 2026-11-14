"""read_level and hillshade_rgba on synthetic in-memory rasters: georeferencing, smoothing when reducing and enlarging,
product boundaries and missing data. These check the display renderer, not any scientific quantity."""
from __future__ import annotations

import math

import numpy as np
import pytest

from lunaops_tiles.render import hillshade_rgba, read_level

from .helpers import centres, mem_raster, plane

PIX = 20.0
N = 400                      # synthetic product: 400 x 400 pixels of 20 m, x and y in [0, 8000] m
GRAD = float(np.hypot(0.05, 0.02))          # the test plane's height change per metre
# Placement tolerance: a height error on the plane equals a position error of err / GRAD metres. 0.1 source pixel (2 m)
# allows GDAL's sub-pixel window precision (about 1 m was measured) and still fails on any half-pixel shift (10 m).
TOL_M = 0.1 * PIX * GRAD


def _product(fn=plane, n=N, pix=PIX, nodata=float("nan")):
    X, Y = centres(0.0, n * pix, pix, n, n)
    return mem_raster(fn(X, Y), 0.0, n * pix, pix, nodata)


@pytest.mark.parametrize("res", [56.8359375, 28.41796875, 3.55224609375])   # zoom 7 and 8 (reducing), zoom 11 (enlarging)
def test_plane_is_reproduced_at_the_right_place(res):
    """A tilted plane must come back as the same plane at the destination pixel centres (no half-pixel shift)."""
    bx0, by1, n = 1000.3, 7000.7, 40
    with _product() as src:
        got = read_level(src, bx0, by1, res, n, n)
    X, Y = centres(bx0, by1, res, n, n)
    assert np.isfinite(got).all()
    err = np.abs(got - plane(X, Y))[2:-2, 2:-2]
    assert err.max() < TOL_M, f"max height error {err.max():.4f} m = position error {err.max() / GRAD:.2f} m"


@pytest.mark.parametrize("res", [56.8359375, 3.55224609375])
def test_hillshade_of_a_plane_has_no_grid(res):
    """The AUD-06 artefact: a plane read at a non-integer reduction (2.84) or enlargement must shade uniformly."""
    bx0, by1, n = 1000.3, 7000.7, 40
    with _product() as src:
        got = read_level(src, bx0, by1, res, n, n)
    grey = hillshade_rgba(got, res)[..., 0].astype(float)[2:-2, 2:-2]
    assert grey.max() - grey.min() <= 1, f"grey varies {grey.min()}..{grey.max()} on a plane"


def test_partly_covered_and_outside_pixels_stay_empty():
    """A block hanging over the product's left and top edges: only pixels wholly inside the product are filled."""
    res, n = 50.0, 20
    bx0, by1 = -275.0, 8275.0          # 5.5 pixels left of x = 0 and above y = 8000
    with _product() as src:
        got = read_level(src, bx0, by1, res, n, n)
    assert np.isnan(got[:, :6]).all() and np.isnan(got[:6, :]).all()     # outside or partly covered (column/row 5)
    assert np.isfinite(got[6:, 6:]).all()
    X, Y = centres(bx0, by1, res, n, n)
    assert np.abs(got[8:-2, 8:-2] - plane(X, Y)[8:-2, 8:-2]).max() < TOL_M


def test_aligned_edges_lose_no_pixel():
    """When the tile grid and the product edge coincide, the edge pixels are filled (floating-point tolerance)."""
    res, n = 40.0, 10
    with _product() as src:
        got = read_level(src, 0.0, N * PIX, res, n, n)
    assert np.isfinite(got).all()


def test_block_outside_the_product_is_all_empty():
    with _product() as src:
        got = read_level(src, 9000.0, 20000.0, 50.0, 16, 16)
    assert got.shape == (16, 16) and np.isnan(got).all()


@pytest.mark.parametrize("nodata", [float("nan"), -9999.0])
@pytest.mark.parametrize("res, n, bx0, by1", [(56.8359375, 100, 1200.0, 6800.0),     # reduced (bilinear)
                                              (7.1044921875, 200, 3300.0, 4700.0)])  # enlarged (cubic)
def test_missing_data_is_never_blended_into_heights(nodata, res, n, bx0, by1):
    """A hole of missing data (NaN, or a numeric nodata value): read values stay within the valid heights' range, the
    hole stays empty, and heights away from the hole are the plane."""
    def holed(X, Y):
        z = plane(X, Y)
        return np.where(np.hypot(X - 4000, Y - 4000) < 600, nodata, z)
    with _product(holed, nodata=nodata) as src:
        got = read_level(src, bx0, by1, res, n, n, nodata)
    X, Y = centres(bx0, by1, res, n, n)
    valid = plane(X, Y)
    fin = np.isfinite(got)
    assert fin.any()
    lo, hi = plane(0, 0), plane(N * PIX, N * PIX)
    assert (got[fin] >= lo - 1).all() and (got[fin] <= hi + 1).all(), "a nodata value leaked into the heights"
    r = np.hypot(X - 4000, Y - 4000)
    assert np.isnan(got[r < 450]).all(), "the hole was filled"
    far = fin & (r > 800)
    assert np.abs(got[far] - valid[far]).max() < TOL_M


def test_rotated_products_are_refused():
    from affine import Affine
    from rasterio.io import MemoryFile
    with MemoryFile() as mf:
        with mf.open(driver="GTiff", width=8, height=8, count=1, dtype="float32",
                     transform=Affine(10, 1, 0, 0, -10, 80)) as ds:
            ds.write(np.zeros((1, 8, 8), np.float32))
        with mf.open() as ds, pytest.raises(ValueError):
            read_level(ds, 0, 80, 10, 4, 4)


def test_hillshade_colours_are_the_engines():
    """Flat ground under the fixed 40 deg light: grey 40 + 190 * sin(40 deg); blue x 1.02; transparent where no height."""
    arr = np.full((8, 8), 5.0, np.float32)
    arr[0, 0] = np.nan
    rgba = hillshade_rgba(arr, 10.0)
    g = int(40 + 190 * math.sin(math.radians(40)))
    assert rgba.shape == (8, 8, 4) and rgba.dtype == np.uint8
    assert rgba[4, 4, 0] == g and rgba[4, 4, 1] == g and rgba[4, 4, 2] == min(255, int(np.uint8(g) * 1.02))
    assert rgba[0, 0, 3] == 0 and rgba[4, 4, 3] == 255


def test_enlarged_coarse_terrain_has_no_creases():
    """A smooth bowl in 240 m pixels drawn at 56.8 m (x 4.2, zoom 7): cubic enlargement shades without the crease grid
    that a bilinear surface has at every 240 m pixel edge."""
    from rasterio.enums import Resampling
    from rasterio.windows import from_bounds

    from .helpers import line_score

    def bowl(X, Y):
        return 2e-5 * ((X - 30000.0) ** 2 + 0.6 * (Y - 26000.0) ** 2)
    pix, n = 240.0, 250                       # 60 km square
    X, Y = centres(0.0, n * pix, pix, n, n)
    res, m, bx0, by1 = 56.8359375, 256, 15000.3, 45000.7
    with mem_raster(bowl(X, Y), 0.0, n * pix, pix) as src:
        got = read_level(src, bx0, by1, res, m, m)
        win = from_bounds(bx0, by1 - m * res, bx0 + m * res, by1, src.transform)
        lin = src.read(1, window=win, out_shape=(m, m), resampling=Resampling.bilinear).astype(np.float32)
    new_cols, new_rows = line_score(hillshade_rgba(got, res)[..., 0])
    lin_cols, lin_rows = line_score(hillshade_rgba(lin, res)[..., 0])
    assert new_cols < 1.3 and new_rows < 1.3, f"cubic enlargement line score {new_cols}/{new_rows}"
    assert max(lin_cols, lin_rows) > max(new_cols, new_rows), "bilinear enlargement was expected to crease"
