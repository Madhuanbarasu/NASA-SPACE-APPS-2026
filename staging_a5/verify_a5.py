import json
import math
from pathlib import Path
import rasterio
import numpy as np

STAGING_DIR = Path(r"E:\LUNA-OPS\staging_a5")
SURF_PATH = STAGING_DIR / "LDEM_80S_20MPP_ADJ.TIF"
ERR_PATH = STAGING_DIR / "LDEM_80S_20MPP_ADJ_ERR.TIF"
META_PATH = STAGING_DIR / "download_meta.json"

def verify_all():
    report = {}

    # 1. Download metadata & checksums
    if META_PATH.exists():
        with open(META_PATH, "r") as f:
            report["download_meta"] = json.load(f)
    else:
        report["download_meta"] = "No download_meta.json found"

    # 2. Check surface DEM
    if not SURF_PATH.exists():
        print(f"Error: {SURF_PATH} does not exist.")
        return
    if not ERR_PATH.exists():
        print(f"Error: {ERR_PATH} does not exist.")
        return

    print("Opening Surface DEM with rasterio...")
    with rasterio.open(SURF_PATH) as ds_surf:
        surf_info = {
            "driver": ds_surf.driver,
            "width": ds_surf.width,
            "height": ds_surf.height,
            "count": ds_surf.count,
            "dtypes": ds_surf.dtypes,
            "crs": str(ds_surf.crs),
            "crs_wkt": ds_surf.crs.to_wkt() if ds_surf.crs else None,
            "transform": list(ds_surf.transform),
            "bounds": {
                "left": ds_surf.bounds.left,
                "bottom": ds_surf.bounds.bottom,
                "right": ds_surf.bounds.right,
                "top": ds_surf.bounds.top
            },
            "res": ds_surf.res,
            "nodata": ds_surf.nodata,
            "overviews": [ds_surf.overviews(i) for i in ds_surf.indexes],
            "tags": ds_surf.tags()
        }
        # Sample center window 1000x1000 to verify data validity and elevation stats
        cx, cy = ds_surf.width // 2, ds_surf.height // 2
        window = rasterio.windows.Window(cx - 500, cy - 500, 1000, 1000)
        sample = ds_surf.read(1, window=window)
        valid = sample[~np.isnan(sample)] if np.isnan(ds_surf.nodata or np.nan) else sample[sample != ds_surf.nodata]
        surf_info["sample_window_1000x1000"] = {
            "min": float(np.min(valid)) if len(valid) > 0 else None,
            "max": float(np.max(valid)) if len(valid) > 0 else None,
            "mean": float(np.mean(valid)) if len(valid) > 0 else None,
            "valid_count": int(len(valid)),
            "total_pixels": int(sample.size)
        }
    report["surface_dem"] = surf_info

    print("Opening Error Map with rasterio...")
    with rasterio.open(ERR_PATH) as ds_err:
        err_info = {
            "driver": ds_err.driver,
            "width": ds_err.width,
            "height": ds_err.height,
            "count": ds_err.count,
            "dtypes": ds_err.dtypes,
            "crs": str(ds_err.crs),
            "crs_wkt": ds_err.crs.to_wkt() if ds_err.crs else None,
            "transform": list(ds_err.transform),
            "bounds": {
                "left": ds_err.bounds.left,
                "bottom": ds_err.bounds.bottom,
                "right": ds_err.bounds.right,
                "top": ds_err.bounds.top
            },
            "res": ds_err.res,
            "nodata": ds_err.nodata,
            "overviews": [ds_err.overviews(i) for i in ds_err.indexes],
            "tags": ds_err.tags()
        }
        cx, cy = ds_err.width // 2, ds_err.height // 2
        window = rasterio.windows.Window(cx - 500, cy - 500, 1000, 1000)
        sample_err = ds_err.read(1, window=window)
        valid_err = sample_err[~np.isnan(sample_err)] if np.isnan(ds_err.nodata or np.nan) else sample_err[sample_err != ds_err.nodata]
        err_info["sample_window_1000x1000"] = {
            "min": float(np.min(valid_err)) if len(valid_err) > 0 else None,
            "max": float(np.max(valid_err)) if len(valid_err) > 0 else None,
            "mean": float(np.mean(valid_err)) if len(valid_err) > 0 else None,
            "valid_count": int(len(valid_err)),
            "total_pixels": int(sample_err.size)
        }
    report["error_map"] = err_info

    # 3. Grid alignment check between DEM and Error map
    align_checks = {
        "dimensions_match": (surf_info["width"] == err_info["width"] and surf_info["height"] == err_info["height"]),
        "transform_match": (surf_info["transform"] == err_info["transform"]),
        "bounds_match": (surf_info["bounds"] == err_info["bounds"]),
        "crs_match": (surf_info["crs"] == err_info["crs"]),
        "resolution_exact_20m": (surf_info["res"] == (20.0, 20.0) and err_info["res"] == (20.0, 20.0))
    }
    report["grid_alignment_checks"] = align_checks

    out_file = STAGING_DIR / "verification_report.json"
    with open(out_file, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\nVerification complete. Report written to {out_file}")
    print(f"Alignment checks: {align_checks}")

if __name__ == "__main__":
    verify_all()

