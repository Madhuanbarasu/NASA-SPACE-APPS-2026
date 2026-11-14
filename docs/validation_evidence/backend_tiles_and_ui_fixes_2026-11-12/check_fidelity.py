"""Which renderer represents the terrain better? For tile pixels where the previous and the current tiles.py differ,
compare each with the true mean height of the finest registered product over that pixel's footprint (read at full
resolution, no resampling). Run from backend/ with the venv. Read-only; writes tiles/fidelity.json."""
import json
import sys
import types
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import from_bounds

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(Path.cwd()))
import lunaops.api.tiles as new  # noqa: E402
from lunaops.engine.dem import resolve_dem_path, usable_levels  # noqa: E402

src = (HERE / "tiles" / "tiles_py_before.py.txt").read_text(encoding="utf-8").replace("from ..engine.dem", "from lunaops.engine.dem")
old = types.ModuleType("tiles_before"); exec(compile(src, "tiles_before", "exec"), old.__dict__)


def heights(mod, z, x, y):
    cap = {}; real = np.gradient
    def grab(a, *args, **kw):
        cap["arr"] = a.copy(); return real(a, *args, **kw)
    mod.np.gradient = grab
    try:
        mod.render_tile(z, x, y)
    finally:
        mod.np.gradient = real
    return cap["arr"]


meta = new.tile_meta()
levels = usable_levels()
rng = np.random.default_rng(1)
out = []
for t, n in [("1/1/0", 40), ("1/1/1", 30), ("2/1/2", 30), ("4/7/8", 30), ("6/31/32", 40)]:
    z, x, y = map(int, t.split("/"))
    a, b = heights(old, z, x, y), heights(new, z, x, y)
    res = meta["resolutions"][z]; x0 = meta["origin"][0] + x * 256 * res; y1 = meta["origin"][1] - y * 256 * res
    rr, cc = np.nonzero(np.abs(a - b) > 1.0)
    pick = rng.choice(len(rr), size=min(n, len(rr)), replace=False) if len(rr) else []
    errs_old, errs_new, used = [], [], {}
    for i in pick:
        r, c = int(rr[i]), int(cc[i])
        bx0, bx1, by1 = x0 + c * res, x0 + (c + 1) * res, y1 - r * res; by0 = by1 - res
        # finest product whose footprint contains the whole pixel footprint
        truth = None
        for lv in levels:   # finest first
            A, _, lc, _, e, f = lv["transform"]
            if bx0 >= lc and bx1 <= lc + A * lv["width"] and by0 >= f + e * lv["height"] and by1 <= f:
                with rasterio.open(resolve_dem_path(lv["path"])) as ds:
                    v = ds.read(1, window=from_bounds(bx0, by0, bx1, by1, ds.transform)).astype(np.float64)
                v = v[np.isfinite(v)]
                if v.size:
                    truth = float(v.mean()); used[lv["level"]] = used.get(lv["level"], 0) + 1
                break
        if truth is None:
            continue
        errs_old.append(abs(float(a[r, c]) - truth)); errs_new.append(abs(float(b[r, c]) - truth))
    row = {"tile": t, "res_m": res, "pixels_checked": len(errs_old), "truth_from_levels": used,
           "old_mean_abs_err_m": round(float(np.mean(errs_old)), 2) if errs_old else None,
           "new_mean_abs_err_m": round(float(np.mean(errs_new)), 2) if errs_new else None,
           "old_max_abs_err_m": round(float(np.max(errs_old)), 2) if errs_old else None,
           "new_max_abs_err_m": round(float(np.max(errs_new)), 2) if errs_new else None,
           "new_closer_count": int(sum(1 for o, nn in zip(errs_old, errs_new) if nn < o))}
    out.append(row); print(row, flush=True)
(HERE / "tiles" / "fidelity.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
