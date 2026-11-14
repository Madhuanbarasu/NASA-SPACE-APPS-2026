"""RF link budget (free-space, single hop). Every input is user-configured; none has a default.

Chain (all in dB units):
  FSPL      = 20 log10(4 pi R / lambda),  lambda = c / f                   [dB]
  EIRP      = Pt + Gt - Ltx                                                [dBW]
  Pr        = EIRP - FSPL - Lother + Gr - Lrx                              [dBW]
            ( = Pt + Gt + Gr - Ltx - Lrx - Lother - FSPL )
  C/N0      = Pr - 10 log10(k) - 10 log10(Ts)                              [dB-Hz]
  Eb/N0     = C/N0 - 10 log10(Rb)                                          [dB]
  margin    = Eb/N0 - (Eb/N0)required                                      [dB]
  C/N       = C/N0 - 10 log10(B)            (only when a bandwidth is given) [dB]
k = 1.380649e-23 J/K, c = 299 792 458 m/s. A stage is evaluated only when every input it needs is present and valid;
otherwise it, and every stage after it, is reported "not evaluated" with the missing or invalid inputs named.
Free space only: no atmosphere, rain, polarisation, multipath, diffraction or surface-propagation effects.
"""
from __future__ import annotations

import math

import numpy as np

from .constants import C_LIGHT, K_BOLTZMANN

# field -> (label, unit, rule); rules: "pos" > 0, "nonneg" >= 0, "real" finite
FIELDS = {
    "pt_w": ("Transmit power", "W", "pos"),
    "pt_dbw": ("Transmit power", "dBW", "real"),
    "gt_dbi": ("Transmit antenna gain", "dBi", "real"),
    "ltx_db": ("Transmitter system losses", "dB", "nonneg"),
    "gr_dbi": ("Receive antenna gain", "dBi", "real"),
    "lrx_db": ("Receiver system losses", "dB", "nonneg"),
    "lother_db": ("Implementation and pointing losses", "dB", "nonneg"),
    "ts_k": ("Receiver system noise temperature", "K", "pos"),
    "freq_hz": ("Frequency", "Hz", "pos"),
    "bandwidth_hz": ("Bandwidth", "Hz", "pos"),
    "rb_bps": ("Data rate", "bit/s", "pos"),
    "ebn0_req_db": ("Required Eb/N0", "dB", "real"),
}
BOUNDS = {"freq_hz": (1e3, 3e12), "pt_w": (1e-12, 1e7), "pt_dbw": (-120.0, 70.0), "gt_dbi": (-50.0, 100.0),
          "gr_dbi": (-50.0, 100.0), "ltx_db": (0.0, 200.0), "lrx_db": (0.0, 200.0), "lother_db": (0.0, 200.0),
          "ts_k": (1e-3, 1e7), "bandwidth_hz": (1e-3, 1e13), "rb_bps": (1e-6, 1e13), "ebn0_req_db": (-30.0, 60.0)}
BASES = {"illustrative": "Illustrative scenario (user-entered values, not hardware specifications)",
         "specification": "Values the user attributes to a hardware specification (see reference)"}


def validate(p: dict | None) -> tuple[dict, dict, list[str]]:
    """(clean values, {field: problem}, notes). Missing fields are absent from `clean`; invalid ones are listed in problems."""
    p = p or {}
    clean, problems, notes = {}, {}, []
    for k, (label, unit, rule) in FIELDS.items():
        v = p.get(k)
        if v is None or v == "":
            continue
        try:
            v = float(v)
        except (TypeError, ValueError):
            problems[k] = f"{label} is not a number"
            continue
        if not math.isfinite(v):
            problems[k] = f"{label} must be finite"
        elif rule == "pos" and v <= 0:
            problems[k] = f"{label} must be greater than 0 {unit}"
        elif rule == "nonneg" and v < 0:
            problems[k] = f"{label} must be 0 dB or more (enter losses as positive dB)"
        elif k in BOUNDS and not (BOUNDS[k][0] <= v <= BOUNDS[k][1]):
            problems[k] = f"{label} is outside the accepted range {BOUNDS[k][0]:g} to {BOUNDS[k][1]:g} {unit}"
        else:
            clean[k] = v
    if "pt_w" in clean and "pt_dbw" in clean and abs(10 * math.log10(clean["pt_w"]) - clean["pt_dbw"]) > 1e-6:
        problems["pt_dbw"] = "Transmit power is given in both W and dBW with different values; give one"
        clean.pop("pt_dbw")
        clean.pop("pt_w")
    if "pt_w" in clean:
        clean["pt_dbw_used"] = 10 * math.log10(clean["pt_w"])
        notes.append(f"Pt = 10 log10({clean['pt_w']:g} W) = {clean['pt_dbw_used']:.3f} dBW")
    elif "pt_dbw" in clean:
        clean["pt_dbw_used"] = clean["pt_dbw"]
    return clean, problems, notes


