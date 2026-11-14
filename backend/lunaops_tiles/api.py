"""HTTP routes of the display-tile package, attached to the existing LUNA-OPS app by start.py (install()).

GET /api/display/tiles/{z}/{x}/{y}.png serves the corrected hillshade tiles; GET /api/display/tiles/info states what
they are. The engine's own /api/tiles/meta (the tile grid) and /api/tiles/{z}/{x}/{y}.png stay unchanged and
reachable. The routes are inserted ahead of the app's other routes so the single-page-app catch-all cannot shadow them.
"""
from __future__ import annotations

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.responses import Response

from lunaops.engine.dem import TerrainError

from . import STATUS, TILES_VERSION, tiles_code_hash
from .render import render_tile

router = APIRouter(prefix="/api/display/tiles", tags=["display tiles (not part of the validated engine)"])
HEADERS = {"Cache-Control": "public, max-age=86400", "X-LunaOps-Renderer": f"lunaops_tiles {TILES_VERSION}"}


@router.get("/info")
def info():
    return {"renderer": "lunaops_tiles", "version": TILES_VERSION, "code_hash": tiles_code_hash(), "status": STATUS,
            "grid": "/api/tiles/meta (the engine's tile grid, unchanged)",
            "note": "Cartographic hillshade from the registered LOLA heights (fixed light direction; not the lunar Sun). "
                    "Display images only; no analysis reads them."}


@router.get("/{z}/{x}/{y}.png")
def tile(z: int, x: int, y: int):
    try:
        png = render_tile(z, x, y)
    except (TerrainError, OSError) as exc:   # rasterio's RasterioIOError is an OSError (the engine route's handling)
        raise HTTPException(422, f"Tile not available: {exc}")
    return Response(png, media_type="image/png", headers=HEADERS)


def install(app: FastAPI) -> None:
    """Attach the display-tile routes ahead of the app's existing routes (so the SPA catch-all cannot shadow them)."""
    n = len(app.router.routes)
    app.include_router(router)
    added = app.router.routes[n:]
    del app.router.routes[n:]
    app.router.routes[0:0] = added
