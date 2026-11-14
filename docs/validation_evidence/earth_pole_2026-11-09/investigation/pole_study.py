"""Read-only study of the Earth pole model (frozen J2000 Z vs IAU_EARTH vs precession+nutation reference).

Nothing in the repository is changed: alternative poles are injected by replacing
lunaops.engine.earth.pole_in_frame inside this process only.
Run from backend/:  python -I pole_study.py <backend dir> <tests dir> <out.json>
"""
import json
import math
import sys
import time

import numpy as np

sys.path.insert(0, sys.argv[1])
sys.path.insert(0, sys.argv[2])
import os  # noqa: E402
os.environ.setdefault("LUNAOPS_KERNEL_SET", "production")

import spiceypy as sp  # noqa: E402

from lunaops import settings  # noqa: E402
from lunaops.engine import earth as EARTH  # noqa: E402
from lunaops.engine import kernels as K  # noqa: E402

ks = K.load()
FRAME = ks.frame
AS = math.pi / (180 * 3600)
FROZEN = EARTH.pole_in_frame


# ---------------------------------------------------------------- independent reference pole (J2000 coordinates)
def ref_pole_j2000(et, nutation=True):
    """Mean pole of date from IAU 2006 precession (IERS Conventions 2010 eq. 5.40: zeta_A, theta_A), plus the
    dominant nutation terms (Meeus, Astronomical Algorithms ch. 22: about 0.5" in dpsi, 0.1" in deps)."""
    t = et / (86400.0 * 36525.0)                       # TDB Julian centuries from J2000 (et is TDB s past J2000)
    zeta = (2.650545 + 2306.083227 * t + 0.2988499 * t ** 2 + 0.01801828 * t ** 3) * AS
    theta = (2004.191903 * t - 0.4294934 * t ** 2 - 0.04182264 * t ** 3) * AS
    zA = (-2.650545 + 2306.077181 * t + 1.0927348 * t ** 2 + 0.01826837 * t ** 3) * AS

    def R1(a):
        c, s = math.cos(a), math.sin(a)
        return np.array([[1, 0, 0], [0, c, s], [0, -s, c]])

    def R2(a):
        c, s = math.cos(a), math.sin(a)
        return np.array([[c, 0, -s], [0, 1, 0], [s, 0, c]])

    def R3(a):
        c, s = math.cos(a), math.sin(a)
        return np.array([[c, s, 0], [-s, c, 0], [0, 0, 1]])
    P = R3(-zA) @ R2(theta) @ R3(-zeta)                # J2000 -> mean equator/equinox of date
    z = np.array([0.0, 0.0, 1.0])
    if nutation:
        T = t
        Om = math.radians(125.04452 - 1934.136261 * T)
        L = math.radians(280.4665 + 36000.7698 * T)
        Lp = math.radians(218.3165 + 481267.8813 * T)
        dpsi = (-17.20 * math.sin(Om) - 1.32 * math.sin(2 * L) - 0.23 * math.sin(2 * Lp) + 0.21 * math.sin(2 * Om)) * AS
        deps = (9.20 * math.cos(Om) + 0.57 * math.cos(2 * L) + 0.10 * math.cos(2 * Lp) - 0.09 * math.cos(2 * Om)) * AS
        epsA = (84381.406 - 46.836769 * t) * AS
        N = R1(-(epsA + deps)) @ R3(-dpsi) @ R1(epsA)  # mean of date -> true of date
        return P.T @ N.T @ z
    return P.T @ z


def make_pole_fn(kind):
    def fn(ets, frame):
        ets = np.atleast_1d(np.asarray(ets, dtype=float))
        p = np.empty((ets.size, 3))
        pd = np.empty((ets.size, 3))
        with EARTH.SPICE_LOCK:
            for i, et in enumerate(ets):
                if kind == "iau":
                    x = np.asarray(sp.sxform("IAU_EARTH", frame, float(et)))
                    p[i], pd[i] = x[:3, 2], x[3:, 2]
                else:
                    x = np.asarray(sp.sxform("J2000", frame, float(et)))
                    z = ref_pole_j2000(float(et), nutation=(kind == "ref"))
                    p[i], pd[i] = x[:3, :3] @ z, x[3:, :3] @ z
        return p, pd
    return fn


POLES = {"frozen": FROZEN, "iau": make_pole_fn("iau"), "ref": make_pole_fn("ref"), "ref_mean": make_pole_fn("ref_mean")}


def use(kind):
    EARTH.pole_in_frame = POLES[kind]


out = {"frame": FRAME, "kernel_profile": ks.profile}

# ---------------------------------------------------------------- 1. pole angles between models
PART3_ONLY = os.environ.get("PART3_ONLY") == "1"
ets = np.linspace(sp.str2et("2000-01-01T12:00:00"), sp.str2et("2049-12-01T00:00:00"), 3 if PART3_ONLY else 600)
ang = {"frozen-iau": [], "frozen-ref": [], "iau-ref": [], "iau-ref_mean": [], "ref-ref_mean": []}
for et in ets:
    v = {k: POLES[k]([et], FRAME)[0][0] for k in POLES}
    for key in ang:
        a, b = key.split("-")
        ang[key].append(math.degrees(math.acos(min(1.0, float(v[a] @ v[b])))) * 3600)
yrs = 2000 + (ets - ets[0]) / (365.25 * 86400)
out["pole_angles_arcsec"] = {k: {"max": max(v), "at_2026": float(np.interp(2026.9, yrs, v)),
                                 "at_2036": float(np.interp(2036.9, yrs, v)), "at_2049": v[-1]}
                             for k, v in ang.items()}
