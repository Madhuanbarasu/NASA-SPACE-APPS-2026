"""Geometric event detection: the engine's adaptive detector (EventDetector.run + build_intervals, as in analyze())
against an independent brute-force scan, on synthetic horizons built to produce the cases V-14 does not score.

Reference: the edge function of the rule (Sun "any": top-edge clearance; Sun "centre": centre clearance; Earth "centre":
centre clearance; Earth "any": top-edge clearance) evaluated every DT seconds over the whole interval, vectorised
(ephem.sample_target + visibility.disk_edges_many for the Sun; earth_disk_state per sample for Earth); a crossing is
placed by linear interpolation between samples. The geometry inputs are the engine's (validated separately: V-01..V-08);
what is independent is the event finding (fixed fine scan vs the adaptive, bound-driven stepping and bisection).
Read only. Usage: python events_independent.py <out json>
"""
import json, math, sys, time
sys.path.insert(0, r"E:\LUNA-OPS\backend")
import numpy as np

from lunaops.engine.earth import earth_disk_state
from lunaops.engine.ephem import Site, earth_geo, sample_target
from lunaops.engine.events import EventConfig, EventDetector, build_intervals, summarize
from lunaops.engine.timeutil import parse_utc
from lunaops.engine.visibility import HorizonProfile, disk_edges_many

NB, BIN = 3600, 0.1
DT = 0.5
SITE = Site(-89.463163, 222.510447, 0.0, 0.0)          # Site01 position; ground 0 m (synthetic horizons)
T0 = parse_utc("2026-11-20T00:00:00Z")


def sun_series(ets, hp):
    s = sample_target(SITE, "sun", ets)
    e = disk_edges_many(hp, s.az, s.el, s.rho)
    return {"top": e["g_top"], "centre": s.el - hp.at(s.az), "az": s.az, "el": s.el, "rho": s.rho}


def earth_series(ets, hp):
    t = sample_target(SITE, "earth", ets)
    top = np.empty(ets.size); cen = np.empty(ets.size)
    for i in range(ets.size):
        st = earth_disk_state(hp, earth_geo(t, i), want_f=False)
        top[i], cen[i] = st["g_top"], st["c"]
    return {"top": top, "centre": cen, "az": t.az, "el": t.el}


def ref_windows(ets, g):
    """Windows where g > 0 (linear-interpolated crossings), clipped to the interval."""
    pos = g > 0
    wins, start = [], (ets[0] if pos[0] else None)
    for i in range(1, ets.size):
        if pos[i] != pos[i - 1]:
            tc = ets[i - 1] + (ets[i] - ets[i - 1]) * g[i - 1] / (g[i - 1] - g[i])
            if pos[i]:
                start = tc
            else:
                wins.append((start, tc)); start = None
    if start is not None:
        wins.append((start, ets[-1]))
    return wins


def detector_windows(hp, et0, et1, key, inc_any=False):
    det = EventDetector(SITE, hp, EventConfig(sunlit_rule="any", dte_rule="centre"))
    t = time.time()
    run = det.run(et0, et1)
    iv = build_intervals(det, et0, et1, run["events"], run["samples"])
    return iv[key], {"samples": det.log.samples if hasattr(det.log, "samples") else None, "s": round(time.time() - t, 1),
                     "summary": summarize(iv[key], et0, et1)}


def compare(ref, det_iv, et0, et1):
    on = [(iv["start_et"], iv["end_et"]) for iv in det_iv if iv["state"] is True]
    unknown = [(iv["start_et"], iv["end_et"]) for iv in det_iv if iv["state"] is None]
    pairs, missed, spurious = [], [], []
    used = set()
    for a, b in ref:
        j = min(range(len(on)), key=lambda k: abs(on[k][0] - a) + abs(on[k][1] - b), default=None)
        if j is None or j in used or abs(on[j][0] - a) > 60 or abs(on[j][1] - b) > 60:
            missed.append((a - et0, b - et0, b - a)); continue
        used.add(j)
        sa = 0.0 if a == et0 else on[j][0] - a          # an edge at the interval bound is exact by construction
        sb = 0.0 if b == et1 else on[j][1] - b
        pairs.append({"ref_start_s": a - et0, "ref_end_s": b - et0, "ref_duration_s": b - a,
                      "start_err_s": sa, "end_err_s": sb, "duration_err_s": (on[j][1] - on[j][0]) - (b - a),
                      "starts_at_analysis_start": a == et0, "ends_at_analysis_end": b == et1})
    for k, (a, b) in enumerate(on):
        if k not in used:
            spurious.append((a - et0, b - et0, b - a))
    return {"matched": pairs, "missed": missed, "spurious": spurious,
            "unknown_intervals": [(a - et0, b - et0) for a, b in unknown]}


