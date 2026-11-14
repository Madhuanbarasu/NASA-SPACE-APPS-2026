"""Three-state timelines: a timeline is a list of contiguous segments [t0, t1) covering the simulation window, each with
state True (open), False (closed) or None (unknown: missing or incomplete data). Unknown is never turned into open or
closed: AND gives False if any input is False, None if any is unknown and none is False; OR gives True if any is True,
None if any is unknown and none is True.

Sample-based timelines (relay legs, link margins) place each open/closed boundary at the zero of the sampled clearance
(or margin) by linear interpolation between the two samples that bracket a sign change; a state that changes twice
between two samples is not seen. The resolution is the sampling step, which is always reported.
"""
from __future__ import annotations

import bisect
import math

import numpy as np


def segments_from_intervals(ivs: list[dict], t0: float, t1: float) -> list[dict]:
    """Engine intervals ({start_et, end_et, state, uncertain, ...}) -> timeline, keeping each interval's flags."""
    out = []
    for iv in sorted(ivs, key=lambda x: x["start_et"]):
        a, b = max(float(iv["start_et"]), t0), min(float(iv["end_et"]), t1)
        if b > a:
            out.append({"t0": a, "t1": b, "state": iv.get("state"), "uncertain": bool(iv.get("uncertain")),
                        "flags": {k: iv.get(k) for k in ("uncertain_reasons", "near_field", "subbin_peak", "brief") if k in iv}})
    return _fill(out, t0, t1)


def _fill(segs: list[dict], t0: float, t1: float) -> list[dict]:
    """Close gaps in coverage with unknown segments and merge equal neighbours."""
    out, t = [], t0
    for s in segs:
        if s["t0"] > t + 1e-6:
            out.append({"t0": t, "t1": s["t0"], "state": None, "uncertain": False, "flags": {"gap_in_source": True}})
        out.append(s)
        t = s["t1"]
    if t < t1 - 1e-6:
        out.append({"t0": t, "t1": t1, "state": None, "uncertain": False, "flags": {"gap_in_source": True}})
    return merge(out)


def merge(segs: list[dict]) -> list[dict]:
    out = []
    for s in segs:
        if s["t1"] <= s["t0"]:
            continue
        if out and out[-1]["state"] == s["state"] and out[-1].get("uncertain") == s.get("uncertain") and \
                abs(out[-1]["t1"] - s["t0"]) < 1e-6:
            out[-1] = {**out[-1], "t1": s["t1"]}
        else:
            out.append(dict(s))
    return out


def segments_from_samples(ets: np.ndarray, clearance: np.ndarray, unknown: np.ndarray | None = None,
                          uncertain: np.ndarray | None = None) -> list[dict]:
    """Open where clearance > 0. Boundaries at the linear zero crossing between bracketing samples; a span next to an
    unknown sample is unknown from midway between the samples."""
    ets = np.asarray(ets, float)
    c = np.asarray(clearance, float)
    unk = (np.zeros(ets.size, bool) if unknown is None else np.asarray(unknown, bool)) | ~np.isfinite(c)   # NaN is unknown
    unc = np.zeros(ets.size, bool) if uncertain is None else np.asarray(uncertain, bool)
    st = [None if bool(unk[i]) else bool(c[i] > 0) for i in range(ets.size)]
    out = []
    if ets.size == 1:
        return [{"t0": float(ets[0]), "t1": float(ets[0]), "state": st[0], "uncertain": bool(unc[0]), "flags": {}}]
    t = float(ets[0])
    for i in range(ets.size - 1):
        a, b = float(ets[i]), float(ets[i + 1])
        sa, sb = st[i], st[i + 1]
        ua = bool(unc[i] or unc[i + 1])
        if sa == sb:
            out.append({"t0": t, "t1": b, "state": sa, "uncertain": ua, "flags": {}})
        elif sa is None or sb is None:
            m = 0.5 * (a + b)
            out.append({"t0": t, "t1": m, "state": sa, "uncertain": ua, "flags": {}})
            out.append({"t0": m, "t1": b, "state": sb, "uncertain": ua, "flags": {}})
        else:
            ca, cb = float(c[i]), float(c[i + 1])
            tz = a + (b - a) * (ca / (ca - cb)) if ca != cb else 0.5 * (a + b)
            out.append({"t0": t, "t1": tz, "state": sa, "uncertain": ua, "flags": {}})
            out.append({"t0": tz, "t1": b, "state": sb, "uncertain": ua, "flags": {}})
        t = b
    return merge(out)


