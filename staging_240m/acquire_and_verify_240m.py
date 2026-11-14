import os
import sys
import time
import json
import hashlib
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
import rasterio
import numpy as np

# Force unbuffered / line-buffered stdout so logs are immediately visible
sys.stdout.reconfigure(line_buffering=True)

REPO_ROOT = Path(r"E:\LUNA-OPS")
STAGING_DIR = REPO_ROOT / "staging_240m"
DEST_DIR = REPO_ROOT / "data" / "dem" / "pgda90_240m"
TEMP_DIR = STAGING_DIR / "temp"

STAGING_DIR.mkdir(parents=True, exist_ok=True)
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# Strict storage on E:
os.environ["TEMP"] = str(TEMP_DIR)
os.environ["TMP"] = str(TEMP_DIR)

CHUNK_SIZE = 64 * 1024 * 1024  # 64 MiB HTTP Range chunk size

DATASETS = [
    {
        "key": "dem",
        "name": "LDEM_60S_240MPP_ADJ.TIF",
        "url": "https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/LDEM_60S_240MPP_ADJ.TIF",
        "expected_bytes": 218961039,
        "expected_sha256": "3f9663257b63022f2b0d5a623482ff3cadddceb91594a4e4ca14a94d8cec8b34",
        "description": "PGDA 90 240 m Lunar South Pole Surface DEM (60S-90S)"
    },
    {
        "key": "err",
        "name": "LDEM_60S_240MPP_ADJ_ERR.TIF",
        "url": "https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/LDEM_60S_240MPP_ADJ_ERR.TIF",
        "expected_bytes": 267005175,
        "expected_sha256": None,
        "description": "PGDA 90 240 m Lunar South Pole Height Error Map (60S-90S)"
    }
]

def format_bytes(n):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if abs(n) < 1024.0:
            return f"{n:3.2f} {unit}"
        n /= 1024.0
    return f"{n:.2f} TB"

def compute_sha256(filepath):
    print(f"Computing SHA-256 for {filepath.name}...")
    t0 = time.time()
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(4 * 1024 * 1024):
            h.update(chunk)
    elapsed = time.time() - t0
    digest = h.hexdigest()
    print(f"  SHA-256 for {filepath.name}: {digest} ({elapsed:.1f}s)")
    return digest