# ---------------------------------------------------------------- set-up: where the Sun and Earth are
probe = np.arange(0.0, 6 * 3600.0 + 1, 600.0) + T0
flat = HorizonProfile(np.full(NB, -10.0), np.zeros(NB, bool))
sp = sun_series(probe, flat)
print(f"Sun from the site over 6 h: az {sp['az'][0]:.2f} -> {sp['az'][-1]:.2f} deg, el {sp['el'].min():.3f}..{sp['el'].max():.3f} deg, "
      f"rho {sp['rho'][0]:.4f}")
AZ_RATE = (sp["az"][-1] - sp["az"][0]) / (probe[-1] - probe[0])


def sun_top_at(t):
    s = sun_series(np.array([t]), flat)
    return float(s["el"][0] + s["rho"][0])


cases = []


def notch_horizon(base, notches):
    """Flat horizon `base` (deg) with V-shaped one-node notches: list of (node azimuth, depth)."""
    h = np.full(NB, base)
    for az, depth in notches:
        h[int(round(az / BIN)) % NB] = base - depth
    return h


# 1-5: short and grazing windows. The base horizon follows the Sun's top-edge path 0.5 mdeg above it (so the top edge
# never clears it), with one V-shaped one-node notch; the notch depth sets how long the top edge peeks through.
dense = np.arange(T0, T0 + 6 * 3600.0 + 1, 10.0)
dsun = sun_series(dense, flat)
order = np.argsort(dsun["az"])
EPS = 0.0005


def tracking_base(eps=EPS):
    h = np.full(NB, 30.0)
    az_lo, az_hi = dsun["az"].min(), dsun["az"].max()
    for i in range(NB):
        a = i * BIN
        if az_lo - 1.0 <= a <= az_hi + 1.0:
            h[i] = np.interp(a, dsun["az"][order], (dsun["el"] + dsun["rho"])[order]) + eps
    return h


tn = T0 + 2 * 3600.0
az_n = float(sun_series(np.array([tn]), flat)["az"][0])
node = int(round(az_n / BIN)) % NB
for extra in (2e-7, 1e-6, 5e-6, 3e-5, 2e-4):
    h = tracking_base(); h[node] -= EPS + extra
    cases.append((f"short window: notch clears the top-edge path by {extra*1e3:.4f} mdeg", "sun_any",
                  HorizonProfile(h, np.zeros(NB, bool)), T0 + 3600.0, T0 + 3 * 3600.0))
base = float(np.max(dsun["el"] + dsun["rho"])) + EPS
# 6: several windows (five notches along the Sun's path, varied depths)
azs = [float(sun_series(np.array([T0 + k * 2400.0]), flat)["az"][0]) for k in range(1, 6)]
cases.append(("several windows: five notches", "sun_any",
              HorizonProfile(notch_horizon(base, list(zip(azs, (0.002, 0.01, 0.0009, 0.05, 0.004)))), np.zeros(NB, bool)),
              T0, T0 + 4 * 3600.0))
# 7: window open at the analysis start, 8: window open at the analysis end (low horizon over the first/second half)
half_az = float(sun_series(np.array([T0 + 1800.0]), flat)["az"][0])
h = np.full(NB, base)
for i in range(NB):
    if ((i * BIN - half_az + 540) % 360) - 180 < 0:   # azimuths the Sun occupies before T0+30 min
        h[i] = base - 0.3
cases.append(("window open at the analysis start (ends inside)", "sun_any", HorizonProfile(h, np.zeros(NB, bool)), T0, T0 + 3600.0))
h2 = np.full(NB, base - 0.3)
for i in range(NB):
    if ((i * BIN - half_az + 540) % 360) - 180 < 0:
        h2[i] = base
cases.append(("window open at the analysis end (starts inside)", "sun_any", HorizonProfile(h2, np.zeros(NB, bool)), T0, T0 + 3600.0))
# 9-10: no visibility / always visible
cases.append(("no visibility (horizon 2 deg above the Sun)", "sun_any", HorizonProfile(np.full(NB, base + 2.0), np.zeros(NB, bool)), T0, T0 + 3 * 3600.0))
cases.append(("always visible (horizon 2 deg below the Sun)", "sun_any", HorizonProfile(np.full(NB, base - 2.5), np.zeros(NB, bool)), T0, T0 + 3 * 3600.0))
# 11: missing terrain across part of the Sun's path (lower-bound bins): unknown there, never counted as visible
inc = np.zeros(NB, bool)
for i in range(NB):
    if 0 <= ((i * BIN - azs[1] + 540) % 360) - 180 < 0.6:
        inc[i] = True
