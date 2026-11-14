"""Earth-disk (and Sun-disk) visibility: the engine against an independent ray-cast.

Independent reference (no engine geometry): a gnomonic grid of view directions around the target's centre; a direction
belongs to Earth if its ray meets the oblate spheroid (a, a, b) of the IERS 2010 radii (quadratic intersection), to the
Sun if it lies within the Sun's angular radius. For each such direction: el - H(az), with H the horizon as specified
to both (piecewise linear in azimuth, nodes every 0.1 deg). Area weights are the gnomonic solid-angle Jacobian.
  f      = visible solid-angle fraction;  g_top / g_bot = largest / smallest clearance on the disk;  c = centre clearance.
Engine under test: lunaops.engine.earth.earth_disk_state (Earth: exact limb ellipse) and visibility.disk_state (Sun).
The engine's geometry inputs (limb ellipse, upper/lower limb extents) come from its own functions, as in production.
Partial cases are evaluated on two grids (1601 and 3201 per side) to show convergence; grazing cases add a zoomed grid
at the top edge, whose position is itself found independently (zoomed ray-cast for Earth; el + rho for the Sun).
Read only. Usage: python disk_independent.py <out json>
"""
import json, math, sys
sys.path.insert(0, r"E:\LUNA-OPS\backend")
import numpy as np

from lunaops import settings
from lunaops.engine.earth import earth_disk_state, intrinsic_radii, limb_ellipse, limb_extrema
from lunaops.engine.visibility import HorizonProfile, disk_state, rule_state

A_KM, _, B_KM = settings.EARTH_RADII_KM
E_ = np.array([1.0, 0, 0]); N_ = np.array([0, 1.0, 0]); U_ = np.array([0, 0, 1.0])   # observer ENU = frame axes
NB = 3600
BIN = 360.0 / NB
AZ0 = 123.456
RHO_SUN = math.asin(settings.R_SUN_KM / 1.496e8)


def unit_azel(az, el):
    a, e = math.radians(az), math.radians(el)
    return np.array([math.cos(e) * math.sin(a), math.cos(e) * math.cos(a), math.sin(e)])


def H_at(h, az):                                        # the horizon definition both sides use
    f = (np.asarray(az) % 360.0) / BIN
    i0 = np.floor(f).astype(int) % NB
    t = f - np.floor(f)
    return h[i0] * (1 - t) + h[(i0 + 1) % NB] * t


def raycast(target, c_dir, half_rad, h, inc, n=1601, d_km=None, pole=None, rho_sun=None, offset=(0.0, 0.0)):
    """n x n gnomonic grid of half-width tan(half_rad) about c_dir, shifted by offset (tangent units; +2nd = up)."""
    t1 = np.cross(c_dir, U_); t1 /= np.linalg.norm(t1); t2 = np.cross(t1, c_dir)    # t1 horizontal, t2 toward zenith
    s = math.tan(half_rad)
    p = np.linspace(-s, s, n) + offset[0]
    qv = np.linspace(-s, s, n) + offset[1]
    if target == "earth":
        z = pole / np.linalg.norm(pole)
        x = np.cross(z, [1.0, 0, 0] if abs(z[0]) < 0.9 else [0, 1.0, 0]); x /= np.linalg.norm(x); y = np.cross(z, x)
        w0 = -d_km * c_dir                                                   # Earth centre -> observer
        S0 = np.array([w0 @ x / A_KM, w0 @ y / A_KM, w0 @ z / B_KM])
    sw = swv = 0.0; gt, gb = -1e9, 1e9; touches_inc = False; nhit = 0
    for r0 in range(0, n, 200):
        P, Q = np.meshgrid(p, qv[r0:r0 + 200])
        D = c_dir[None, None, :] + P[..., None] * t1 + Q[..., None] * t2
        w = 1.0 / (1.0 + P * P + Q * Q) ** 1.5
        D /= np.linalg.norm(D, axis=2)[..., None]
        if target == "earth":
            Sd = np.stack([D @ x / A_KM, D @ y / A_KM, D @ z / B_KM], axis=-1)
            bq = Sd @ S0; aq = np.sum(Sd * Sd, axis=-1); cq = S0 @ S0 - 1.0
            hit = (bq * bq - aq * cq >= 0) & (bq < 0)
        else:
            hit = D @ c_dir >= math.cos(rho_sun)
        if not hit.any():
            continue
        el = np.degrees(np.arcsin(np.clip(D[..., 2], -1, 1)))
        az = np.degrees(np.arctan2(D[..., 0], D[..., 1])) % 360.0
        clear = el - H_at(h, az)
        ii = (np.floor(az / BIN).astype(int)) % NB
        touches_inc |= bool(np.any(hit & (inc[ii] | inc[(ii + 1) % NB])))
        sw += float(np.sum(w[hit])); swv += float(np.sum(w[hit] * (clear[hit] > 0)))
        gt = max(gt, float(clear[hit].max())); gb = min(gb, float(clear[hit].min())); nhit += int(hit.sum())
    return {"f": swv / sw if sw else float("nan"), "g_top": gt, "g_bot": gb, "touches_incomplete": touches_inc,
            "grid_step_deg": math.degrees(2 * s / (n - 1)), "hits": nhit}


