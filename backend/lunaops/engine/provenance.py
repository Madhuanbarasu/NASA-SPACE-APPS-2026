"""Provenance and result labels (blueprint Sections 6.4, 8.9; C03, C06, U-05).

Every result carries enough provenance to reproduce it. Labels separate
what a number is (Geometric, Estimated) from whether its tests have passed
(Validated, Pending validation). A quantity is labelled Validated only when
the archived validation report shows all its tests passed for this exact
code version and the production kernel set.
"""
from __future__ import annotations

import json
import platform
import subprocess

from .. import ALGORITHM_VERSION, __version__, settings
from ..fingerprint import code_fingerprint, suite_fingerprint
from .dem import error_map_for, product_key, read_registry, terrain_is_synthetic, usable_levels
from .kernels import load

FRAME_TESTS = ["V-02a", "V-02b", "V-02c", "V-02d", "V-02e"]   # C07: alignment verified before production outputs
# Tests each quantity needs before it can be labelled Validated. Reconciled (Phase 3) with the README block
# "validated-requirements" and docs/TRACEABILITY.md; tests/test_phase3_labels.py keeps the three in step.
#   V-09 sunlit fraction vs LOLA AVGVISIB        -> disk_visibility, events, power_indicator
#   V-10 Earth visibility vs PGDA 69 ("any")     -> disk_visibility, events
#   V-11 no sunlight inside PSRs (18.6 yr)       -> horizon, disk_visibility, events, power_indicator
#   V-12 illumination vs LROC references         -> horizon, disk_visibility, events
#   V-13 Earth occultation vs eclipse contacts   -> disk_visibility, events, power_indicator
# events and power_indicator also depend on the horizon and disk model (V-06, V-07, V-08).
QUANTITY_TESTS = {
    "sun_earth_azel": ["V-01", *FRAME_TESTS, "V-03", "V-04"],
    "horizon": [*FRAME_TESTS, "V-06", "V-07", "V-11", "V-12"],
    "disk_visibility": [*FRAME_TESTS, "V-06", "V-07", "V-08", "V-09", "V-10", "V-11", "V-12", "V-13"],
    "events": [*FRAME_TESTS, "V-05", "V-06", "V-07", "V-08", "V-09", "V-10", "V-11", "V-12", "V-13", "V-14"],
    "power_indicator": [*FRAME_TESTS, "V-06", "V-07", "V-08", "V-08b", "V-09", "V-11", "V-13"],
}
# required for every Validated label (README): accessibility audit and performance benchmarks
GLOBAL_TESTS = ["U-04", "U-06"]
# quantities whose values depend on the terrain products used (validation must cover those products)
TERRAIN_QUANTITIES = ("horizon", "disk_visibility", "events", "power_indicator")
QUANTITY_KIND = {
    "sun_earth_azel": "Geometric",
    "horizon": "Geometric",
    "disk_visibility": "Geometric",
    "events": "Geometric",
    "power_indicator": "Estimated",
}


def code_version() -> str:
    try:
        rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=settings.REPO_ROOT,
                             capture_output=True, text=True, timeout=2)
        if rev.returncode == 0 and rev.stdout.strip():
            return f"{__version__}+{rev.stdout.strip()}"
    except Exception:
        pass
    return __version__


def validation_report() -> dict | None:
    p = settings.VALIDATION_REPORT
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def report_digest() -> str | None:
    import hashlib
    p = settings.VALIDATION_REPORT
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None


def label_blockers(rep: dict | None) -> list[str]:
    """Reasons why no quantity can be labelled Validated, independent of individual test status."""
    ks = load()
    reasons = []
    if rep is None:
        return ["no validation report has been run"]
    if rep.get("code_fingerprint") != code_fingerprint():
        reasons.append("the validation report was produced by different code")
    if rep.get("suite_fingerprint") != suite_fingerprint():
        reasons.append("the validation report was produced by a different version of the tests or validation scripts")
    if rep.get("pytest_exit_code") != 0:
        reasons.append("the automated test suite did not pass completely (pytest exit code "
                       f"{rep.get('pytest_exit_code')}); every test, including integrity tests, must pass")
    if rep.get("kernel_profile") != "production" or ks.profile != "production":
        reasons.append("production NAIF kernels were not used")
    rep_k = sorted(k.get("sha256") or "" for k in rep.get("kernels", []))
    cur_k = sorted(f.get("sha256") or "" for f in ks.files)
    if rep_k != cur_k:
        reasons.append("the report's kernel files differ from the loaded kernel files")
    return reasons


