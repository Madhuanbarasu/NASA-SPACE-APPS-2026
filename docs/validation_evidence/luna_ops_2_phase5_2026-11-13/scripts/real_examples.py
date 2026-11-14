"""Phase 5: landing screening on real registered LOLA products (timing, peak memory, example outputs).

Read only (no registry or report is written). Run from backend/:  python <this file> <out_dir>
Peak memory is the process's peak working set (Windows GetProcessMemoryInfo), which includes Python, numpy, numba
and rasterio themselves.
"""
from __future__ import annotations

import ctypes
import json
import sys
import time
from ctypes import wintypes
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
from lunaops_landing import assess as A  # noqa: E402

OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)


class PMC(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t), ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t), ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t)]


_k32 = ctypes.WinDLL("kernel32")
_psapi = ctypes.WinDLL("psapi")
_k32.GetCurrentProcess.restype = wintypes.HANDLE
_psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC), wintypes.DWORD]
_psapi.GetProcessMemoryInfo.restype = wintypes.BOOL


def mem_mb():
    c = PMC()
    c.cb = ctypes.sizeof(PMC)
    _psapi.GetProcessMemoryInfo(_k32.GetCurrentProcess(), ctypes.byref(c), c.cb)
    return round(c.WorkingSetSize / 2**20, 1), round(c.PeakWorkingSetSize / 2**20, 1)


CASES = [
    # name, config, footprint (lat, lon, radius), thresholds (user-defined assumptions for the demonstration only)
    ("site01_5m_1500m", {"lat": -89.463163, "lon": 222.510447, "window_half_m": 1500.0},
     (-89.463163, 222.510447, 50.0), {"slope_deg": 10.0, "roughness_m": 0.5, "relief_m": 10.0}),
    ("site01_5m_3000m", {"lat": -89.463163, "lon": 222.510447, "window_half_m": 3000.0},
     (-89.463163, 222.510447, 100.0), {"slope_deg": 10.0}),
    ("site01_20m_same_site", {"lat": -89.463163, "lon": 222.510447, "window_half_m": 3000.0,
                              "product": "20m:LDEM_80S_20MPP_ADJ.TIF"},
     (-89.463163, 222.510447, 100.0), {"slope_deg": 10.0}),
    ("shackleton_rim_20m", {"lat": -89.9, "lon": 0.0, "window_half_m": 4000.0},
     (-89.9, 0.0, 100.0), {"slope_deg": 10.0}),
    ("lat85_80m", {"lat": -85.0, "lon": 30.0, "window_half_m": 20000.0, "product": "80m:LDEM_80S_80MPP_ADJ.tiff"},
     (-85.0, 30.0, 100.0), {"slope_deg": 10.0}),
]

report = {"memory_start_mb": mem_mb(), "cases": []}
for name, cfg, (flat, flon, rad), th in CASES:
    t0 = time.perf_counter()
    a = A.assess(cfg)
    t1 = time.perf_counter()
    fp = A.footprint(a, flat, flon, rad, th)
    t2 = time.perf_counter()
    payload = A.to_json(a)
    payload["footprint"] = fp
    (OUT / f"{name}.json").write_text(json.dumps(payload, indent=1))
    s = payload["summary"]
    report["cases"].append({
        "case": name, "product": a.config["product"], "pixels": [a.win.nrows, a.win.ncols],
        "assess_s": round(t1 - t0, 2), "footprint_s": round(t2 - t1, 3), "memory_mb_now_peak": mem_mb(),
        "valid_share": s["valid_share"], "measured_share": s["measured_share"], "slope_deg": s["slope_deg"],
        "roughness_m": s["roughness_m"], "depressions": s["depressions"],
        "footprint_findings": {f["key"]: f["status"] for f in fp["findings"]},
        "footprint_coverage": fp["coverage"] and {k: fp["coverage"][k] for k in ("valid_pct", "measured_pct")}})
    print(json.dumps(report["cases"][-1]), flush=True)
# repeat of the last case: served from the in-memory cache (it keeps the latest 3 assessments)
t0 = time.perf_counter()
A.assess(dict(CASES[-1][1]))
report["cached_repeat_s"] = round(time.perf_counter() - t0, 4)
report["memory_end_mb"] = mem_mb()
(OUT / "summary.json").write_text(json.dumps(report, indent=1))
print(json.dumps({k: report[k] for k in ("memory_start_mb", "cached_repeat_s", "memory_end_mb")}))