def earth_geo(az, el, d_km, pole):
    r = d_km * unit_azel(az, el)
    Q0, QA, QB = (v[0] for v in limb_ellipse(r[None, :], pole[None, :]))
    ru, rd, dm, _f = limb_extrema(Q0, QA, QB, U_, E_, N_, math.radians(el), math.radians(az), 64, 1e-12, 200)
    al, be = (float(x) for x in intrinsic_radii(np.array(d_km)))
    return {"az": az, "el": el, "Q0": Q0, "QA": QA, "QB": QB, "rho_up": ru, "rho_down": rd, "delta_max": dm,
            "alpha": al, "beta": be, "e": E_, "n": N_, "u": U_}


def top_zoom(target, c_dir, h, inc, d_km=None, pole=None):
    """Zoomed ray-cast (window 2 % of the radius wide) centred on the top edge: resolves slivers and the top clearance."""
    rad = math.asin(A_KM / d_km) if target == "earth" else RHO_SUN
    return raycast(target, c_dir, rad * 0.02, h, inc, n=1201, d_km=d_km, pole=pole, rho_sun=RHO_SUN,
                   offset=(0.0, math.tan(rad) * 0.995))


POLE = np.array((0.3, -0.2, 0.93))
LOW = np.full(NB, -89.0)
TOP = {"earth": 8.0 + top_zoom("earth", unit_azel(AZ0, 8.0), LOW, np.zeros(NB, bool), 384400.0, POLE)["g_top"] - 97.0,
       "sun": 8.0 + math.degrees(RHO_SUN)}
print("independent top-edge elevations (deg):", {k: round(v, 6) for k, v in TOP.items()})

rng = np.random.default_rng(20261114)
grid_az = np.arange(NB) * BIN
cases = []


def add(name, target, el0, hfun, inc_fun=None, d_km=384400.0, pole=POLE, expect=None):
    h = np.array([hfun(a) for a in grid_az], dtype=float)
    inc = np.zeros(NB, bool) if inc_fun is None else np.array([inc_fun(a) for a in grid_az])
    cases.append((name, target, el0, h, inc, d_km, np.array(pole, float), expect))


def rel(a):
    return ((a - AZ0 + 180.0) % 360.0) - 180.0


for tgt in ("earth", "sun"):
    rr = 0.95 if tgt == "earth" else 0.266
    add(f"{tgt}: fully visible (horizon 3 deg below the centre)", tgt, 8.0, lambda a: 5.0, expect="f=1")
    add(f"{tgt}: fully blocked (horizon 3 deg above the centre)", tgt, 8.0, lambda a: 11.0, expect="f=0")
    add(f"{tgt}: half (flat horizon through the centre)", tgt, 8.0, lambda a: 8.0, expect="f~0.5")
    add(f"{tgt}: partial, upper part visible (horizon half a radius above the centre)", tgt, 8.0,
        lambda a, r=rr: 8.0 + 0.5 * r, expect="0<f<0.5")
    add(f"{tgt}: crater wall (steep horizon, 0.8 deg per deg of azimuth, through the centre)", tgt, 8.0,
        lambda a: 8.0 + 0.8 * rel(a), expect="0<f<1")
    rough = rng.normal(0.0, 0.6, NB)
    add(f"{tgt}: jagged horizon (random nodes, sigma 0.6 deg, around the centre)", tgt, 8.0,
        lambda a, r=rough: 8.0 + r[int(round(a / BIN)) % NB], expect="0<f<1")
    add(f"{tgt}: below the local horizontal but above a lower terrain horizon (peak site)", tgt, -0.3,
        lambda a: -2.5, expect="f=1 (no clipping at 0 deg)")
    add(f"{tgt}: below the local horizontal and below the terrain horizon", tgt, -3.0, lambda a: -1.0, expect="f=0")
    add(f"{tgt}: grazing, sliver visible (horizon 0.002 deg below the top edge)", tgt, 8.0,
        lambda a, t=tgt: TOP[t] - 0.002, expect="any=True, f tiny, g_top ~ +0.002")
    add(f"{tgt}: grazing, just hidden (horizon 0.002 deg above the top edge)", tgt, 8.0,
        lambda a, t=tgt: TOP[t] + 0.002, expect="any=False, g_top ~ -0.002")
