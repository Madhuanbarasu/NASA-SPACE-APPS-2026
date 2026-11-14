"""LOLA terrain access (blueprint Sections 5.1, 6.1-6.3, 8.4; Q10).

Data stay local and versioned (data/dem/registry.json). The registry holds a
list of products, so several files can share a pixel scale (for example the
PGDA 5 m mosaic plus several PGDA 5 m site DEMs). Every product records its
CRS, transform, units, nodata and SHA-256. The engine uses an analytic south
polar stereographic transform only after verifying it against the file's own
CRS to better than 1 mm; otherwise the file is refused.

Heights are metres above the 1,737.4 km sphere. Missing data become NaN and
are never replaced with a flat surface (C08). Values outside +/-20 km (no lunar
surface point is that far from the sphere) are also treated as nodata.

Safeguards (C08): a registered product whose file is missing or whose size no
longer matches the registry is never skipped silently; any analysis that would
have used it is refused with the reason. Cache keys and provenance are built
from the products actually usable now, so changing the registry, removing a
file or toggling synthetic terrain can never return a stale horizon.

Error maps belong to exactly one DEM: each records the SHA-256 of its DEM, and
a horizon bin's uncertainty is read only from the error map of the product that
supplied that bin's blocking terrain sample.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path, PureWindowsPath

import numpy as np

from .. import settings
from .frames import south_polar_stereo_xy, unit_from_latlon

LEVEL_ORDER = ["5m", "10m", "20m", "40m", "60m", "80m", "120m", "240m"]
MAX_ABS_HEIGHT_M = 20_000.0   # plausibility bound: lunar heights lie within about -9.1 to +10.8 km


class TerrainError(RuntimeError):
    pass


def registry_path() -> Path:
    return settings.DEM_DIR / "registry.json"


def _windows_abs(p: str | Path) -> PureWindowsPath | None:
    """A Windows absolute path (drive letter or UNC) recorded on another machine, read on any OS."""
    s = str(p)
    if "\\" not in s and not (len(s) > 1 and s[1] == ":"):
        return None
    w = PureWindowsPath(s)
    return w if w.is_absolute() else None


def _search_bases() -> list[tuple[Path, str]]:
    """DEM_DIR first, then only the folders listed in LUNAOPS_DEM_FALLBACK_DIRS (never an implicit one)."""
    out = [(Path(settings.DEM_DIR), "DEM_DIR")]
    for d in getattr(settings, "DEM_FALLBACK_DIRS", []) or []:
        out.append((Path(d), f"fallback:{d}"))
    return out


def resolve_dem_path_source(p: str | Path) -> tuple[Path, str]:
    """Resolve a DEM or error-map path and say where it was found.

    Relative paths and paths recorded on another machine (POSIX or Windows) are looked up under DEM_DIR,
    then under the explicitly listed fallback folders. The source is "absolute", "DEM_DIR",
    "fallback:<folder>" or "unresolved" (the returned path then does not exist and is reported missing).
    """
    win = _windows_abs(p) if not Path(p).is_absolute() else None
    if win is not None:
        # e.g. C:\Users\...\data\dem\pgda90_80m\x.tif recorded on Windows, read on Linux/macOS
        parts = [q.lower() for q in win.parts]
        if "dem" in parts:
            idx = len(parts) - 1 - parts[::-1].index("dem")
            sub = Path(*win.parts[idx + 1:])
            for base, label in _search_bases():
                if (base / sub).exists():
                    return base / sub, label
        # not found: fall through, so the unresolved path is reported missing (never matched by bare name)
    path = Path(p)
    if path.is_absolute():
        if path.exists():
            return path, "absolute"
        # absolute path recorded on a different machine: use the part after the last 'dem' folder
        parts = path.parts
        if "dem" in parts:
            idx = len(parts) - 1 - parts[::-1].index("dem")
            sub = Path(*parts[idx + 1:])
            for base, label in _search_bases():
                if (base / sub).exists():
                    return base / sub, label
        return path, "unresolved"
    for base, label in _search_bases():
        if (base / path).exists():
            return base / path, label
    return Path(settings.DEM_DIR) / path, "unresolved"


def resolve_dem_path(p: str | Path) -> Path:
    """Resolve a DEM or error-map path (see resolve_dem_path_source)."""
    return resolve_dem_path_source(p)[0]


def product_key(rec: dict) -> str:
    return f"{rec['level']}:{Path(rec['path']).name}"


def _migrate(reg: dict) -> dict:
    """Convert the original one-file-per-level registry into the product list."""
    if "products" in reg:
        reg.setdefault("error_maps", {})
        return reg
    products = []
    for level, rec in (reg.get("levels") or {}).items():
        rec = dict(rec)
        rec.setdefault("level", level)
        products.append(rec)
    emaps = {}
    for level, em in (reg.get("error_maps") or {}).items():
        owner = next((p for p in products if p["level"] == level), None)
        if owner:
            emaps[product_key(owner)] = em
    return {"products": products, "error_maps": emaps}


def read_registry() -> dict:
    p = registry_path()
    if not p.exists():
        return {"products": [], "error_maps": {}}
    return _migrate(json.loads(p.read_text()))


def write_registry(reg: dict) -> None:
    reg = _migrate(reg)
    reg["products"].sort(key=_sort_key)
    registry_path().parent.mkdir(parents=True, exist_ok=True)
    registry_path().write_text(json.dumps({"products": reg["products"], "error_maps": reg["error_maps"]},
                                          indent=2, sort_keys=True))


def _sort_key(rec: dict):
    lv = rec.get("level", "")
    idx = LEVEL_ORDER.index(lv) if lv in LEVEL_ORDER else 99
    return (float(rec.get("pixel_m") or 1e9), idx, int(rec.get("priority", 50)), Path(rec["path"]).name)


def file_problem(rec: dict) -> str | None:
    """Why a registered file cannot be used as registered (None if it looks intact).

    Cheap check (existence and byte size). `python -m lunaops.acquire verify` re-hashes every file.
    """
    path = resolve_dem_path(rec["path"])
    if not path.exists():
        return f"{path.name} is registered but missing from {path.parent}"
    want = rec.get("bytes")
    if want is not None and path.stat().st_size != int(want):
        return (f"{path.name} has changed on disk ({path.stat().st_size} bytes, registered {int(want)} bytes); "
                "re-register it")
    return None


def broken_products() -> list[tuple[dict, str]]:
    """Registered, eligible (non-synthetic, or synthetic while allowed) products that fail file_problem."""
    out = []
    for rec in read_registry()["products"]:
        if rec.get("synthetic") and not settings.SYNTHETIC_TERRAIN_ALLOWED:
            continue
        why = file_problem(rec)
        if why:
            out.append((rec, why))
    return out


def no_terrain_reason() -> str:
    """Why no terrain is usable: an empty registry, or registered files that are missing or changed."""
    broken = broken_products()
    if not broken:
        return ("No terrain data are registered. Download the PGDA LOLA DEMs listed in the README and register "
                "them with `python -m lunaops.acquire register-dem`.")
    return ("No registered terrain is usable: " + "; ".join(why for _, why in broken) +
            ". Restore the file(s) or run `python -m lunaops.acquire unregister-dem`.")


def usable_levels() -> list[dict]:
    """Registered products usable now, finest first (name kept for compatibility)."""
    out = []
    for rec in read_registry()["products"]:
        if rec.get("synthetic") and not settings.SYNTHETIC_TERRAIN_ALLOWED:
            continue
        if file_problem(rec):
            continue
        out.append(rec)
    out.sort(key=_sort_key)
    return out


def terrain_is_synthetic() -> bool:
    return any(lv.get("synthetic") for lv in usable_levels())


def error_map_for(rec: dict, reg: dict | None = None) -> dict | None:
    """The error map associated with this DEM product, only if it was registered for these exact bytes."""
    reg = reg if reg is not None else read_registry()
    em = reg.get("error_maps", {}).get(product_key(rec))
    if not em or not em.get("dem_sha256") or em.get("dem_sha256") != rec.get("sha256"):
        return None
    if file_problem(em):
        return None
    return em


def products_digest() -> list[list]:
    """Stable digest of the terrain actually usable now; feeds horizon cache keys, result IDs and tiles.

    One entry per usable product: key, SHA-256, and the SHA-256 of its associated error map (or None).
    Missing files, synthetic terrain while disallowed, and stale error maps are therefore all reflected.
    """
    reg = read_registry()
    out = []
    for p in usable_levels():
        em = error_map_for(p, reg)
        out.append([product_key(p), p.get("sha256"), em.get("sha256") if em else None])
    return sorted(out, key=lambda r: (r[0], r[1] or ""))


def _refuse_broken(x: float, y: float, half_m: float, what: str) -> None:
    """C08: refuse when a registered product that would cover (x, y) +/- half_m is missing or changed."""
    hits = []
    for rec, why in broken_products():
        try:
            bx0, by0, bx1, by1 = _bounds(rec)
        except Exception:
            hits.append(why)
            continue
        h = settings.DEM_WINDOW_HALF_M.get(rec.get("level"), 50_000.0) if half_m is None else half_m
        if not (x + h < bx0 or x - h > bx1 or y + h < by0 or y - h > by1):
            hits.append(why)
    if hits:
        raise TerrainError(f"{what} withheld: " + "; ".join(hits) +
                           ". Restore the file(s) or run `python -m lunaops.acquire unregister-dem`; "
                           "LUNA-OPS never substitutes another product silently.")


def _bounds(rec: dict) -> tuple[float, float, float, float]:
    a, _, c, _, e, f = rec["transform"]
    x0, x1 = c, c + a * rec["width"]
    y1, y0 = f, f + e * rec["height"]
    return min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)


# ------------------------------------------------------------ inspection
def inspect_raster(path: Path, kind: str = "dem") -> dict:
    """Read CRS, geometry and units of a GeoTIFF and verify the stereographic transform.

    kind="dem": heights; refuses samples that look like km or lie outside +/-20 km.
    kind="error_map": height uncertainties in metres (typically 0.1-10 m), so the km heuristic is not
    applied; refuses negative samples instead.
    """
    import rasterio
    from pyproj import CRS, Transformer

    with rasterio.open(path) as src:
        if src.count < 1:
            raise TerrainError(f"{path.name} has no raster bands")
        crs = src.crs
        if crs is None:
            raise TerrainError(f"{path.name} has no embedded CRS; it cannot be georeferenced safely")
        t = src.transform
        if abs(t.b) > 0 or abs(t.d) > 0:
            raise TerrainError(f"{path.name} is rotated; only north-up rasters are supported")
        info = {
            "width": src.width,
            "height": src.height,
            "transform": [t.a, t.b, t.c, t.d, t.e, t.f],
            "nodata": src.nodata,
            "dtype": src.dtypes[0],
            "scale": float(src.scales[0]) if src.scales else 1.0,
            "offset": float(src.offsets[0]) if src.offsets else 0.0,
            "units_tag": (src.units[0] if src.units else None) or None,
            "crs_wkt": crs.to_wkt(),
            "pixel_m": abs(t.a),
            "has_overviews": bool(src.overviews(1)),
            "area_or_point": (src.tags().get("AREA_OR_POINT") or None),
        }
        win = rasterio.windows.Window(src.width // 2 - 64, src.height // 2 - 64, 128, 128)
        sample = src.read(1, window=win, boundless=True, fill_value=src.nodata if src.nodata is not None else np.nan)
    sample = sample.astype("float64")
    if info["nodata"] is not None:
        sample[sample == info["nodata"]] = np.nan
    sample = sample * info["scale"] + info["offset"]
    finite = sample[np.isfinite(sample)]
    if finite.size:
        span = float(np.nanmax(np.abs(finite)))
        info["sample_abs_max"] = span
        if kind == "error_map":
            if float(np.min(finite)) < 0.0:
                raise TerrainError(f"{path.name}: negative values in an error map; it is not a height uncertainty map.")
        else:
            if 0 < span < 20.0:
                raise TerrainError(
                    f"{path.name}: sampled heights are below 20 in magnitude; values may be in km, not m. "
                    "Confirm units before registering."
                )
            if span > MAX_ABS_HEIGHT_M:
                raise TerrainError(
                    f"{path.name}: sampled values reach {span:.0f} in magnitude, beyond any lunar height; "
                    "the file probably uses an undeclared nodata value. Declare it before registering."
                )
    pc = CRS.from_wkt(info["crs_wkt"])
    tr = Transformer.from_crs(pc.geodetic_crs, pc, always_xy=True)
    worst = 0.0
    for lat, lon in [(-89.5, 10.0), (-87.0, 135.0), (-85.0, 250.0), (-80.0, 330.0), (-70.0, 45.0)]:
        x1, y1 = tr.transform(lon if lon <= 180 else lon - 360, lat)
        p = unit_from_latlon(math.radians(lat), math.radians(lon))
        x2, y2 = south_polar_stereo_xy(p, settings.R_MOON_M)
        worst = max(worst, abs(x1 - x2), abs(y1 - y2))
    info["stereo_check_max_m"] = worst
    if worst > 1e-3:
        raise TerrainError(
            f"{path.name}: its CRS differs from the spherical south polar stereographic projection "
            f"(R = 1737.4 km, lon_0 = 0) by up to {worst:.3f} m; refusing to use it without reprojection."
        )
    return info


# ------------------------------------------------------------- windows
@dataclass
class LevelWindow:
    """A terrain window around a site.

    Geometry is always the *nominal* window (half-width DEM_WINDOW_HALF_M of the level, clipped to the
    product): x0/y0 are the centre of its pixel [0, 0], band_m derives from the nominal half-width. `data`
    holds the loaded block, which (Phase 3 item 6, adaptive mode) may be a sub-block of the nominal window
    starting at nominal row/column (row_off, col_off); nom_shape is then the nominal (rows, cols). Every
    sampler converts coordinates with the nominal origin, so a value is bitwise the same whether the block
    or the whole nominal window is loaded; reading outside the loaded block grows it from the file (ensure).
    Windows built directly (tests, variance grids) are complete: offsets 0, nom_shape None."""
    level: str
    data: np.ndarray        # float32 heights (m), NaN = no data (the loaded block)
    x0: float               # x of the nominal pixel centre [0, 0]
    y0: float               # y of the nominal pixel centre [0, 0]
    dx: float               # pixel size in x (m, > 0)
    dy: float               # pixel size in y (m, < 0 for north-up)
    band_m: float           # max distance this window serves
    pixel_m: float
    meta: dict = field(default_factory=dict)
    row_off: int = 0                    # loaded block offset within the nominal window
    col_off: int = 0
    nom_shape: tuple | None = None      # nominal (rows, cols); None: data is the nominal window
    source: dict | None = None          # how to read more: {"lv": record, "row0", "col0"} (nominal block origin)
    nominal_hmax: float | None = None   # max finite height over the nominal window (streamed)

    @property
    def shape(self) -> tuple[int, int]:
        return tuple(self.nom_shape) if self.nom_shape is not None else self.data.shape

    @property
    def complete(self) -> bool:
        return self.row_off == 0 and self.col_off == 0 and self.data.shape == self.shape

    def ensure(self, r0: int, r1: int, c0: int, c1: int) -> bool:
        """Make the loaded block cover nominal rows [r0, r1) and columns [c0, c1) (clipped to the nominal
        window), re-reading the union of the current and requested blocks from the file. True if it grew."""
        nr, nc = self.shape
        r0, c0 = max(0, int(r0)), max(0, int(c0))
        r1, c1 = min(nr, int(r1)), min(nc, int(c1))
        if r1 <= r0 or c1 <= c0:
            return False
        lr0, lc0 = self.row_off, self.col_off
        lr1, lc1 = lr0 + self.data.shape[0], lc0 + self.data.shape[1]
        if self.data.size and lr0 <= r0 and lc0 <= c0 and r1 <= lr1 and c1 <= lc1:
            return False
        if self.source is None:
            return False                                     # a complete hand-built window: nothing to read
        if self.data.size:
            r0, c0, r1, c1 = min(r0, lr0), min(c0, lc0), max(r1, lr1), max(c1, lc1)
        lv, br, bc = self.source["lv"], self.source["row0"], self.source["col0"]
        self.data = _read_block(lv, bc + c0, br + r0, c1 - c0, r1 - r0)
        self.row_off, self.col_off = r0, c0
        return True

    def ensure_full(self) -> bool:
        nr, nc = self.shape
        return self.ensure(0, nr, 0, nc)


CHUNK_ROWS = 256      # rows per chunk for in-place processing (bounds the temporaries)


def _process_block(arr: np.ndarray, lv: dict) -> np.ndarray:
    """Nodata, scale/offset and plausibility, in place on a float32 block: the same float32 operations as the
    original whole-window read, element by element, applied in row chunks so no full-size temporary exists."""
    nod = lv.get("nodata")
    sc, of = np.float32(lv.get("scale", 1.0)), np.float32(lv.get("offset", 0.0))
    for r in range(0, arr.shape[0], CHUNK_ROWS):
        a = arr[r:r + CHUNK_ROWS]
        if nod is not None:
            a[a == np.float32(nod)] = np.nan
        a *= sc
        a += of
        a[~(np.abs(a) <= MAX_ABS_HEIGHT_M)] = np.nan     # implausible or non-finite -> nodata, never a surface
    return arr


def _finite_stats(arr: np.ndarray) -> tuple[bool, float]:
    """(any finite value, max finite value) without full-size temporaries: fmax ignores NaN like nanmax and
    returns the same value."""
    any_fin, hmax = False, -math.inf
    for r in range(0, arr.shape[0], CHUNK_ROWS):
        a = arr[r:r + CHUNK_ROWS]
        if a.size and np.isfinite(a).any():
            any_fin = True
            hmax = max(hmax, float(np.fmax.reduce(a, axis=None)))
    return any_fin, hmax


def _read_block(lv: dict, col0: int, row0: int, ncols: int, nrows: int, out: np.ndarray | None = None) -> np.ndarray:
    """Read product pixels [row0, row0 + nrows) x [col0, col0 + ncols) as processed float32 heights, into `out`
    (a float32 (nrows, ncols) view, e.g. a slice of a shared buffer) when given."""
    import rasterio
    from rasterio.windows import Window

    path, _source = resolve_dem_path_source(lv["path"])
    if out is None:
        out = np.empty((nrows, ncols), dtype=np.float32)
    if nrows and ncols:
        with rasterio.open(path) as src:
            if src.dtypes[0] == "float32":
                src.read(1, window=Window(col0, row0, ncols, nrows), out=out)
            else:
                out[...] = src.read(1, window=Window(col0, row0, ncols, nrows)).astype(np.float32)
        _process_block(out, lv)
    return out


def _window_geometry(lv: dict, cx: float, cy: float, half_m: float) -> dict | None:
    """Pixel block of the window of half-width half_m around (cx, cy), clipped to the product (the same
    arithmetic as the original reader); None if there is no overlap."""
    bx0, by0, bx1, by1 = _bounds(lv)
    if cx + half_m < bx0 or cx - half_m > bx1 or cy + half_m < by0 or cy - half_m > by1:
        return None
    a, _, c, _, e, f = lv["transform"]
    col_c = (cx - c) / a
    row_c = (cy - f) / e
    half_px = int(math.ceil(half_m / abs(a)))
    col0 = max(0, int(math.floor(col_c)) - half_px)
    row0 = max(0, int(math.floor(row_c)) - half_px)
    col1 = min(lv["width"], int(math.floor(col_c)) + half_px + 1)
    row1 = min(lv["height"], int(math.floor(row_c)) + half_px + 1)
    if col1 <= col0 or row1 <= row0:
        return None
    return {"col0": col0, "row0": row0, "col1": col1, "row1": row1}


def _read_window(lv: dict, cx: float, cy: float, half_m: float) -> LevelWindow | None:
    """Window of half-width half_m around (cx, cy), clipped to the product; None if no overlap.
    (The reference loader: LUNAOPS_WINDOW_MODE=full, exactly the pre-Phase-3 code path.)"""
    import rasterio
    from rasterio.windows import Window

    bx0, by0, bx1, by1 = _bounds(lv)
    if cx + half_m < bx0 or cx - half_m > bx1 or cy + half_m < by0 or cy - half_m > by1:
        return None
    a, _, c, _, e, f = lv["transform"]
    path, source = resolve_dem_path_source(lv["path"])
    with rasterio.open(path) as src:
        col_c = (cx - c) / a
        row_c = (cy - f) / e
        half_px = int(math.ceil(half_m / abs(a)))
        col0 = max(0, int(math.floor(col_c)) - half_px)
        row0 = max(0, int(math.floor(row_c)) - half_px)
        col1 = min(lv["width"], int(math.floor(col_c)) + half_px + 1)
        row1 = min(lv["height"], int(math.floor(row_c)) + half_px + 1)
        if col1 <= col0 or row1 <= row0:
            return None
        arr = src.read(1, window=Window(col0, row0, col1 - col0, row1 - row0)).astype(np.float32)
    nod = lv.get("nodata")
    if nod is not None:
        arr[arr == np.float32(nod)] = np.nan
    arr = arr * np.float32(lv.get("scale", 1.0)) + np.float32(lv.get("offset", 0.0))
    arr[~(np.abs(arr) <= MAX_ABS_HEIGHT_M)] = np.nan     # implausible or non-finite -> nodata, never a surface
    x0 = c + (col0 + 0.5) * a
    y0 = f + (row0 + 0.5) * e
    return LevelWindow(lv["level"], arr, x0, y0, a, e, half_m - 2.0 * abs(a), abs(a),
                       {k: lv.get(k) for k in ("product", "page", "sha256", "path", "synthetic")}
                       | {"key": product_key(lv), "resolved_from": source})


def initial_reach_m(lv: dict, nominal_half_m: float) -> float:
    """Initial loading reach of a product (performance only): DEM_INITIAL_REACH_M by product_id, else by
    level, else the nominal half-width. Must satisfy 0 < reach <= nominal half-width."""
    r = settings.DEM_INITIAL_REACH_M.get(lv.get("product_id"), settings.DEM_INITIAL_REACH_M.get(lv["level"]))
    if r is None:
        return nominal_half_m
    r = float(r)
    if not 0.0 < r <= nominal_half_m:
        raise ValueError(f"DEM_INITIAL_REACH_M for {lv.get('product_id') or lv['level']} must be in "
                         f"(0, {nominal_half_m:g}] m (the nominal window half-width), not {r:g}")
    return r


STREAM_ROWS = 512     # rows per block of the streaming pass over a nominal window


def _stream_stats(lv: dict, g: dict) -> tuple[bool, float]:
    """(any finite height, max finite height) over a nominal block, read STREAM_ROWS rows at a time."""
    any_fin, hmax = False, -math.inf
    for r in range(g["row0"], g["row1"], STREAM_ROWS):
        blk = _read_block(lv, g["col0"], r, g["col1"] - g["col0"], min(STREAM_ROWS, g["row1"] - r))
        a, m = _finite_stats(blk)
        if a:
            any_fin = True
            hmax = max(hmax, m)
    return any_fin, hmax


def _load_pyramid_adaptive(levels: list[dict], cx: float, cy: float) -> list[LevelWindow]:
    """Phase 3 item 6: the same windows as the reference loader (same products, order, nominal geometry and
    bands), with each window's initial block read straight into one shared float32 buffer (no second copy in
    the horizon kernel). A product whose initial reach is below its nominal half-width loads only that part;
    its nominal any-data test and maximum height come from a streaming pass over the whole nominal window."""
    plan = []
    for lv in levels:
        half = settings.DEM_WINDOW_HALF_M.get(lv["level"], 50_000.0)
        g = _window_geometry(lv, cx, cy, half)
        if g is None:
            continue
        reach = initial_reach_m(lv, half)
        if reach >= half:
            lg = g
        else:
            gi = _window_geometry(lv, cx, cy, reach)
            lg = None if gi is None else {"col0": max(gi["col0"], g["col0"]), "row0": max(gi["row0"], g["row0"]),
                                          "col1": min(gi["col1"], g["col1"]), "row1": min(gi["row1"], g["row1"])}
        plan.append((lv, half, g, lg))
    sizes = [0 if lg is None else (lg["row1"] - lg["row0"]) * (lg["col1"] - lg["col0"]) for _lv, _h, _g, lg in plan]
    buf = np.empty(int(sum(sizes)), dtype=np.float32)
    out, pos = [], 0
    for (lv, half, g, lg), size in zip(plan, sizes):
        if lg is not None:
            nr_l, nc_l = lg["row1"] - lg["row0"], lg["col1"] - lg["col0"]
            data = _read_block(lv, lg["col0"], lg["row0"], nc_l, nr_l, out=buf[pos:pos + size].reshape(nr_l, nc_l))
            r_off, c_off = lg["row0"] - g["row0"], lg["col0"] - g["col0"]
        else:
            data = np.empty((0, 0), dtype=np.float32)
            r_off = c_off = 0
        pos += size
        nom = (g["row1"] - g["row0"], g["col1"] - g["col0"])
        if lg == g:
            any_fin, hmax = _finite_stats(data)
        else:
            any_fin, hmax = _stream_stats(lv, g)
        if not any_fin:
            continue
        a, _, c, _, e, f = lv["transform"]
        _path, source = resolve_dem_path_source(lv["path"])
        w = LevelWindow(lv["level"], data, c + (g["col0"] + 0.5) * a, f + (g["row0"] + 0.5) * e, a, e,
                        half - 2.0 * abs(a), abs(a),
                        {k: lv.get(k) for k in ("product", "page", "sha256", "path", "synthetic")}
                        | {"key": product_key(lv), "resolved_from": source},
                        row_off=r_off, col_off=c_off, nom_shape=nom,
                        source={"lv": lv, "row0": g["row0"], "col0": g["col0"]}, nominal_hmax=hmax)
        w.meta["loaded_initially_px"] = int(data.size)
        w.meta["nominal_px"] = int(nom[0] * nom[1])
        out.append(w)
    return out


def load_pyramid(lat: float, lon: float) -> list[LevelWindow]:
    """Terrain windows around a site from every registered product that overlaps it, finest first.

    LUNAOPS_WINDOW_MODE=full: the reference loader (whole nominal windows, as before Phase 3).
    Otherwise (adaptive, default): identical windows, loaded into one buffer, coarse products possibly only
    up to their initial reach and grown on demand (see LevelWindow)."""
    levels = usable_levels()
    if not levels:
        raise TerrainError(no_terrain_reason())
    p = unit_from_latlon(math.radians(lat), math.radians(lon))
    cx, cy = south_polar_stereo_xy(p, settings.R_MOON_M)
    _refuse_broken(cx, cy, None, "Terrain horizon")
    if settings.WINDOW_MODE == "full":
        out = []
        for lv in levels:
            half = settings.DEM_WINDOW_HALF_M.get(lv["level"], 50_000.0)
            w = _read_window(lv, cx, cy, half)
            if w is not None and np.isfinite(w.data).any():
                out.append(w)
    else:
        out = _load_pyramid_adaptive(levels, cx, cy)
    if not out:
        raise TerrainError("No registered terrain product overlaps this site.")
    # distance bands never shrink from fine to coarse products
    band = 0.0
    for w in out:
        w.band_m = max(w.band_m, band)
        band = w.band_m
    return out


def expand_into_new_buffer(pyr: list[LevelWindow], full: set) -> None:
    """Load the whole nominal block of the windows in `full` and repack every window into one new shared float32
    buffer (expanded windows read straight from the file into their slices, the others copied), so the kernel
    still uses the windows in place (no concatenated second copy). Values are bitwise those of the file."""
    plan = []
    for i, w in enumerate(pyr):
        if i in full and w.source is not None and not w.complete:
            nr, nc = w.shape
            plan.append((w, True, nr, nc))
        else:
            plan.append((w, False) + tuple(w.data.shape))
    buf = np.empty(int(sum(nr * nc for _w, _x, nr, nc in plan)), dtype=np.float32)
    pos = 0
    for w, grow, nr, nc in plan:
        view = buf[pos:pos + nr * nc].reshape(nr, nc)
        pos += nr * nc
        if grow:
            lv, br, bc = w.source["lv"], w.source["row0"], w.source["col0"]
            _read_block(lv, bc, br, nc, nr, out=view)
            w.row_off = w.col_off = 0
        elif w.data.size:
            view[...] = w.data
        w.data = view


def window_hmax(w: LevelWindow) -> float | None:
    """Max finite height over a window's nominal extent (None if it has no data)."""
    if w.nominal_hmax is not None:
        return w.nominal_hmax if math.isfinite(w.nominal_hmax) else None
    return float(np.nanmax(w.data)) if np.isfinite(w.data).any() else None