L_CORR_QUANTITIES = ("horizon", "events", "power_indicator")


def label_rules() -> dict:
    """Everything that decides a label besides the report itself (hashed into result IDs)."""
    return {"quantity_tests": QUANTITY_TESTS, "global_tests": GLOBAL_TESTS, "terrain_quantities": TERRAIN_QUANTITIES,
            "l_corr_quantities": L_CORR_QUANTITIES,
            "terrain_pin": "every non-synthetic product used (key, sha256, error-map sha256) must be listed in the "
                           "report's terrain_products"}


def label_rules_digest() -> str:
    import hashlib
    return hashlib.sha256(json.dumps(label_rules(), sort_keys=True).encode()).hexdigest()[:16]


def _product_id(p: dict) -> tuple:
    return (p.get("key"), p.get("sha256"), p.get("error_map_sha256"))


def compute_labels(report_tests: dict, blockers: list[str], synthetic: bool, l_corr_reason: str | None = None,
                   used_products: list[dict] | None = None, report_products: list[dict] | None = None) -> dict:
    """Pure label rule (tested exhaustively). report_tests: {test ID: {"status": ...}} from the report;
    blockers: report-level reasons (code, suite, kernels, pytest); used_products: the result's terrain
    products ({key, sha256, error_map_sha256, synthetic}), None when there is no result (status page)."""
    def st(t):
        return (report_tests or {}).get(t, {}).get("status", "not run")

    global_failing = [f"{t}: {st(t)} (required for every Validated label)" for t in GLOBAL_TESTS if st(t) != "passed"]
    covered = {_product_id(p) for p in report_products or []}
    uncovered = [p for p in used_products or [] if not p.get("synthetic") and _product_id(p) not in covered]
    out = {}
    for q, tests in QUANTITY_TESTS.items():
        status = {t: st(t) for t in tests}
        failing = [f"{t}: {s_}" for t, s_ in status.items() if s_ != "passed"]
        terrain = ([f"terrain product not covered by validation report: {p.get('key')}" for p in uncovered]
                   if q in TERRAIN_QUANTITIES else [])
        extra = [l_corr_reason] if (l_corr_reason and q in L_CORR_QUANTITIES) else []
        reasons = blockers + global_failing + failing + terrain + extra
        lab = "Validated" if not reasons else "Pending validation"
        if synthetic and q in TERRAIN_QUANTITIES:
            lab = "Synthetic test terrain - not a lunar result"
        out[q] = {"kind": QUANTITY_KIND[q], "validation": lab, "tests": status, "reasons": reasons}
    return out


def labels(synthetic: bool | None = None, l_corr_assumed: bool = False,
           used_products: list[dict] | None = None) -> dict:
    """Labels for each quantity. synthetic: whether the result in hand used synthetic terrain
    (from its horizon); None falls back to whether any usable product is synthetic.
    l_corr_assumed: the result's horizon uncertainty uses the uncalibrated L_corr assumption; the
    horizon, events and power labels then carry that reason and stay "Pending validation".
    used_products: the result's terrain products; each non-synthetic one must be covered by the report."""
    from .horizon import l_corr_label
    rep = validation_report()
    synthetic = terrain_is_synthetic() if synthetic is None else bool(synthetic)
    return compute_labels((rep or {}).get("tests") or {}, label_blockers(rep), synthetic,
                          l_corr_label() if l_corr_assumed else None, used_products,
                          (rep or {}).get("terrain_products"))


def terrain_products_record() -> list[dict]:
    """Non-synthetic terrain products usable now, with their error maps (recorded by run_validation)."""
    reg = read_registry()
    out = []
    for v in usable_levels():
        if v.get("synthetic"):
            continue
        em = error_map_for(v, reg)
        out.append({"key": product_key(v), "sha256": v.get("sha256"),
                    "error_map_sha256": em.get("sha256") if em else None})
    return sorted(out, key=lambda p: p["key"])


