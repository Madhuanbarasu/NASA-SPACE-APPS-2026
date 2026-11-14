"""Read-only: event-timing impact of the new CIP pole vs the old frozen J2000 pole (real detector)."""
import json, os, sys, time
import numpy as np
sys.path.insert(0, sys.argv[1]); sys.path.insert(0, sys.argv[2])
os.environ.setdefault("LUNAOPS_KERNEL_SET", "production")
import spiceypy as sp
from lunaops.engine import earth as EARTH, kernels as K
K.load()
NEW = EARTH.pole_in_frame
def frozen(ets, frame):
    ets = np.atleast_1d(np.asarray(ets, dtype=float)); p = np.empty((ets.size, 3)); pd = np.empty((ets.size, 3))
    with EARTH.SPICE_LOCK:
        for i, et in enumerate(ets):
            x = np.asarray(sp.sxform("J2000", frame, float(et))); p[i], pd[i] = x[:3, 2], x[3:, 2]
    return p, pd
from earth_helpers import horizon
from lunaops.engine.ephem import Site, sample_target
from lunaops.engine.events import EventConfig, EventDetector
site = Site(-89.0, 45.0, 0.0, 0.0)
def run(fn, hp, a, b):
    EARTH.pole_in_frame = fn
    d = EventDetector(site, hp, EventConfig()); r = d.run(a, b)
    EARTH.pole_in_frame = NEW
    return [e for e in r["events"] if e["function"].startswith("earth")], sum(f["function"].startswith("earth") for f in d.log.estimate_failures)
out = {}
for start in ("2026-11-01T00:00:00", "2036-11-01T00:00:00", "2046-11-01T00:00:00"):
    a = sp.str2et(start); b = a + 30 * 86400
    tt = sample_target(site, "earth", np.linspace(a, b, 400)); az0, lv = float(np.median(tt.az)), float(np.median(tt.el))
    for hn, hp in {"flat": horizon("flat", az0, lv), "sloped0.6": horizon("sloped", az0, lv, 0.6),
                   "sloped0.8": horizon("sloped", az0, lv, 0.8), "notched": horizon("notched", az0, lv, 0.6, depth=0.8, width_deg=0.5)}.items():
        en, fn_ = run(NEW, hp, a, b); eo, fo = run(frozen, hp, a, b)
        row = {"estimate_failures_new": fn_, "estimate_failures_frozen": fo}
        for f in ("earth_c", "earth_top", "earth_bot"):
            A = [(e["et"], e["direction"]) for e in en if e["function"] == f]; B = [(e["et"], e["direction"]) for e in eo if e["function"] == f]
            same = len(A) == len(B) and all(x[1] == y[1] for x, y in zip(A, B))
            row[f] = {"n_new": len(A), "n_frozen": len(B), "same_sequence": same,
                      "max_abs_shift_s": max((abs(x[0] - y[0]) for x, y in zip(A, B)), default=0.0) if same else None}
        out[f"{start[:4]}/{hn}"] = row
        print(start[:4], hn, json.dumps(row), flush=True)
json.dump(out, open(sys.argv[3], "w"), indent=1)
