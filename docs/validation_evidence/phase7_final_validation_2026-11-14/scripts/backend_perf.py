"""Phase 7 Part H: backend performance against the running server on port 8000 (no new server is started).

For each request: wall time (submit -> result available) and the server process working set sampled every 0.25 s
(start, peak during the request, end). Sites and windows are chosen so that the analyses are not already cached:
  * analysis, 1-day, 30-day and 365-day windows at one site (the first run also computes and caches the horizon);
  * the same 30-day request again (result cache hit);
  * landing screening at a new site (cold) and the same request again;
  * communication simulation (direct link, illustrative relay H1, DTN) on the 30-day and 365-day results;
  * display tiles (lunaops_tiles) and the 3D terrain request.
RF values and relay orbit are the Phase 6 ILLUSTRATIVE scenario inputs, not hardware specifications or a real spacecraft.
Usage: python backend_perf.py <server pid> <out json>
"""
import ctypes
import json
import sys
import threading
import time
import urllib.request
from ctypes import wintypes

BASE = "http://127.0.0.1:8000"
PID = int(sys.argv[1])
OUT = sys.argv[2]


class PMC(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t), ("a", ctypes.c_size_t), ("b", ctypes.c_size_t), ("c", ctypes.c_size_t),
                ("d", ctypes.c_size_t), ("e", ctypes.c_size_t), ("f", ctypes.c_size_t)]


k32, ps = ctypes.WinDLL("kernel32"), ctypes.WinDLL("psapi")
k32.OpenProcess.restype = wintypes.HANDLE
ps.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC), wintypes.DWORD]
H = k32.OpenProcess(0x1000 | 0x0010, False, PID)   # PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_VM_READ


def ws_mb():
    c = PMC(); c.cb = ctypes.sizeof(PMC)
    if not ps.GetProcessMemoryInfo(H, ctypes.byref(c), c.cb):
        return None, None
    return round(c.WorkingSetSize / 2**20, 1), round(c.PeakWorkingSetSize / 2**20, 1)


