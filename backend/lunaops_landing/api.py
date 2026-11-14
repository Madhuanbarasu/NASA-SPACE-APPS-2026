"""HTTP routes of the landing screening package, attached to the existing LUNA-OPS app by start.py (install()).

The routes live under /api/landing/ and are inserted ahead of the app's other routes so the single-page-app
catch-all cannot shadow them. No existing route, engine module or validated output is changed.
"""
from __future__ import annotations

import math

import numpy as np
from fastapi import APIRouter, FastAPI, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

from lunaops.engine.dem import TerrainError

from . import LANDING_VERSION, VALIDATION_STATUS, landing_code_hash
from . import assess as A
from . import render as Rn
from .sources import latlon_to_xy, read_manifest

router = APIRouter(prefix="/api/landing", tags=["landing (preliminary screening)"])


class Thresholds(BaseModel):
    slope_deg: float | None = Field(None, ge=0, le=90)
    roughness_m: float | None = Field(None, ge=0, le=1000)
    relief_m: float | None = Field(None, ge=0, le=10000)
    min_valid_pct: float | None = Field(95.0, ge=0, le=100)


class FootprintIn(BaseModel):
    lat: float
    lon: float
    radius_m: float = Field(50.0, ge=1, le=5000)
    thresholds: Thresholds = Thresholds()


class AssessIn(BaseModel):
    lat: float
    lon: float
    window_half_m: float = Field(1500.0, ge=100, le=30000)
    product: str | None = None
    roughness_baseline_m: float | None = Field(None, gt=0, le=10000)
    roughness_window_px: int | None = Field(None, ge=3, le=25)
    min_depth_m: float = Field(1.0, gt=0, le=1000)
    min_diameter_m: float | None = Field(None, ge=0)
    max_diameter_m: float | None = Field(None, gt=0)
    footprint: FootprintIn | None = None


def _layer_array(a: A.Assessment, name: str) -> np.ndarray | None:
    w = a.win
    return {"elevation": w.z, "slope": a.slope, "roughness": a.rough, "uncertainty": w.err,
            "nasa_slope": w.aux.get("slope")}.get(name)


def _payload(a: A.Assessment) -> dict:
    out = A.to_json(a)
    for L in out["layers"]:
        arr = _layer_array(a, L["name"])
        L["legend"] = Rn.legend(L["name"], Rn.value_range(L["name"], arr)) if arr is not None else None
    out["extent_xy_m"] = list(a.win.bounds)
    out["roughness_windows_m"] = [round(wp * a.win.pixel_m, 2) for wp in A.ROUGHNESS_WINDOWS_PX]
    return out


def _get(aid: str) -> A.Assessment:
    a = A.get(aid)
    if a is None:
        raise HTTPException(404, "This assessment is no longer held by the server (it keeps the latest few). Run it again.")
    return a


@router.get("/meta")
def meta():
    return {"landing_version": LANDING_VERSION, "landing_code_sha256": landing_code_hash(),
            "validation_status": VALIDATION_STATUS, "status_text": A.STATUS_TEXT,
            "auxiliary_products": [{k: e.get(k) for k in ("key", "kind", "product", "dem_product_key", "units", "source_url")}
                                   for e in read_manifest().get("products", [])],
            "roughness_windows_px": list(A.ROUGHNESS_WINDOWS_PX),
            "thresholds": "user-defined assumptions; no defaults are supplied"}


@router.post("/assess")
def post_assess(body: AssessIn):
    try:
        a = A.assess(body.model_dump(exclude={"footprint"}))
    except (A.LandingInputError, TerrainError) as exc:
        raise HTTPException(422, str(exc))
    out = _payload(a)
    fp = body.footprint or FootprintIn(lat=body.lat, lon=body.lon)
    out["footprint"] = A.footprint(a, fp.lat, fp.lon, fp.radius_m, fp.thresholds.model_dump())
    return out


@router.post("/{aid}/footprint")
def post_footprint(aid: str, body: FootprintIn):
    a = _get(aid)
    try:
        return A.footprint(a, body.lat, body.lon, body.radius_m, body.thresholds.model_dump())
    except A.LandingInputError as exc:
        raise HTTPException(422, str(exc))


@router.get("/{aid}/layer/{name}.png")
def layer_png(aid: str, name: str, threshold: float | None = Query(None, ge=0, le=1000)):
    a = _get(aid)
    w = a.win
    if name == "coverage":
        png = Rn.coverage_png(w.z, w.aux.get("count"))
    elif name in ("slope_exceed", "roughness_exceed"):
        if threshold is None:
            raise HTTPException(422, "A threshold is required for this layer.")
        png = Rn.exceed_png(a.slope if name == "slope_exceed" else a.rough, threshold)
    else:
        arr = _layer_array(a, name)
        if arr is None:
            raise HTTPException(404, f"Layer {name} is not available for this terrain product.")
        png = Rn.ramp_png(name, arr, Rn.value_range(name, arr))
    return Response(png, media_type="image/png", headers={"Cache-Control": "private, max-age=3600"})


@router.get("/{aid}/point")
def point(aid: str, lat: float, lon: float):
    a = _get(aid)
    w = a.win
    x, y = latlon_to_xy(lat, lon)
    rc = w.pixel_of(x, y)
    if rc is None:
        return {"inside": False}
    r, c = rc

    def v(arr, nd):
        if arr is None:
            return None
        q = float(arr[r, c])
        return None if not math.isfinite(q) else round(q, nd)

    cnt = w.aux.get("count")
    lab = int(a.labels[r, c])
    return {"inside": True, "elevation_m": v(w.z, 2), "slope_deg": v(a.slope, 2), "roughness_m": v(a.rough, 3),
            "tri_m": v(a.tri, 3), "height_sigma_m": v(w.err, 3), "nasa_slope_deg": v(w.aux.get("slope"), 2),
            "slope_sigma_deg": v(w.aux.get("slope_error"), 2), "lola_returns": v(cnt, 0),
            "missing": not math.isfinite(float(w.z[r, c])), "depression_id": lab or None,
            "depression_depth_m": v(a.depth, 2) if lab else None}


def install(app: FastAPI) -> None:
    """Attach the landing routes ahead of the app's existing routes (so the SPA catch-all cannot shadow them)."""
    n = len(app.router.routes)
    app.include_router(router)
    added = app.router.routes[n:]
    del app.router.routes[n:]
    app.router.routes[0:0] = added
