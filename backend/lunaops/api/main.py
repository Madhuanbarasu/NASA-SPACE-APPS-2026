"""LUNA-OPS API (blueprint Section 9). Serves computed results unchanged.

Run:  uvicorn lunaops.api.main:app --port 8000   (from backend/)
Docs: http://localhost:8000/docs (OpenAPI, requirement B18)
"""
from __future__ import annotations

import csv
import io
import json
import threading
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .. import ALGORITHM_VERSION, __version__, settings
from ..engine import kernels as kmod
from ..engine.analysis import AnalysisRequest, cached_analyze, compare, result_id
from ..engine.cache import get_result
from ..engine.catalog import load_catalog
from ..engine.dem import (TerrainError, broken_products, coverage_check, no_terrain_reason, read_registry,
                          terrain_grid, terrain_is_synthetic)
from ..engine.frames import CoordinateError, validate_latlon
from ..engine.power import PANELS
from ..engine.provenance import code_version, label_blockers, labels, validation_report
from ..fingerprint import code_fingerprint
from ..engine.timeutil import TimeInputError
from .tiles import render_tile, tile_meta

settings.ensure_dirs()           # importing settings creates nothing; the server creates its data folders
app = FastAPI(title="LUNA-OPS API", version=__version__,
              description="Lunar Landing Site Navigator: Sun and Earth against the terrain horizon. "
                          "All values are computed by the LUNA-OPS science engine; see /api/status for data provenance.")
# The server is local (start.py binds 127.0.0.1). Only pages served from this machine may call it from a
# browser, so an arbitrary website cannot start analysis jobs or read results through the user's browser.
LOCAL_ORIGIN_RE = r"^https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$"
app.add_middleware(CORSMiddleware, allow_origin_regex=LOCAL_ORIGIN_RE, allow_methods=["GET", "POST"],
                   allow_headers=["Content-Type"])

EXEC = ThreadPoolExecutor(max_workers=2)
JOBS: dict[str, dict] = {}
JOBS_LOCK = threading.Lock()
COMPARES: dict[str, dict] = {}


# ----------------------------------------------------------------- models
class AnalysisIn(BaseModel):
    lat: float = Field(..., description="Planetocentric latitude, degrees")
    lon: float = Field(..., description="East longitude, degrees")
    start_utc: str
    end_utc: str
    step_s: float = settings.DEFAULT_SERIES_STEP_S
    observer_profile: Literal["surface", "astronaut", "equipment"] = "surface"
    observer_h_m: float = 0.0
    sunlit_rule: Literal["any", "centre", "full"] = "any"
    dte_rule: Literal["any", "centre", "full"] = "centre"
    margin_deg: float = 0.0
    panel_model: Literal["vertical_tracking", "horizontal", "fixed_vertical"] = "vertical_tracking"
    panel_az_deg: float = 0.0
    site_name: str | None = None
    site_id: str | None = None


class SiteIn(BaseModel):
    lat: float
    lon: float
    name: str | None = None
    id: str | None = None


class WindowIn(BaseModel):
    start_utc: str
    end_utc: str
    label: str | None = None


class CompareIn(BaseModel):
    sites: list[SiteIn]
    windows: list[WindowIn]
    step_s: float = 3600.0
    observer_profile: Literal["surface", "astronaut", "equipment"] = "surface"
    observer_h_m: float = 0.0
    sunlit_rule: Literal["any", "centre", "full"] = "any"
    dte_rule: Literal["any", "centre", "full"] = "centre"
    margin_deg: float = 0.0
    panel_model: Literal["vertical_tracking", "horizontal", "fixed_vertical"] = "vertical_tracking"
    panel_az_deg: float = 0.0


# ------------------------------------------------------------------ jobs
def _submit(kind: str, fn, *args) -> str:
    jid = uuid.uuid4().hex[:16]
    with JOBS_LOCK:
        JOBS[jid] = {"id": jid, "kind": kind, "status": "queued", "progress": 0.0, "message": "Queued",
                     "result_id": None, "error": None}

    def progress(msg: str, frac: float):
        with JOBS_LOCK:
            JOBS[jid].update(message=msg, progress=round(float(frac), 3))

    def run():
        with JOBS_LOCK:
            JOBS[jid].update(status="running", message="Starting")
        try:
            rid = fn(progress, *args)
            with JOBS_LOCK:
                JOBS[jid].update(status="done", progress=1.0, message="Done", result_id=rid)
        except (TerrainError, TimeInputError, CoordinateError, ValueError, kmod.KernelError) as exc:
            with JOBS_LOCK:
                JOBS[jid].update(status="error", error=str(exc), message="Stopped")
        except Exception as exc:  # pragma: no cover
            traceback.print_exc()
            with JOBS_LOCK:
                JOBS[jid].update(status="error", error=f"Internal error: {exc}", message="Stopped")

    EXEC.submit(run)
    return jid


