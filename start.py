"""Start LUNA-OPS with one command (Windows, macOS, Linux).

    python start.py --demo     # first look: test kernels + synthetic terrain (labelled, not lunar data)
    python start.py            # your registered NASA kernels and LOLA terrain (README steps 2-3)

It checks Python and the required packages, builds the interface once if needed
(Node 20+), prepares demo data if asked, picks a free port, starts the server and
opens your browser.

Demo mode keeps its kernels in data/kernels_demo and its synthetic terrain in
data/dem_demo, so the production kernels and the LOLA terrain registry in
data/dem are never read or changed by it. Keep this window open while
you use the app; press Ctrl+C to stop.
"""
from __future__ import annotations

import argparse
import os
import shutil
import socket
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
NEEDED = ["spiceypy", "numpy", "numba", "rasterio", "pyproj", "fastapi", "uvicorn", "pydantic", "PIL", "shapefile"]


def fail(msg: str) -> None:
    print("\nLUNA-OPS could not start:\n  " + msg.replace("\n", "\n  ") + "\n")
    sys.exit(1)


def free_port(start: int) -> int:
    for port in range(start, start + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    fail(f"No free port found between {start} and {start + 49}.")
    return start


def build_frontend(no_build: bool) -> None:
    """Build frontend/dist once with npm when it is missing (it is not kept in git)."""
    frontend = ROOT / "frontend"
    if (frontend / "dist" / "index.html").exists():
        return
    how = "  cd frontend && npm ci && npm run build"
    npm = shutil.which("npm")
    if no_build or npm is None:
        why = "--no-build was given" if no_build else "npm (Node 20 or later) was not found"
        fail(f"The built interface (frontend/dist) is missing and {why}. Build it once with\n{how}")
    print("Building the interface once (frontend/dist) with npm; this takes a minute ...")
    steps = ([[npm, "ci", "--no-audit", "--no-fund"]] if not (frontend / "node_modules").exists() else [])
    steps.append([npm, "run", "build"])
    for cmd in steps:
        if subprocess.run(cmd, cwd=frontend).returncode != 0:
            fail(f"`{' '.join(cmd[1:])}` failed in frontend/. Fix the error above, or build by hand with\n{how}")
    if not (frontend / "dist" / "index.html").exists():
        fail(f"The interface build finished but frontend/dist/index.html is missing. Build by hand with\n{how}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--demo", action="store_true", help="use labelled test kernels and synthetic terrain")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--no-build", action="store_true",
                    help="do not build frontend/dist automatically when it is missing (fail instead)")
    args = ap.parse_args()

    if sys.version_info < (3, 11):
        fail(f"Python 3.11 or newer is needed; this is {sys.version.split()[0]}.\n"
             "Install Python 3.11, 3.12 or 3.13 from python.org and run this file with it.")
    missing = []
    for mod in NEEDED:
        try:
            __import__(mod)
        except Exception:
            missing.append(mod)
    if missing:
        fail("These packages are missing: " + ", ".join(missing) + "\n"
             f"Install them with:\n  {Path(sys.executable).name} -m pip install -r \"{BACKEND / 'requirements.txt'}\"\n"
             "If installation fails, use Python 3.11, 3.12 or 3.13 (some scientific packages may lack wheels for newer versions).")
    build_frontend(args.no_build)

    if args.demo:
        os.environ["LUNAOPS_ALLOW_SYNTHETIC"] = "1"
        os.environ["LUNAOPS_KERNEL_SET"] = "demo"        # data/kernels_demo; production kernels are never touched
        # data/dem_demo: synthetic terrain gets its own registry; the LOLA registry in data/dem is never touched
        data_dir = Path(os.environ.get("LUNAOPS_DATA_DIR", ROOT / "data"))
        os.environ["LUNAOPS_DEM_DIR"] = str(data_dir / "dem_demo")
    sys.path.insert(0, str(BACKEND))
    from lunaops import settings
    from lunaops import acquire
    settings.ensure_dirs()
    from lunaops.engine.dem import broken_products, read_registry
    from lunaops.engine.kernels import migrate_misplaced_demo_lock

    moved = migrate_misplaced_demo_lock()
    if moved:
        print(moved)

    lock = settings.KERNEL_DIR / "lock.json"
    products = read_registry()["products"]
    if args.demo:
        if not lock.exists():
            print("Preparing labelled test kernels (downloads about 32 MB once) ...")
            try:
                acquire.main(["sandbox-kernels"])
            except SystemExit as exc:
                if exc.code not in (0, None):
                    fail("Downloading the test kernels failed. Check your internet connection; GitHub and PyPI must be reachable.")
            except Exception as exc:
                fail(f"Downloading the test kernels failed: {exc}\nCheck your internet connection; GitHub and PyPI must be reachable.")
        if not any(p.get("synthetic") for p in products):
            print("Creating synthetic test terrain in data/dem_demo (not lunar data) ...")
            acquire.main(["synthetic-terrain", "--kind", "hills"])
    else:
        if not lock.exists():
            print("Note: no production NASA kernels yet. Run `python -m lunaops.acquire kernels` in backend/, or use --demo.")
        if not any(not p.get("synthetic") for p in products):
            print("Note: no LOLA terrain registered yet (README step 3). Terrain results are withheld until then.")
        for _rec, why in broken_products():
            print(f"Note: {why}. Analyses that need it are refused until you restore it "
                  "(README step 3) or run `python -m lunaops.acquire unregister-dem`.")

    port = free_port(args.port)
    url = f"http://localhost:{port}"
    import uvicorn
    from lunaops.api.main import app
    # LUNA-OPS 2.0 Phase 5: preliminary landing screening. Its code (backend/lunaops_landing) is outside the validated
    # engine's code and suite fingerprints; it only adds /api/landing/* routes to the same app.
    from lunaops_landing.api import install as install_landing
    install_landing(app)
    # LUNA-OPS 2.0 Phase 6: preliminary communication simulation (backend/lunaops_comms, also outside both fingerprints);
    # it only adds /api/comms/* routes and reads completed engine analysis results.
    from lunaops_comms.api import install as install_comms
    install_comms(app)
    # Pre-Phase 7 audit AUD-06: corrected hillshade map images (backend/lunaops_tiles, outside both fingerprints). It
    # only adds /api/display/tiles/* routes; the engine's /api/tiles/meta and /api/tiles/* routes are unchanged.
    from lunaops_tiles.api import install as install_tiles
    install_tiles(app)

    print("\n" + "=" * 60)
    print(f"  LUNA-OPS is starting at  {url}")
    print("  Keep this window open while you use the app. Ctrl+C stops it.")
    if args.demo:
        print("  Demo mode: test kernels and synthetic terrain, labelled in the app.")
    print("=" * 60 + "\n")
    if not args.no_browser:
        threading.Timer(2.5, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
