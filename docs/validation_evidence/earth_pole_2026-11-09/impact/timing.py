import os, sys, time
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
a = sp.str2et("2026-11-14T00:00:00"); b = a + 30 * 86400
tt = sample_target(site, "earth", np.linspace(a, b, 400))
hp = horizon("sloped", float(np.median(tt.az)), float(np.median(tt.el)), 0.6)
res = {"frozen": [], "CIP": []}
for rep in range(3):
    for name, fn in (("frozen", frozen), ("CIP", NEW)):
        EARTH.pole_in_frame = fn
        t = time.perf_counter(); r = EventDetector(site, hp, EventConfig()).run(a, b); res[name].append(time.perf_counter() - t)
        nsamp = len(r.get("samples", []))
EARTH.pole_in_frame = NEW
print({k: [round(x, 2) for x in v] for k, v in res.items()}, "median ratio CIP/frozen %.3f" % (np.median(res["CIP"]) / np.median(res["frozen"])))
