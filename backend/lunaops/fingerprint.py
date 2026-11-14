"""Code fingerprint: SHA-256 over every source file of the lunaops package.

Validation reports, result IDs and horizon cache keys carry this fingerprint, so
an edited engine can never inherit labels, cached horizons or cached results
produced by different code (blueprint C04, C06).
"""
from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path

PKG = Path(__file__).resolve().parent


@lru_cache(maxsize=1)
def code_fingerprint() -> str:
    h = hashlib.sha256()
    for p in sorted(PKG.rglob("*.py")):
        rel = p.relative_to(PKG).as_posix()
        if "__pycache__" in rel:
            continue
        h.update(rel.encode())
        h.update(b"\0")
        h.update(p.read_bytes().replace(b"\r\n", b"\n"))   # same digest on Windows checkouts
        h.update(b"\0")
    for p in sorted((PKG / "manifests").glob("*.json")):
        h.update(p.name.encode())
        h.update(p.read_bytes().replace(b"\r\n", b"\n"))
    return h.hexdigest()


SUITE_DIRS = ("tests", "validation")


@lru_cache(maxsize=1)
def suite_fingerprint() -> str:
    """SHA-256 over the automated tests and validation scripts (backend/tests, backend/validation).

    Recorded in the validation report and in every external result file. A report whose suite
    fingerprint differs from the suite on disk cannot support a Validated label, so editing a test
    or a pass criterion invalidates the report until the suite is run again.
    """
    backend = PKG.parent
    h = hashlib.sha256()
    for d in SUITE_DIRS:
        for p in sorted((backend / d).rglob("*.py")):
            rel = p.relative_to(backend).as_posix()
            if "__pycache__" in rel:
                continue
            h.update(rel.encode())
            h.update(b"\0")
            h.update(p.read_bytes().replace(b"\r\n", b"\n"))
            h.update(b"\0")
    return h.hexdigest()
