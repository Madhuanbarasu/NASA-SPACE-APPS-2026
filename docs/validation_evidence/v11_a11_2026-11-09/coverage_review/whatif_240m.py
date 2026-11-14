"""A11 what-if: would PGDA 90 LDEM_60S_240MPP_ADJ.TIF, as the engine's 240 m level, close the incomplete horizons?

    LUNAOPS_WINDOW_MODE=full LUNAOPS_DEM_FALLBACK_DIRS=<80 m folder> \
        python -I whatif_240m.py <horizon_coverage_200.json> <LDEM_60S_240MPP_ADJ.TIF> <sha256> <out.json> [all]

Nothing is registered: the 240 m window is read by the engine's reference loader (dem._read_window) from an
in-memory record and appended to the registered pyramid for each point, with the 240 m nominal half-width from
settings (600 km). Reference window mode keeps every window a separate array. For each point that was incomplete
with the registered terrain alone (or every point, with "all"), the horizon is recomputed (a) as registered, to reproduce the baseline, and
(b) with the 240 m window added; only completeness is recorded (no sunlight is computed).
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "backend"))
from lunaops import settings  # noqa: E402
from lunaops.engine import dem  # noqa: E402
from lunaops.engine.horizon import compute_horizon  # noqa: E402

assert settings.WINDOW_MODE == "full", "run with LUNAOPS_WINDOW_MODE=full"
rows = [r for r in json.load(open(sys.argv[1])) if r["incomplete_bins"] > 0 or sys.argv[5:] == ["all"]]
lv240 = {"level": "240m", "path": str(Path(sys.argv[2]).resolve()), "pixel_m": 240.0, "width": 7760, "height": 7760,
         "transform": [240.0, 0.0, -931200.0, 0.0, -240.0, 931200.0], "nodata": None, "synthetic": False,
         "product": "PGDA 90 LDEM_60S_240MPP_ADJ.TIF (what-if, not registered)", "sha256": sys.argv[3]}
out = []
for r in rows:
    base = compute_horizon(r["lat"], r["lon"], 0.0)
    pyr = dem.load_pyramid(r["lat"], r["lon"])
    cx, cy = dem.south_polar_stereo_xy(dem.unit_from_latlon(math.radians(r["lat"]), math.radians(r["lon"])),
                                       settings.R_MOON_M)
    w = dem._read_window(lv240, cx, cy, settings.DEM_WINDOW_HALF_M["240m"])
    w.band_m = max(w.band_m, pyr[-1].band_m)
    hz = compute_horizon(r["lat"], r["lon"], 0.0, pyramid=pyr + [w])
    rec = {"lat": r["lat"], "lon": r["lon"], "incomplete_registered": int(np.sum(base.incomplete)),
           "incomplete_registered_adaptive_run": r["incomplete_bins"],
           "incomplete_with_240m": int(np.sum(hz.incomplete)), "h_max_m_with_240m": hz.params["h_max_m"],
           "max_stop_step_with_240m": hz.params["stopping_diagnostics"]["max_stop_step"],
           "levels_with_240m": [lv.get("level") for lv in hz.levels]}
    out.append(rec)
    print(json.dumps(rec), flush=True)
json.dump(out, open(sys.argv[4], "w"), indent=1)
