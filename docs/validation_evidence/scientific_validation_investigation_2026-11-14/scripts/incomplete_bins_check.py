"""Real cached results whose horizon has incomplete bins (terrain coverage ran out): how much time does each result
report as visible (True) or hidden (False) although the disk's verdict rests on incomplete (lower-bound) bins and must
be "unknown" under the engine's own documented rule ("a hidden verdict resting on them stays valid, anything visible
becomes unknown")?

Per minute over each result's window: Sun / Earth position from the engine's ephemeris, the disk's azimuth span from
its angular radius, the incomplete bins it spans, and the top-edge clearance against the stored horizon (a lower bound
there). Expected state: unknown if the span touches an incomplete bin and the top edge clears it (g_top > 0); otherwise
the stored interval state is not questioned. Read only (cache files are opened read only).
Usage: python incomplete_bins_check.py <out json>
"""
import json, os, sqlite3, sys
sys.path.insert(0, r"E:\LUNA-OPS\backend")
import numpy as np

from lunaops.engine.ephem import Site, sample_target
from lunaops.engine.visibility import HorizonProfile, disk_edges_many, half_width_az

CACHE = r"E:\LUNA-OPS\data\cache"
con = sqlite3.connect(f"file:{CACHE}/cache.sqlite?mode=ro", uri=True)
inc_keys = set()
for k, p in con.execute("select key, path from horizons"):
    z = np.load(os.path.join(CACHE, os.path.basename(p)))
    if z["inc"].any():
        inc_keys.add(k)
out = []
for rid, p in con.execute("select id, path from results"):
    fp = os.path.join(CACHE, os.path.basename(p))
    if not os.path.exists(fp):
        continue
    r = json.load(open(fp))
    hz = r["horizon"]
    if hz["key"] not in inc_keys:
        continue
    h = np.asarray(hz["h_deg"], float); inc = np.asarray(hz["incomplete"], bool)
    hp = HorizonProfile(h, inc)
    site = Site(r["site"]["lat"], r["site"]["lon"], r["site"]["ground_h_m"], hz["obs_h_m"])
    et0, et1 = r["window"]["start_et"], r["window"]["end_et"]
    ets = np.arange(et0 + 30.0, et1, 60.0)
    rec = {"result": rid, "lat": r["site"]["lat"], "lon": r["site"]["lon"], "incomplete_share": hz["incomplete_share"],
           "window": [r["window"]["start_utc"], r["window"]["end_utc"]]}
    for tgt in ("sun", "earth"):
        t = sample_target(site, tgt, ets)
        rho = t.rho if tgt == "sun" else np.degrees(np.arcsin(6378.1366 / t.dist_km))   # outer (equatorial) radius
        g_top = disk_edges_many(hp, t.az, t.el, rho)["g_top"]
        touch = np.zeros(ets.size, bool)
        for i in range(ets.size):
            hw = half_width_az(float(t.el[i]), float(rho[i]))
            idx = hp.span_nodes(float(t.az[i]) - hw, float(t.az[i]) + hw)
            touch[i] = bool(inc[idx % hp.n].any())
        must_unknown = touch & (g_top > 0)
        ivs = r["intervals"][f"{tgt}_any"]
        st = np.full(ets.size, -1)        # 1 True, 0 False, 2 unknown
        for iv in ivs:
            m = (ets >= iv["start_et"]) & (ets < iv["end_et"])
            st[m] = 2 if iv["state"] is None else int(bool(iv["state"]))
        rec[tgt] = {"minutes": int(ets.size), "minutes_over_incomplete_and_clear": int(must_unknown.sum()),
                    "reported_unknown_there": int(np.sum(must_unknown & (st == 2))),
                    "reported_visible_there": int(np.sum(must_unknown & (st == 1))),
                    "reported_hidden_there": int(np.sum(must_unknown & (st == 0))),
                    "reported_unknown_total_min": int(np.sum(st == 2)),
                    "summary_unknown_hours": r["summary"][f"{tgt}_any"].get("unknown_hours")}
    out.append(rec)
    print(json.dumps(rec))
json.dump(out, open(sys.argv[1], "w"), indent=1)
print(f"{len(out)} cached results use a horizon with incomplete bins")
