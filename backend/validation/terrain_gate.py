"""Shared, hash-bound terrain acceptance gate for the final V-09, V-10, V-11 and V-12 runs (Phase 4 A6).

A run of these external validations is final only if the terrain it used is the terrain that was accepted:
- the levels REQUIRED_LEVELS (the A5 20 m terrain and the wider 240 m terrain) are registered and present;
- every registered non-synthetic DEM product and its error map are present as registered (existence and size,
  dem.file_problem; `python -m lunaops.acquire verify` re-hashes the files and belongs to every final run);
- every pair of overlapping registered non-synthetic products is accepted in reference/terrain_acceptance.json,
  each side identified by its registry key, DEM SHA-256 and error-map SHA-256.

Why every overlapping pair: products meet in two ways at run time.
- Horizon heights: a ray hands over between products at the band ends (5 m -> 20 m at ~8 km, 20 m -> 80 m at ~40 km,
  80 m -> 240 m at ~250 km) and falls through to the next coarser product with data at a data edge (20 m -> 240 m
  where the 20 m window crosses the 80 S edge).
- Horizon sigma: the cross-product allowance pairs the site's product with each blocking product (5 m or 20 m
  site with an 80 m or 240 m blocker).
Over the registered hierarchy the union is every overlapping finer/coarser pair, so all are required.

There is no switch that bypasses the gate. The acceptance file's digest is recorded in each run's metadata
(common.run_meta) and merge_external refuses a V-09..V-12 status other than "not run" unless the run met the gate
under the acceptance in force when the report is built.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

GATED_TESTS = ("V-09", "V-10", "V-11", "V-12")
REQUIRED_LEVELS = ("20m", "240m")           # A5 20 m terrain; wider 240 m terrain (A10/A11/A12 coverage)
ACCEPTANCE_FILE = Path(__file__).resolve().parent / "reference" / "terrain_acceptance.json"
_SHA = re.compile(r"^[0-9a-f]{64}$")
_REQUIRED_FIELDS = ("scope", "evidence", "source", "approver", "approved_date")


def load_acceptance(path: Path | None = None) -> dict:
    """The acceptance record, checked for structure (refuses empty approver, date, scope or evidence)."""
    data = json.loads(Path(path or ACCEPTANCE_FILE).read_text())
    if data.get("schema") != 1 or not isinstance(data.get("accepted_pairs"), list):
        raise ValueError("terrain acceptance: unknown schema")
    for i, e in enumerate(data["accepted_pairs"]):
        for side in ("fine", "coarse"):
            s = e.get(side) or {}
            if not s.get("key") or not _SHA.match(str(s.get("dem_sha256"))) or not _SHA.match(
                    str(s.get("error_map_sha256"))):
                raise ValueError(f"terrain acceptance entry {i}: {side} needs key, dem_sha256 and error_map_sha256")
        if e["fine"]["key"] == e["coarse"]["key"]:
            raise ValueError(f"terrain acceptance entry {i}: a product cannot be paired with itself")
        for f in _REQUIRED_FIELDS:
            if not str(e.get(f) or "").strip():
                raise ValueError(f"terrain acceptance entry {i}: '{f}' is required")
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", e["approved_date"]):
            raise ValueError(f"terrain acceptance entry {i}: approved_date must be YYYY-MM-DD")
    return data


def acceptance_digest(path: Path | None = None) -> str:
    """SHA-256 of the canonical JSON of the acceptance record (formatting-independent)."""
    data = json.loads(Path(path or ACCEPTANCE_FILE).read_text())
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _side(rec: dict, em: dict | None) -> tuple:
    from lunaops.engine.dem import product_key
    return (product_key(rec), rec.get("sha256"), em.get("sha256") if em else None)


def registered_terrain(reg: dict | None = None) -> list[dict]:
    """Registered non-synthetic products, finest first, with their error map and any file problem."""
    from lunaops.engine.dem import _bounds, _sort_key, file_problem, product_key, read_registry
    reg = reg if reg is not None else read_registry()
    out = []
    for rec in sorted((p for p in reg["products"] if not p.get("synthetic")), key=_sort_key):
        em = reg.get("error_maps", {}).get(product_key(rec))
        problems = []
        why = file_problem(rec)
        if why:
            problems.append(why)
        if not em:
            problems.append(f"{product_key(rec)} has no registered error map")
        elif em.get("dem_sha256") != rec.get("sha256"):
            problems.append(f"the error map of {product_key(rec)} was registered for other DEM bytes")
        else:
            why = file_problem(em)
            if why:
                problems.append(f"error map of {product_key(rec)}: {why}")
        out.append({"rec": rec, "error_map": em, "key": product_key(rec), "bounds": _bounds(rec),
                    "pixel_m": float(rec.get("pixel_m") or abs(rec["transform"][0])), "problems": problems})
    return out


def _overlap(a: tuple, b: tuple) -> bool:
    return min(a[2], b[2]) > max(a[0], b[0]) and min(a[3], b[3]) > max(a[1], b[1])


def required_pairs(products: list[dict]) -> list[tuple[dict, dict]]:
    """Every pair of distinct products whose footprints overlap (positive area), finer (then key) first."""
    ps = sorted(products, key=lambda p: (p["pixel_m"], p["key"]))
    return [(a, b) for i, a in enumerate(ps) for b in ps[i + 1:] if _overlap(a["bounds"], b["bounds"])]


def evaluate(reg: dict | None = None, acceptance_path: Path | None = None) -> dict:
    """The gate: {"ok", "reasons", "acceptance_digest", "required_levels", "levels_present", "required_pairs",
    "accepted_pairs", "missing_pairs"}. Never reads raster contents."""
    reasons = []
    try:
        acc = load_acceptance(acceptance_path)
        digest = acceptance_digest(acceptance_path)
    except (OSError, ValueError) as exc:
        return {"ok": False, "reasons": [f"terrain acceptance record unusable: {exc}"], "acceptance_digest": None,
                "required_levels": list(REQUIRED_LEVELS), "levels_present": [], "required_pairs": [],
                "accepted_pairs": [], "missing_pairs": []}
    prods = registered_terrain(reg)
    present = sorted({p["rec"]["level"] for p in prods if not p["problems"]})
    missing_levels = [lv for lv in REQUIRED_LEVELS if lv not in present]
    if missing_levels:
        reasons.append(f"terrain levels not registered and present here: {', '.join(missing_levels)} "
                       "(A5 20 m; wider 240 m)")
    for p in prods:
        reasons.extend(p["problems"])
    accepted = {frozenset((_side_t(e["fine"]), _side_t(e["coarse"]))) for e in acc["accepted_pairs"]}
    req, ok_pairs, missing = [], [], []
    for a, b in required_pairs(prods):
        label = f"{a['key']} / {b['key']}"
        req.append(label)
        if frozenset((_side(a["rec"], a["error_map"]), _side(b["rec"], b["error_map"]))) in accepted:
            ok_pairs.append(label)
        else:
            missing.append(label)
    if missing:
        reasons.append("A6 acceptance missing or not matching the registered DEM/error-map SHA-256 for: "
                       + "; ".join(missing))
    return {"ok": not reasons, "reasons": reasons, "acceptance_digest": digest,
                "required_levels": list(REQUIRED_LEVELS), "levels_present": present, "required_pairs": req,
                "accepted_pairs": ok_pairs, "missing_pairs": missing}


def _side_t(s: dict) -> tuple:
    return (s["key"], s["dem_sha256"], s["error_map_sha256"])


def final_terrain_prerequisites() -> tuple[bool, str]:
    """(ok, reasons) for the scripts' score(); the full detail is evaluate()."""
    g = evaluate()
    return g["ok"], "; ".join(g["reasons"])

