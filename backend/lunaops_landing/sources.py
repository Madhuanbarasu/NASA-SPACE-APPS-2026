"""Terrain sources for landing screening: the engine's registered LOLA products (read only), their registered error
maps, and auxiliary per-DEM products from the separate landing manifest (data/landing/manifest.json).

The production terrain registry (data/dem/registry.json) is only read here, never written. Auxiliary products
(PGDA 78 LDEC count map, NASA slope map, slope-uncertainty map) are tied to one DEM by its SHA-256 and grid; one
whose DEM, grid, size or SHA-256 does not match is not used, and the reason is reported.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from lunaops import settings
from lunaops.engine import dem as edem
from lunaops.engine.frames import south_polar_stereo_xy, unit_from_latlon

R = settings.R_MOON_M
MAX_SIDE_PX = 1201                    # analysis windows are at most 1201 x 1201 pixels (bounded memory and time)
AUX_KINDS = ("count", "slope", "slope_error")


# ------------------------------------------------------------------ projection (spherical south polar stereographic)
def latlon_to_xy(lat: float, lon: float) -> tuple[float, float]:
    """The engine's own forward transform (verified against every DEM's CRS at registration)."""
    return south_polar_stereo_xy(unit_from_latlon(math.radians(lat), math.radians(lon)), R)


def xy_to_latlon(x, y):
    """Inverse of latlon_to_xy: rho = 2R tan(alpha/2), alpha = angular distance from the south pole;
    x = rho sin(lon), y = rho cos(lon). Works on scalars and arrays."""
    rho = np.hypot(x, y)
    alpha = 2.0 * np.arctan(rho / (2.0 * R))
    lat = -90.0 + np.degrees(alpha)
    lon = np.mod(np.degrees(np.arctan2(x, y)), 360.0)
    return lat, lon


def point_scale(x, y):
    """Point scale factor k of the projection (true scale at the pole): k = 1 + (rho / 2R)^2 = 2 / (1 - sin(lat)).
    Map distance = k x distance on the 1737.4 km sphere."""
    return 1.0 + (np.hypot(x, y) / (2.0 * R)) ** 2


# ------------------------------------------------------------------ landing manifest
def landing_dir() -> Path:
    return settings.DATA_DIR / "landing"


def manifest_path() -> Path:
    return landing_dir() / "manifest.json"


def read_manifest() -> dict:
    p = manifest_path()
    if not p.exists():
        return {"products": []}
    return json.loads(p.read_text())


_SHA_OK: dict[tuple, bool] = {}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def aux_problem(entry: dict, dem_rec: dict) -> str | None:
    """Why an auxiliary product cannot be used with this DEM, or None. The SHA-256 is verified once per process
    for each (path, size, mtime)."""
    if entry.get("dem_sha256") != dem_rec.get("sha256"):
        return "it belongs to a different DEM file (SHA-256 mismatch)"
    for k in ("transform", "width", "height"):
        if entry.get(k) != dem_rec.get(k):
            return f"its grid ({k}) differs from the DEM's"
    p = landing_dir() / entry["path"]
    if not p.is_file():
        return f"file missing: {p}"
    st = p.stat()
    if st.st_size != entry.get("bytes"):
        return "file size differs from the manifest"
    key = (str(p), st.st_size, st.st_mtime_ns)
    if key not in _SHA_OK:
        _SHA_OK[key] = _sha256(p) == entry.get("sha256")
    if not _SHA_OK[key]:
        return "file SHA-256 differs from the manifest"
    return None


def aux_for(dem_rec: dict) -> tuple[dict[str, dict], list[str]]:
    """{kind: entry} usable with this DEM, plus notes on entries refused."""
    out, notes = {}, []
    key = edem.product_key(dem_rec)
    for e in read_manifest().get("products", []):
        if e.get("dem_product_key") != key or e.get("kind") not in AUX_KINDS:
            continue
        why = aux_problem(e, dem_rec)
        if why:
            notes.append(f"{e.get('product', e['path'])} not used: {why}")
        else:
            out[e["kind"]] = e
    return out, notes


# ------------------------------------------------------------------ windows
@dataclass
class Window:
    rec: dict
    col0: int
    row0: int
    ncols: int
    nrows: int
    z: np.ndarray                      # float32 heights (m above the 1737.4 km sphere), NaN = no data
    err: np.ndarray | None             # float32 RMS height uncertainty (m) from the DEM's registered error map
    aux: dict[str, np.ndarray] = field(default_factory=dict)
    aux_entries: dict[str, dict] = field(default_factory=dict)
    error_map: dict | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def pixel_m(self) -> float:
        return abs(float(self.rec["transform"][0]))

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        """(xmin, ymin, xmax, ymax) of the window's pixel edges in projected metres."""
        a, _, c, _, e, f = self.rec["transform"]
        x0 = c + a * self.col0
        y_top = f + e * self.row0
        return x0, y_top + e * self.nrows, x0 + a * self.ncols, y_top

    def centres(self) -> tuple[np.ndarray, np.ndarray]:
        """Projected x of each column centre and y of each row centre."""
        a, _, c, _, e, f = self.rec["transform"]
        xs = c + a * (self.col0 + np.arange(self.ncols) + 0.5)
        ys = f + e * (self.row0 + np.arange(self.nrows) + 0.5)
        return xs, ys

    def pixel_of(self, x: float, y: float) -> tuple[int, int] | None:
        a, _, c, _, e, f = self.rec["transform"]
        col = int(math.floor((x - c) / a)) - self.col0
        row = int(math.floor((y - f) / e)) - self.row0
        if 0 <= row < self.nrows and 0 <= col < self.ncols:
            return row, col
        return None


