"""AUD-06 tile-level verification: the engine's renderer (lunaops.api.tiles) against lunaops_tiles, offline, read only.

For each test tile: line score (the addendum's measure, on the grey channel), transparency agreement, brightness, render
time (median of 3), and an enlarged before/after image pair. Groups:
  A zoomed-out tiles drawn from the 20 m product (zoom 5-7);  B full-detail tiles (zoom 9-12, 5 m Site01 and 20 m only);
  C tiles where only the 240 m product exists (60-80 deg S, outside the 20 m product), reduced and enlarged;
  D tiles crossing product edges (5 m Site01, 20 m product) and the map's outer edge;  E the composed zoomed-out tiles
  (zoom 1-4).
Usage: python tile_verification.py <out folder>
"""
import io, json, math, statistics, sys, time
from pathlib import Path

sys.path.insert(0, r"E:\LUNA-OPS\backend")
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402
from pyproj import Transformer  # noqa: E402

from lunaops.api import tiles as engine  # noqa: E402
from lunaops_tiles import render as new  # noqa: E402

OUT = Path(sys.argv[1]); (OUT / "images" / "tiles").mkdir(parents=True, exist_ok=True)
meta = engine.tile_meta()
RES = meta["resolutions"]
T = Transformer.from_proj("+proj=longlat +R=1737400 +no_defs", engine.STEREO_PROJ4, always_xy=True)


def score(img):   # identical to the addendum's level_probe.py / ovr_probe.py score()
    hp = img - (np.roll(img, 1, 0) + np.roll(img, -1, 0) + np.roll(img, 1, 1) + np.roll(img, -1, 1)) / 4
    hp = hp[2:-2, 2:-2]; n = hp.std() + 1e-12
    return (round(float(np.abs(hp.mean(axis=0)).mean() / n * math.sqrt(hp.shape[0])), 2),
            round(float(np.abs(hp.mean(axis=1)).mean() / n * math.sqrt(hp.shape[1])), 2))


def tile_of_xy(X, Y, z):
    s = 256 * RES[z]
    return z, int((X - meta["origin"][0]) // s), int((meta["origin"][1] - Y) // s)


def tile_of(lat, lon, z):
    X, Y = T.transform(lon if lon <= 180 else lon - 360, lat)
    return tile_of_xy(X, Y, z)


def timed(fn, zxy, n=3):
    ts, png = [], None
    for _ in range(n):
        t = time.perf_counter(); png = fn(*zxy); ts.append(time.perf_counter() - t)
    return png, statistics.median(ts)


def rgba(png):
    return np.asarray(Image.open(io.BytesIO(png)).convert("RGBA"))


SITE = (-89.463163, 222.510447)
groups = {
    "A zoomed-out 20 m": [tile_of(*SITE, z) for z in (5, 6, 7)] + [tile_of(-85.0, 30.0, z) for z in (5, 6, 7)],
    "B full detail": [tile_of(*SITE, z) for z in (9, 10, 11, 12)] + [tile_of(-85.0, 30.0, z) for z in (9, 10, 11)],
    "C 240 m only": [tile_of(-75.0, 100.0, z) for z in (5, 6, 7, 8, 9)] + [tile_of(-70.0, 300.0, z) for z in (7, 8)],
    "D edges": [tile_of_xy(-3000.0, -12000.0, 9), tile_of_xy(-19000.0, -12000.0, 8),      # 5 m Site01 product edges
                tile_of_xy(304000.0, 10000.0, 6), tile_of_xy(304000.0, 304000.0, 6),     # 20/80 m product edge, corner
                tile_of_xy(-931200.0 + 10, 0.0, 4), tile_of_xy(650000.0, 650000.0, 5)],  # map edge, outside the 60 deg circle
    "E composed zoomed-out": [(1, 0, 0), (1, 1, 1), (2, 1, 1), (3, 3, 4), (4, 7, 8)],
}
rows = []
for g, zxys in groups.items():
    for zxy in zxys:
        pe, te = timed(engine.render_tile, zxy); pn, tn = timed(new.render_tile, zxy)
        a, b = rgba(pe), rgba(pn)
        m = (a[..., 3] > 0) | (b[..., 3] > 0)
        row = {"group": g, "tile": "/".join(map(str, zxy)), "m_per_px": round(RES[zxy[0]], 3),
               "opaque_frac": round(float((b[..., 3] > 0).mean()), 4),
               "alpha_equal": bool((a[..., 3] == b[..., 3]).all()), "alpha_diff_px": int((a[..., 3] != b[..., 3]).sum()),
               "engine_score": score(a[..., 0].astype(float)) if m.all() else None,
               "new_score": score(b[..., 0].astype(float)) if m.all() else None,
               "grey_mean_engine": round(float(a[..., 0][a[..., 3] > 0].mean()), 2) if (a[..., 3] > 0).any() else None,
               "grey_mean_new": round(float(b[..., 0][b[..., 3] > 0].mean()), 2) if (b[..., 3] > 0).any() else None,
               "mean_abs_grey_diff": round(float(np.abs(a[..., 0].astype(int) - b[..., 0].astype(int))[m].mean()), 2) if m.any() else None,
               "engine_s": round(te, 3), "new_s": round(tn, 3)}
        rows.append(row)
        name = f"{g.split()[0]}_{row['tile'].replace('/', '_')}"
        pair = Image.new("RGBA", (2 * 512 + 8, 512), (16, 22, 30, 255))
        pair.paste(Image.fromarray(a).resize((512, 512), Image.NEAREST), (0, 0))
        pair.paste(Image.fromarray(b).resize((512, 512), Image.NEAREST), (520, 0))
        pair.convert("RGB").save(OUT / "images" / "tiles" / f"{name}_engine-left_new-right.png", optimize=True)
        print(json.dumps(row))
(OUT / "logs").mkdir(exist_ok=True)
(OUT / "logs" / "tile_verification.json").write_text(json.dumps(rows, indent=1))
for g in groups:
    rs = [r for r in rows if r["group"] == g]
    es = [r["engine_s"] for r in rs]; ns = [r["new_s"] for r in rs]
    print(f"SUMMARY {g}: tiles {len(rs)}; alpha equal {sum(r['alpha_equal'] for r in rs)}/{len(rs)}; "
          f"max new score {max((max(r['new_score']) for r in rs if r['new_score']), default=None)}; "
          f"max engine score {max((max(r['engine_score']) for r in rs if r['engine_score']), default=None)}; "
          f"render s engine median {statistics.median(es):.3f} max {max(es):.3f} | new median {statistics.median(ns):.3f} max {max(ns):.3f}")