cases.append(("missing terrain over part of the path (low horizon, incomplete bins)", "sun_any",
              HorizonProfile(np.full(NB, base - 0.3), inc), T0, T0 + 4 * 3600.0))
# 12: uncertain terrain - horizon sigma 0.01 deg, Sun's top edge clears it by only ~0.002 deg in a notch
sig = np.full(NB, 0.01)
cases.append(("uncertain terrain: window inside the horizon uncertainty (sigma 0.01 deg)", "sun_any",
              HorizonProfile(notch_horizon(base, [(az_n, 0.004)]), np.zeros(NB, bool), sig), T0 + 3600.0, T0 + 3 * 3600.0))
# 13: Sun centre rule over the same five notches (different edge function)
cases.append(("Sun centre rule: horizon through the centre path with notches", "sun_centre",
              HorizonProfile(notch_horizon(base - float(np.mean(sp['rho'])), list(zip(azs, (0.002, 0.01, 0.0009, 0.05, 0.004)))), np.zeros(NB, bool)),
              T0, T0 + 4 * 3600.0))

out = []
for name, key, hp, et0, et1 in cases:
    ets = np.arange(et0, et1 + 1e-9, DT)
    s = sun_series(ets, hp) if key.startswith("sun") else earth_series(ets, hp)
    g = s["top"] if key.endswith("any") else s["centre"]
    # where the verdict rests on incomplete bins the reference cannot decide: report those samples
    ref = ref_windows(ets, g)
    det_iv, info = detector_windows(hp, et0, et1, key)
    cmp_ = compare(ref, det_iv, et0, et1)
    if hp.inc.any():                                   # visible over lower-bound bins must be unknown (engine rule)
        from lunaops.engine.visibility import half_width_az
        touch = np.array([bool(hp.inc[hp.span_nodes(float(s['az'][i]) - half_width_az(float(s['el'][i]), float(s['rho'][i])),
                                                      float(s['az'][i]) + half_width_az(float(s['el'][i]), float(s['rho'][i]))) % hp.n].any())
                          for i in range(ets.size)])
        must = touch & (g > 0)
        det_unk = np.zeros(ets.size, bool); det_vis = np.zeros(ets.size, bool)
        for iv in det_iv:
            m = (ets >= iv['start_et']) & (ets < iv['end_et'])
            if iv['state'] is None: det_unk |= m
            elif iv['state'] is True: det_vis |= m
        cmp_['expected_unknown_s'] = float(must.sum() * DT)
        cmp_['detector_unknown_s'] = float(det_unk.sum() * DT)
        cmp_['expected_unknown_but_reported_visible_s'] = float((must & det_vis).sum() * DT)
    flags = [{k: iv.get(k) for k in ("state", "duration_s", "brief", "uncertain", "uncertain_reasons")} for iv in det_iv]
    rec = {"case": name, "rule": key, "interval_s": et1 - et0, "reference_windows": len(ref), **cmp_, "detector": info,
           "detector_intervals": flags}
    out.append(rec)
    errs = [abs(p["start_err_s"]) for p in cmp_["matched"]] + [abs(p["end_err_s"]) for p in cmp_["matched"]]
    durs = [round(p["ref_duration_s"], 1) for p in cmp_["matched"]]
    print(f"{name[:78]:78s} | ref windows {len(ref)} (durations s {durs}) | matched {len(cmp_['matched'])} missed {len(cmp_['missed'])} "
          f"spurious {len(cmp_['spurious'])} unknown {len(cmp_['unknown_intervals'])} | max edge err {max(errs, default=0):.3f} s | "
          f"uncertain flags {[f['uncertain'] for f in flags if f['state']]} | {info['s']} s"
          + (f" | expected unknown {cmp_['expected_unknown_s']:.0f} s, detector unknown {cmp_['detector_unknown_s']:.0f} s, "
             f"reported visible instead {cmp_['expected_unknown_but_reported_visible_s']:.0f} s" if 'expected_unknown_s' in cmp_ else ''), flush=True)
json.dump({"site": "Site01 position, synthetic horizons", "dt_s": DT, "cases": out}, open(sys.argv[1], "w"), indent=1, default=float)
