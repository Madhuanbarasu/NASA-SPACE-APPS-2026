import sys, math, numpy as np
import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ".")
from disk_exact import exact
from lunaops.engine.visibility import HorizonProfile, disk_state
rng = np.random.default_rng(3)
azn = np.arange(3600)*0.1
def horizon(kind):
    if kind == "level":
        return lambda el: HorizonProfile(np.full(3600, el - 0.1), np.zeros(3600, bool))
    if kind == "steep":   # 10 deg/deg slopes: side contacts
        return lambda el: HorizonProfile(el + 2.0*np.sin(np.radians(azn*60)), np.zeros(3600, bool))
    if kind == "rough":
        base = 0.8*np.sin(np.radians(azn*7)) + 0.3*np.sin(np.radians(azn*23)) + 0.15*rng.standard_normal(3600)
        return lambda el: HorizonProfile(el + base, np.zeros(3600, bool))
worst = {}
for name, rho in (("sun", 0.2667), ("earth", 0.95)):
    for el in (1.0, 7.0, 20.0, 37.0, 59.9):
        for kind in ("level", "steep", "rough"):
            mk = horizon(kind)
            hp = mk(el)
            ef, eg = 0.0, 0.0
            for az in np.linspace(10, 350, 25):
                st = disk_state(hp, float(az), el, rho)
                f, gt, gb = exact(hp, float(az), el, rho)
                ef = max(ef, abs(st["f"]-f))
                # edge-clearance accuracy matters near zero: compare when |g| small, plus overall
                eg = max(eg, abs(st["g_top"]-gt), abs(st["g_bot"]-gb))
            worst[(name, el, kind)] = (ef, eg)
            print(f"{name:5s} el={el:5.1f} {kind:5s}  max|df|={ef:.2e}  max|dg|={eg:.2e} deg")

# timing (after numba compile)
import time
from lunaops.engine.visibility import disk_edges_many
hp = horizon("rough")(5.0)
az = np.linspace(0, 360, 20000, endpoint=False); el = np.full(az.size, 5.0)
for rho in (0.2667, 0.95):
    disk_edges_many(hp, az[:10], el[:10], np.full(10, rho))
    t = time.time(); disk_edges_many(hp, az, el, np.full(az.size, rho)); dt = time.time() - t
    print(f"rho={rho}: {1e6*dt/az.size:.1f} us per disk")