def _missing(clean: dict, problems: dict, need: list[str]) -> list[str]:
    out = []
    for k in need:
        if k == "pt":
            if "pt_dbw_used" not in clean:
                out.append("pt_dbw" if "pt_dbw" in problems else ("pt_w" if "pt_w" in problems else "pt_w"))
        elif k not in clean:
            out.append(k)
    return out


STAGES = [
    ("fspl_db", "Free-space path loss", "dB", ["freq_hz", "distance"], "20 log10(4 pi R / lambda), lambda = c / f"),
    ("eirp_dbw", "EIRP", "dBW", ["pt", "gt_dbi", "ltx_db"], "Pt + Gt - Ltx"),
    ("pr_dbw", "Received carrier power", "dBW", ["gr_dbi", "lrx_db", "lother_db"], "EIRP - FSPL - Lother + Gr - Lrx"),
    ("cn0_dbhz", "Carrier-to-noise density C/N0", "dB-Hz", ["ts_k"], "Pr - 10 log10(k) - 10 log10(Ts)"),
    ("ebn0_db", "Eb/N0", "dB", ["rb_bps"], "C/N0 - 10 log10(Rb)"),
    ("margin_db", "Link margin", "dB", ["ebn0_req_db"], "Eb/N0 - required Eb/N0"),
]


def evaluate(p: dict | None, distance_km) -> dict:
    """Evaluate the chain at one distance or an array of distances (km). Returns the stage values (scalars or arrays),
    per-stage status and the names of missing or invalid inputs; never fills a missing input."""
    clean, problems, notes = validate(p)
    d_m = np.asarray(distance_km, dtype=float) * 1000.0
    scalar = d_m.ndim == 0
    vals: dict[str, np.ndarray | None] = {}
    status = []
    blocked_by: list[str] = []
    for key, label, unit, need, formula in STAGES:
        miss = [m for m in _missing(clean, problems, [n for n in need if n != "distance"])]
        if "distance" in need and not np.all(np.isfinite(d_m) & (d_m > 0)):
            miss.append("distance")
        if blocked_by or miss:
            vals[key] = None
            status.append({"key": key, "label": label, "unit": unit, "formula": formula, "evaluated": False,
                           "missing": [m for m in miss if m not in problems], "invalid": [m for m in miss if m in problems],
                           "blocked_by_earlier": bool(blocked_by) and not miss})
            blocked_by = blocked_by or [key]
            continue
        if key == "fspl_db":
            lam = C_LIGHT / clean["freq_hz"]
            v = 20.0 * np.log10(4.0 * math.pi * d_m / lam)
        elif key == "eirp_dbw":
            v = np.asarray(clean["pt_dbw_used"] + clean["gt_dbi"] - clean["ltx_db"], dtype=float)
        elif key == "pr_dbw":
            v = vals["eirp_dbw"] - vals["fspl_db"] - clean["lother_db"] + clean["gr_dbi"] - clean["lrx_db"]
        elif key == "cn0_dbhz":
            v = vals["pr_dbw"] - 10.0 * math.log10(K_BOLTZMANN) - 10.0 * math.log10(clean["ts_k"])
        elif key == "ebn0_db":
            v = vals["cn0_dbhz"] - 10.0 * math.log10(clean["rb_bps"])
        else:
            v = vals["ebn0_db"] - clean["ebn0_req_db"]
        vals[key] = np.asarray(v, dtype=float)
        status.append({"key": key, "label": label, "unit": unit, "formula": formula, "evaluated": True})
    cn_db = None
    if vals.get("cn0_dbhz") is not None and "bandwidth_hz" in clean:
        cn_db = vals["cn0_dbhz"] - 10.0 * math.log10(clean["bandwidth_hz"])

    def out(v):
        if v is None:
            return None
        return float(v) if scalar else v

    return {"values": {k: out(v) for k, v in vals.items()}, "cn_db": out(cn_db), "stages": status,
            "inputs": clean, "problems": problems, "notes": notes,
            "constants": {"k_boltzmann_J_per_K": K_BOLTZMANN, "ten_log10_k_dBW_per_K_Hz": round(10 * math.log10(K_BOLTZMANN), 4),
                          "c_m_per_s": C_LIGHT},
            "complete": vals.get("margin_db") is not None,
            "basis": BASES.get((p or {}).get("basis"), BASES["illustrative"]),
            "reference": (p or {}).get("reference") or None}


def breakdown(p: dict | None, distance_km: float) -> dict:
    """The chain at one distance, as rows for display (value or 'not evaluated' with the reason)."""
    r = evaluate(p, float(distance_km))
    rows = []
    for st in r["stages"]:
        v = r["values"][st["key"]]
        rows.append({**st, "value": None if v is None else round(float(v), 4)})
    return {"distance_km": float(distance_km), "rows": rows, "cn_db": None if r["cn_db"] is None else round(r["cn_db"], 4),
            "inputs": r["inputs"], "problems": r["problems"], "notes": r["notes"], "constants": r["constants"],
            "complete": r["complete"], "basis": r["basis"], "reference": r["reference"]}
