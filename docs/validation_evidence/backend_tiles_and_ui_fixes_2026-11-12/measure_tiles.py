"""Measure backend hillshade tile rendering (lunaops.api.tiles.render_tile): wall time, process CPU time and peak working
set per tile, each tile rendered in a fresh child process (so one tile's memory cannot hide another's), with a time cap.
Run from backend/ with the project venv. Read-only: renders tiles in memory and writes only into --out.

    .venv/Scripts/python.exe ../docs/validation_evidence/backend_tiles_and_ui_fixes_2026-11-12/measure_tiles.py --label before --out <dir> [--cap 300]

Windows only (CPU and memory are read from the child with GetProcessTimes / GetProcessMemoryInfo through ctypes; no
packages installed). Writes <out>/tiles-<label>.json and the PNG of every tile that finished (<out>/png-<label>/z_x_y.png).
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BACKEND = Path.cwd()

# tiles: the four that contain the 5 m Site01 product at zooms 1-4 (slow before), normal tiles at the same zooms, and
# tiles around Site01 at finer zooms (where the 5 m product is legitimately used)
SITE01_XY = (-11000.0, -12000.0)   # polar stereographic metres, inside the 5 m product (x -19..-3 km, y -20..-4 km)


def tiles_to_measure(meta) -> list[tuple[int, int, int, str]]:
    ox, oy = meta["origin"]
    out = []
    def at(z, xy):
        r = meta["resolutions"][z]
        return int((xy[0] - ox) // (256 * r)), int((oy - xy[1]) // (256 * r))
    for z in (1, 2, 3, 4):
        x, y = at(z, SITE01_XY)
        out.append((z, x, y, "contains the 5 m product"))
    for z, x, y in ((1, 1, 1), (1, 1, 0), (2, 2, 1), (2, 0, 2), (3, 2, 4), (4, 6, 8)):
        out.append((z, x, y, "normal (no 5 m product)"))
    for z in (5, 6, 8, 10, len(meta["resolutions"]) - 1):
        x, y = at(z, SITE01_XY)
        out.append((z, x, y, "contains the 5 m product (fine zoom)"))
    return out


CHILD = r'''
import sys, time
sys.path.insert(0, ".")
from lunaops.api.tiles import render_tile
z, x, y, path = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
t0 = time.perf_counter()
png = render_tile(z, x, y)
dt = time.perf_counter() - t0
open(path, "wb").write(png)
print(f"RENDER_S {dt:.3f}")
'''


class PMC(ctypes.Structure):
    _fields_ = [("cb", wt.DWORD), ("PageFaultCount", wt.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t), ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t), ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]


class PE32(ctypes.Structure):
    _fields_ = [("dwSize", wt.DWORD), ("cntUsage", wt.DWORD), ("th32ProcessID", wt.DWORD), ("th32DefaultHeapID", ctypes.c_size_t),
                ("th32ModuleID", wt.DWORD), ("cntThreads", wt.DWORD), ("th32ParentProcessID", wt.DWORD), ("pcPriClassBase", ctypes.c_long),
                ("dwFlags", wt.DWORD), ("szExeFile", ctypes.c_char * 260)]


def descendants(pid: int) -> list[int]:
    """pid and all its descendants (the venv python.exe on Windows is a launcher that starts the real interpreter)."""
    k32 = ctypes.windll.kernel32
    snap = k32.CreateToolhelp32Snapshot(0x2, 0)
    pairs = []
    e = PE32(); e.dwSize = ctypes.sizeof(PE32)
    ok = k32.Process32First(snap, ctypes.byref(e))
    while ok:
        pairs.append((e.th32ProcessID, e.th32ParentProcessID))
        ok = k32.Process32Next(snap, ctypes.byref(e))
    k32.CloseHandle(snap)
    out, frontier = [pid], [pid]
    while frontier:
        nxt = [c for c, par in pairs if par in frontier and c not in out]
        out += nxt; frontier = nxt
    return out


def sample_one(pid: int):
    k32, psapi = ctypes.windll.kernel32, ctypes.windll.psapi
    h = k32.OpenProcess(0x1000 | 0x0010, False, pid)   # QUERY_LIMITED_INFORMATION | VM_READ
    if not h:
        return None
    try:
        c, e, kt, ut = wt.FILETIME(), wt.FILETIME(), wt.FILETIME(), wt.FILETIME()
        k32.GetProcessTimes(h, ctypes.byref(c), ctypes.byref(e), ctypes.byref(kt), ctypes.byref(ut))
        ft = lambda f: ((f.dwHighDateTime << 32) | f.dwLowDateTime) / 1e7
        m = PMC(); m.cb = ctypes.sizeof(PMC)
        psapi.GetProcessMemoryInfo(h, ctypes.byref(m), m.cb)
        return {"cpu_s": ft(kt) + ft(ut), "peak_ws_mb": m.PeakWorkingSetSize / 2**20}
    finally:
        k32.CloseHandle(h)


def sample(pid: int):
    """CPU time summed over the launcher and its descendants; the largest peak working set among them (the renderer)."""
    rows = [s for s in (sample_one(p) for p in descendants(pid)) if s]
    if not rows:
        return None
    return {"cpu_s": sum(r["cpu_s"] for r in rows), "peak_ws_mb": max(r["peak_ws_mb"] for r in rows)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--cap", type=float, default=300.0, help="seconds after which a tile render is stopped")
    args = ap.parse_args()
    out = Path(args.out); png_dir = out / f"png-{args.label}"; png_dir.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(BACKEND))
    from lunaops.api.tiles import tile_meta
    from lunaops.fingerprint import code_fingerprint
    meta = tile_meta()
    rows = []
    for z, x, y, kind in tiles_to_measure(meta):
        png = png_dir / f"{z}_{x}_{y}.png"
        t0 = time.perf_counter()
        p = subprocess.Popen([sys.executable, "-c", CHILD, str(z), str(x), str(y), str(png)], cwd=BACKEND,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        last = None; stopped = False
        while p.poll() is None:
            s = sample(p.pid)
            if s: last = s
            if time.perf_counter() - t0 > args.cap:
                for d in reversed(descendants(p.pid)):   # the real interpreter too, not only the venv launcher
                    try: os.kill(d, 9)
                    except OSError: pass
                stopped = True; break
            time.sleep(0.25)
        so, se = p.communicate()
        wall = time.perf_counter() - t0
        render_s = next((float(l.split()[1]) for l in so.splitlines() if l.startswith("RENDER_S")), None)
        row = {"tile": f"{z}/{x}/{y}", "kind": kind, "res_m_per_px": meta["resolutions"][z], "completed": not stopped and p.returncode == 0,
               "stopped_at_cap_s": args.cap if stopped else None, "render_s": render_s, "wall_s_incl_process_start": round(wall, 2),
               "cpu_s_last_sample": round(last["cpu_s"], 1) if last else None, "peak_ws_mb_last_sample": round(last["peak_ws_mb"], 1) if last else None,
               "png_sha256": hashlib.sha256(png.read_bytes()).hexdigest() if png.exists() and not stopped else None,
               "stderr_tail": se.strip().splitlines()[-1:] if se.strip() else []}
        rows.append(row)
        print(json.dumps(row), flush=True)
    (out / f"tiles-{args.label}.json").write_text(json.dumps({"label": args.label, "code_fingerprint": code_fingerprint(),
        "cap_s": args.cap, "machine_cpus": os.cpu_count(), "tiles": rows}, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