def download_resumable(item):
    name = item["name"]
    url = item["url"]
    expected_total = item["expected_bytes"]
    dest_path = STAGING_DIR / name
    part_path = STAGING_DIR / f"{name}.part"

    print(f"\n=======================================================")
    print(f"[{datetime.now(timezone.utc).isoformat()}] Processing: {name}")
    print(f"Description: {item['description']}")
    print(f"URL: {url}")
    print(f"Staging path: {dest_path}")
    print(f"Expected Size: {expected_total:,} bytes ({format_bytes(expected_total)})")
    print(f"Range Chunk Size: {format_bytes(CHUNK_SIZE)}")
    print(f"=======================================================")

    # Check if already complete in staging or destination
    if dest_path.exists() and dest_path.stat().st_size == expected_total:
        print(f"File {name} already exists in staging with exact size ({expected_total:,} bytes).")
        digest = compute_sha256(dest_path)
        return {
            "name": name,
            "path": str(dest_path),
            "bytes": expected_total,
            "sha256": digest,
            "status": "already_downloaded"
        }

    start_time = time.time()
    max_retries = 15

    while True:
        current_bytes = part_path.stat().st_size if part_path.exists() else 0
        if current_bytes >= expected_total:
            break

        chunk_end = min(current_bytes + CHUNK_SIZE - 1, expected_total - 1)
        chunk_len = chunk_end - current_bytes + 1
        pct = (current_bytes / expected_total) * 100
        chunk_idx = (current_bytes // CHUNK_SIZE) + 1
        total_chunks = (expected_total + CHUNK_SIZE - 1) // CHUNK_SIZE

        print(f"\n[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] Chunk {chunk_idx}/{total_chunks}: "
              f"bytes {current_bytes:,}-{chunk_end:,} ({format_bytes(chunk_len)}) | Progress: {pct:.2f}%")

        chunk_success = False
        for attempt in range(1, max_retries + 1):
            current_bytes = part_path.stat().st_size if part_path.exists() else 0
            if current_bytes > chunk_end:
                chunk_success = True
                break

            range_header = f"bytes={current_bytes}-{chunk_end}"
            req = urllib.request.Request(url, headers={
                "User-Agent": "LUNA-OPS-Acquire/1.5.0",
                "Range": range_header
            })

            try:
                t_req = time.time()
                with urllib.request.urlopen(req, timeout=30) as resp:
                    if resp.status != 206:
                        raise ValueError(f"Expected HTTP 206 Partial Content, received HTTP {resp.status}")

                    cr = resp.headers.get("Content-Range")
                    if not cr or not cr.startswith(f"bytes {current_bytes}-"):
                        raise ValueError(f"Invalid Content-Range header: {cr}, expected prefix 'bytes {current_bytes}-'")

                    bytes_in_chunk = 0
                    last_sync = current_bytes
                    with open(part_path, "ab") as f:
                        while True:
                            block = resp.read(1024 * 1024)  # 1 MiB stream read
                            if not block:
                                break
                            f.write(block)
                            bytes_in_chunk += len(block)
                            if bytes_in_chunk - last_sync >= 8 * 1024 * 1024:
                                f.flush()
                                os.fsync(f.fileno())
                                last_sync = bytes_in_chunk

                        f.flush()
                        os.fsync(f.fileno())

                    new_size = part_path.stat().st_size
                    elapsed_chunk = time.time() - t_req
                    chunk_speed = bytes_in_chunk / elapsed_chunk if elapsed_chunk > 0 else 0
                    print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] Chunk {chunk_idx} complete: "
                          f"{format_bytes(bytes_in_chunk)} in {elapsed_chunk:.1f}s ({format_bytes(chunk_speed)}/s) | "
                          f"File size: {format_bytes(new_size)} ({new_size / expected_total * 100:.2f}%)")

                    if new_size >= chunk_end + 1:
                        chunk_success = True
                        break
                    else:
                        print(f"Premature stream completion. Written: {new_size:,}, expected: {chunk_end + 1:,}. Retrying...")
                        time.sleep(2)

            except Exception as e:
                backoff = min(30, 2 ** min(attempt, 5))
                print(f"[Attempt {attempt}/{max_retries}] Network error: {e}. Backing off {backoff}s...")
                time.sleep(backoff)

        if not chunk_success:
            raise RuntimeError(f"Failed to download chunk {current_bytes}-{chunk_end} after {max_retries} attempts.")

    # All chunks complete
    final_size = part_path.stat().st_size
    print(f"\n[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] Download complete: {final_size:,} bytes.")
    if final_size != expected_total:
        raise ValueError(f"Size mismatch: {final_size:,} != expected {expected_total:,}")

    if dest_path.exists():
        dest_path.unlink()
    part_path.rename(dest_path)
    print(f"Renamed {part_path.name} -> {dest_path.name}")

    total_duration = time.time() - start_time
    digest = compute_sha256(dest_path)

    if item.get("expected_sha256"):
        if digest.lower() != item["expected_sha256"].lower():
            raise ValueError(f"SHA-256 mismatch for {name}!\nComputed: {digest}\nExpected: {item['expected_sha256']}")
        print(f"  SHA-256 VERIFIED against expected fingerprint.")
    else:
        print(f"  SHA-256 recorded: {digest}")

    return {
        "name": name,
        "url": url,
        "path": str(dest_path),
        "expected_bytes": expected_total,
        "actual_bytes": final_size,
        "sha256": digest,
        "duration_s": total_duration,
        "status": "downloaded_and_verified"
    }