def bilinear(w: LevelWindow, x: float, y: float) -> float:
    fc = (x - w.x0) / w.dx
    fr = (y - w.y0) / w.dy
    c0, r0 = int(math.floor(fc)), int(math.floor(fr))
    nr, nc = w.shape
    if c0 < 0 or r0 < 0 or c0 + 1 >= nc or r0 + 1 >= nr:
        return float("nan")
    w.ensure(r0, r0 + 2, c0, c0 + 2)
    tc, tr = fc - c0, fr - r0
    q = w.data[r0 - w.row_off:r0 - w.row_off + 2, c0 - w.col_off:c0 - w.col_off + 2]
    if not np.all(np.isfinite(q)):
        return float("nan")      # any nodata neighbour -> nodata (Section 8.4 safeguards)
    return float((q[0, 0] * (1 - tc) + q[0, 1] * tc) * (1 - tr) + (q[1, 0] * (1 - tc) + q[1, 1] * tc) * tr)


def site_height_window(pyr: list[LevelWindow], lat: float, lon: float) -> tuple[float, int]:
    """Ground height at the site and the index of the window (product) that supplied it.

    The first window in pyramid order (finest first) with data at the site. The index, not the level,
    identifies the site product: several products may share a level (C08: never invented).
    """
    p = unit_from_latlon(math.radians(lat), math.radians(lon))
    x, y = south_polar_stereo_xy(p, settings.R_MOON_M)
    for i, w in enumerate(pyr):
        h = bilinear(w, x, y)
        if math.isfinite(h):
            return h, i
    raise TerrainError("No registered terrain product covers this site.")


