"""Shared helpers for the display-tile tests: in-memory synthetic rasters and the AUD-06 line score.

No environment variable is set and no registry is written: synthetic rasters live in memory (rasterio MemoryFile).
"""
from __future__ import annotations

import math
from contextlib import contextmanager

import numpy as np


@contextmanager
def mem_raster(arr: np.ndarray, left: float, top: float, pixel: float, nodata=float("nan")):
    """A north-up single-band float32 GeoTIFF in memory, upper-left corner (left, top), square pixels."""
    from affine import Affine
    from rasterio.io import MemoryFile

    h, w = arr.shape
    profile = {"driver": "GTiff", "width": w, "height": h, "count": 1, "dtype": "float32",
               "transform": Affine(pixel, 0, left, 0, -pixel, top), "nodata": nodata}
    with MemoryFile() as mf:
        with mf.open(**profile) as ds:
            ds.write(arr.astype(np.float32), 1)
        with mf.open() as ds:
            yield ds


def plane(x, y, a=0.05, b=0.02, c=100.0):
    return a * x + b * y + c


def centres(bx0: float, by1: float, res: float, ncols: int, nrows: int):
    """Projected coordinates of the destination pixel centres (X, Y), shape (nrows, ncols)."""
    xs = bx0 + (np.arange(ncols) + 0.5) * res
    ys = by1 - (np.arange(nrows) + 0.5) * res
    return np.meshgrid(xs, ys)


def line_score(img: np.ndarray) -> tuple[float, float]:
    """Strength of 1-pixel straight lines along columns and rows (the addendum's measure).

    The image is high-passed (each pixel minus the mean of its four neighbours); each column and row of that is
    averaged, and the mean magnitude is divided by the expected noise level. About 0.6-0.9: no lines; about 3: clear lines.
    """
    img = np.asarray(img, dtype=float)
    hp = img - (np.roll(img, 1, 0) + np.roll(img, -1, 0) + np.roll(img, 1, 1) + np.roll(img, -1, 1)) / 4
    hp = hp[2:-2, 2:-2]
    n = hp.std() + 1e-12
    return (round(float(np.abs(hp.mean(axis=0)).mean() / n * math.sqrt(hp.shape[0])), 2),
            round(float(np.abs(hp.mean(axis=1)).mean() / n * math.sqrt(hp.shape[1])), 2))