def call(method, path, body=None, timeout=3600):
    data = json.dumps(body).encode() if body is not None else None
    rq = urllib.request.Request(BASE + path, data=data, method=method, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(rq, timeout=timeout) as r:
        raw = r.read()
        return r.status, raw


def measured(name, fn):
    samples, stop = [], threading.Event()

    def sampler():
        while not stop.is_set():
            samples.append(ws_mb()[0]); time.sleep(0.25)

    m0 = ws_mb()[0]; th = threading.Thread(target=sampler, daemon=True); th.start()
    t0 = time.perf_counter()
    try:
        info = fn(); err = None
    except Exception as exc:   # recorded, not hidden
        info, err = None, f"{type(exc).__name__}: {exc}"
    dt = time.perf_counter() - t0
    stop.set(); th.join()
    m1 = ws_mb()[0]
    row = {"case": name, "wall_s": round(dt, 3), "ws_start_mb": m0, "ws_peak_during_mb": max([s for s in samples if s] + [m0, m1]),
           "ws_end_mb": m1, "info": info, "error": err}
    print(json.dumps(row)[:400], flush=True)
    return row


def analysis(lat, lon, start, end):
    st, raw = call("POST", "/api/analysis", {"lat": lat, "lon": lon, "start_utc": start, "end_utc": end})
    j = json.loads(raw); rid, jid, cached = j["result_id"], j["job_id"], j["result_id"] is not None
    while rid is None:
        time.sleep(0.5)
        js = json.loads(call("GET", f"/api/jobs/{jid}")[1])
        if js.get("status") in ("done", "error", "failed"):
            if js.get("status") != "done":
                raise RuntimeError(json.dumps(js)[:300])
            rid = js.get("result_id") or (js.get("result") or {}).get("result_id")
    res = json.loads(call("GET", f"/api/results/{rid}")[1])
    return {"result_id": rid, "cached": cached, "samples": len((res.get("series") or {}).get("t_utc", []) or []),
            "labels": res.get("labels") or res.get("validation_labels")}


ILL = "Illustrative demonstration values (Phase 6 evidence), not a hardware specification"
DTE = {"pt_w": 20.0, "gt_dbi": 20.0, "ltx_db": 1.0, "gr_dbi": 60.0, "lrx_db": 1.0, "lother_db": 3.0, "ts_k": 50.0,
       "freq_hz": 8.45e9, "rb_bps": 1.0e6, "ebn0_req_db": 2.5, "bandwidth_hz": 2.0e6}
UP = {"pt_w": 5.0, "gt_dbi": 3.0, "ltx_db": 1.0, "gr_dbi": 20.0, "lrx_db": 1.0, "lother_db": 2.0, "ts_k": 400.0,
      "freq_hz": 2.25e9, "rb_bps": 1.0e6, "ebn0_req_db": 2.5}
DOWN = {"pt_w": 50.0, "gt_dbi": 30.0, "ltx_db": 1.0, "gr_dbi": 60.0, "lrx_db": 1.0, "lother_db": 3.0, "ts_k": 50.0,
        "freq_hz": 8.45e9, "rb_bps": 1.0e6, "ebn0_req_db": 2.5}
H1 = {"name": "H1 hypothetical elliptical orbit (illustrative)", "a_km": 6000.0, "e": 0.6, "i_deg": 60.0, "raan_deg": 0.0,
      "argp_deg": 90.0, "m0_deg": 0.0, "frame": "LME_EPOCH", "step_s": 60.0}
DTN = {"volume_mbit": 20000.0, "rate_kbps": 1000.0, "path": "any_rf"}


def comms(rid, start):
    body = {"result_id": rid, "direct_link": DTE, "relay": {**H1, "epoch_utc": start}, "relay_up_link": UP,
            "relay_down_link": DOWN, "dtn": DTN}
    st, raw = call("POST", "/api/comms/simulate", body)
    j = json.loads(raw)
    return {"http": st, "bytes": len(raw), "direct_stats": (j.get("direct") or {}).get("stats"),
            "relay_samples": (j.get("relay") or {}).get("samples") or (j.get("relay") or {}).get("n_samples")}


def landing(lat, lon):
    st, raw = call("POST", "/api/landing/assess", {"lat": lat, "lon": lon, "window_half_m": 1500})
    s = json.loads(raw)["summary"]
    return {"http": st, "bytes": len(raw), "pixels": s["pixels"], "slope_median": s["slope_deg"]["median"],
            "depressions": s["depressions"]["count"]}


def getter(path):
    def f():
        st, raw = call("GET", path)
        return {"http": st, "bytes": len(raw)}
    return f


LAT, LON = -88.2417, 61.3703          # not analysed before in this project's evidence (fresh horizon)
rows = [{"case": "server idle", "ws_mb": ws_mb()}]
rows.append(measured("analysis 1 day (cold: horizon computed)", lambda: analysis(LAT, LON, "2027-02-01T00:00:00Z", "2027-02-02T00:00:00Z")))
r30 = measured("analysis 30 days", lambda: analysis(LAT, LON, "2027-02-01T00:00:00Z", "2027-03-03T00:00:00Z")); rows.append(r30)
r365 = measured("analysis 365 days", lambda: analysis(LAT, LON, "2027-02-01T00:00:00Z", "2028-02-01T00:00:00Z")); rows.append(r365)
rows.append(measured("analysis 30 days again (result cache)", lambda: analysis(LAT, LON, "2027-02-01T00:00:00Z", "2027-03-03T00:00:00Z")))
rows.append(measured("landing 1.5 km half-width, new site (cold)", lambda: landing(-87.5153, 128.7720)))
rows.append(measured("landing same request again", lambda: landing(-87.5153, 128.7720)))
if r30["info"]:
    rows.append(measured("comms direct + relay H1 + DTN, 30-day result", lambda: comms(r30["info"]["result_id"], "2027-02-01T00:00:00Z")))
if r365["info"]:
    rows.append(measured("comms direct + relay H1 + DTN, 365-day result", lambda: comms(r365["info"]["result_id"], "2027-02-01T00:00:00Z")))
rows.append(measured("display tile 0/0/0", getter("/api/display/tiles/0/0/0.png")))
rows.append(measured("display tile 3/4/3", getter("/api/display/tiles/3/4/3.png")))
rows.append(measured("3D terrain (site above)", getter(f"/api/terrain?lat={LAT}&lon={LON}")))
rows.append(measured("status", getter("/api/status")))
rows.append({"case": "server end", "ws_mb": ws_mb()})
json.dump({"pid": PID, "base": BASE, "rows": rows}, open(OUT, "w"), indent=1)