def site_height(pyr: list[LevelWindow], lat: float, lon: float) -> tuple[float, str]:
    """Ground height at the site and the level of the product that supplied it (see site_height_window)."""
    h, i = site_height_window(pyr, lat, lon)
    return h, pyr[i].level


def coverage_check(lat: float, lon: float) -> dict:
    """Which registered products cover a site (U-01, C08)."""
    levels = usable_levels()
    if not levels:
        return {"covered": False, "levels": [], "products": [], "reason": no_terrain_reason()}
    if lat > -60.0:
        return {"covered": False, "levels": [], "products": [],
                "reason": "The registered LOLA products cover 60-90 S only (south-pole-first scope, Q6)."}
    import rasterio

    p = unit_from_latlon(math.radians(lat), math.radians(lon))
    x, y = south_polar_stereo_xy(p, settings.R_MOON_M)
    try:
        _refuse_broken(x, y, None, "Terrain coverage")
    except TerrainError as exc:
        return {"covered": False, "levels": [], "products": [], "reason": str(exc)}
    hits = []
    for lv in levels:
        bx0, by0, bx1, by1 = _bounds(lv)
        if not (bx0 <= x <= bx1 and by0 <= y <= by1):
            continue
        with rasterio.open(resolve_dem_path(lv["path"])) as src:
            r, c = src.index(x, y)
            if 0 <= r < src.height and 0 <= c < src.width:
                v = src.read(1, window=((r, r + 1), (c, c + 1)))[0, 0]
                if (lv.get("nodata") is None or v != lv["nodata"]) and np.isfinite(v):
                    hv = float(v) * float(lv.get("scale", 1.0)) + float(lv.get("offset", 0.0))
                    if abs(hv) <= MAX_ABS_HEIGHT_M:
                        hits.append(lv)
    if not hits:
        return {"covered": False, "levels": [], "products": [],
                "reason": "No registered terrain product has data at this point."}
    levels_hit = []
    for h in hits:
        if h["level"] not in levels_hit:
            levels_hit.append(h["level"])
    return {"covered": True, "levels": levels_hit, "products": [product_key(h) for h in hits],
            "finest": hits[0]["level"], "reason": None}


