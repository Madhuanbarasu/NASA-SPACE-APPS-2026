import sys, math, numpy as np
import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ".")
from disk_exact import cap_column
from lunaops.engine.visibility import HorizonProfile, disk_state
rng = np.random.default_rng(3); azn = np.arange(3600)*0.1
base = 0.8*np.sin(np.radians(azn*7)) + 0.3*np.sin(np.radians(azn*23)) + 0.15*rng.standard_normal(3600)
worst = 0
for el in (7.0, 37.0, 59.9):
    hp = HorizonProfile(el + base, np.zeros(3600, bool))
    for az in np.linspace(10, 350, 25):
        rho = 0.95
        hw = math.degrees(math.asin(math.sin(math.radians(rho))/math.cos(math.radians(el))))
        grid = az + np.linspace(-hw, hw, 400001)
        nodes = np.arange(math.ceil((az-hw)/0.1), math.floor((az+hw)/0.1)+1)*0.1
        azs = np.sort(np.concatenate([grid, nodes]))
        lo, hi = cap_column(az, el, rho, azs); m = np.isfinite(lo)
        H = hp.at(azs[m]); gt = np.max(hi[m]-H); gb = np.min(lo[m]-H)
        st = disk_state(hp, float(az), el, rho)
        worst = max(worst, abs(st["g_top"]-gt), abs(st["g_bot"]-gb))
print(f"Earth disk, rough horizon, reference incl. node points: max |dg| = {worst:.2e} deg")
