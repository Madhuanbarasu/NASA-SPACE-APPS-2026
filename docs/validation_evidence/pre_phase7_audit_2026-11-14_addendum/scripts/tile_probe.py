# Read-only diagnostic: render the hillshade tiles around Site01 offline (no server) and look for a periodic grid.
import io, math, sys
sys.path.insert(0, r"E:\LUNA-OPS\backend")
import numpy as np
from PIL import Image
from pyproj import Transformer
from lunaops.api import tiles
from lunaops.engine.dem import usable_levels
meta = tiles.tile_meta()
print("levels", [(l["level"], l.get("product"), l["pixel_m"]) for l in usable_levels()])
print("resolutions", [round(r, 2) for r in meta["resolutions"]])
t = Transformer.from_proj("+proj=longlat +R=1737400 +no_defs", tiles.STEREO_PROJ4, always_xy=True)
# a flat point just south-west of the site, where the screenshot crop shows the grid
for lon, lat in [(222.510447 - 360, -89.463163)]:
    X, Y = t.transform(lon, lat)
    for z in range(len(meta["resolutions"])):
        r = meta["resolutions"][z]
        if not 20 < r < 130: continue
        tx = int((X - meta["origin"][0]) / (256 * r)); ty = int((meta["origin"][1] - Y) / (256 * r))
        png = tiles.render_tile(z, tx, ty)
        im = Image.open(io.BytesIO(png)); a = np.asarray(im)[..., 0].astype(float); al = np.asarray(im)[..., 3]
        im.save(sys.argv[1] + f"/tile_{z}_{tx}_{ty}.png")
        res_line = []
        for name, axis in (("cols", 0), ("rows", 1)):
            # second difference of the mean profile isolates 1-pixel lines; report the strongest periods
            prof = a.mean(axis=axis); d = prof - np.convolve(prof, np.ones(9) / 9, mode="same"); d = d[6:-6]
            f = np.abs(np.fft.rfft(d - d.mean())); k = np.argsort(f[3:])[::-1][:3] + 3
            res_line.append(f"{name}: periods px {[round(len(d)/kk, 1) for kk in k]} amp {[round(f[kk]/len(d)*2, 2) for kk in k]}")
        print(f"z{z} res {r:.1f} m tile {tx},{ty} opaque {(al == 255).mean():.3f}", " | ".join(res_line))
