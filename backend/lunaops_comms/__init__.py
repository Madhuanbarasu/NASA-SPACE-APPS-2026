"""LUNA-OPS mission communication simulation (preliminary, comms 0.1.0).

This package is deliberately OUTSIDE the validated science engine (backend/lunaops), like lunaops_landing:

* lunaops.fingerprint.code_fingerprint() hashes every .py file under backend/lunaops plus its manifests, and
  suite_fingerprint() hashes backend/tests and backend/validation. Nothing here is inside either, so the official
  validation report keeps matching the validated engine, and NOTHING here is covered by it.
* Direct-to-Earth geometry is NOT recomputed: it is read from a completed engine analysis result (Earth azimuth,
  elevation, distance and clearance series, the terrain horizon and the Earth-visibility intervals), together with the
  engine's own validation labels, which are passed through verbatim and never upgraded.
* Everything this package calculates (RF link budgets, the hypothetical relay, window algebra, the store-and-forward
  planner) is labelled VALIDATION_STATUS.

Geometric visibility is not a radio link: a link is only called RF-feasible when a user-configured link budget meets
its user-configured required Eb/N0. There are no reliability scores, recommendations or invented hardware values, and
a simulated relay is always a hypothetical orbit, never an actual NASA satellite.
"""
from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path

COMMS_VERSION = "0.1.0"
VALIDATION_STATUS = "Preliminary simulation, not part of the validated engine"
PKG = Path(__file__).resolve().parent


@lru_cache(maxsize=1)
def comms_code_hash() -> str:
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
