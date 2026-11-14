"""Phase 6: communication simulation on completed engine analysis results from data/cache (read only).

Run from backend/:  python <this file> <out_dir>
Relay orbits and RF values below are ILLUSTRATIVE scenario inputs chosen for demonstration: they are not hardware
specifications and not the orbit of any real or planned spacecraft.
"""
from __future__ import annotations

import ctypes
import json
import sys
import time
from ctypes import wintypes
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
from lunaops_comms import service as SV  # noqa: E402

OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)


class PMC(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t), ("a", ctypes.c_size_t), ("b", ctypes.c_size_t), ("c", ctypes.c_size_t),
                ("d", ctypes.c_size_t), ("e", ctypes.c_size_t), ("f", ctypes.c_size_t)]


_k32, _ps = ctypes.WinDLL("kernel32"), ctypes.WinDLL("psapi")
_k32.GetCurrentProcess.restype = wintypes.HANDLE
_ps.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC), wintypes.DWORD]


def mem():
    c = PMC()
    c.cb = ctypes.sizeof(PMC)
    _ps.GetProcessMemoryInfo(_k32.GetCurrentProcess(), ctypes.byref(c), c.cb)
    return round(c.WorkingSetSize / 2**20, 1), round(c.PeakWorkingSetSize / 2**20, 1)


ILLUSTRATIVE = "Illustrative demonstration values (Phase 6 evidence), not a hardware specification"
DTE = {"pt_w": 20.0, "gt_dbi": 20.0, "ltx_db": 1.0, "gr_dbi": 60.0, "lrx_db": 1.0, "lother_db": 3.0, "ts_k": 50.0,
       "freq_hz": 8.45e9, "rb_bps": 1.0e6, "ebn0_req_db": 2.5, "bandwidth_hz": 2.0e6, "basis": "illustrative", "reference": ILLUSTRATIVE}
UP = {"pt_w": 5.0, "gt_dbi": 3.0, "ltx_db": 1.0, "gr_dbi": 20.0, "lrx_db": 1.0, "lother_db": 2.0, "ts_k": 400.0,
      "freq_hz": 2.25e9, "rb_bps": 1.0e6, "ebn0_req_db": 2.5, "basis": "illustrative", "reference": ILLUSTRATIVE}
DOWN = {"pt_w": 50.0, "gt_dbi": 30.0, "ltx_db": 1.0, "gr_dbi": 60.0, "lrx_db": 1.0, "lother_db": 3.0, "ts_k": 50.0,
        "freq_hz": 8.45e9, "rb_bps": 1.0e6, "ebn0_req_db": 2.5, "basis": "illustrative", "reference": ILLUSTRATIVE}
# H1: argument of periapsis 90 deg puts the periapsis over the lunar NORTH (z > 0) and the apoapsis over the SOUTH
H1 = {"name": "H1 hypothetical elliptical orbit, apoapsis over the lunar south", "a_km": 6000.0, "e": 0.6, "i_deg": 60.0,
      "raan_deg": 0.0, "argp_deg": 90.0, "m0_deg": 0.0, "frame": "LME_EPOCH", "step_s": 60.0}
H2 = {"name": "H2 hypothetical 100 km circular lunar-polar orbit", "a_km": 1837.4, "e": 0.0, "i_deg": 90.0, "raan_deg": 0.0,
      "argp_deg": 0.0, "m0_deg": 0.0, "frame": "LME_EPOCH", "step_s": 30.0}
# H3: the same elements in J2000: polar to Earth's equator, about 24 deg from lunar-polar (frame demonstration)
H3 = {**H2, "name": "H3 = H2 elements in J2000 (polar to Earth's equator, not the Moon's)", "frame": "J2000"}
DTN = {"volume_mbit": 20000.0, "rate_kbps": 1000.0, "path": "any_rf"}

CASES = [
    ("site01_7d_direct_and_H1", "ed1d46ecace2cbae1c710283", H1),
    ("lat89_lon200_7d_no_dte_H1", "684a93e585762c77b11ef389", H1),
    ("lat89_lon200_7d_no_dte_H2", "684a93e585762c77b11ef389", H2),
    ("lat89_lon200_7d_no_dte_H3_frame_demo", "684a93e585762c77b11ef389", H3),
    ("lat84_lon359_30d_H1", "c9b10862d307661e0c2b7ef0", H1),
    ("lat78_lon22_30d_terrain_blocked_H1", "c2119090cd2ba9da7600ea6d", H1),
]
rep = {"memory_start_mb": mem(), "inputs": {"direct_link": DTE, "relay_up_link": UP, "relay_down_link": DOWN, "dtn": DTN,
                                             "relays": {"H1": H1, "H2": H2, "H3": H3}}, "cases": []}
for name, rid, relay in CASES:
    res = SV.load_result(rid)
    body = {"result_id": rid, "direct_link": DTE, "relay": {**relay, "epoch_utc": res["window"]["start_utc"]},
            "relay_up_link": UP, "relay_down_link": DOWN, "dtn": DTN}
    t0 = time.perf_counter()
    out = SV.simulate(body)
    t1 = time.perf_counter()
    body["direct_link"] = {**DTE, "rb_bps": 2.0e6}           # a link-budget edit: relay geometry comes from the cache
    out2 = SV.simulate(body)
    t2 = time.perf_counter()
    (OUT / f"{name}.json").write_text(json.dumps(out, indent=1))
    c = out["comparison"]
    rl = out["relay"]
    row = {"case": name, "result_id": rid, "site": [out["site"]["lat"], out["site"]["lon"]],
           "window": [out["window"]["start_utc"], out["window"]["end_utc"]], "relay": relay["name"],
           "relay_samples": rl["samples"], "simulate_s": round(t1 - t0, 2), "relink_s": round(t2 - t1, 3), "memory_mb": mem(),
           "engine_labels": out["engine_labels"],
           "direct_geometric": c["direct_geometric"], "direct_rf": c["direct_rf"], "direct_margin_db": out["direct"]["link"].get("margin_db"),
           "terrain_blocked_h": out["direct"]["terrain_blocked_stats"]["open_h"],
           "relay_orbit": rl["orbit"], "relay_leg1": rl["leg1"]["stats"], "relay_leg2": rl["leg2"]["stats"],
           "relay_geometric": c["relay_geometric"], "relay_rf": c["relay_rf"], "any_geometric": c["any_geometric"], "any_rf": c["any_rf"],
           "relay_adds_geometric_h": c.get("relay_adds_geometric_h"), "relay_adds_rf_h": c.get("relay_adds_rf_h"),
           "leg1_margin_db": rl["leg1"]["link"].get("margin_db"), "leg2_margin_db": rl["leg2"]["link"].get("margin_db"),
           "dtn": {k: out["dtn"].get(k) for k in ("evaluated", "complete", "completion_utc", "elapsed_h", "contacts_used", "remaining_mbit", "reason")},
           "rb2M_direct_rf_h": out2["comparison"]["direct_rf"]["open_h"] if out2["comparison"]["direct_rf"] else None}
    rep["cases"].append(row)
    print(json.dumps({k: row[k] for k in ("case", "simulate_s", "relink_s", "memory_mb", "relay_samples")}), flush=True)
rep["memory_end_mb"] = mem()
(OUT / "summary.json").write_text(json.dumps(rep, indent=1))
print(json.dumps({"memory_start_mb": rep["memory_start_mb"], "memory_end_mb": rep["memory_end_mb"]}))