def _breaks(*tls: list[dict]) -> list[float]:
    return sorted({s["t0"] for tl in tls for s in tl} | {s["t1"] for tl in tls for s in tl})


def _at(tl: list[dict], t: float, starts: list[float] | None = None) -> dict | None:
    starts = starts if starts is not None else [s["t0"] for s in tl]
    i = bisect.bisect_right(starts, t) - 1
    if 0 <= i < len(tl) and tl[i]["t0"] <= t < tl[i]["t1"]:
        return tl[i]
    return None


def combine(op: str, *tls: list[dict]) -> list[dict]:
    """'and' / 'or' / 'and_not' (first AND NOT second) of timelines, three-valued."""
    bs = _breaks(*tls)
    starts = [[s["t0"] for s in tl] for tl in tls]
    out = []
    for a, b in zip(bs[:-1], bs[1:]):
        if b - a <= 1e-9:
            continue
        mid = 0.5 * (a + b)
        segs = [_at(tl, mid, st) for tl, st in zip(tls, starts)]
        vals = [None if s is None else s["state"] for s in segs]
        unc = any(s is not None and s.get("uncertain") for s in segs)
        if op == "and_not":
            vals = [vals[0], None if vals[1] is None else (not vals[1])]
            op_ = "and"
        else:
            op_ = op
        if op_ == "and":
            v = False if any(x is False for x in vals) else (None if any(x is None for x in vals) else True)
        else:
            v = True if any(x is True for x in vals) else (None if any(x is None for x in vals) else False)
        out.append({"t0": a, "t1": b, "state": v, "uncertain": unc and v is not None, "flags": {}})
    return merge(out)


def stats(tl: list[dict], t0: float, t1: float) -> dict:
    """Open time, windows, gaps (closed or unknown time between windows) and unknown time; hours."""
    wins = [s for s in tl if s["state"] is True]
    gaps = []
    prev_end = None
    for w in wins:
        if prev_end is not None and w["t0"] > prev_end:
            gaps.append(w["t0"] - prev_end)
        prev_end = w["t1"]
    open_s = sum(w["t1"] - w["t0"] for w in wins)
    unknown_s = sum(s["t1"] - s["t0"] for s in tl if s["state"] is None)
    total = max(t1 - t0, 1e-9)
    return {"open_h": open_s / 3600.0, "open_share": open_s / total, "windows": len(wins),
            "uncertain_windows": sum(1 for w in wins if w.get("uncertain")),
            "longest_window_h": max((w["t1"] - w["t0"] for w in wins), default=0.0) / 3600.0,
            "gaps_between_windows": len(gaps), "mean_gap_h": (sum(gaps) / len(gaps) / 3600.0) if gaps else None,
            "longest_gap_h": (max(gaps) / 3600.0) if gaps else None, "unknown_h": unknown_s / 3600.0,
            "starts_open": bool(tl and tl[0]["state"] is True), "ends_open": bool(tl and tl[-1]["state"] is True)}


def next_change(tl: list[dict], t: float) -> dict | None:
    """The state at t and the time of the next state change (None after the window)."""
    s = _at(tl, t)
    if s is None:
        return None
    nxt = next((x for x in tl if x["t0"] >= s["t1"] - 1e-9), None)
    nxt_open = next((x for x in tl if x["t0"] >= t and x["state"] is True and x is not s), None)
    return {"state": s["state"], "until_et": s["t1"], "seconds_to_change": s["t1"] - t if nxt else None,
            "next_state": nxt["state"] if nxt else None,
            "next_open_et": (t if s["state"] is True else (nxt_open["t0"] if nxt_open else None))}


def to_json(tl: list[dict], iso) -> list[dict]:
    return [{"start_et": round(s["t0"], 3), "end_et": round(s["t1"], 3), "start_utc": iso(s["t0"]), "end_utc": iso(s["t1"]),
             "duration_h": round((s["t1"] - s["t0"]) / 3600.0, 5), "state": s["state"], "uncertain": bool(s.get("uncertain")),
             **({"flags": s["flags"]} if s.get("flags") else {})} for s in tl]


def round_stats(st: dict) -> dict:
    return {k: (round(v, 5) if isinstance(v, float) and math.isfinite(v) else v) for k, v in st.items()}
