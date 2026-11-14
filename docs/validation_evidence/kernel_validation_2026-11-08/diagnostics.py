"""Read-only A2 diagnostics on the installed production kernels (data/kernels).

Repeats the V-02e and frozen-pole computations of the test suite with per-epoch detail. Changes nothing.
Run from backend/ with the project venv:  python <this file> <backend/tests dir> <out.json>
"""
import json
import math
import os
import sys

import numpy as np

os.environ.setdefault("LUNAOPS_KERNEL_SET", "production")
sys.path.insert(0, os.getcwd())
sys.path.insert(0, sys.argv[1])

import spiceypy as sp  # noqa: E402

from lunaops import settings  # noqa: E402
from lunaops.engine import kernels as K  # noqa: E402
from lunaops.engine.timeutil import parse_utc  # noqa: E402

ks = K.load()
out = {"kernel_profile": ks.profile, "frame": ks.frame, "kernels": [f["name"] + " " + f["sha256"] for f in
                                                                    json.load(open(settings.PRODUCTION_KERNEL_DIR / "lock.json"))["files"]]}
print("profile", ks.profile, "frame", ks.frame)


# ---------------------------------------------------------------- V-02e
def resid(et):
    m = np.array(sp.pxform("MOON_ME_DE421", ks.frame, et))
    return math.acos(max(-1.0, min(1.0, (np.trace(m) - 1) / 2))) * settings.R_MOON_M


test_epochs = [(y, resid(parse_utc(f"{y}-06-01T00:00:00Z"))) for y in range(2026, 2037)]
monthly = [resid(parse_utc(f"{y}-{mo:02d}-01T00:00:00Z")) for y in range(2026, 2037) for mo in range(1, 13)]
daily = [resid(e) for e in np.arange(parse_utc("2026-01-01T00:00:00Z"), parse_utc("2037-01-01T00:00:00Z"), 86400.0)]
wide = []
for y in range(1901, 2050):
    try:
        wide.append((y, resid(parse_utc(f"{y}-06-01T00:00:00Z"))))
    except Exception as exc:  # outside a kernel's coverage
        wide.append((y, None))
out["V02e"] = {"rule": "d_max <= 1.0 m (test epochs: 1 June 2026..2036)",
               "test_epochs_m": test_epochs, "d_max_test_m": max(v for _, v in test_epochs),
               "monthly_2026_2036_max_m": max(monthly), "monthly_2026_2036_min_m": min(monthly),
               "daily_2026_2036_max_m": max(daily), "daily_2026_2036_n": len(daily),
               "yearly_1901_2049_max_m": max(v for _, v in wide if v is not None),
               "yearly_1901_2049": wide}
print("V-02e test-epoch d_max %.4f m; monthly max %.4f; daily max %.4f (n=%d); 1901-2049 yearly max %.4f" % (
    out["V02e"]["d_max_test_m"], max(monthly), max(daily), len(daily), out["V02e"]["yearly_1901_2049_max_m"]))

# ---------------------------------------------------------------- frozen pole
from earth_helpers import horizon  # noqa: E402
from lunaops.engine.earth import earth_disk_state, limb_ellipse, limb_extrema, pole_area_bound  # noqa: E402
from lunaops.engine.ephem import Site, earth_geo, sample_target  # noqa: E402

sv = settings.EARTH_SOLVER
t0, t1 = sp.str2et("2000-01-01T12:00:00"), sp.str2et("2049-12-01T00:00:00")
ets = np.linspace(t0, t1, 200)
site = Site(-89.0, 45.0, 0.0, 0.0)
t = sample_target(site, "earth", ets)
e, n, u = t.earth["basis"]
hz = {"sloped_0.8 (test)": horizon("sloped", float(np.median(t.az)), float(np.median(t.el)), 0.8),
      "flat": horizon("flat", float(np.median(t.az)), float(np.median(t.el)))}