def _do_analysis(progress, req: AnalysisRequest) -> str:
    return cached_analyze(req, progress)["id"]


def _do_compare(progress, body: CompareIn) -> str:
    base = body.model_dump(exclude={"sites", "windows"})
    out = compare([s.model_dump() for s in body.sites], [w.model_dump() for w in body.windows], base, progress)
    cid = uuid.uuid5(uuid.NAMESPACE_URL, json.dumps(out["cells"] and [c["result_id"] for c in out["cells"]])).hex[:16]
    out["id"] = cid
    COMPARES[cid] = out
    return cid


# ---------------------------------------------------------------- routes
@app.get("/api/status")
def status():
    out = {"version": __version__, "code_version": code_version(), "code_fingerprint": code_fingerprint(),
           "algorithm_version": ALGORITHM_VERSION}
    try:
        ks = kmod.load()
        out["kernels"] = {"loaded": True, "profile": ks.profile, "frame": ks.frame, "coverage_utc": ks.coverage_utc,
                          "files": ks.provenance(), "warnings": ks.warnings, "de421_available": ks.de421_available}
    except kmod.KernelError as exc:
        out["kernels"] = {"loaded": False, "error": str(exc)}
    out["kernels"]["kernel_set"] = settings.KERNEL_SET
    reg = read_registry()
    from ..engine.dem import product_key
    out["terrain"] = {"levels": {product_key(v): {kk: v.get(kk) for kk in ("level", "product", "pixel_m", "sha256", "bytes",
                                                                         "synthetic", "registered_utc", "page", "citation")}
                                 for v in reg["products"]},
                      "error_maps": sorted(reg.get("error_maps", {})),
                      "synthetic_in_use": terrain_is_synthetic(),
                      "synthetic_allowed": settings.SYNTHETIC_TERRAIN_ALLOWED,
                      "problems": [why for _rec, why in broken_products()]}
    rep = validation_report()
    out["validation"] = None if rep is None else {k: rep.get(k) for k in ("run_utc", "code_version", "code_fingerprint",
                                                                         "kernel_profile", "tests")}
    try:
        out["validation_blockers"] = label_blockers(rep)
    except Exception:
        out["validation_blockers"] = ["kernels not loaded"]
    try:
        out["labels"] = labels()
    except Exception:
        out["labels"] = None
    out["panels"] = PANELS
    return out


@app.get("/api/catalog")
def catalog():
    return load_catalog()


@app.get("/api/coverage")
def coverage(lat: float, lon: float):
    try:
        la, lo = validate_latlon(lat, lon)
    except CoordinateError as exc:
        raise HTTPException(422, str(exc))
    return {"lat": la, "lon": lo, **coverage_check(la, lo)}


@app.post("/api/analysis")
def post_analysis(body: AnalysisIn):
    req = AnalysisRequest(**body.model_dump())
    try:
        validate_latlon(req.lat, req.lon)
        rid = result_id(req)
    except (CoordinateError, ValueError, kmod.KernelError) as exc:
        raise HTTPException(422, str(exc))
    if get_result(rid) is not None:
        return {"result_id": rid, "job_id": None}
    return {"result_id": None, "job_id": _submit("analysis", _do_analysis, req)}


@app.post("/api/compare")
def post_compare(body: CompareIn):
    if not body.sites or not body.windows:
        raise HTTPException(422, "Give at least one site and one window.")
    if len(body.sites) * len(body.windows) > 48:
        raise HTTPException(422, "At most 48 site-window cells per comparison.")
    return {"job_id": _submit("compare", _do_compare, body)}


@app.get("/api/jobs/{jid}")
def job(jid: str):
    with JOBS_LOCK:
        j = JOBS.get(jid)
    if not j:
        raise HTTPException(404, "Unknown job")
    return j


@app.get("/api/results/{rid}")
def result(rid: str):
    res = get_result(rid)
    if res is None:
        raise HTTPException(404, "Unknown result")
    return JSONResponse(res)


