"""Generate tests/reference/erfa_cip_2000_2049.json with ERFA (the open-source SOFA implementation).

    python -m pip install pyerfa==2.0.1.5          # in a separate environment; not a LUNA-OPS dependency
    python generate_erfa_cip.py erfa_cip_2000_2049.json

For 601 TT epochs evenly spaced from 2000-01-01T12:00 TT (J2000.0) to 2049-12-31T12:00 TT, plus the SOFA test
date MJD 53736, it records ERFA's IAU 2000B nutation (eraNut00b) and the third rows of the IAU 2006
bias-precession matrix (rbp) and bias-precession-nutation matrix (rbpn) from eraPn06: the mean pole and the
Celestial Intermediate Pole of date in the GCRS. LUNA-OPS's own implementation (engine.earth_orientation) is
compared with these values in tests/test_phase4_earth_pole.py. The file is reference data: regenerate it only
to change the ERFA version, never to make a test pass.
"""
import json
import sys

import erfa
import numpy as np

DJ00 = 2451545.0
days = list(np.linspace(0.0, 18262.0, 601)) + [2400000.5 + 53736.0 - DJ00]
rows = []
for d in days:
    dpsi, deps = erfa.nut00b(DJ00, d)
    epsa, rb, rp, rbp, rn, rbpn = erfa.pn06(DJ00, d, dpsi, deps)
    rows.append({"tt_days_since_j2000": float(d), "dpsi": float(dpsi), "deps": float(deps),
                 "mean_pole": [float(x) for x in rbp[2]], "cip": [float(x) for x in rbpn[2]]})
meta = {"generator": "tests/reference/generate_erfa_cip.py", "pyerfa": erfa.__version__,
        "liberfa": erfa.version.erfa_version, "sofa_release": erfa.version.sofa_version,
        "functions": "eraNut00b, eraPn06 (row 3 of rbp and rbpn)", "time_scale": "TT",
        "epochs": len(rows)}
json.dump({"meta": meta, "rows": rows}, open(sys.argv[1], "w"), indent=0)
print(meta)
