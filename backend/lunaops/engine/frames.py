"""Coordinates and local frames (blueprint Sections 7.2, 7.4, 8.1; tests V-02, V-03).

Conventions
- Planetocentric latitude, east-positive longitude, heights above the
  1,737.4 km LOLA sphere, all in the body-fixed frame named in the kernel
  lock (MOON_ME_DE440_ME421 in production).
- Local zenith is the sphere normal at the site (a slope never tilts it).
- Azimuth is clockwise from north; elevation is measured from the plane
  perpendicular to the zenith (same definitions as Horizons and AZLCPO).
- Exactly at a pole, north is taken as the body +X axis and east = north x up.
  AZLCPO documents this rule for the north pole; at the south pole it is a
  LUNA-OPS convention (Q9, VT-10).
"""
from __future__ import annotations

import math

import numpy as np

from .. import settings

POLE_TOL = 1e-12  # norm of z x u below which the pole convention applies (IB-4)


class CoordinateError(ValueError):
    pass


def validate_latlon(lat_deg: float, lon_deg: float) -> tuple[float, float]:
    """Range-check and normalize coordinates (U-01). Longitude -> [0, 360)."""
    try:
        lat = float(lat_deg)
        lon = float(lon_deg)
    except (TypeError, ValueError) as exc:
        raise CoordinateError("Latitude and longitude must be numbers in decimal degrees.") from exc
    if not (math.isfinite(lat) and math.isfinite(lon)):
        raise CoordinateError("Latitude and longitude must be finite numbers.")
    if not -90.0 <= lat <= 90.0:
        raise CoordinateError(f"Latitude {lat} is outside -90 to 90 degrees.")
    if not -360.0 <= lon <= 360.0:
        raise CoordinateError(f"Longitude {lon} is outside -360 to 360 degrees.")
    return lat, lon % 360.0


def unit_from_latlon(lat_rad: float, lon_rad: float) -> np.ndarray:
    if abs(abs(lat_rad) - math.pi / 2) < 1e-15:      # exact pole: no spurious x, y round-off
        return np.array([0.0, 0.0, math.copysign(1.0, lat_rad)])
    cl = math.cos(lat_rad)
    return np.array([cl * math.cos(lon_rad), cl * math.sin(lon_rad), math.sin(lat_rad)])


def latlon_to_xyz_m(lat_deg: float, lon_deg: float, height_m: float) -> np.ndarray:
    """Body-fixed position (m) of a point at height above the reference sphere."""
    u = unit_from_latlon(math.radians(lat_deg), math.radians(lon_deg))
    return (settings.R_MOON_M + height_m) * u


def xyz_to_latlon(xyz: np.ndarray) -> tuple[float, float, float]:
    r = float(np.linalg.norm(xyz))
    lat = math.degrees(math.asin(xyz[2] / r))
    lon = math.degrees(math.atan2(xyz[1], xyz[0])) % 360.0
    return lat, lon, r - settings.R_MOON_M


def cross3(a, b) -> np.ndarray:
    """Cross product of 3-vectors along the last axis (broadcasting like np.cross). Same arithmetic, in the same
    order, as np.cross (c0 = a1 b2 - a2 b1, c1 = a2 b0 - a0 b2, c2 = a0 b1 - a1 b0), so bitwise identical, without
    np.cross's per-call axis handling, which dominated the per-step cost of the event detector (Phase 3 item 8)."""
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    out = np.empty(np.broadcast_shapes(a.shape, b.shape))
    a0, a1, a2 = a[..., 0], a[..., 1], a[..., 2]
    b0, b1, b2 = b[..., 0], b[..., 1], b[..., 2]
    out[..., 0] = a1 * b2 - a2 * b1
    out[..., 1] = a2 * b0 - a0 * b2
    out[..., 2] = a0 * b1 - a1 * b0
    return out


def enu_basis(lat_deg: float, lon_deg: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """East, north, up unit vectors in the body-fixed frame (Section 8.1)."""
    u = unit_from_latlon(math.radians(lat_deg), math.radians(lon_deg))
    zxu = np.cross(np.array([0.0, 0.0, 1.0]), u)
    norm = float(np.linalg.norm(zxu))
    if norm < POLE_TOL:
        n = np.array([1.0, 0.0, 0.0])          # pole convention: north = body +X
        e = np.cross(n, u)                      # east = north x up
        e /= np.linalg.norm(e)
        return e, n, u
    e = zxu / norm
    n = np.cross(u, e)
    return e, n, u


def azel(v: np.ndarray, e: np.ndarray, n: np.ndarray, u: np.ndarray) -> tuple[float, float]:
    """Azimuth (deg, clockwise from north, [0, 360)) and elevation (deg) of vector v."""
    r = float(np.linalg.norm(v))
    el = math.degrees(math.asin(max(-1.0, min(1.0, float(np.dot(v, u)) / r))))
    az = math.degrees(math.atan2(float(np.dot(v, e)), float(np.dot(v, n)))) % 360.0
    return az, el


def south_polar_stereo_xy(p: np.ndarray, radius_m: float) -> tuple[float, float]:
    """Spherical south polar stereographic (true scale at the pole, lon_0 = 0).

    For a unit vector p: x = 2R py / (1 - pz), y = 2R px / (1 - pz). This is
    checked numerically against each DEM's embedded CRS before use (dem.py).
    """
    d = 1.0 - p[2]
    return 2.0 * radius_m * p[1] / d, 2.0 * radius_m * p[0] / d