def terrain_grid(lat: float, lon: float, radius_m: float, n: int = 160) -> dict:
    """Downsampled height grid around a site for the 3D view (display only)."""
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.windows import from_bounds

    levels = usable_levels()
    if not levels:
        raise TerrainError(no_terrain_reason())
    p = unit_from_latlon(math.radians(lat), math.radians(lon))
    cx, cy = south_polar_stereo_xy(p, settings.R_MOON_M)
    chosen = None
    for lv in levels:  # finest product that covers the full window
        bx0, by0, bx1, by1 = _bounds(lv)
        if cx - radius_m >= bx0 and cx + radius_m <= bx1 and cy - radius_m >= by0 and cy + radius_m <= by1:
            chosen = lv
            break
    if chosen is None:
        raise TerrainError("No single terrain product covers this 3D window.")
    with rasterio.open(resolve_dem_path(chosen["path"])) as src:
        win = from_bounds(cx - radius_m, cy - radius_m, cx + radius_m, cy + radius_m, src.transform)
        arr = src.read(1, window=win, out_shape=(n, n), resampling=Resampling.average,
                       boundless=True, fill_value=chosen.get("nodata") if chosen.get("nodata") is not None else np.nan)
    arr = arr.astype(np.float32)
    if chosen.get("nodata") is not None:
        arr[arr == np.float32(chosen["nodata"])] = np.nan
    arr = arr * chosen.get("scale", 1.0) + chosen.get("offset", 0.0)
    from .frames import enu_basis
    e, nn, u = enu_basis(lat, lon)
    ds = 10.0
    base = settings.R_MOON_M * u

    def xy(vec):
        q = vec / np.linalg.norm(vec)
        return np.array(south_polar_stereo_xy(q, settings.R_MOON_M))

    j = np.column_stack([(xy(base + ds * e) - xy(base - ds * e)) / (2 * ds),
                         (xy(base + ds * nn) - xy(base - ds * nn)) / (2 * ds)])
    jinv = np.linalg.inv(j)
    ax = jinv @ np.array([1.0, 0.0])
    ay = jinv @ np.array([0.0, 1.0])
    gx = ax[0] * e + ax[1] * nn
    gy = ay[0] * e + ay[1] * nn
    gx /= np.linalg.norm(gx)
    gy /= np.linalg.norm(gy)
    return {
        "grid_basis_bodyfixed": {"x": gx.round(9).tolist(), "y": gy.round(9).tolist(), "up": u.round(9).tolist()},
        "row0": "north edge of the projection grid (max y); columns increase in x",
        "level": chosen["level"],
        "product": chosen.get("product"),
        "n": n,
        "radius_m": radius_m,
        "center_xy": [cx, cy],
        "heights": [None if not np.isfinite(v) else round(float(v), 2) for v in arr.ravel()],
        "note": "Display grid resampled by averaging; scientific results use the full-resolution pyramid.",
    }
