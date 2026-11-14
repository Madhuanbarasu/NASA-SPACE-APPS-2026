"""Before/after map screenshots: side-by-side images and grid-line scores (the addendum's line score).

The score is measured on the map's upper-left area (x 60-380, y 20-340 px of the map pane), clear of the zoom buttons,
the selected-site ring at the centre, the readout and the legend. Usage: python compare_shots.py <evidence folder>
"""
import math, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

def line_score(img):
    hp = img - (np.roll(img, 1, 0) + np.roll(img, -1, 0) + np.roll(img, 1, 1) + np.roll(img, -1, 1)) / 4
    hp = hp[2:-2, 2:-2]; n = hp.std() + 1e-12
    return (round(float(np.abs(hp.mean(axis=0)).mean() / n * math.sqrt(hp.shape[0])), 2),
            round(float(np.abs(hp.mean(axis=1)).mean() / n * math.sqrt(hp.shape[1])), 2))

root = Path(sys.argv[1]); (root / "images").mkdir(exist_ok=True)
names = ["map-1-whole", "map-2-site", "map-3-zoom-in-1", "map-4-zoom-in-2", "map-5-zoom-in-3", "map-6-zoom-in-4",
         "landing-backdrop-only", "landing-slope-default"]
print("shot | before cols/rows | after cols/rows")
for n in names:
    b = Image.open(root / "before/screenshots" / f"{n}.png").convert("RGB"); a = Image.open(root / "after/screenshots" / f"{n}.png").convert("RGB")
    if n.startswith("map-"):
        box = (60, 20, 380, 340)
        sb = line_score(np.asarray(b.convert("L").crop(box), float)); sa = line_score(np.asarray(a.convert("L").crop(box), float))
        print(f"{n} | {sb} | {sa}")
    w, h = b.size
    pair = Image.new("RGB", (2 * w + 12, h + 28), (16, 22, 30)); d = ImageDraw.Draw(pair)
    pair.paste(b, (0, 28)); pair.paste(a, (w + 12, 28))
    d.text((8, 8), f"BEFORE (engine /api/tiles)  {n}", fill=(230, 230, 230)); d.text((w + 20, 8), "AFTER (lunaops_tiles /api/display/tiles)", fill=(230, 230, 230))
    pair.save(root / "images" / f"compare-{n}.png", optimize=True)
