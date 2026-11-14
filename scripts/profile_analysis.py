"""Profile one analysis on the terrain and kernels registered on this machine.

    cd backend
    python ../scripts/profile_analysis.py                                    # PGDA 78 Site01, 30 days
    python ../scripts/profile_analysis.py --lat -89.9 --lon 0 --start 2026-11-14 --days 7 --top 30

Prints the wall time of the analysis (the horizon is computed once first and then taken from the cache, so
the timed run measures the event detection and series; --cold also times a run with the horizon computed),
then the functions with the largest cumulative and own time (cProfile). Use it to find hotspots on real data
before optimising (Phase 3 item 8 optimised only hotspots measured this way). The horizon cache under
data/cache is written as in normal use; nothing else is changed.
"""
from __future__ import annotations

import argparse
import cProfile
import io
import pstats
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lat", type=float, default=-89.463163)
    ap.add_argument("--lon", type=float, default=222.510447)
    ap.add_argument("--start", default="2026-11-14")
    ap.add_argument("--days", type=float, default=30.0)
    ap.add_argument("--top", type=int, default=25)
    ap.add_argument("--cold", action="store_true", help="also time a run that computes the horizon")
    a = ap.parse_args()

    from lunaops import settings
    from lunaops.engine import cache
    from lunaops.engine.analysis import AnalysisRequest, analyze

    settings.ensure_dirs()
    t0 = datetime.fromisoformat(a.start)
    req = AnalysisRequest(lat=a.lat, lon=a.lon, start_utc=t0.strftime("%Y-%m-%dT%H:%M:%SZ"),
                          end_utc=(t0 + timedelta(days=a.days)).strftime("%Y-%m-%dT%H:%M:%SZ"))
    t = time.perf_counter()
    analyze(req)                                   # compiles numba kernels and fills the horizon cache
    first = time.perf_counter() - t
    if a.cold:
        cache.clear()
        t = time.perf_counter()
        analyze(req)
        print(f"analysis with the horizon computed: {time.perf_counter() - t:.2f} s")
    t = time.perf_counter()
    analyze(req)
    print(f"first run (compilation + horizon): {first:.2f} s; analysis with a cached horizon: "
          f"{time.perf_counter() - t:.2f} s")
    pr = cProfile.Profile()
    pr.enable()
    analyze(req)
    pr.disable()
    for key in ("cumulative", "tottime"):
        s = io.StringIO()
        pstats.Stats(pr, stream=s).sort_stats(key).print_stats(a.top)
        print(f"--- sorted by {key} ---")
        print(s.getvalue())
    return 0


if __name__ == "__main__":
    sys.exit(main())