def _manifest_frames() -> dict:
    from pathlib import Path
    man = json.loads((Path(__file__).resolve().parents[1] / "manifests" / "datasets.json").read_text())
    return {d["id"]: d.get("frame") for d in man.get("dem_levels", [])}


def _frame_fields(tf: dict) -> dict:
    """Same keys as before Phase 3, now derived from product metadata, plus the structured form."""
    return {"frame_and_datum": "; ".join(x for x in (tf["frame"], tf["datum"]) if x),
            "frame_alignment": tf["frame_alignment"], "frame_details": tf,
            "frame_source": "product metadata: manifest frame per product_id, sphere radius from the product CRS"}


def terrain_frame(products: list[dict]) -> dict:
    """Frame, datum and alignment text derived from the products' own metadata (not a fixed string)."""
    import re
    frames_by_id = _manifest_frames()
    frames, radii = set(), set()
    for p in products:
        if p.get("synthetic"):
            frames.add("synthetic test terrain (south polar stereographic on the reference sphere; no lunar frame)")
        else:
            frames.add(frames_by_id.get(p.get("product_id")) or f"unknown: product {p.get('product_id')!r} not in the manifest")
        m = re.search(r"SPHEROID\[[^,]*,\s*([0-9.]+)", p.get("crs_wkt") or "")
        radii.add(f"{float(m.group(1)):.1f} m (from the product CRS)" if m else
                  f"{settings.R_MOON_M:.1f} m (no CRS recorded; LUNA-OPS reference sphere)")
    frames = sorted(frames)
    return {"frame": "; ".join(frames) if frames else None,
            "datum": "heights above the sphere of radius " + "; ".join(sorted(radii)) if radii else None,
            "frame_alignment": ("DE421 ME DEMs used in the DE440 ME421 frame; residual measured by V-02e"
                                if any("DE421" in (f or "") for f in frames) else None)}


def record(params: dict, horizon_meta: dict | None, detection_log: dict | None,
           synthetic: bool | None = None) -> dict:
    ks = load()
    reg = read_registry()
    usable = usable_levels()
    used_keys = {lv.get("key") for lv in (horizon_meta or {}).get("levels") or []}
    return {
        "code_version": code_version(),
        "code_fingerprint": code_fingerprint(),
        "algorithm_version": ALGORITHM_VERSION,
        "validation_report_sha256": report_digest(),
        "kernels": {"profile": ks.profile, "frame": ks.frame, "files": ks.provenance(),
                    "coverage_utc": list(ks.coverage_utc), "warnings": ks.warnings},
        "terrain": {
            "products": [{"key": product_key(v), "used_for_this_site": product_key(v) in used_keys,
                          **{kk: v.get(kk) for kk in (
                "level", "product", "page", "path", "sha256", "bytes", "pixel_m", "registered_utc", "units",
                "synthetic", "citation")}} for v in usable],
            "error_maps": {product_key(v): {kk: em.get(kk) for kk in ("product", "sha256", "path", "dem_sha256")}
                           for v in usable if (em := error_map_for(v, reg))},
            **_frame_fields(terrain_frame([v for v in usable if product_key(v) in used_keys] or usable)),
            "interpolation": "bilinear; any nodata neighbour treated as nodata",
            "synthetic": terrain_is_synthetic() if synthetic is None else bool(synthetic),
        },
        "horizon": horizon_meta,
        "parameters": params,
        "event_detection": detection_log,
        "label_rules_digest": label_rules_digest(),
        "aberration": settings.ABCORR,
        "refraction": "none (no atmosphere)",
        "earth_shape": {"model": "oblate spheroid, IERS Conventions 2010 (TN 36): a = 6378136.6 m, 1/f = 298.25642",
                        "radii_km": list(settings.EARTH_RADII_KM),
                        "disk": "exact projected limb ellipse; circular cap only within proven bounds "
                                "(delta_max, E_g, E_f)",
                        "atmosphere": "not modelled (geometric line of sight to the solid Earth)"},
        "earth_pole": settings.EARTH_POLE_LABEL,
        "platform": {"python": platform.python_version()},
    }