print("pole angles (arcsec):", json.dumps(out["pole_angles_arcsec"], indent=1))

# ---------------------------------------------------------------- 2. P1/P2/P3 per model vs the reference pole
from earth_helpers import horizon  # noqa: E402
from lunaops.engine.earth import earth_disk_state  # noqa: E402
from lunaops.engine.ephem import Site, earth_geo, sample_target  # noqa: E402

site = Site(-89.0, 45.0, 0.0, 0.0)
ets200 = np.linspace(sp.str2et("2000-01-01T12:00:00"), sp.str2et("2049-12-01T00:00:00"), 200)
samples = {}
for k in ("frozen", "iau", "ref"):
    use(k)
    samples[k] = sample_target(site, "earth", ets200)
use("frozen")
t0 = samples["frozen"]
hps = {"flat": horizon("flat", float(np.median(t0.az)), float(np.median(t0.el))),
       "sloped0.8": horizon("sloped", float(np.median(t0.az)), float(np.median(t0.el)), 0.8)}
cmp = {}
for model in (() if PART3_ONLY else ("frozen", "iau")):
    for hn, hp in hps.items():
        P1 = P2 = P3 = 0.0
        p2_by_year = {}
        for i in range(ets200.size):
            g1, g2 = earth_geo(samples[model], i), earth_geo(samples["ref"], i)
            P1 = max(P1, abs(g1["rho_up"] - g2["rho_up"]), abs(g1["rho_down"] - g2["rho_down"]))
            s1, s2 = earth_disk_state(hp, g1, force="ellipse"), earth_disk_state(hp, g2, force="ellipse")
            d2 = max(abs(s1["g_top"] - s2["g_top"]), abs(s1["g_bot"] - s2["g_bot"]))
            P2 = max(P2, d2)
            y = int(sp.et2utc(float(ets200[i]), "ISOC", 0)[:4])
            p2_by_year[y // 10 * 10] = max(p2_by_year.get(y // 10 * 10, 0.0), d2)
            if not (math.isnan(s1["f"]) or math.isnan(s2["f"])):
                P3 = max(P3, abs(s1["f"] - s2["f"]))
        cmp[f"{model}_vs_ref/{hn}"] = {"P1_deg": math.degrees(P1), "P2_deg": P2, "P3": P3, "P2_by_decade_deg": p2_by_year}
out["model_vs_reference_2000_2049"] = cmp
print("model vs reference pole:", json.dumps(cmp, indent=1))

# ---------------------------------------------------------------- 3. event timing with the real detector
from lunaops.engine.events import EventConfig, EventDetector  # noqa: E402


def run_events(kind, hp, et0, et1):
    use(kind)
    det = EventDetector(site, hp, EventConfig())
    r = det.run(et0, et1)
    fails = [f for f in det.log.estimate_failures if f["function"].startswith("earth")]
    use("frozen")
    return [e for e in r["events"] if e["function"] in ("earth_c", "earth_top", "earth_bot")], len(fails)


timing = {}
for start in ("2026-11-01T00:00:00", "2036-11-01T00:00:00", "2046-11-01T00:00:00"):
    et0 = sp.str2et(start)
    et1 = et0 + 30 * 86400
    use("frozen")
    tt = sample_target(site, "earth", np.linspace(et0, et1, 400))
    az0, lvl = float(np.median(tt.az)), float(np.median(tt.el))
    for hn, hp in {"flat": horizon("flat", az0, lvl), "sloped0.6": horizon("sloped", az0, lvl, 0.6),
                   "sloped0.8": horizon("sloped", az0, lvl, 0.8),
                   "notched": horizon("notched", az0, lvl, 0.6, depth=0.8, width_deg=0.5)}.items():
        t_start = time.time()
        ev = {}
        fl = {}
        for k in ("ref", "frozen", "iau"):
            ev[k], fl[k] = run_events(k, hp, et0, et1)
        res = {"estimate_failures": fl}
        for k in ("frozen", "iau"):
            for fn in ("earth_c", "earth_top", "earth_bot"):
                a = [(e["et"], e["direction"]) for e in ev[k] if e["function"] == fn]
                b = [(e["et"], e["direction"]) for e in ev["ref"] if e["function"] == fn]
                used, dts, unmatched = set(), [], 0
                for ta, da in a:
                    cand = [(abs(ta - tb), j) for j, (tb, db) in enumerate(b) if db == da and j not in used]
                    if cand and min(cand)[0] < 1800:
                        d, j = min(cand)
                        used.add(j)
                        dts.append(ta - b[j][0])
                    else:
                        unmatched += 1
                res[f"{k}/{fn}"] = {"n": len(a), "n_ref": len(b), "unmatched": unmatched + (len(b) - len(used)),
                                    "max_abs_dt_s": max((abs(x) for x in dts), default=0.0),
                                    "median_abs_dt_s": float(np.median(np.abs(dts))) if dts else 0.0,
                                    "n_over_1s": int(sum(abs(x) > 1.0 for x in dts))}
        timing[f"{start[:4]}/{hn}"] = res
        print(start[:4], hn, f"{time.time() - t_start:.0f}s", json.dumps(
            {k: (v if k == "estimate_failures" else (v["n"], v["unmatched"], round(v["max_abs_dt_s"], 3),
                                                       v["n_over_1s"])) for k, v in res.items()}))
out["event_timing_vs_reference_30d"] = timing
json.dump(out, open(sys.argv[3], "w"), indent=1, default=float)