rows = []
for i, et in enumerate(ets):
    p_j = t.earth["pole"][i]
    p_i = np.asarray(sp.pxform("IAU_EARTH", ks.frame, float(et)))[:, 2]
    eps = math.acos(min(1.0, float(p_j @ p_i)))
    r = t.unit[i] * t.dist_km[i]
    Q0, QA, QB = (x[0] for x in limb_ellipse(r[None], p_i[None]))
    ru, rd, dm, _ = limb_extrema(Q0, QA, QB, u, e, n, math.radians(t.el[i]), math.radians(t.az[i]),
                                 sv["bracket"], sv["tol"], sv["maxiter"])
    g1 = earth_geo(t, i)
    g2 = {**g1, "Q0": Q0, "QA": QA, "QB": QB, "rho_up": ru, "rho_down": rd, "delta_max": dm}
    eta = (g1["alpha"] - g1["beta"]) * math.sin(eps)
    row = {"utc": sp.et2utc(float(et), "ISOC", 0), "eps_arcsec": math.degrees(eps) * 3600, "eta_deg": math.degrees(eta),
           "el_deg": float(t.el[i]), "P1_deg": math.degrees(max(abs(g1["rho_up"] - ru), abs(g1["rho_down"] - rd)))}
    for name, hp in hz.items():
        s1, s2 = earth_disk_state(hp, g1, force="ellipse"), earth_disk_state(hp, g2, force="ellipse")
        lim2 = eta * (1 + max(s1["slope_span"], s2["slope_span"]) / min(s1["c_min"], s2["c_min"]))
        p2 = max(abs(s1[f] - s2[f]) for f in ("g_top", "g_bot"))
        row[name] = {"P2_deg": p2, "P2_bound_deg": math.degrees(lim2), "slope_span": s1["slope_span"],
                     "c_min": s1["c_min"], "c_equal": s1["c"] == s2["c"],
                     "P3": None if (math.isnan(s1["f"]) or math.isnan(s2["f"])) else abs(s1["f"] - s2["f"]),
                     "P3_bound": pole_area_bound(g1["alpha"], g1["beta"], eta)}
    rows.append(row)


def worst(key, sub=None):
    vals = [(r[sub][key] if sub else r[key]) for r in rows]
    vals = [v for v in vals if v is not None]
    return max(vals)


summ = {"epochs": len(rows), "span": [rows[0]["utc"], rows[-1]["utc"]], "site": [-89.0, 45.0],
        "eps_arcsec_min": min(r["eps_arcsec"] for r in rows), "eps_arcsec_max": worst("eps_arcsec"),
        "P1_max_deg": worst("P1_deg")}
for name in hz:
    summ[name] = {"P2_max_deg": worst("P2_deg", name),
                  "P2_bound_max_deg": worst("P2_bound_deg", name),
                  "P2_max_ratio_to_bound": max(r[name]["P2_deg"] / r[name]["P2_bound_deg"] for r in rows if r[name]["P2_bound_deg"] > 0),
                  "P2_epochs_over_1e-5_deg": sum(r[name]["P2_deg"] >= 1e-5 for r in rows),
                  "P3_max": worst("P3", name), "c_equal_all": all(r[name]["c_equal"] for r in rows),
                  "all_P2_within_bound": all(r[name]["P2_deg"] <= r[name]["P2_bound_deg"] * (1 + 1e-9) for r in rows),
                  "all_P3_within_bound": all(r[name]["P3"] is None or r[name]["P3"] <= r[name]["P3_bound"] + 1e-9
                                             for r in rows)}
i_w = max(range(len(rows)), key=lambda k: rows[k]["sloped_0.8 (test)"]["P2_deg"])
summ["worst_P2_epoch"] = rows[i_w]
out["frozen_pole"] = {"summary": summ, "rows": rows}
print(json.dumps(summ, indent=1))
json.dump(out, open(sys.argv[2], "w"), indent=1)
