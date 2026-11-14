"""Missing-terrain boundaries in the interval builder (2026-11-14; docs/validation_evidence/
scientific_validation_followup_2026-11-14).

Over incomplete (lower-bound) horizon bins a disk that would be visible is "unknown". The interval builder must cut at
the times a disk's verdict starts or stops resting on such bins, so unknown time is never reported as visible, while
complete horizons keep exactly the previous intervals. The reference here is the engine's own per-target unknown flag
sampled every second (the state definition under test is the interval construction, not the disk geometry, which is
covered by V-08 and the independent ray-cast in the investigation evidence).
"""
from __future__ import annotations

import numpy as np
import pytest

from conftest import needs_kernels

NB = 3600
SITE = (-89.463163, 222.510447)            # Site01 position, synthetic horizons (ground 0 m)
T0_UTC = "2026-11-20T00:00:00Z"


def _setup(h, inc, hours=4.0):
    from lunaops.engine.ephem import Site
    from lunaops.engine.events import EventConfig, EventDetector
    from lunaops.engine.timeutil import parse_utc
    from lunaops.engine.visibility import HorizonProfile
    det = EventDetector(Site(SITE[0], SITE[1], 0.0, 0.0), HorizonProfile(h, inc), EventConfig())
    et0 = parse_utc(T0_UTC)
    return det, et0, et0 + hours * 3600.0


def _sun_az(det, et):
    return float(det.evaluate(et).geo["sun"]["az"])


def _intervals(det, et0, et1, key="sun_any"):
    from lunaops.engine.events import build_intervals
    run = det.run(et0, et1)
    return build_intervals(det, et0, et1, run["events"], run["samples"])[key]


def _reference_unknown(det, et0, et1, step=1.0):
    ts = np.arange(et0, et1, step) + 0.5 * step
    return ts, np.array([bool(det.evaluate(float(t)).geo["sun"]["state"].get("unknown")) for t in ts])


def _state_at(ivs, t):
    for iv in ivs:
        if iv["start_et"] <= t < iv["end_et"]:
            return iv["state"]
    return "outside"


def _runs(mask):
    edges = np.flatnonzero(np.diff(mask.astype(int)))
    return edges


def _incomplete_around(az_c, width_deg):
    inc = np.zeros(NB, bool)
    for i in range(NB):
        if 0.0 <= ((i * 0.1 - az_c + 540.0) % 360.0) - 180.0 < width_deg:
            inc[i] = True
    return inc


@needs_kernels
def test_visible_time_over_missing_terrain_is_unknown(kernels):
    """The investigation's case: a low horizon with incomplete bins across part of the Sun's path (6,782 s)."""
    det, et0, et1 = _setup(np.full(NB, 0.0), np.zeros(NB, bool))
    inc = _incomplete_around(_sun_az(det, et0 + 4800.0), 0.6)
    det, et0, et1 = _setup(np.full(NB, 0.0), inc)
    ivs = _intervals(det, et0, et1)
    ts, ref = _reference_unknown(det, et0, et1)
    got = np.array([_state_at(ivs, t) for t in ts], dtype=object)
    # samples within the bisection tolerance (1 s) of an interval boundary may fall on either side of it
    bounds = np.array([iv["start_et"] for iv in ivs] + [ivs[-1]["end_et"]])
    far = np.min(np.abs(ts[:, None] - bounds[None, :]), axis=1) > det.cfg.tol_s
    assert 6700 < ref.sum() < 6900                                     # the investigated case (6,782 s)
    assert not np.any((got == True) & ref & far), "unknown time reported as visible"  # noqa: E712
    assert np.sum((got == True) & ref) <= 2                            # noqa: E712  at most the boundary seconds
    assert not np.any(((got == None) != ref) & far)                    # noqa: E711
    unk = sum(iv["end_et"] - iv["start_et"] for iv in ivs if iv["state"] is None)
    assert abs(unk - ref.sum()) <= 2.0


@needs_kernels
def test_two_missing_terrain_runs_give_two_unknown_intervals(kernels):
    det, et0, et1 = _setup(np.full(NB, 0.0), np.zeros(NB, bool), hours=6.0)
    inc = _incomplete_around(_sun_az(det, et0 + 5000.0), 0.1) | _incomplete_around(_sun_az(det, et0 + 15000.0), 0.1)
    det, et0, et1 = _setup(np.full(NB, 0.0), inc, hours=6.0)
    ivs = _intervals(det, et0, et1)
    ts, ref = _reference_unknown(det, et0, et1)
    unknown = [iv for iv in ivs if iv["state"] is None]
    assert len(unknown) == 2 == len(_runs(ref)) // 2
    for iv, (a, b) in zip(unknown, zip(ts[_runs(ref)[0::2] + 1], ts[_runs(ref)[1::2] + 1])):
        assert abs(iv["start_et"] - (a - 0.5)) <= 1.0 and abs(iv["end_et"] - (b - 0.5)) <= 1.0
    assert all(iv["state"] is True for iv in ivs if iv["state"] is not None)


@needs_kernels
def test_window_opening_on_missing_terrain_at_the_analysis_start(kernels):
    det, et0, et1 = _setup(np.full(NB, 0.0), np.zeros(NB, bool), hours=2.0)
    inc = _incomplete_around(_sun_az(det, et0) - 0.5, 1.2)            # the Sun starts over the incomplete run
    det, et0, et1 = _setup(np.full(NB, 0.0), inc, hours=2.0)
    ivs = _intervals(det, et0, et1)
    assert ivs[0]["state"] is None and ivs[0]["start_et"] == et0
    assert any(iv["state"] is True for iv in ivs)                       # it leaves the run inside the window


@needs_kernels
def test_hidden_over_missing_terrain_stays_hidden(kernels):
    """A lower bound that already blocks the disk is a valid hidden verdict: no unknown time."""
    det, et0, et1 = _setup(np.full(NB, 5.0), np.zeros(NB, bool))
    inc = _incomplete_around(_sun_az(det, et0 + 4800.0), 0.6)
    det, et0, et1 = _setup(np.full(NB, 5.0), inc)
    ivs = _intervals(det, et0, et1)
    assert [iv["state"] for iv in ivs] == [False]


@needs_kernels
def test_complete_horizons_keep_the_previous_intervals(kernels):
    """No incomplete bins: no extra cuts, and the intervals equal those built from the events alone (old behaviour)."""
    from lunaops.engine.events import build_intervals, full_state, incomplete_cuts
    rng = np.random.default_rng(7)
    det, et0, et1 = _setup(np.zeros(NB), np.zeros(NB, bool))
    g = det.evaluate(et0).geo["sun"]
    h = g["el"] + g["rho"] + rng.normal(0.0, 0.004, NB)          # straddles the Sun's top edge: many windows
    det, et0, et1 = _setup(h, np.zeros(NB, bool))
    assert incomplete_cuts(det, et0, et1) == []
    run = det.run(et0, et1)
    new = build_intervals(det, et0, et1, run["events"], run["samples"])["sun_any"]
    cuts = sorted({et0, et1, *[ev["et"] for ev in run["events"] if et0 < ev["et"] < et1]})
    old = []
    for a, b in zip(cuts[:-1], cuts[1:]):
        v = full_state(det, 0.5 * (a + b))["rules"]["sun_any"]
        if old and old[-1][2] == v and abs(old[-1][1] - a) < 1e-6:
            old[-1][1] = b
        else:
            old.append([a, b, v])
    assert [(iv["start_et"], iv["end_et"], iv["state"]) for iv in new] == [tuple(x) for x in old]
    assert len(new) > 3
