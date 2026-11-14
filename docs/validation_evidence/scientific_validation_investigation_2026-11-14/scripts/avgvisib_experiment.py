"""V-09 / V-10 controlled experiment: why does the computed average visibility differ from LOLA AVGVISIB?

Same points, same 18.6-year hourly Sun/Earth geometry and the same "any part of the disc" scoring as the existing run
(backend/validation/v09_v10_avgvisib.py: track, evaluate_point); only the horizon input changes:
  A  engine horizon, observer 0 m                 (reproduces the stored per-point value of the 2026-11-12 run)
  B  engine horizon, observer 2 m                 (sensitivity to the undocumented observer height)
  C  same engine horizon algorithm on terrain whose near field (finest products, out to the 20 m window, 40 km) is
     replaced by the 20 m LOLA product averaged to 60 m pixels (the pixel size of AVGVISIB's source DEM,
     LDEM_85S_060M); 80 m and 240 m far field unchanged; observer 0 m
Read only: no registry, dataset, cache or engine file is written (LUNAOPS_WINDOW_MODE=full only changes how windows
are loaded in this process; output-invariant per tests/test_phase3_windows.py).
Usage: python avgvisib_experiment.py <per-point json> <out json> [--limit N]
"""
import json, os, sys, time
from pathlib import Path

os.environ["LUNAOPS_WINDOW_MODE"] = "full"
sys.path.insert(0, r"E:\LUNA-OPS\backend")
import numpy as np  # noqa: E402

from lunaops.engine.dem import LevelWindow, load_pyramid  # noqa: E402
from lunaops.engine.horizon import compute_horizon  # noqa: E402
from validation.v09_v10_avgvisib import evaluate_point, track  # noqa: E402

src, dst = Path(sys.argv[1]), Path(sys.argv[2])
R = json.loads(src.read_text())
LIMIT = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None


def pick(test, n_worst, n_ctrl):
    pts = [p for p in R["results"][test]["points"] if p["outcome"] == "scored"]
    d = np.array([(p["computed"] - p["reference"]) * 100 for p in pts])
    worst = list(np.argsort(-np.abs(d))[:n_worst])
    ctrl = []
    for s in (4, 3, 2, 1, 0):                      # controls: best-agreeing point per stratum, brightest strata first
        cand = [i for i, p in enumerate(pts) if p["stratum"] == s and i not in worst and abs(d[i]) < 2.0]
        if cand:
            ctrl.append(min(cand, key=lambda i: abs(d[i])))
        if len(ctrl) == n_ctrl:
            break
    return [(pts[i], "worst") for i in worst] + [(pts[i], "control") for i in ctrl]


def pyramid_60m(lat, lon):
    """The engine's pyramid with the 5 m / 20 m windows replaced by the 20 m window averaged to 60 m pixels."""
    pyr = load_pyramid(lat, lon)
    w20 = next(w for w in pyr if w.level == "20m")
    a = w20.data
    nr, nc = (a.shape[0] // 3) * 3, (a.shape[1] // 3) * 3
    avg = a[:nr, :nc].reshape(nr // 3, 3, nc // 3, 3).mean(axis=(1, 3)).astype(np.float32)   # NaN if any input NaN
    w60 = LevelWindow(level="60m", data=avg, x0=w20.x0 + w20.dx, y0=w20.y0 + w20.dy, dx=3 * w20.dx, dy=3 * w20.dy,
                      band_m=w20.band_m, pixel_m=60.0, meta={"key": "60m:block-average of the 20 m LOLA product"})
    return [w60] + [w for w in pyr if w.level not in ("5m", "10m", "20m")]


variants = {
    "A_engine_0m": lambda lat, lon, h: compute_horizon(lat, lon, 0.0),
    "B_engine_2m": lambda lat, lon, h: compute_horizon(lat, lon, 2.0),
    "C_60m_near_field_0m": lambda lat, lon, h: compute_horizon(lat, lon, 0.0, pyramid=pyramid_60m(lat, lon)),
}
obs_h = {"A_engine_0m": 0.0, "B_engine_2m": 2.0, "C_60m_near_field_0m": 0.0}
t0 = time.time()
trk = track(R["assumptions"]["start_utc"], R["assumptions"]["years"])
print(f"track: {trk['ets'].size} hours in {time.time() - t0:.0f} s", flush=True)
out = {"source": src.name, "engine": R["meta"]["code_fingerprint"], "assumptions": R["assumptions"], "points": []}
for test, target, nw, nc in (("V-09", "sun", 10, 5), ("V-10", "earth", 6, 4)):
    sel = pick(test, nw, nc)[:LIMIT] if LIMIT else pick(test, nw, nc)
    for p, role in sel:
        rec = {"test": test, "role": role, "lat": p["lat"], "lon": p["lon"], "stratum": p["stratum"],
               "reference": p["reference"], "reference_3x3": [p["reference_3x3_min"], p["reference_3x3_max"]],
               "stored_computed": p["computed"]}
        for name, fn in variants.items():
            t = time.time()
            r = evaluate_point(p["lat"], p["lon"], target, trk, obs_h[name], horizon_fn=fn)
            rec[name] = {k: r.get(k) for k in ("outcome", "computed", "ground_h_m", "exact_hours", "exact_unknown", "reason")}
            rec[name]["s"] = round(time.time() - t, 1)
        out["points"].append(rec)
        print(json.dumps({k: (round(v * 100, 2) if k in ("reference", "stored_computed") else v) for k, v in rec.items()
                          if k in ("test", "role", "lat", "lon", "reference", "stored_computed")}),
              {n: (None if rec[n]["computed"] is None else round(rec[n]["computed"] * 100, 2)) for n in variants}, flush=True)
        dst.write_text(json.dumps(out, indent=1))
print(f"done in {time.time() - t0:.0f} s")