def verify_rasterio_geometry(dem_path, err_path):
    print("\n=======================================================")
    print("Rasterio Inspection & Grid Geometry Verification")
    print("=======================================================")
    
    report = {}

    with rasterio.open(dem_path) as ds_dem:
        dem_info = {
            "driver": ds_dem.driver,
            "width": ds_dem.width,
            "height": ds_dem.height,
            "count": ds_dem.count,
            "dtypes": ds_dem.dtypes,
            "crs": str(ds_dem.crs),
            "crs_wkt": ds_dem.crs.to_wkt() if ds_dem.crs else None,
            "transform": list(ds_dem.transform),
            "bounds": {
                "left": ds_dem.bounds.left,
                "bottom": ds_dem.bounds.bottom,
                "right": ds_dem.bounds.right,
                "top": ds_dem.bounds.top
            },
            "res": ds_dem.res,
            "nodata": ds_dem.nodata,
            "overviews": [ds_dem.overviews(i) for i in ds_dem.indexes],
        }
        # Center sample 1000x1000
        cx, cy = ds_dem.width // 2, ds_dem.height // 2
        w = rasterio.windows.Window(cx - 500, cy - 500, 1000, 1000)
        s = ds_dem.read(1, window=w)
        valid = s[~np.isnan(s)] if np.isnan(ds_dem.nodata or np.nan) else s[s != ds_dem.nodata]
        dem_info["center_sample_1000x1000"] = {
            "min_m": float(np.min(valid)) if len(valid) > 0 else None,
            "max_m": float(np.max(valid)) if len(valid) > 0 else None,
            "mean_m": float(np.mean(valid)) if len(valid) > 0 else None,
            "valid_count": int(len(valid)),
            "total_pixels": int(s.size)
        }
    report["dem"] = dem_info

    with rasterio.open(err_path) as ds_err:
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
        }
        cx, cy = ds_err.width // 2, ds_err.height // 2
        w = rasterio.windows.Window(cx - 500, cy - 500, 1000, 1000)
        s_err = ds_err.read(1, window=w)
        valid_err = s_err[~np.isnan(s_err)] if np.isnan(ds_err.nodata or np.nan) else s_err[s_err != ds_err.nodata]
        err_info["center_sample_1000x1000"] = {
            "min_m": float(np.min(valid_err)) if len(valid_err) > 0 else None,
            "max_m": float(np.max(valid_err)) if len(valid_err) > 0 else None,
            "mean_m": float(np.mean(valid_err)) if len(valid_err) > 0 else None,
            "valid_count": int(len(valid_err)),
            "total_pixels": int(s_err.size)
        }
    report["err"] = err_info

    # Grid alignment assertions
    checks = {
        "dimensions_equal": (dem_info["width"] == err_info["width"] == 7760 and dem_info["height"] == err_info["height"] == 7760),
        "resolution_exact_240m": (dem_info["res"] == (240.0, 240.0) and err_info["res"] == (240.0, 240.0)),
        "transform_equal": (dem_info["transform"] == err_info["transform"] == [240.0, 0.0, -931200.0, 0.0, -240.0, 931200.0]),
        "bounds_equal": (dem_info["bounds"] == err_info["bounds"]),
        "crs_equal": (dem_info["crs"] == err_info["crs"]),
        "dem_values_in_lunar_range": (-9100.0 <= dem_info["center_sample_1000x1000"]["min_m"] and dem_info["center_sample_1000x1000"]["max_m"] <= 10800.0),
        "err_values_non_negative": (err_info["center_sample_1000x1000"]["min_m"] >= 0.0)
    }
    report["alignment_checks"] = checks

    for k, v in checks.items():
        print(f"  Check '{k}': {'PASS' if v else 'FAIL'}")
        if not v:
            raise ValueError(f"Grid check failed: {k}")

    return report

def main():
    print(f"Starting Phase 4 240 m Acquisition at {datetime.now(timezone.utc).isoformat()}")
    results = {}
    for item in DATASETS:
        res = download_resumable(item)
        results[item["key"]] = res

    # Verification
    dem_staged = STAGING_DIR / DATASETS[0]["name"]
    err_staged = STAGING_DIR / DATASETS[1]["name"]

    geo_report = verify_rasterio_geometry(dem_staged, err_staged)

    # Save staging report
    summary = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "datasets": results,
        "rasterio_verification": geo_report
    }
    with open(STAGING_DIR / "acquisition_report.json", "w") as f:
        json.dump(summary, f, indent=2)

    print("\nAll downloads, hashes, and Rasterio geometry checks PASSED.")
    return 0

if __name__ == "__main__":
    sys.exit(main())