add("earth: missing terrain over the disk, horizon (lower bound) through the centre", "earth", 8.0, lambda a: 8.0,
    inc_fun=lambda a: abs(rel(a)) < 3.0, expect="unknown (the visible part rests on incomplete bins)")
add("earth: missing terrain over the disk, lower bound already above the disk", "earth", 8.0, lambda a: 11.0,
    inc_fun=lambda a: abs(rel(a)) < 3.0, expect="hidden stands (a lower bound already blocks)")
add("earth: perigee distance 356,500 km, partial", "earth", 8.0, lambda a: 8.3, d_km=356500.0, expect="0<f<1")
add("earth: apogee 406,700 km, pole along the line of sight, partial", "earth", 8.0, lambda a: 7.6,
    d_km=406700.0, pole=tuple(unit_azel(AZ0, 8.0)), expect="0<f<1")

out, worst = [], {"df": 0.0, "dg": 0.0}
for name, tgt, el0, h, inc, d_km, pole, expect in cases:
    hp = HorizonProfile(h, inc)
    c_dir = unit_azel(AZ0, el0)
    if tgt == "earth":
        geo = earth_geo(AZ0, el0, d_km, pole)
        eng = earth_disk_state(hp, geo, want_f=True)
        half = geo["alpha"] * 1.03
    else:
        eng = disk_state(hp, AZ0, el0, math.degrees(RHO_SUN))
        half = RHO_SUN * 1.03
    kw = dict(d_km=d_km, pole=pole, rho_sun=RHO_SUN)
    ref = raycast(tgt, c_dir, half, h, inc, n=1601, **kw)
    if any(k in name for k in ("partial", "half", "wall", "jagged")):
        fine = raycast(tgt, c_dir, half, h, inc, n=3201, **kw)
        ref = {**fine, "f_coarse_grid": ref["f"], "coarse_step_deg": ref["grid_step_deg"]}
    if "grazing" in name:
        z = top_zoom(tgt, c_dir, h, inc, d_km if tgt == "earth" else None, pole)
        ref["g_top"] = max(ref["g_top"], z["g_top"]); ref["zoom_step_deg"] = z["grid_step_deg"]
        ref["any_zoom"] = z["g_top"] > 0
    c_ref = el0 - float(H_at(h, AZ0))
    rec = {"case": name, "target": tgt, "expect": expect,
           "engine": {k: eng.get(k) for k in ("f", "c", "g_top", "g_bot", "unknown", "method")},
           "independent": {**ref, "c": c_ref},
           "rules_engine": {r: rule_state(eng, r) for r in ("any", "centre", "full")}}
    if not eng.get("unknown"):
        df = abs(eng["f"] - ref["f"]); dgt = abs(eng["g_top"] - ref["g_top"]); dgb = abs(eng["g_bot"] - ref["g_bot"])
        rec["abs_diff"] = {"f": df, "g_top_deg": dgt, "g_bot_deg": dgb, "c_deg": abs(eng["c"] - c_ref)}
        rec["rules_independent"] = {"any": ref["g_top"] > 0, "centre": c_ref >= 0, "full": ref["g_bot"] >= 0}
        rec["rules_agree"] = all(rec["rules_engine"][r] == rec["rules_independent"][r] for r in ("any", "centre", "full"))
        worst["df"] = max(worst["df"], df); worst["dg"] = max(worst["dg"], dgt, dgb)
    out.append(rec)
    e = rec["engine"]; a = rec.get("abs_diff", {})
    fs = "nan" if e["f"] != e["f"] else f"{e['f']:.6g}"
    print(f"{name[:84]:84s} | engine f={fs} g_top={e['g_top']:+.5f} unk={e['unknown']} | indep f={ref['f']:.6g} g_top={ref['g_top']:+.5f}"
          f" | |df|={a.get('f', float('nan')):.1e} |dg|={max(a.get('g_top_deg', 0), a.get('g_bot_deg', 0)):.1e} | rules agree={rec.get('rules_agree')}")
print(f"\nworst |f| difference {worst['df']:.2e}; worst edge-clearance difference {worst['dg']:.2e} deg; "
      f"grid steps: 1601 -> {out[0]['independent']['grid_step_deg']:.1e} deg, 3201 -> about half that, zoom -> about 1e-5 deg")
json.dump({"cases": out, "worst": worst, "top_edges_deg": TOP}, open(sys.argv[1], "w"), indent=1, default=float)
