"""Projection and footprint geometry: the landing package must use the same projection as the engine, the DEM
CRS and the frontend South Polar Map (proj4 +proj=stere +lat_0=-90 +lat_ts=-90 +lon_0=0 +k=1 +R=1737400)."""
from __future__ import annotations

import math

import numpy as np
import pytest
from pyproj import Transformer

from lunaops.testing import STEREO_PROJ4
from lunaops_landing.sources import latlon_to_xy, point_scale, xy_to_latlon

POINTS = [(-89.463163, 222.510447), (-89.2, 200.0), (-85.0, 10.0), (-80.0, 300.0), (-70.0, 123.4), (-60.0, 0.0)]


@pytest.mark.parametrize("lat,lon", POINTS)
def test_forward_matches_pyproj_and_inverse_round_trips(lat, lon):
    x, y = latlon_to_xy(lat, lon)
    t = Transformer.from_crs("+proj=longlat +R=1737400 +no_defs", STEREO_PROJ4, always_xy=True)
    px, py = t.transform(lon, lat)
    assert abs(x - px) < 1e-3 and abs(y - py) < 1e-3              # < 1 mm, the engine's own acceptance bound
    la, lo = xy_to_latlon(x, y)
    assert la == pytest.approx(lat, abs=1e-10)
    assert (lo - lon + 180) % 360 - 180 == pytest.approx(0, abs=1e-9)


@pytest.mark.parametrize("lat", [-89.9, -85.0, -80.0, -70.0])
def test_point_scale_equals_numerical_derivative(lat):
    R = 1737400.0
    x0, y0 = latlon_to_xy(lat, 30.0)
    x1, y1 = latlon_to_xy(lat + 1e-4, 30.0)
    k_num = math.hypot(x1 - x0, y1 - y0) / (R * math.radians(1e-4))
    assert float(point_scale(x0, y0)) == pytest.approx(k_num, rel=1e-6)
    assert float(point_scale(x0, y0)) == pytest.approx(2 / (1 - math.sin(math.radians(lat))), rel=1e-12)