def products_covering(x: float, y: float, half_m: float) -> list[dict]:
    """Usable registered products (finest first) whose grid fully contains the square window."""
    out = []
    for lv in edem.usable_levels():
        if _block(lv, x, y, half_m) is not None:
            out.append(lv)
    return out


def clamp_half(lv: dict, half_m: float) -> float:
    return min(half_m, abs(lv["transform"][0]) * (MAX_SIDE_PX // 2))


def _block(lv: dict, x: float, y: float, half_m: float) -> tuple[int, int, int] | None:
    a, _, c, _, e, f = lv["transform"]
    half_m = clamp_half(lv, half_m)
    half_px = int(math.ceil(half_m / abs(a)))
    col0 = int(math.floor((x - c) / a)) - half_px
    row0 = int(math.floor((y - f) / e)) - half_px
    side = 2 * half_px + 1
    if col0 < 0 or row0 < 0 or col0 + side > lv["width"] or row0 + side > lv["height"]:
        return None
    return col0, row0, side


def _read_aligned(path: Path, col0: int, row0: int, n: int, nodata, negative_is_missing: bool) -> np.ndarray:
    import rasterio
    from rasterio.windows import Window as RW

    with rasterio.open(path) as src:
        a = src.read(1, window=RW(col0, row0, n, n)).astype(np.float32)
        nod = src.nodata if nodata is None else nodata
    if nod is not None and not (isinstance(nod, float) and math.isnan(nod)):
        a[a == np.float32(nod)] = np.nan
    a[~np.isfinite(a)] = np.nan
    if negative_is_missing:
        a[a < 0] = np.nan
    return a


def read_window(lv: dict, x: float, y: float, half_m: float) -> Window:
    """Full-resolution window of product lv around (x, y). Heights go through the engine's own reader
    (nodata, scale/offset and plausibility exactly as in the validated engine)."""
    blk = _block(lv, x, y, half_m)
    if blk is None:
        raise edem.TerrainError("The analysis window is not fully covered by this terrain product.")
    col0, row0, n = blk
    edem._refuse_broken(x, y, half_m, "Landing assessment")          # C08: never substitute silently
    z = edem._read_block(lv, col0, row0, n, n)
    w = Window(rec=lv, col0=col0, row0=row0, ncols=n, nrows=n, z=z, err=None)
    em = edem.error_map_for(lv)
    if em is not None and em.get("same_grid_as_dem"):
        w.err = _read_aligned(edem.resolve_dem_path(em["path"]), col0, row0, n, em.get("nodata"), True)
        w.error_map = em
    elif em is not None:
        w.notes.append("The registered error map is not on the DEM's grid; height uncertainty is not shown.")
    else:
        w.notes.append("No error map is registered for this DEM; height uncertainty is unavailable.")
    entries, notes = aux_for(lv)
    w.notes.extend(notes)
    for kind, e in entries.items():
        w.aux[kind] = _read_aligned(landing_dir() / e["path"], col0, row0, n, e.get("nodata"), kind != "count")
        w.aux_entries[kind] = e
    return w
