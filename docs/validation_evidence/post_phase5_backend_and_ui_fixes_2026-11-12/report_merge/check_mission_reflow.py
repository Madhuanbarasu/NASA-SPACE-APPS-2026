"""Run U-04 live audit on the active Mission Dashboard at 320 px post-merge.
Starts the server with the newly merged report.json and measures the reflow.
"""
import os
import sys
import time
import json
import subprocess
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
REPORT_MERGE_DIR = REPO_ROOT / "docs" / "validation_evidence" / "post_phase5_backend_and_ui_fixes_2026-11-12" / "report_merge"
OUT_DIR = REPORT_MERGE_DIR / "u04_postmerge"
OUT_DIR.mkdir(parents=True, exist_ok=True)

PYTHON_EXE = str(REPO_ROOT / "backend" / ".venv" / "Scripts" / "python.exe")
PORT = 8765
BASE_URL = f"http://127.0.0.1:{PORT}"

print(f"=== Starting LUNA-OPS server on {BASE_URL} with newly merged report.json ===")
server_proc = subprocess.Popen(
    [PYTHON_EXE, "start.py", "--no-browser", "--no-build", "--port", str(PORT)],
    cwd=str(REPO_ROOT),
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
)

try:
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

    # Run U-04 audit
    print("\n--- Running U-04 live accessibility audit (post-merge) ---")
    u04_cmd = [
        "node",
        "frontend/scripts/a11y-live-audit.mjs",
        "--base", BASE_URL,
        "--out", str(OUT_DIR),
        "--label", "postmerge",
    ]
    u04_log = REPORT_MERGE_DIR / "u04_postmerge.log"
    with open(u04_log, "w", encoding="utf-8") as log_f:
        res = subprocess.run(u04_cmd, cwd=str(REPO_ROOT), stdout=log_f, stderr=subprocess.STDOUT, text=True)
    print(f"U-04 audit exit code: {res.returncode}")

finally:
    print("\n=== Shutting down server ===")
    server_proc.terminate()
    try:
        server_out, _ = server_proc.communicate(timeout=5)
    except Exception:
        server_proc.kill()
        server_out, _ = server_proc.communicate()
    print("Server stopped cleanly.")

audit_file = OUT_DIR / "audit-postmerge.json"
if audit_file.exists():
    d = json.loads(audit_file.read_text(encoding="utf-8"))
    for v in d.get("views", []):
        if v.get("view") == "mission":
            print("\n=== MISSION VIEW RESULTS AT 320px ===")
            reflow = v.get("reflow320", {})
            print(f"docScrollW: {reflow.get('docScrollW')}")
            print(f"horizontalScroll: {reflow.get('horizontalScroll')}")
            print(f"offenders: {reflow.get('offenders')}")
            print(f"offenderCount: {reflow.get('offenderCount')}")