@app.get("/api/compare/{cid}")
def compare_result(cid: str):
    if cid not in COMPARES:
        raise HTTPException(404, "Unknown comparison")
    return COMPARES[cid]


def _csv(rows: list[list], header: list[str], preamble: list[str]) -> PlainTextResponse:
    buf = io.StringIO()
    for line in preamble:
        buf.write(f"# {line}\n")
    w = csv.writer(buf)
    w.writerow(header)
    w.writerows(rows)
    return PlainTextResponse(buf.getvalue(), media_type="text/csv")


def _preamble(res: dict) -> list[str]:
    p = res["provenance"]
    return [f"LUNA-OPS result {res['id']} sha256 {res['sha256']}",
            f"site lat {res['site']['lat']} lon {res['site']['lon']} ground {res['site']['ground_h_m']} m; "
            f"observer {p['parameters']['observer']['label']} {p['parameters']['observer']['height_m']} m",
            f"rules: sunlit={p['parameters']['rules']['sunlit']} dte={p['parameters']['rules']['dte']} "
            f"margin={p['parameters']['rules']['full_disk_margin_deg']} deg",
            f"kernels profile {p['kernels']['profile']} frame {p['kernels']['frame']}; aberration {p['aberration']}",
            f"code {p['code_version']} algorithm {p['algorithm_version']}",
            "labels: " + "; ".join(f"{k}={v['kind']}/{v['validation']}" for k, v in res["labels"].items())] + \
        _ld_preamble(p) + _uncertainty_preamble(p)


def _ld_preamble(p: dict) -> list[str]:
    """Label of the limb-darkened power columns (Phase 3 item 2), when the result has them."""
    ld = (p.get("parameters") or {}).get("limb_darkening")
    if not ld:
        return []
    return [f"power_rel_ld / sun_visible_flux_fraction_ld: {ld.get('label')}; coefficients {ld.get('coefficients')} "
            f"({ld.get('citation')}); power_rel (uniform disk) unchanged"]


def _uncertainty_preamble(p: dict) -> list[str]:
    """Horizon-uncertainty model lines; the L_corr label appears wherever sigma or uncertain flags are exported."""
    u = (p.get("parameters") or {}).get("horizon_uncertainty")
    if not u:
        return []
    lines = [f"horizon uncertainty: {u.get('correlation_model')} correlation, L_corr {u.get('L_corr_m')} m "
             f"({u.get('L_corr_status')}); uncertain if within k={u.get('uncertain_sigma_k')} sigma; "
             f"sigma above {u.get('sigma_nonlinear_deg')} deg forces uncertain; sigma computed: {u.get('sigma_computed')}"]
    if u.get("sigma_computed"):
        lines.append(u.get("L_corr_label", ""))
    return lines


@app.get("/api/results/{rid}/series.csv")
def export_series(rid: str):
    res = get_result(rid)
    if res is None:
        raise HTTPException(404, "Unknown result")
    s = res["series"]
    pm = res["provenance"]["parameters"]["panel"]["model"]
    n = len(s["utc"])
    f_ld = s["sun"].get("f_ld") or [None] * n                 # results computed before algorithm 1.4.0 lack it
    p_ld = s["power"][pm].get("series_ld") or [None] * n
    rows = [[s["utc"][i], s["sun"]["az"][i], s["sun"]["el"][i], s["sun"]["rho"][i], s["sun"]["f"][i], s["sun"]["c"][i],
             s["earth"]["az"][i], s["earth"]["el"][i], s["earth"]["rho"][i], s["earth"]["f"][i], s["earth"]["c"][i],
             s["earth_occults_sun"][i], s["power"][pm]["series"][i], f_ld[i], p_ld[i]] for i in range(n)]
    return _csv(rows, ["utc", "sun_az_deg", "sun_el_deg", "sun_radius_deg", "sun_visible_fraction", "sun_centre_clearance_deg",
                       "earth_az_deg", "earth_el_deg", "earth_radius_deg", "earth_visible_fraction",
                       "earth_centre_clearance_deg", "earth_occults_sun_fraction", f"power_rel_{pm}",
                       "sun_visible_flux_fraction_ld", f"power_rel_ld_{pm}"], _preamble(res))


@app.get("/api/results/{rid}/events.csv")
def export_events(rid: str):
    res = get_result(rid)
    if res is None:
        raise HTTPException(404, "Unknown result")
    rows = [[e["utc"], e["target"], e["name"], e["function"]] for e in res["events"]]
    return _csv(rows, ["utc", "target", "event", "function"], _preamble(res))


