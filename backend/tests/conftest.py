"""Test fixtures.

Kernel tests use the production kernel set in $LUNAOPS_DATA_DIR/kernels (or data/kernels)
when one is installed, otherwise the demo set in data/kernels_demo, so the validation
report always describes the kernels in use. The profile (production or sandbox-test) is recorded in the report, and
a sandbox run can never mark production results Validated.
"""
from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
_app_data = Path(os.environ.get("LUNAOPS_DATA_DIR", REPO / "data"))


def _pick_source() -> Path:
    """The production set if one is installed, otherwise the demo set (or LUNAOPS_KERNEL_SOURCE)."""
    if os.environ.get("LUNAOPS_KERNEL_SOURCE"):
        return Path(os.environ["LUNAOPS_KERNEL_SOURCE"])
    for d in (_app_data / "kernels", _app_data / "kernels_demo"):
        if (d / "lock.json").exists():
            return d
    return _app_data / "kernels"


SRC_KERNELS = _pick_source()
SRC_PROFILE = None
if (SRC_KERNELS / "lock.json").exists():
    import json as _json
    SRC_PROFILE = _json.loads((SRC_KERNELS / "lock.json").read_text()).get("profile")
# copy into the folder the profile belongs to, and select that set for this test session
_SET = "production" if SRC_PROFILE == "production" else "demo"
_dest_name = "kernels" if _SET == "production" else "kernels_demo"

_tmp = Path(tempfile.mkdtemp(prefix="lunaops_test_"))
(_tmp / _dest_name).mkdir()
if (SRC_KERNELS / "lock.json").exists():
    for f in SRC_KERNELS.iterdir():
        if f.is_file():
            try:
                os.link(f, _tmp / _dest_name / f.name)      # fast on one filesystem
            except OSError:
                shutil.copy2(f, _tmp / _dest_name / f.name)  # Windows or cross-device
os.environ["LUNAOPS_DATA_DIR"] = str(_tmp)
os.environ["LUNAOPS_ALLOW_SYNTHETIC"] = "1"
os.environ["LUNAOPS_KERNEL_SET"] = _SET
# The test data folder is temporary; real PGDA files (if the user has them) stay in the repo's data/dem.
# List it explicitly so tests that copy the committed registry can resolve its relative paths there.
os.environ["LUNAOPS_DEM_FALLBACK_DIRS"] = str(REPO / "data" / "dem")


def pytest_sessionfinish(session, exitstatus):
    """Remove this session's temporary data folder (hard links only; source kernels are untouched)."""
    shutil.rmtree(_tmp, ignore_errors=True)


HAVE_KERNELS = (SRC_KERNELS / "lock.json").exists()
needs_kernels = pytest.mark.skipif(not HAVE_KERNELS, reason="no kernel lock (run lunaops.acquire kernels)")


@pytest.fixture(scope="session")
def kernels():
    if not HAVE_KERNELS:
        pytest.skip("no kernel lock")
    from lunaops.engine.kernels import load
    return load()


def _register_synthetic(kind: str, specs) -> dict:
    from lunaops import settings
    from lunaops.acquire import _basic_info
    from lunaops.engine.dem import read_registry, write_registry
    from lunaops.engine.kernels import sha256_of
    from lunaops.testing import write_synthetic_dem

    out = settings.DEM_DIR / "synthetic"
    out.mkdir(parents=True, exist_ok=True)
    reg = read_registry()
    reg["products"] = [p for p in reg["products"] if not p.get("synthetic")]
    for level, pixel, half in specs:
        p = out / f"SYNTH_{kind.upper()}_{level}.tif"
        if not p.exists():
            write_synthetic_dem(p, pixel, half, kind=kind)
        reg["products"].append({"level": level, "product_id": f"synthetic_{level}", "path": str(p),
                                "sha256": sha256_of(p), "bytes": p.stat().st_size,
                                "product": f"SYNTHETIC TEST TERRAIN ({kind})", "synthetic": True, "pixel_m": pixel,
                                **_basic_info(p)})
    write_registry(reg)
    return reg


@pytest.fixture(scope="session")
def synthetic_crater():
    return _register_synthetic("crater", (("20m", 20.0, 45_000.0), ("240m", 240.0, 300_000.0)))
