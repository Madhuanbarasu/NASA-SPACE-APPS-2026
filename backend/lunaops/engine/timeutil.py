"""Time handling (blueprint Section 7.1, requirement B04, test V-01/U-02).

Users give UTC in ISO 8601. The engine computes in TDB seconds past J2000
(SPICE "ET") using the pinned leapseconds kernel. Leap seconds after the
LSK's last entry are unknown, so future UTC labels can be off by one second
per unannounced leap second; results flag dates after the LSK's last entry.
"""
from __future__ import annotations

import re
from datetime import datetime

import spiceypy as sp

from .kernels import SPICE_LOCK, load

ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}(:\d{2}(\.\d+)?)?)?Z?$")
LAST_LEAP_SECOND_UTC = "2017-01-01T00:00:00"  # last entry in naif0012.tls (fallback only)


class TimeInputError(ValueError):
    pass


def parse_utc(text: str) -> float:
    """ISO 8601 UTC string -> ET (TDB seconds past J2000)."""
    if not isinstance(text, str) or not ISO_RE.match(text.strip()):
        raise TimeInputError(f"'{text}' is not an ISO 8601 UTC time such as 2026-11-14T09:00:00Z")
    t = text.strip().rstrip("Z")
    try:
        dt = datetime.fromisoformat(t)
    except ValueError as exc:
        raise TimeInputError(f"'{text}' is not a valid calendar time: {exc}") from exc
    load()
    with SPICE_LOCK:
        return float(sp.str2et(dt.strftime("%Y-%m-%dT%H:%M:%S.%f")))


def to_utc(et: float, digits: int = 3) -> str:
    load()
    with SPICE_LOCK:
        return sp.et2utc(float(et), "ISOC", digits) + "Z"


def check_window(et0: float, et1: float, step_s: float, max_days: float) -> list[str]:
    """Validate a request window against kernel coverage (U-02). Returns warnings."""
    ks = load()
    if et1 <= et0:
        raise TimeInputError("The end time must be after the start time.")
    if (et1 - et0) / 86400.0 > max_days:
        raise TimeInputError(f"The window is longer than the {max_days:.0f}-day limit.")
    if step_s < 1.0:
        raise TimeInputError("The step must be at least 1 second.")
    if (et1 - et0) / step_s > 200_000:
        raise TimeInputError("The step is too small for this window (over 200,000 samples).")
    c0, c1 = ks.coverage_et
    # leave a margin for light-time and curvature estimation
    if et0 < c0 + 86400.0 or et1 > c1 - 86400.0:
        raise TimeInputError(
            f"The window must lie inside kernel coverage {ks.coverage_utc[0]} to {ks.coverage_utc[1]} "
            "(with a one-day margin)."
        )
    warnings = []
    last = last_leap_second_utc()
    if et1 > parse_utc(last):
        warnings.append(
            f"This window extends past the last leap second in the loaded leap-second kernel ({last[:10]}). "
            "UTC labels after it can shift by 1 s for each leap second announced later, and positions there are "
            "ephemeris predictions."
        )
    return warnings


def last_leap_second_utc() -> str:
    """The last leap-second epoch of the loaded leap-second kernel (DELTET/DELTA_AT), as an ISO UTC string.
    The warning depends only on the request and the kernels, never on the wall clock, so a result is the same
    whenever it is computed (Phase 3 item 8). Falls back to LAST_LEAP_SECOND_UTC if the pool has no table."""
    load()
    try:
        with SPICE_LOCK:
            v = sp.gdpool("DELTET/DELTA_AT", 0, 1000)
            cal = sp.etcal(float(v[-1]))            # e.g. '2017 JAN 01 00:00:00.000'
    except Exception:  # noqa: BLE001 - SPICE raises if the variable is absent
        return LAST_LEAP_SECOND_UTC
    d = datetime.strptime(cal[:11], "%Y %b %d")
    return d.strftime("%Y-%m-%dT00:00:00")