@app.get("/api/results/{rid}/intervals.csv")
def export_intervals(rid: str):
    res = get_result(rid)
    if res is None:
        raise HTTPException(404, "Unknown result")
    rows = []
    for key, ivs in res["intervals"].items():
        for iv in ivs:
            rows.append([key, iv["start_utc"], iv["end_utc"], iv["state"], iv["duration_h"], iv["brief"], iv["uncertain"],
                         ";".join(iv.get("uncertain_reasons") or []), iv.get("near_field"), iv.get("subbin_peak")])
    return _csv(rows, ["quantity", "start_utc", "end_utc", "state", "duration_h", "brief", "uncertain",
                       "uncertain_reasons", "near_field", "subbin_peak"], _preamble(res))


@app.get("/api/results/{rid}/result.json")
def export_json(rid: str):
    res = get_result(rid)
    if res is None:
        raise HTTPException(404, "Unknown result")
    return Response(json.dumps(res, sort_keys=True, indent=1), media_type="application/json",
                    headers={"Content-Disposition": f'attachment; filename="lunaops_{rid}.json"'})


@app.get("/api/compare/{cid}/compare.csv")
def export_compare(cid: str):
    if cid not in COMPARES:
        raise HTTPException(404, "Unknown comparison")
    c = COMPARES[cid]
    rows = []
    for cell in c["cells"]:
        sm = cell.get("summary") or {}
        sr = c["base"]["sunlit_rule"]
        dr = c["base"]["dte_rule"]
        pw = (sm.get("power") or {}).get(c["base"]["panel_model"]) or {}
        rows.append([cell["site"].get("name") or f"{cell['site']['lat']:.4f},{cell['site']['lon']:.4f}",
                     cell["window"]["start_utc"], cell["window"]["end_utc"], cell["result_id"],
                     (sm.get(f"sun_{sr}") or {}).get("percent"), (sm.get(f"sun_{sr}") or {}).get("longest_gap_h"),
                     (sm.get(f"earth_{dr}") or {}).get("percent"), (sm.get(f"earth_{dr}") or {}).get("longest_gap_h"),
                     (sm.get("overlap") or {}).get("percent"), pw.get("mean"), pw.get("equivalent_full_sun_h"),
                     cell.get("error")])
    return _csv(rows, ["site", "start_utc", "end_utc", "result_id", "sunlit_percent", "longest_dark_h", "dte_percent",
                       "longest_dte_gap_h", "overlap_percent", "power_rel_mean", "equivalent_full_sun_h", "error"],
                [f"LUNA-OPS comparison {cid}; every cell is the single-site result with the listed result_id"])


@app.get("/api/terrain")
def terrain(lat: float, lon: float, radius_km: float = Query(8.0, gt=0.0, le=50.0), n: int = 160):
    try:
        la, lo = validate_latlon(lat, lon)
        return terrain_grid(la, lo, radius_km * 1000.0, max(32, min(n, 256)))
    except (CoordinateError, TerrainError) as exc:
        raise HTTPException(422, str(exc))


@app.get("/api/tiles/meta")
def tiles_meta():
    m = tile_meta()
    if m is None:
        return {"available": False, "reason": no_terrain_reason()}
    return {"available": True, **m}


@app.get("/api/tiles/{z}/{x}/{y}.png")
def tile(z: int, x: int, y: int):
    try:
        png = render_tile(z, x, y)
    except (TerrainError, OSError) as exc:   # rasterio's RasterioIOError is an OSError
        raise HTTPException(422, f"Tile not available: {exc}")
    return Response(png, media_type="image/png", headers={"Cache-Control": "public, max-age=86400"})


@app.get("/api/validation")
def validation():
    return validation_report() or {"status": "No validation report yet. Run `python -m validation.run_validation`."}


# ---------------------------------------------------------- frontend
def _dist_file(path: str):
    """A file inside FRONTEND_DIST, or None. Paths that resolve outside it (../, symlinks) are never served."""
    root = settings.FRONTEND_DIST.resolve()
    try:
        f = (root / path).resolve()
    except (OSError, ValueError):
        return None
    return f if path and f.is_relative_to(root) and f.is_file() else None


if (settings.FRONTEND_DIST / "index.html").exists():
    if (settings.FRONTEND_DIST / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=settings.FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        f = _dist_file(path)
        if f is not None:
            return FileResponse(f)
        return FileResponse(settings.FRONTEND_DIST / "index.html")
