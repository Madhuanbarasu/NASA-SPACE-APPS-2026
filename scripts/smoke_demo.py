"""End-to-end smoke test of `python start.py --demo` (used by CI; also runs locally).

    python scripts/smoke_demo.py [--port 8765] [--python backend/.venv/bin/python]

Starts the launcher in demo mode (test kernels in data/kernels_demo, synthetic terrain in
data/dem_demo, prebuilt frontend/dist), then checks over HTTP that the interface and API are
served, a site near the pole is covered, a one-day analysis completes and is labelled synthetic,
cross-origin requests from other sites are refused, the frontend route does not serve files
outside frontend/dist, and the LOLA registry data/dem/registry.json is unchanged.
Exit code 0 on success. Uses only the Python standard library.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "data" / "dem" / "registry.json"


def sha(p: Path) -> str | None:
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None


def http(url: str, data: dict | None = None, headers: dict | None = None, method: str | None = None):
    body = json.dumps(data).encode() if data is not None else None
    h = {"Content-Type": "application/json"} if body else {}
    h.update(headers or {})
    req = urllib.request.Request(url, data=body, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def check(cond: bool, msg: str) -> None:
    print(("PASS  " if cond else "FAIL  ") + msg, flush=True)
    if not cond:
        raise SystemExit(1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--startup-timeout", type=float, default=900.0)
    ap.add_argument("--job-timeout", type=float, default=1200.0)
    a = ap.parse_args()

    reg_before = sha(REGISTRY)
    proc = subprocess.Popen([a.python, str(ROOT / "start.py"), "--demo", "--no-browser", "--no-build",
                             "--port", str(a.port)], cwd=ROOT)
    try:
        base = None
        t0 = time.time()
        while time.time() - t0 < a.startup_timeout:
            if proc.poll() is not None:
                check(False, f"start.py exited early with code {proc.returncode}")
            for port in range(a.port, a.port + 5):     # start.py picks the next free port if needed
                try:
                    st, _, body = http(f"http://127.0.0.1:{port}/api/status")
                    if st == 200 and b"kernels" in body:
                        base = f"http://127.0.0.1:{port}"
                        break
                except OSError:
                    pass
            if base:
                break
            time.sleep(3)
        check(base is not None, f"server answered /api/status within {a.startup_timeout:.0f} s")
        print(f"      server at {base} after {time.time() - t0:.0f} s")

        st, _, body = http(base + "/api/status")
        status = json.loads(body)
        check(status["kernels"].get("kernel_set") == "demo" or "sandbox" in json.dumps(status["kernels"]).lower(),
              "demo kernel set is active")

        st, _, body = http(base + "/")
        check(st == 200 and b'<div id="root"' in body, "interface (frontend/dist/index.html) is served at /")

        st, _, body = http(base + "/api/coverage?lat=-89.5&lon=45")
        cov = json.loads(body)
        check(st == 200 and cov.get("covered") is True, f"site at -89.5, 45 is covered ({cov.get('finest')})")

        st, _, body = http(base + "/api/tiles/meta")
        check(st == 200 and json.loads(body).get("available") is True, "map tiles are available")

        req = {"lat": -89.5, "lon": 45.0, "start_utc": "2026-11-20T00:00:00", "end_utc": "2026-11-21T00:00:00"}
        st, _, body = http(base + "/api/analysis", req)
        check(st == 200, f"analysis accepted ({st})")
        sub = json.loads(body)
        rid = sub.get("result_id")
        if not rid:
            jid = sub["job_id"]
            t1 = time.time()
            while time.time() - t1 < a.job_timeout:
                job = json.loads(http(base + f"/api/jobs/{jid}")[2])
                if job["status"] in ("done", "error"):
                    break
                time.sleep(3)
            check(job["status"] == "done", f"analysis job finished: {job['status']} {job.get('error') or ''}")
            print(f"      job took {time.time() - t1:.0f} s (includes one-time numba compile)")
            rid = job["result_id"]
        st, _, body = http(base + f"/api/results/{rid}")
        res = json.loads(body)
        check(st == 200 and "intervals" in res, "result is served")
        lab = (res.get("labels", {}).get("horizon") or {}).get("validation")
        check(lab == "Synthetic test terrain - not a lunar result", f"result is labelled as synthetic test terrain ({lab!r})")

        st, hdr, _ = http(base + "/api/status", headers={"Origin": "https://evil.example"})
        check(not any(k.lower() == "access-control-allow-origin" for k in hdr), "other web origins get no CORS grant")
        st, hdr, _ = http(base + "/api/status", headers={"Origin": "http://localhost:5173"})
        check(any(k.lower() == "access-control-allow-origin" for k in hdr), "local dev origin gets a CORS grant")

        st, _, body = http(base + "/..%2F..%2Fbackend%2Flunaops%2Fsettings.py")
        check(b"SYNTHETIC_TERRAIN_ALLOWED" not in body, "frontend route does not serve files outside frontend/dist")

        check(sha(REGISTRY) == reg_before, "data/dem/registry.json is unchanged")
        print("Smoke test passed.")
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    sys.exit(main())
