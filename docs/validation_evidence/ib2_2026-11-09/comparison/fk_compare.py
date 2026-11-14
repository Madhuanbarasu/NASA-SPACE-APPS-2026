"""Read-only: compare lunar frame kernels numerically (no project code, no project files written)."""
import math, sys
import numpy as np
import spiceypy as sp
K = sys.argv[1]; S = sys.argv[2]
base = [f"{K}/naif0012.tls", f"{K}/pck00011.tpc", f"{K}/de440s.bsp", f"{K}/moon_pa_de440_200625.bpc"]
sets = {"A: 250416 (pinned)": base + [f"{K}/moon_de440_250416.tf"],
        "B: 220930 (pck readme)": base + [f"{K}/moon_de440_220930.tf".replace(K, S)],
        "C: production load order (250416, then DE421 PCK + 080317)": base + [f"{K}/moon_de440_250416.tf", f"{K}/moon_pa_de421_1900-2050.bpc", f"{K}/moon_080317.tf"],
        "D: 220930 + DE421 PCK + 080317": base + [f"{S}/moon_de440_220930.tf", f"{K}/moon_pa_de421_1900-2050.bpc", f"{K}/moon_080317.tf"]}
sp.furnsh(base[0])
ets = np.linspace(sp.str2et("1900-01-01"), sp.str2et("2050-01-01"), 2001)
sp.kclear()
R_M = 1737.4e3
res, azel = {}, {}
site = None
for name, files in sets.items():
    sp.kclear()
    for f in files: sp.furnsh(f)
    info = {}
    for fr in ("MOON_ME_DE440_ME421", "MOON_PA_DE440", "MOON_ME", "MOON_PA", "MOON_ME_DE421"):
        c = sp.namfrm(fr)
        rel = None
        if c:
            try: rel = sp.gcpool(f"TKFRAME_{c}_RELATIVE", 0, 1)[0]
            except Exception: rel = None
        info[fr] = (c, rel)
    res[name] = np.array([sp.pxform("J2000", "MOON_ME_DE440_ME421", float(e)) for e in ets])
    # alias MOON_ME vs the pinned frame, as a surface displacement
    a = [math.acos(max(-1, min(1, (np.trace(sp.pxform("MOON_ME", "MOON_ME_DE440_ME421", float(e))) - 1) / 2))) * R_M for e in ets[::50]]
    # topocentric Sun and Earth vectors at a south-polar site, as the engine computes them
    pos = np.array(sp.latrec(1737.4, math.radians(222.510447), math.radians(-89.463163)))
    v = []
    for e in ets[::20]:
        for tgt in ("SUN", "EARTH"):
            st, _ = sp.spkcpo(tgt, float(e), "MOON_ME_DE440_ME421", "OBSERVER", "CN+S", pos, "MOON", "MOON_ME_DE440_ME421")
            v.append(np.array(st[:3]) / np.linalg.norm(st[:3]))
    azel[name] = np.array(v)
    print(f"{name}\n   frame IDs/relatives: {info}\n   alias MOON_ME vs MOON_ME_DE440_ME421 at the surface: max {max(a):.3f} m")
ref = "A: 250416 (pinned)"
for name in sets:
    if name == ref: continue
    d = np.max(np.abs(res[name] - res[ref])); dv = np.max(np.linalg.norm(azel[name] - azel[ref], axis=1))
    print(f"{name} vs A: max |delta R(J2000->MOON_ME_DE440_ME421)| = {d:.3e}; max Sun/Earth direction difference = {dv:.3e} rad")
print("epochs:", len(ets), "from 1900 to 2050")
