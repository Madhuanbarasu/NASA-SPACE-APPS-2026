"""Run U-04 accessibility audit and U-06 performance audits on the live application.
Starts `start.py --no-browser --no-build --port 8765` as a subprocess, runs all audits,
and cleanly shuts down the server.
"""
import os
import sys
import time
import subprocess
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
EVIDENCE_DIR = REPO_ROOT / "docs" / "validation_evidence" / "post_phase5_backend_and_ui_fixes_2026-11-12"
U04_OUT = EVIDENCE_DIR / "u04_audit"
U06_RAW = EVIDENCE_DIR / "u06_perf" / "raw"
LOGS_DIR = EVIDENCE_DIR / "logs"

U04_OUT.mkdir(parents=True, exist_ok=True)
U06_RAW.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

PYTHON_EXE = str(REPO_ROOT / "backend" / ".venv" / "Scripts" / "python.exe")
PORT = 8765
BASE_URL = f"http://127.0.0.1:{PORT}"

print(f"=== Starting LUNA-OPS server on {BASE_URL} ===")
server_proc = subprocess.Popen(
    [PYTHON_EXE, "start.py", "--no-browser", "--no-build", "--port", str(PORT)],
    cwd=str(REPO_ROOT),
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
)

server_log_path = LOGS_DIR / "server_audits.log"

try:
    # Poll until server is ready
    ready = False
    start_time = time.time()
    while time.time() - start_time < 30:
        try:
            with urllib.request.urlopen(f"{BASE_URL}/", timeout=2) as resp:
                if resp.status == 200:
                    ready = True
                    break
        except Exception:
            time.sleep(1)

    if not ready:
        raise RuntimeError("Server failed to respond within 30 seconds")
    print(f"Server is ready! (took {time.time() - start_time:.1f}s)")

    # 1. U-04 accessibility audit
    print("\n--- Running U-04 live accessibility audit ---")
    u04_cmd = [
        "node",
        "frontend/scripts/a11y-live-audit.mjs",
        "--base", BASE_URL,
        "--out", str(U04_OUT),
        "--label", "postphase5",
    ]
    u04_log_path = LOGS_DIR / "10_audit_a11y.log"
    with open(u04_log_path, "w", encoding="utf-8") as log_f:
        res = subprocess.run(u04_cmd, cwd=str(REPO_ROOT), stdout=log_f, stderr=subprocess.STDOUT, text=True)
    print(f"U-04 audit exit code: {res.returncode}")
    if u04_log_path.exists():
        print(f"U-04 log size: {u04_log_path.stat().st_size} bytes")

    # 2. U-06 performance audit: native
    print("\n--- Running U-06 performance audit (native) ---")
    perf_native_cmd = [
        "node",
        "frontend/scripts/perf-audit.mjs",
        "--base", BASE_URL,
        "--out", str(U06_RAW),
        "--label", "final",
        "--profile", "native",
        "--phase5", "1",
    ]
    perf_native_log = LOGS_DIR / "12_perf_native.log"
    with open(perf_native_log, "w", encoding="utf-8") as log_f:
        res = subprocess.run(perf_native_cmd, cwd=str(REPO_ROOT), stdout=log_f, stderr=subprocess.STDOUT, text=True)
    print(f"U-06 native exit code: {res.returncode}")

    # 3. U-06 performance audit: cpu4x
    print("\n--- Running U-06 performance audit (cpu4x) ---")
    perf_cpu4x_cmd = [
        "node",
        "frontend/scripts/perf-audit.mjs",
        "--base", BASE_URL,
        "--out", str(U06_RAW),
        "--label", "final",
        "--profile", "cpu4x",
        "--phase5", "1",
    ]
    perf_cpu4x_log = LOGS_DIR / "12_perf_cpu4x.log"
    with open(perf_cpu4x_log, "w", encoding="utf-8") as log_f:
        res = subprocess.run(perf_cpu4x_cmd, cwd=str(REPO_ROOT), stdout=log_f, stderr=subprocess.STDOUT, text=True)
    print(f"U-06 cpu4x exit code: {res.returncode}")

    # 4. U-06 performance audit: cpu4x-net10mbps
    print("\n--- Running U-06 performance audit (cpu4x-net10mbps) ---")
    perf_net_cmd = [
        "node",
        "frontend/scripts/perf-audit.mjs",
        "--base", BASE_URL,
        "--out", str(U06_RAW),
        "--label", "final",
        "--profile", "cpu4x-net10mbps",
        "--phase5", "1",
    ]
    perf_net_log = LOGS_DIR / "12_perf_cpu4x-net10mbps.log"
    with open(perf_net_log, "w", encoding="utf-8") as log_f:
        res = subprocess.run(perf_net_cmd, cwd=str(REPO_ROOT), stdout=log_f, stderr=subprocess.STDOUT, text=True)
    print(f"U-06 cpu4x-net10mbps exit code: {res.returncode}")

finally:
    print("\n=== Shutting down server ===")
    server_proc.terminate()
    try:
        server_out, _ = server_proc.communicate(timeout=5)
    except Exception:
        server_proc.kill()
        server_out, _ = server_proc.communicate()
    with open(server_log_path, "w", encoding="utf-8") as f:
        f.write(server_out or "")
    print("Server stopped cleanly.")

