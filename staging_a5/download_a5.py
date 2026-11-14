import os
import sys
import time
import json
import hashlib
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# Ensure TEMP and TMP are strictly on E:
os.environ["TEMP"] = r"E:\LUNA-OPS\staging_a5\temp"
os.environ["TMP"] = r"E:\LUNA-OPS\staging_a5\temp"

STAGING_DIR = Path(r"E:\LUNA-OPS\staging_a5")
TEMP_DIR = STAGING_DIR / "temp"
TEMP_DIR.mkdir(parents=True, exist_ok=True)

DOWNLOADS = [
    {
        "name": "LDEM_80S_20MPP_ADJ.TIF",
        "url": "https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/LDEM_80S_20MPP_ADJ.TIF",
        "description": "PGDA 90 20m Lunar South Pole Surface DEM"
    },
    {
        "name": "LDEM_80S_20MPP_ADJ_ERR.TIF",
        "url": "https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/LDEM_80S_20MPP_ADJ_ERR.TIF",
        "description": "PGDA 90 20m Lunar South Pole Error Map"
    }
]

def format_bytes(n):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if abs(n) < 1024.0:
            return f"{n:3.2f} {unit}"
        n /= 1024.0
    return f"{n:.2f} TB"

def download_file(item):
    name = item["name"]
    url = item["url"]
    dest_path = STAGING_DIR / name
    part_path = STAGING_DIR / f"{name}.part"

    print(f"\n[{datetime.now(timezone.utc).isoformat()}] Starting download for {name}")
    print(f"URL: {url}")
    print(f"Destination: {dest_path}")

    # Check headers
    req = urllib.request.Request(url, headers={"User-Agent": "LUNA-OPS-Acquire/1.5.0"})
    
    start_time = time.time()
    iso_start = datetime.now(timezone.utc).isoformat()

    existing_bytes = 0
    if part_path.exists():
        existing_bytes = part_path.stat().st_size
        print(f"Found existing partial file with {format_bytes(existing_bytes)} ({existing_bytes} bytes). Attempting resume...")
        req.add_header("Range", f"bytes={existing_bytes}-")

    opener = urllib.request.build_opener()
    try:
        resp = opener.open(req)
    except urllib.error.HTTPError as e:
        if e.code == 416: # Range Not Satisfiable (maybe already complete)
            print("Range not satisfiable; checking existing file.")
            existing_bytes = 0
            part_path.unlink(missing_ok=True)
            resp = opener.open(urllib.request.Request(url, headers={"User-Agent": "LUNA-OPS-Acquire/1.5.0"}))
        else:
            raise

    http_status = resp.status
    headers = dict(resp.headers)
    print(f"HTTP Status: {http_status}")
    print(f"Content-Type: {headers.get('Content-Type')}")
    print(f"Content-Length: {headers.get('Content-Length')}")
    print(f"Last-Modified: {headers.get('Last-Modified')}")
    print(f"ETag: {headers.get('ETag')}")

    content_range = headers.get('Content-Range')
    if content_range:
        # e.g. "bytes 1000-5000/5001"
        total_expected_bytes = int(content_range.split('/')[-1])
    else:
        total_expected_bytes = int(headers.get('Content-Length', 0)) + existing_bytes

    print(f"Total expected size: {format_bytes(total_expected_bytes)} ({total_expected_bytes} bytes)")

    # Open file in append or write mode
    mode = "ab" if existing_bytes > 0 and http_status == 206 else "wb"
    if mode == "wb":
        existing_bytes = 0

    downloaded = existing_bytes
    chunk_size = 1024 * 1024 # 1 MB chunks
    last_print_time = time.time()
    last_print_bytes = downloaded

    with open(part_path, mode) as f:
        while True:
            chunk = resp.read(chunk_size)
            if not chunk:
                break
            f.write(chunk)
            downloaded += len(chunk)
            now = time.time()
            if now - last_print_time >= 5.0: # Print every 5 seconds
                speed = (downloaded - last_print_bytes) / (now - last_print_time)
                pct = (downloaded / total_expected_bytes * 100) if total_expected_bytes else 0
                elapsed = now - start_time
                print(f"Progress: {format_bytes(downloaded)} / {format_bytes(total_expected_bytes)} ({pct:.1f}%) | Speed: {format_bytes(speed)}/s | Elapsed: {elapsed:.1f}s")
                last_print_time = now
                last_print_bytes = downloaded

    finish_time = time.time()
    iso_finish = datetime.now(timezone.utc).isoformat()
    duration = finish_time - start_time
    avg_speed = (downloaded - existing_bytes) / duration if duration > 0 else 0

    print(f"\nDownload completed in {duration:.1f}s. Average speed: {format_bytes(avg_speed)}/s")
    print(f"Downloaded bytes: {downloaded} (Expected: {total_expected_bytes})")

    if total_expected_bytes and downloaded != total_expected_bytes:
        raise ValueError(f"Byte count mismatch: downloaded {downloaded} != expected {total_expected_bytes}")

    # Move part file to final destination
    if dest_path.exists():
        dest_path.unlink()
    part_path.rename(dest_path)

    # Compute SHA-256
    print("Computing SHA-256 checksum...")
    sha256 = hashlib.sha256()
    with open(dest_path, "rb") as f:
        while chunk := f.read(4 * 1024 * 1024):
            sha256.update(chunk)
    digest = sha256.hexdigest()
    print(f"SHA-256: {digest}")

    return {
        "name": name,
        "url": url,
        "path": str(dest_path),
        "http_status": http_status,
        "http_headers": {
            "Content-Length": headers.get("Content-Length"),
            "Content-Type": headers.get("Content-Type"),
            "Last-Modified": headers.get("Last-Modified"),
            "ETag": headers.get("ETag"),
            "Content-Range": content_range
        },
        "expected_bytes": total_expected_bytes,
        "actual_bytes": downloaded,
        "sha256": digest,
        "start_utc": iso_start,
        "finish_utc": iso_finish,
        "duration_seconds": round(duration, 2),
        "avg_speed_bps": round(avg_speed, 2)
    }

def main():
    results = []
    for item in DOWNLOADS:
        res = download_file(item)
        results.append(res)

    meta_file = STAGING_DIR / "download_meta.json"
    with open(meta_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nAll downloads completed successfully. Metadata saved to {meta_file}")

if __name__ == "__main__":
    main()

