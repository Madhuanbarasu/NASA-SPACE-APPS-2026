"""Analytic synthetic terrain for automated tests (V-06, V-07).

These rasters are not lunar data. They are flagged synthetic in the registry,
refused by the engine unless LUNAOPS_ALLOW_SYNTHETIC=1, and labelled in
every result that uses them.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np

from . import settings

STEREO_PROJ4 = ("+proj=stere +lat_0=-90 +lat_ts=-90 +lon_0=0 +k=1 +x_0=0 +y_0=0 "
                "+R=1737400 +units=m +no_defs")

# crater rim centred on the pole: Gaussian ring of height H at radius Rr
RIM_HEIGHT_M = 1500.0
RIM_RADIUS_M = 12_000.0
RIM_WIDTH_M = 2_000.0


def synthetic_height(x: np.ndarray, y: np.ndarray, kind: str) -> np.ndarray:
    if kind == "sphere":
        return np.zeros_like(x, dtype=np.float64)
    r = np.hypot(x, y)
    if kind == "hills":
        # rim whose height varies with azimuth, so a low Sun passes in and out of view (UI demos only)
        th = np.arctan2(y, x)
        rim = 320.0 + 260.0 * np.sin(3 * th) + 140.0 * np.sin(7 * th + 1.0)
        return np.maximum(rim, 0.0) * np.exp(-0.5 * ((r - RIM_RADIUS_M) / RIM_WIDTH_M) ** 2) + \
            40.0 * np.exp(-0.5 * (r / 1500.0) ** 2)
    return RIM_HEIGHT_M * np.exp(-0.5 * ((r - RIM_RADIUS_M) / RIM_WIDTH_M) ** 2)


def write_synthetic_dem(path: Path, pixel: float, half: float, kind: str = "crater") -> None:
    import rasterio
    from rasterio.crs import CRS
    from rasterio.transform import from_origin

    n = int(round(2 * half / pixel))
    xs = -half + pixel * (np.arange(n) + 0.5)
    ys = half - pixel * (np.arange(n) + 0.5)
    X, Y = np.meshgrid(xs, ys)
    Z = synthetic_height(X, Y, kind).astype(np.float32)
    with rasterio.open(path, "w", driver="GTiff", width=n, height=n, count=1, dtype="float32",
                       crs=CRS.from_proj4(STEREO_PROJ4), transform=from_origin(-half, half, pixel, pixel),
                       nodata=-9999.0, compress="deflate", tiled=True) as dst:
        dst.write(Z, 1)
        dst.update_tags(1, units="m")
        dst.update_tags(SYNTHETIC="TEST TERRAIN - NOT LUNAR DATA")


def reference_horizon(lat: float, lon: float, obs_h_m: float, az_deg: np.ndarray, kind: str,
                      max_d: float = 60_000.0, step: float = 2.0) -> np.ndarray:
    """Independent brute-force horizon from the analytic height function (no DEM, no interpolation)."""
    from .engine.frames import enu_basis, south_polar_stereo_xy, unit_from_latlon

    R0 = settings.R_MOON_M
    e, n, u = enu_basis(lat, lon)
    p0 = unit_from_latlon(math.radians(lat), math.radians(lon))
    x0, y0 = south_polar_stereo_xy(p0, R0)
    h0 = float(synthetic_height(np.array([x0]), np.array([y0]), kind)[0])
    S = (R0 + h0 + obs_h_m) * u
    d = np.arange(step, max_d, step)
    delta = d / R0
    out = np.empty(az_deg.size)
    for i, a in enumerate(np.radians(az_deg)):
        t = math.cos(a) * n + math.sin(a) * e
        P = np.outer(np.cos(delta), u) + np.outer(np.sin(delta), t)
        X = 2 * R0 * P[:, 1] / (1 - P[:, 2])
        Y = 2 * R0 * P[:, 0] / (1 - P[:, 2])
        h = synthetic_height(X, Y, kind)
        V = (R0 + h)[:, None] * P - S
        s = (V @ u) / np.linalg.norm(V, axis=1)
        out[i] = math.degrees(math.asin(s.max()))
    return out


def v14_horizon(site, et0: float, days: float = 1.0):
    """Synthetic V-14 horizon that the Sun and Earth both cross often (detection test only, not terrain).

    Every azimuth bin a body visits (within 2 deg) gets a horizon that oscillates with a 1.5 deg
    period about that body's typical top-edge elevation, plus one-bin notches. Earth's arc is
    written last, so where the arcs overlap the horizon follows Earth's level.
    """
    from .engine.ephem import sample_target
    from .engine.visibility import HorizonProfile

    ets = np.arange(et0, et0 + days * 86400.0 + 1, 600.0)
    h = np.full(3600, 30.0)
    az_deg = np.arange(3600) * 0.1
    rng = np.random.default_rng(int(abs(site.lat * 1000 + site.lon)) + 7)
    for target in ("sun", "earth"):
        s = sample_target(site, target, ets)
        level = float(np.median(s.el + s.rho))
        visited = np.zeros(3600, bool)
        for a in s.az:
            i = int(round(a / 0.1))
            visited[np.arange(i - 20, i + 21) % 3600] = True
        idx = np.where(visited)[0]
        h[idx] = level + 0.05 + 0.35 * np.sin(np.radians(az_deg[idx] * 240.0)) \
            + 0.02 * np.sin(np.radians(az_deg[idx] * 1000.0))
        notch = rng.choice(idx, max(1, idx.size // 25), replace=False)
        h[notch] -= rng.uniform(0.1, 0.8, notch.size)
    return HorizonProfile(h, np.zeros(3600, bool))


def interpolated_windows(ets: np.ndarray, v: np.ndarray) -> list[tuple[float, float]]:
    """Positive runs of v sampled at ets, with each edge placed by linear interpolation between the
    bracketing samples (sub-second precision for the smooth event functions used in V-14)."""
    on = v > 0
    out, start = [], None
    for i in range(1, ets.size):
        if on[i] and not on[i - 1]:
            start = ets[i - 1] + (ets[i] - ets[i - 1]) * (-v[i - 1]) / (v[i] - v[i - 1])
        if not on[i] and on[i - 1] and start is not None:
            end = ets[i - 1] + (ets[i] - ets[i - 1]) * v[i - 1] / (v[i - 1] - v[i])
            out.append((float(start), float(end)))
            start = None
    return out


# ------------------------------------------------------------------ V-14 checking
def reference_crossings(ets: np.ndarray, v: np.ndarray) -> list[tuple[float, int]]:
    """Every sign change of v sampled at ets as (time, direction), +1 = becomes positive. The time is
    placed by linear interpolation between the bracketing samples."""
    on = v > 0
    idx = np.where(on[1:] != on[:-1])[0]
    out = []
    for i in idx:
        t = ets[i] + (ets[i + 1] - ets[i]) * (-v[i]) / (v[i + 1] - v[i])
        out.append((float(t), +1 if on[i + 1] else -1))
    return out


class CrossingAccumulator:
    """Collects reference crossings from consecutive chunks of a brute-force series, carrying the last
    sample across chunk boundaries so no crossing is lost at a boundary."""

    def __init__(self):
        self.crossings: list[tuple[float, int]] = []
        self.first_on: bool | None = None
        self.t0 = self.t1 = None
        self._last = None

    def add(self, ets: np.ndarray, v: np.ndarray) -> None:
        if ets.size == 0:
            return
        if self._last is not None:
            ets = np.concatenate([[self._last[0]], ets])
            v = np.concatenate([[self._last[1]], v])
        else:
            self.first_on = bool(v[0] > 0)
            self.t0 = float(ets[0])
        self.crossings += reference_crossings(ets, v)
        self._last = (float(ets[-1]), float(v[-1]))
        self.t1 = float(ets[-1])


def required_crossings(crossings, first_on: bool, t0: float, t1: float, min_window: float = 2.0):
    """Edges of positive windows lasting at least min_window. A window open at t0 or t1 counts with its
    duration inside [t0, t1]; only its interior edges are required."""
    req, on, start = [], first_on, (t0 if first_on else None)
    for t, d in crossings:
        if d > 0:
            start, on = t, True
        elif on:
            if t - start >= min_window:
                if start > t0:
                    req.append((start, +1))
                req.append((t, -1))
            on = False
    if on and start is not None and t1 - start >= min_window and start > t0:
        req.append((start, +1))
    return sorted(req)


def match_events(required, crossings, events: list[float], directions: list[int], match_s: float = 3.0):
    """Direction-aware matching of detector events to reference crossings.

    Returns (offsets of matched required crossings, missed required crossings, unmatched detector
    events). An unmatched event is one with no reference crossing of the same direction within match_s;
    such events must be checked against the event function directly (they may be sub-sample windows
    the 1 s reference cannot see)."""
    ev = np.asarray(events, float)
    dr = np.asarray(directions, int)
    offsets, missed = [], []
    for t, d in required:
        cand = ev[dr == d]
        dt = float(np.min(np.abs(cand - t))) if cand.size else math.inf
        (offsets if dt <= match_s else missed).append(dt if dt <= match_s else (t, d))
    unmatched = []
    ref_t = {+1: np.array([t for t, d in crossings if d > 0]), -1: np.array([t for t, d in crossings if d < 0])}
    for t, d in zip(ev, dr):
        r = ref_t[int(d)]
        if not r.size or float(np.min(np.abs(r - t))) > match_s:
            unmatched.append((float(t), int(d)))
    return offsets, missed, unmatched


def confirm_event(fn_values, t: float, direction: int, half_s: float = 1.5, step_s: float = 0.02) -> bool:
    """True if the event function really changes sign in the stated direction within +/-half_s of t.
    fn_values(ets) -> values of the event function."""
    ets = np.arange(t - half_s, t + half_s + step_s / 2, step_s)
    return any(d == direction for _, d in reference_crossings(ets, np.asarray(fn_values(ets), float)))


def target_edges(site, hp, target: str, ets: np.ndarray, coarse_s: float = 60.0, guard: float = 10.0) -> dict:
    """Brute-force references c, g_top, g_bot (deg) for a target on a uniform 1 s grid `ets`.

    Sun: the vectorized exact spherical cap (disk_edges_many) at every sample. Earth (Phase 3, exact oblate
    limb, ~1 ms per sample): the exact model on a `coarse_s` subgrid, and at every 1 s sample of each coarse
    interval where a crossing is possible, i.e. where the signs differ or either end lies within
    `guard` x (largest coarse-step change of that function over the series) of zero. Elsewhere the samples are
    filled linearly between the exact coarse values; they keep one sign there, so they add no crossings and
    never hide one."""
    from .engine.earth import earth_disk_state
    from .engine.ephem import earth_geo, sample_target
    from .engine.visibility import disk_edges_many

    ets = np.asarray(ets, dtype=float)
    if target != "earth":
        s = sample_target(site, target, ets)
        return disk_edges_many(hp, s.az, s.el, s.rho)

    def exact(t):
        tt = sample_target(site, "earth", t)
        out = np.empty((tt.et.size, 3))
        for i in range(tt.et.size):
            st = earth_disk_state(hp, earth_geo(tt, i), want_f=False)
            out[i] = st["c"], st["g_top"], st["g_bot"]
        return out

    stride = max(1, int(round(coarse_s / (ets[1] - ets[0])))) if ets.size > 1 else 1
    ci = np.unique(np.append(np.arange(0, ets.size, stride), ets.size - 1))
    gc = exact(ets[ci])
    full = np.empty((ets.size, 3))
    for j in range(3):
        full[:, j] = np.interp(ets, ets[ci], gc[:, j])
    full[ci] = gc
    step = np.max(np.abs(np.diff(gc, axis=0)), axis=0) if ci.size > 1 else np.zeros(3)
    need = np.zeros(ci.size - 1, dtype=bool)
    for j in range(3):
        a, b = gc[:-1, j], gc[1:, j]
        need |= ((a > 0) != (b > 0)) | (np.minimum(np.abs(a), np.abs(b)) <= guard * step[j])
    for k in np.nonzero(need)[0]:
        lo, hi = ci[k], ci[k + 1]
        if hi - lo > 1:
            full[lo + 1:hi] = exact(ets[lo + 1:hi])
    return {"c": full[:, 0], "g_top": full[:, 1], "g_bot": full[:, 2]}
