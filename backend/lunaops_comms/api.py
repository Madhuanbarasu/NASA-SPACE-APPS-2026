"""HTTP routes of the communication simulation package, attached to the existing app by start.py (install()).

Routes live under /api/comms/ and are inserted ahead of the app's other routes so the single-page-app catch-all cannot
shadow them. No existing route, engine module or validated output is changed.
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from . import COMMS_VERSION, VALIDATION_STATUS, comms_code_hash
from . import linkbudget as LB
from . import relay as RL
from . import service as SV
from .constants import ConstantError, moon_gm

router = APIRouter(prefix="/api/comms", tags=["communication (preliminary simulation)"])


class LinkIn(BaseModel):
    """Every field optional and without a default value: a missing field leaves the dependent stages unevaluated."""
    model_config = ConfigDict(extra="forbid")
    pt_w: float | None = None
    pt_dbw: float | None = None
    gt_dbi: float | None = None
    ltx_db: float | None = None
    gr_dbi: float | None = None
    lrx_db: float | None = None
    lother_db: float | None = None
    ts_k: float | None = None
    freq_hz: float | None = None
    bandwidth_hz: float | None = None
    rb_bps: float | None = None
    ebn0_req_db: float | None = None
    basis: Literal["illustrative", "specification"] = "illustrative"
    reference: str | None = Field(None, max_length=500)


class RelayIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    a_km: float | None = None
    e: float | None = None
    i_deg: float | None = None
    raan_deg: float | None = None
    argp_deg: float | None = None
    m0_deg: float | None = None
    epoch_utc: str | None = None
    frame: Literal["J2000", "LME_EPOCH"] | None = None
    # step and grazing altitude are range-checked by the service, which reports a problem for the relay alone instead of
    # failing the whole simulation (a schema bound here returned 422 for everything, direct-to-Earth included)
    step_s: float | None = None
    grazing_alt_km: float | None = None
    name: str | None = Field(None, max_length=80)


class DtnIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # checked by the planner (store_and_forward), which reports why it was not evaluated; a schema bound here returned
    # 422 for the whole simulation while the user was still typing (e.g. a volume of 0)
    volume_mbit: float | None = None
    rate_kbps: float | None = None
    path: Literal["direct_rf", "earth_visible", "relay_rf", "relay_geometric", "any_rf", "any_geometric"] = "direct_rf"
    start_utc: str | None = None


class SimIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    result_id: str = Field(..., min_length=4, max_length=64)
    reference_utc: str | None = None
    direct_link: LinkIn | None = None
    relay: RelayIn | None = None
    relay_up_link: LinkIn | None = None
    relay_down_link: LinkIn | None = None
    dtn: DtnIn | None = None


class BudgetIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    link: LinkIn
    distance_km: float = Field(..., gt=0, le=1e9)


@router.get("/meta")
def meta():
    try:
        gm = moon_gm()
    except ConstantError as exc:
        gm = {"error": str(exc)}
    return {"comms_version": COMMS_VERSION, "comms_code_sha256": comms_code_hash(), "status": VALIDATION_STATUS,
            "gm": gm, "link_fields": {k: {"label": v[0], "unit": v[1]} for k, v in LB.FIELDS.items()},
            "relay_frames": list(RL.FRAMES), "relay_step_s": [RL.MIN_STEP_S, RL.MAX_STEP_S], "relay_max_samples": RL.MAX_SAMPLES,
            "defaults": "none: every RF and orbital parameter is user-entered"}


@router.post("/linkbudget")
def linkbudget(body: BudgetIn):
    return {"status": VALIDATION_STATUS, **LB.breakdown(body.link.model_dump(), body.distance_km)}


@router.post("/simulate")
def simulate(body: SimIn):
    d = body.model_dump()
    try:
        return SV.simulate(d)
    except LookupError as exc:
        raise HTTPException(404, str(exc))
    except (SV.CommsInputError, ConstantError) as exc:
        raise HTTPException(422, str(exc))


def install(app: FastAPI) -> None:
    """Attach the communication routes ahead of the app's existing routes."""
    n = len(app.router.routes)
    app.include_router(router)
    added = app.router.routes[n:]
    del app.router.routes[n:]
    app.router.routes[0:0] = added
