"""PNG rendering of hazard-map layers on the DEM window's own grid (one PNG pixel per DEM pixel, row 0 = north edge
of the projection grid), so an OpenLayers ImageStatic layer with the window's projected bounds aligns pixel for pixel
with the South Polar Map. Missing values are fully transparent; nothing is interpolated or filled.

Colour ramps are perceptually ordered sequential ramps (cividis-, magma-, plasma- and viridis-like anchor colours,
linearly interpolated). The legend range of each layer is returned with the layer so the key matches the image.
"""
from __future__ import annotations

import io

import numpy as np
from PIL import Image

RAMPS = {
    "elevation": ["#00204c", "#31446b", "#666970", "#958f78", "#cbba69", "#ffe945"],
    "slope": ["#000004", "#3b0f70", "#8c2981", "#de4968", "#fe9f6d", "#fcfdbf"],
    "roughness": ["#0d0887", "#6a00a8", "#b12a90", "#e16462", "#fca636", "#f0f921"],
    "uncertainty": ["#440154", "#3b528b", "#21918c", "#5ec962", "#fde725"],
}
RAMPS["nasa_slope"] = RAMPS["slope"]
COVERAGE = {"missing": (238, 154, 107, 235), "interpolated": (95, 168, 232, 150), "measured": (127, 200, 169, 235),
            "present": (150, 160, 175, 120)}
EXCEED = (238, 90, 90, 230)
SLOPE_RANGE = (0.0, 40.0)


def _hex(c: str) -> tuple[int, int, int]:
    return int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16)


def _lut(name: str) -> np.ndarray:
    anchors = np.array([_hex(c) for c in RAMPS[name]], dtype=np.float64)
    t = np.linspace(0, 1, 256)
    pos = np.linspace(0, 1, len(anchors))
    return np.stack([np.interp(t, pos, anchors[:, i]) for i in range(3)], axis=1).astype(np.uint8)


def value_range(name: str, a: np.ndarray) -> tuple[float, float] | None:
    v = a[np.isfinite(a)]
    if v.size == 0:
        return None
    if name in ("slope", "nasa_slope"):
        return SLOPE_RANGE
    if name == "elevation":
        lo, hi = np.percentile(v, [2, 98])
    else:
        lo, hi = 0.0, float(np.percentile(v, 98))
    if hi - lo < 1e-6:
        hi = lo + 1e-6
    return float(lo), float(hi)


def _png(rgba: np.ndarray) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(rgba, "RGBA").save(buf, format="PNG", optimize=False, compress_level=6)
    return buf.getvalue()


def ramp_png(name: str, a: np.ndarray, rng: tuple[float, float] | None) -> bytes:
    rgba = np.zeros(a.shape + (4,), dtype=np.uint8)
    ok = np.isfinite(a)
    if rng is not None and ok.any():
        lo, hi = rng
        idx = np.clip(((a[ok] - lo) / (hi - lo) * 255.0), 0, 255).astype(np.uint8)
        rgba[ok, :3] = _lut(name)[idx]
        rgba[ok, 3] = 255
    return _png(rgba)


def coverage_png(z: np.ndarray, count: np.ndarray | None) -> bytes:
    rgba = np.zeros(z.shape + (4,), dtype=np.uint8)
    valid = np.isfinite(z)
    rgba[~valid] = COVERAGE["missing"]
    if count is None:
        rgba[valid] = COVERAGE["present"]
    else:
        meas = valid & (count > 0)
        rgba[valid & ~meas] = COVERAGE["interpolated"]
        rgba[meas] = COVERAGE["measured"]
    return _png(rgba)


def exceed_png(a: np.ndarray, thr: float) -> bytes:
    rgba = np.zeros(a.shape + (4,), dtype=np.uint8)
    rgba[np.isfinite(a) & (a > thr)] = EXCEED
    return _png(rgba)


def legend(name: str, rng) -> dict:
    stops = RAMPS.get(name)
    return {"ramp": stops, "range": None if rng is None else [round(rng[0], 3), round(rng[1], 3)],
            "clipped_above": name in ("slope", "nasa_slope")}
