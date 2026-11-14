"""LUNA-OPS landing-site hazard screening (preliminary, landing 0.1.0).

This package is deliberately OUTSIDE the validated science engine (backend/lunaops):

* lunaops.fingerprint.code_fingerprint() hashes every .py file under backend/lunaops plus its manifests, and
  suite_fingerprint() hashes backend/tests and backend/validation. Nothing in this package is inside either,
  so the official validation report keeps matching the validated engine, and NOTHING here is covered by it.
* Results from this package are never labelled "Validated". They are preliminary DEM-derived screening values
  with their own version (LANDING_VERSION) and their own code hash (landing_code_hash()).
* It reads terrain through the engine's registry and readers (read only) and never writes the production
  terrain registry (data/dem/registry.json); auxiliary landing products have their own manifest
  (data/landing/manifest.json).

Nothing here certifies a landing site as safe. There is no combined score, probability, ranking or safe/unsafe
verdict: every finding is reported separately with its source, resolution and limitations.
"""
from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path

LANDING_VERSION = "0.1.0"
VALIDATION_STATUS = "Preliminary screening - not part of the validated engine"
PKG = Path(__file__).resolve().parent


@lru_cache(maxsize=1)
def landing_code_hash() -> str:
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
