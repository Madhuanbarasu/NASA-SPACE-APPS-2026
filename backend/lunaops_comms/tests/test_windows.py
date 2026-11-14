"""Three-valued timeline algebra, sample crossings, gaps and next-change logic."""
from __future__ import annotations

import numpy as np
import pytest

from lunaops_comms import windows as W


def seg(a, b, s, unc=False):
    return {"t0": float(a), "t1": float(b), "state": s, "uncertain": unc, "flags": {}}


def test_crossings_are_linearly_interpolated():
    ets = np.array([0.0, 10.0, 20.0, 30.0])
    tl = W.segments_from_samples(ets, np.array([-1.0, 1.0, 3.0, -1.0]))
    assert [s["state"] for s in tl] == [False, True, False]
    assert tl[0]["t1"] == pytest.approx(5.0) and tl[1]["t1"] == pytest.approx(27.5)


def test_unknown_samples_stay_unknown():
    ets = np.arange(5) * 10.0
    tl = W.segments_from_samples(ets, np.array([1.0, 1.0, np.nan, 1.0, 1.0]))
    assert [s["state"] for s in tl] == [True, None, True]
    assert tl[1]["t0"] == pytest.approx(15.0) and tl[1]["t1"] == pytest.approx(25.0)


def test_three_valued_and_or():
    a = [seg(0, 10, True), seg(10, 20, None), seg(20, 30, False)]
    b = [seg(0, 15, True), seg(15, 30, True)]
    land = W.combine("and", a, b)
    lor = W.combine("or", a, [seg(0, 30, False)])
    assert [(s["t0"], s["t1"], s["state"]) for s in land] == [(0, 10, True), (10, 20, None), (20, 30, False)]
    assert [s["state"] for s in lor] == [True, None, False]
    nb = W.combine("and_not", [seg(0, 30, True)], [seg(0, 10, True), seg(10, 30, False)])
    assert [(s["t0"], s["state"]) for s in nb] == [(0, False), (10, True)]


def test_intersection_of_contact_windows():
    leg1 = [seg(0, 10, True), seg(10, 20, False), seg(20, 40, True)]
    leg2 = [seg(0, 5, False), seg(5, 25, True), seg(25, 40, False)]
    both = W.combine("and", leg1, leg2)
    assert [(s["t0"], s["t1"]) for s in both if s["state"]] == [(5, 10), (20, 25)]


def test_stats_and_gaps():
    tl = [seg(0, 3600, True), seg(3600, 7200, False), seg(7200, 9000, True), seg(9000, 18000, None), seg(18000, 21600, True)]
    st = W.stats(tl, 0, 21600)
    assert st["windows"] == 3 and st["open_h"] == pytest.approx(2.5)
    assert st["gaps_between_windows"] == 2 and st["longest_gap_h"] == pytest.approx(2.5) and st["mean_gap_h"] == pytest.approx(1.75)
    assert st["unknown_h"] == pytest.approx(2.5)


def test_next_change_and_next_open():
    tl = [seg(0, 10, False), seg(10, 20, True), seg(20, 30, False)]
    n = W.next_change(tl, 4.0)
    assert n["state"] is False and n["seconds_to_change"] == pytest.approx(6.0) and n["next_open_et"] == 10.0
    assert W.next_change(tl, 12.0)["next_open_et"] == 12.0
    last = W.next_change(tl, 25.0)
    assert last["next_open_et"] is None and last["seconds_to_change"] is None


def test_engine_intervals_keep_flags_and_fill_gaps():
    ivs = [{"start_et": 0, "end_et": 10, "state": True, "uncertain": True, "uncertain_reasons": ["below_k_sigma"]},
           {"start_et": 15, "end_et": 30, "state": False, "uncertain": False}]
    tl = W.segments_from_intervals(ivs, 0, 30)
    assert [s["state"] for s in tl] == [True, None, False]
    assert tl[0]["uncertain"] and tl[0]["flags"]["uncertain_reasons"] == ["below_k_sigma"] and tl[1]["flags"]["gap_in_source"]
