"""Compare the PNG of every tile rendered before and after the tiles.py change (pixel by pixel, RGBA). Read-only over
tiles/png-before and tiles/png-after; writes tiles/compare.json. Run with the backend venv (Pillow, NumPy)."""
import json
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent / "tiles"
rows = []
for a in sorted((HERE / "png-after").glob("*.png")):
    b = HERE / "png-before" / a.name
    A = np.asarray(Image.open(a).convert("RGBA")).astype(int)
    row = {"tile": a.stem.replace("_", "/"), "after_opaque_share": round(float((A[..., 3] > 0).mean()), 4)}
    if b.exists():
        B = np.asarray(Image.open(b).convert("RGBA")).astype(int)
        d = np.abs(A - B)
        row.update({"identical": bool((d == 0).all()), "pixels_differing": int((d.max(axis=2) > 0).sum()),
                    "max_abs_diff": int(d.max()), "mean_abs_diff_rgb": round(float(d[..., :3].mean()), 4),
                    "alpha_changed": int((A[..., 3] != B[..., 3]).sum())})
    else:
        row["before"] = "not completed before (stopped at the cap)"
    rows.append(row)
    print(row)
(HERE / "compare.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
