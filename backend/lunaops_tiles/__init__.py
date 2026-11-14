"""LUNA-OPS display tiles: corrected hillshade map images (tiles 0.1.0, AUD-06 of the pre-Phase 7 audit).

This package is deliberately OUTSIDE the validated science engine (backend/lunaops), like lunaops_landing and
lunaops_comms:

* lunaops.fingerprint.code_fingerprint() hashes every .py file under backend/lunaops plus its manifests, and
  suite_fingerprint() hashes backend/tests and backend/validation. Nothing here is inside either, so the validation
  report, every cached result ID and every horizon cache key keep matching the validated engine. NOTHING in this
  package is covered by that validation.
* It renders display images only: the cartographic hillshade of the South Polar Map and of the Landing hazard map's
  backdrop. No analysis, horizon, landing finding or communication result reads these images.
* It reuses the engine's tile grid (lunaops.api.tiles.tile_meta, TILE, _empty) and its terrain registry and file lookup
  (lunaops.engine.dem.usable_levels, resolve_dem_path) by import, read only. It holds no terrain data of its own.
* What it changes: how each registered LOLA product is read into a tile. The engine's renderer uses a rasterio
  boundless read; in rasterio 1.5.2 that path reduces the data to the tile size with nearest-neighbour sampling whatever
  resampling is requested, which draws a faint grid into the hillshade (docs/validation_evidence/
  pre_phase7_audit_2026-11-14_addendum, pre_phase7_aud06_architecture_review_2026-11-14). Here each product is read
  with a normal windowed read, cropped to the product: bilinear when the product is reduced (GDAL uses the file's
  overviews), cubic when it is enlarged (a bilinear surface creases at every product pixel edge, which the hillshade
  also draws as a grid). The hillshade formula, light direction, grey ramp, tile size and grid are the engine's.

Its rendering tests check the images, not science: passing them does not make this package validated.
"""
from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path

TILES_VERSION = "0.1.0"
STATUS = "Display rendering only - not part of the validated engine and not scientifically validated"
PKG = Path(__file__).resolve().parent


@lru_cache(maxsize=1)
def tiles_code_hash() -> str:
    """SHA-256 over this package's source files (tests excluded), the same convention as lunaops.fingerprint."""
    h = hashlib.sha256()
    for p in sorted(PKG.rglob("*.py")):
        rel = p.relative_to(PKG).as_posix()
        if "__pycache__" in rel or rel.startswith("tests/"):
            continue
        h.update(rel.encode())
        h.update(b"\0")
        h.update(p.read_bytes().replace(b"\r\n", b"\n"))
        h.update(b"\0")
    return h.hexdigest()
