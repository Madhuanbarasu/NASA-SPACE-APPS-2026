"""Compare the height grids (before hillshading) of the previous and the current tiles.py for the same tiles: where do
the rendered tiles differ, and by how much in metres. The previous renderer is loaded from tiles/tiles_py_before.py.txt
(a copy of lunaops/api/tiles.py before the change). Run from backend/ with the venv. Read-only; writes tiles/heights.json."""
import json
import math
import sys
import types
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(Path.cwd()))
import lunaops.api.tiles as new  # noqa: E402
from lunaops.engine.dem import usable_levels  # noqa: E402

src = (HERE / "tiles" / "tiles_py_before.py.txt").read_text(encoding="utf-8").replace("from ..engine.dem", "from lunaops.engine.dem")
old = types.ModuleType("tiles_before"); exec(compile(src, "tiles_before", "exec"), old.__dict__)


def heights(mod, z, x, y):
    """Run the module's render_tile with the hillshade replaced by a capture of the height grid."""
    cap = {}
    real = np.gradient
    def grab(a, *args, **kw):
        cap["arr"] = a.copy(); return real(a, *args, **kw)
    mod.np.gradient = grab
    try:
        mod.render_tile(z, x, y)
    finally:
        mod.np.gradient = real
    return cap.get("arr")


meta = new.tile_meta()
levels = usable_levels()
rows = []
for t in ["1/1/0", "1/1/1", "2/2/1", "2/1/2", "3/3/4", "4/7/8", "5/15/16", "6/31/32"]:
    z, x, y = map(int, t.split("/"))
    a, b = heights(old, z, x, y), heights(new, z, x, y)
    # np.nan_to_num(arr, nan=mean) is what reaches np.gradient; compare those grids
    d = np.abs(a - b)
    res = meta["resolutions"][z]; x0 = meta["origin"][0] + x * 256 * res; y1 = meta["origin"][1] - y * 256 * res
    # distance (in tile pixels) of each differing pixel from the nearest product boundary inside this tile
    edges = []
    for lv in levels:
        A, _, c, _, e, f = lv["transform"]
        for bx in (c, c + A * lv["width"]):
            edges.append(("x", (bx - x0) / res))
        for by in (f + e * lv["height"], f):
            edges.append(("y", (y1 - by) / res))
    rr, cc = np.nonzero(d > 1e-3)
    def near(r, cl):
        return min(abs(cl + 0.5 - v) if k == "x" else abs(r + 0.5 - v) for k, v in edges)
    dist = [near(r, cl) for r, cl in zip(rr, cc)]
    row = {"tile": t, "res_m": res, "pixels_differing_gt_1mm": int(len(rr)), "max_height_diff_m": round(float(d.max()), 3),
           "p99_height_diff_m": round(float(np.percentile(d[d > 1e-3], 99)), 3) if len(rr) else 0.0,
           "within_2px_of_a_product_edge": int(sum(1 for v in dist if v <= 2)), "farther_than_2px": int(sum(1 for v in dist if v > 2))}
    rows.append(row); print(row)
(HERE / "tiles" / "heights.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
