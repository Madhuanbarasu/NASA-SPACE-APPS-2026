import os
import sys
import time
import json
import hashlib
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

# Force line-buffering on stdout so logs are never delayed by Windows pipe buffering
sys.stdout.reconfigure(line_buffering=True)

# Ensure TEMP and TMP are strictly on E:
os.environ["TEMP"] = r"E:\LUNA-OPS\staging_a5\temp"
os.environ["TMP"] = r"E:\LUNA-OPS\staging_a5\temp"

STAGING_DIR = Path(r"E:\LUNA-OPS\staging_a5")
TEMP_DIR = STAGING_DIR / "temp"
TEMP_DIR.mkdir(parents=True, exist_ok=True)

CHUNK_SIZE = 128 * 1024 * 1024  # 128 MiB range chunk size

DOWNLOADS = [
    {
        "name": "LDEM_80S_20MPP_ADJ.TIF",
        "url": "https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/LDEM_80S_20MPP_ADJ.TIF",
        "expected_bytes": 2696082051,
        "description": "PGDA 90 20m Lunar South Pole Surface DEM"
    },
    {
        "name": "LDEM_80S_20MPP_ADJ_ERR.TIF",
        "url": "https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/LDEM_80S_20MPP_ADJ_ERR.TIF",
        "expected_bytes": 3954709201,
        "description": "PGDA 90 20m Lunar South Pole Error Map"
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
    print(f"SHA-256 for {filepath.name}: {digest} (computed in {elapsed:.1f}s)")
    return digest

def download_file_chunked(item):
    name = item["name"]
    url = item["url"]
    expected_total = item["expected_bytes"]
    dest_path = STAGING_DIR / name
    part_path = STAGING_DIR / f"{name}.part"

    print(f"\n=======================================================")
    print(f"[{datetime.now(timezone.utc).isoformat()}] Processing: {name}")
    print(f"URL: {url}")
    print(f"Target: {dest_path}")
    print(f"Expected Size: {expected_total:,} bytes ({format_bytes(expected_total)})")
    print(f"Range Chunk Size: {format_bytes(CHUNK_SIZE)}")
    print(f"=======================================================")

    # Check if already complete
    if dest_path.exists():
        actual_size = dest_path.stat().st_size
        if actual_size == expected_total:
            print(f"File {name} already fully downloaded ({actual_size:,} bytes). Skipping download.")
            digest = compute_sha256(dest_path)
            return {
                "name": name,
                "path": str(dest_path),
                "bytes": actual_size,
                "sha256": digest,
                "skipped": True
            }
        else:
            print(f"Warning: Existing {dest_path} size {actual_size} != expected {expected_total}. Moving to .part")
            if part_path.exists():
                part_path.unlink()
            dest_path.rename(part_path)

    start_time = time.time()
    max_retries = 20

    while True:
        current_bytes = part_path.stat().st_size if part_path.exists() else 0
        if current_bytes >= expected_total:
            break

        chunk_end = min(current_bytes + CHUNK_SIZE - 1, expected_total - 1)
        chunk_len = chunk_end - current_bytes + 1
        pct = (current_bytes / expected_total) * 100

        print(f"\n[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] Chunk request: bytes {current_bytes:,}-{chunk_end:,} ({format_bytes(chunk_len)}) | Total progress: {pct:.2f}%")

        # Retry loop for this range chunk
        chunk_success = False
        for attempt in range(1, max_retries + 1):
            # Recalculate range from current file size on disk
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
                        raise ValueError(f"Expected HTTP 206, got {resp.status}")

                    cr = resp.headers.get("Content-Range")
                    if not cr or not cr.startswith(f"bytes {current_bytes}-"):
                        raise ValueError(f"Invalid Content-Range: {cr}, expected prefix 'bytes {current_bytes}-'")
                    cl = int(resp.headers.get("Content-Length", 0))
                    # Read and append to file
                    bytes_in_chunk = 0
                    last_sync = current_bytes
                    with open(part_path, "ab") as f:
                        while True:
                            block = resp.read(1024 * 1024)  # 1 MiB
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

                    # Check chunk completion
                    new_size = part_path.stat().st_size
                    elapsed_chunk = time.time() - t_req
                    chunk_speed = bytes_in_chunk / elapsed_chunk if elapsed_chunk > 0 else 0
                    print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] Chunk received: {format_bytes(bytes_in_chunk)} in {elapsed_chunk:.1f}s ({format_bytes(chunk_speed)}/s) | New size: {format_bytes(new_size)} ({new_size / expected_total * 100:.2f}%)")

                    if new_size >= chunk_end + 1:
                        chunk_success = True
                        break
                    else:
                        print(f"Premature connection close in chunk. Written: {new_size:,}, needed: {chunk_end + 1:,}. Retrying remainder...")
                        time.sleep(2)

            except Exception as e:
                backoff = min(60, 2 ** min(attempt, 6))
                print(f"[Attempt {attempt}/{max_retries}] Network error: {e}. Backing off {backoff}s...")
                time.sleep(backoff)

        if not chunk_success:
            raise RuntimeError(f"Failed to download chunk {current_bytes}-{chunk_end} after {max_retries} attempts.")

    # All chunks complete
    final_size = part_path.stat().st_size
    print(f"\nFile download finished: {final_size:,} bytes.")
    if final_size != expected_total:
        raise ValueError(f"Size mismatch: {final_size:,} != {expected_total:,}")

    if dest_path.exists():
        dest_path.unlink()
    part_path.rename(dest_path)
    print(f"Moved {part_path.name} -> {dest_path.name}")

    total_duration = time.time() - start_time
    digest = compute_sha256(dest_path)

    return {
        "name": name,
        "url": url,
        "path": str(dest_path),
        "expected_bytes": expected_total,
        "actual_bytes": final_size,
        "sha256": digest,
        "duration_seconds": round(total_duration, 2)
    }

def verify_products():
    print("\n=======================================================")
    print(f"[{datetime.now(timezone.utc).isoformat()}] Starting Post-Download Integrity Verification")
    print("=======================================================")
    import rasterio
    import numpy as np

    surf_path = STAGING_DIR / "LDEM_80S_20MPP_ADJ.TIF"
    err_path = STAGING_DIR / "LDEM_80S_20MPP_ADJ_ERR.TIF"

    assert surf_path.exists(), f"Missing {surf_path}"
    assert err_path.exists(), f"Missing {err_path}"

    report = {"timestamp": datetime.now(timezone.utc).isoformat()}

    print("\n--- Verifying Surface DEM ---")
    with rasterio.open(surf_path) as ds:
        surf_info = {
            "file": surf_path.name,
            "driver": ds.driver,
            "width": ds.width,
            "height": ds.height,
            "count": ds.count,
            "dtypes": [str(d) for d in ds.dtypes],
            "crs": str(ds.crs),
            "transform": [float(x) for x in ds.transform],
            "bounds": {"left": ds.bounds.left, "bottom": ds.bounds.bottom, "right": ds.bounds.right, "top": ds.bounds.top},
            "res": [float(r) for r in ds.res],
            "nodata": float(ds.nodata) if ds.nodata is not None else None
        }
        # Sample center 1000x1000 window
        cx, cy = ds.width // 2, ds.height // 2
        w = rasterio.windows.Window(cx - 500, cy - 500, 1000, 1000)
        s = ds.read(1, window=w)
        valid = s[~np.isnan(s)] if np.isnan(ds.nodata or np.nan) else s[s != ds.nodata]
        surf_info["sample_1000x1000"] = {
            "valid_count": int(len(valid)),
            "min_elevation_m": float(np.min(valid)) if len(valid) else None,
            "max_elevation_m": float(np.max(valid)) if len(valid) else None,
            "mean_elevation_m": float(np.mean(valid)) if len(valid) else None
        }
    report["surface_dem"] = surf_info
    print(json.dumps(surf_info, indent=2))

    print("\n--- Verifying Error Map ---")
    with rasterio.open(err_path) as ds:
        err_info = {
            "file": err_path.name,
            "driver": ds.driver,
            "width": ds.width,
            "height": ds.height,
            "count": ds.count,
            "dtypes": [str(d) for d in ds.dtypes],
            "crs": str(ds.crs),
            "transform": [float(x) for x in ds.transform],
            "bounds": {"left": ds.bounds.left, "bottom": ds.bounds.bottom, "right": ds.bounds.right, "top": ds.bounds.top},
            "res": [float(r) for r in ds.res],
            "nodata": float(ds.nodata) if ds.nodata is not None else None
        }
        cx, cy = ds.width // 2, ds.height // 2
        w = rasterio.windows.Window(cx - 500, cy - 500, 1000, 1000)
        s = ds.read(1, window=w)
        valid_err = s[~np.isnan(s)] if np.isnan(ds.nodata or np.nan) else s[s != ds.nodata]
        err_info["sample_1000x1000"] = {
            "valid_count": int(len(valid_err)),
            "min_err_m": float(np.min(valid_err)) if len(valid_err) else None,
            "max_err_m": float(np.max(valid_err)) if len(valid_err) else None,
            "mean_err_m": float(np.mean(valid_err)) if len(valid_err) else None
        }
    report["error_map"] = err_info
    print(json.dumps(err_info, indent=2))

    print("\n--- Cross-Grid Alignment Checks ---")
    alignment = {
        "dimensions_identical": (surf_info["width"] == err_info["width"] and surf_info["height"] == err_info["height"]),
        "transform_identical": (surf_info["transform"] == err_info["transform"]),
        "bounds_identical": (surf_info["bounds"] == err_info["bounds"]),
        "crs_identical": (surf_info["crs"] == err_info["crs"]),
        "resolution_exact_20m": (surf_info["res"] == [20.0, 20.0] and err_info["res"] == [20.0, 20.0]),
        "error_values_positive": (err_info["sample_1000x1000"]["min_err_m"] is not None and err_info["sample_1000x1000"]["min_err_m"] >= 0.0)
    }
    report["alignment_checks"] = alignment
    print(json.dumps(alignment, indent=2))

    all_passed = all(alignment.values())
    print(f"\nFinal Alignment Verification: {'PASS' if all_passed else 'FAIL'}")

    out_file = STAGING_DIR / "final_verification_report.json"
    with open(out_file, "w") as f:
        json.dump(report, f, indent=2)
    print(f"Report written to {out_file}")
    return report

def main():
    results = []
    for item in DOWNLOADS:
        res = download_file_chunked(item)
        results.append(res)

    meta_file = STAGING_DIR / "resumed_download_meta.json"
    with open(meta_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nAll downloads completed. Meta saved to {meta_file}")

    # Run verification
    verify_products()

if __name__ == "__main__":
    main()

