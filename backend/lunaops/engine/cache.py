"""Caches (blueprint Section 9): SQLite index plus files, keyed by site, observer
height, DEM versions and algorithm version (horizons) or by the full request
and kernel set (results)."""
from __future__ import annotations

import json
import sqlite3
import threading
import time

import numpy as np

from .. import settings

_LOCK = threading.Lock()


def _db():
    return settings.CACHE_DIR / "cache.sqlite"


def _conn():
    settings.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(_db())
    c.execute("CREATE TABLE IF NOT EXISTS horizons (key TEXT PRIMARY KEY, path TEXT, meta TEXT, created REAL)")
    c.execute("CREATE TABLE IF NOT EXISTS results (id TEXT PRIMARY KEY, path TEXT, created REAL)")
    return c


def put_cached_horizon(hz) -> None:
    settings.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = settings.CACHE_DIR / f"horizon_{hz.key}.npz"
    from .horizon import EXTRA_ARRAYS

    extra = {f"x_{name}": getattr(hz, name) for name in EXTRA_ARRAYS if getattr(hz, name) is not None}
    np.savez_compressed(path, h=hz.h_deg, d=hz.block_dist_m, inc=hz.incomplete,
                        sigma=hz.sigma_deg if hz.sigma_deg is not None else np.array([]), **extra)
    meta = {"lat": hz.lat, "lon": hz.lon, "obs_h_m": hz.obs_h_m, "ground_h_m": hz.ground_h_m,
            "site_level": hz.site_level, "levels": hz.levels, "params": hz.params}
    with _LOCK, _conn() as c:
        c.execute("INSERT OR REPLACE INTO horizons VALUES (?,?,?,?)", (hz.key, str(path), json.dumps(meta), time.time()))


def get_cached_horizon(key: str):
    from .horizon import EXTRA_ARRAYS, Horizon

    with _LOCK, _conn() as c:
        row = c.execute("SELECT path, meta FROM horizons WHERE key=?", (key,)).fetchone()
    if not row:
        return None
    try:
        z = np.load(row[0])
    except Exception:
        return None
    m = json.loads(row[1])
    sigma = z["sigma"] if z["sigma"].size else None
    extra = {name: z[f"x_{name}"] for name in EXTRA_ARRAYS if f"x_{name}" in z.files}
    for name in ("near_field", "cross_product", "discrepancy_unknown", "sigma_nonlinear"):
        if name in extra:
            extra[name] = extra[name].astype(bool)
    return Horizon(m["lat"], m["lon"], m["obs_h_m"], m["ground_h_m"], m["site_level"], z["h"], z["d"],
                   z["inc"].astype(bool), sigma, m["levels"], key, m["params"], **extra)


def put_result(res: dict) -> None:
    settings.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = settings.CACHE_DIR / f"result_{res['id']}.json"
    path.write_text(json.dumps(res, sort_keys=True, separators=(",", ":")))
    with _LOCK, _conn() as c:
        c.execute("INSERT OR REPLACE INTO results VALUES (?,?,?)", (res["id"], str(path), time.time()))


def get_result(rid: str):
    with _LOCK, _conn() as c:
        row = c.execute("SELECT path FROM results WHERE id=?", (rid,)).fetchone()
    if not row:
        return None
    try:
        with open(row[0]) as f:
            return json.loads(f.read())
    except Exception:
        return None


def clear() -> None:
    with _LOCK, _conn() as c:
        c.execute("DELETE FROM horizons")
        c.execute("DELETE FROM results")
