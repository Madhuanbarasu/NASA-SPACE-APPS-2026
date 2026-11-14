"""SPICE kernel loading (blueprint Sections 5.2, 7.1, 7.3; Q15).

Kernels are loaded only from a lock.json, which records each file's role,
source URL, retrieval time and SHA-256. Every load re-hashes the files, so a
silently replaced kernel is refused, not used.

Production NAIF kernels live in data/kernels (profile "production"); demo/test
kernels live in data/kernels_demo (profile "sandbox-test"). The folder selected
by settings.KERNEL_SET must hold a lock of the matching profile, so a demo set
can never be loaded as production or the reverse.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import threading
from datetime import datetime, timezone
from dataclasses import dataclass, field
from pathlib import Path

import spiceypy as sp

from .. import settings

# CSPICE is not thread-safe: every SPICE call in LUNA-OPS goes through this lock.
SPICE_LOCK = threading.RLock()

LOAD_ORDER = ["lsk", "text_pck", "spk", "lunar_pck", "lunar_fk", "lunar_fk_assoc"]
OPTIONAL_ROLES = ["de421_pck", "de421_fk"]


class KernelError(RuntimeError):
    pass


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class KernelSet:
    profile: str
    frame: str
    pa_frame: str | None
    files: list[dict]
    coverage_utc: tuple[str, str]
    coverage_et: tuple[float, float]
    moon_radii_km: tuple[float, float, float]
    warnings: list[str] = field(default_factory=list)
    de421_available: bool = False

    def provenance(self) -> list[dict]:
        return [
            {k: f.get(k) for k in ("role", "name", "sha256", "bytes", "source", "retrieved_utc", "notes")}
            for f in self.files
        ]


_loaded: KernelSet | None = None


# which lock profile each folder may hold
PROFILE_FOR_SET = {"production": "production", "demo": "sandbox-test"}


def lock_path(kernel_dir: Path | None = None) -> Path:
    return (kernel_dir or settings.KERNEL_DIR) / "lock.json"


def read_lock(kernel_dir: Path | None = None) -> dict:
    p = lock_path(kernel_dir)
    if not p.exists():
        if (kernel_dir or settings.KERNEL_DIR) == settings.DEMO_KERNEL_DIR:
            raise KernelError("No demo kernel lock. Run `python start.py --demo` or "
                              "`python -m lunaops.acquire sandbox-kernels`.")
        raise KernelError(
            "No production kernel lock. Run `python -m lunaops.acquire kernels` to download the "
            "pinned NAIF kernels (see README), or start with `python start.py --demo` for test kernels."
        )
    return json.loads(p.read_text())


def migrate_misplaced_demo_lock() -> str | None:
    """Move a sandbox-test kernel set out of the production folder (layout used before separation).

    Returns a message when something was moved. Nothing is deleted: if the demo folder already has
    a lock, the misplaced set goes to kernels_demo/superseded_<UTC>/.
    """
    prod = settings.PRODUCTION_KERNEL_DIR
    lp = prod / "lock.json"
    if not lp.exists():
        return None
    try:
        lock = json.loads(lp.read_text())
    except Exception:
        return None
    if lock.get("profile") != "sandbox-test":
        return None
    target = settings.DEMO_KERNEL_DIR
    if (target / "lock.json").exists():
        target = target / ("superseded_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    target.mkdir(parents=True, exist_ok=True)
    for f in lock.get("files", []):
        src = prod / f["name"]
        if src.exists():
            shutil.move(str(src), str(target / f["name"]))
    shutil.move(str(lp), str(target / "lock.json"))
    return f"Moved the sandbox test kernels from {prod} to {target} (production and demo kernels are now kept apart)."


def _coverage(spk_paths: list[str], pck_paths: list[str]) -> tuple[float, float]:
    """Intersection of SPK coverage (Moon, Earth, Sun) and lunar PCK coverage."""
    lo, hi = -1e300, 1e300
    for spk in spk_paths:
        for body in (301, 399, 10):
            cell = sp.cell_double(20000)
            try:
                sp.spkcov(spk, body, cell)
            except Exception:
                continue
            n = sp.wncard(cell)
            if n == 0:
                continue
            b0, _ = sp.wnfetd(cell, 0)
            _, b1 = sp.wnfetd(cell, n - 1)
            lo, hi = max(lo, b0), min(hi, b1)
    for pck in pck_paths:
        ids = sp.cell_int(100)
        sp.pckfrm(pck, ids)
        for i in range(sp.card(ids)):
            cell = sp.cell_double(20000)
            sp.pckcov(pck, ids[i], cell)
            n = sp.wncard(cell)
            if n:
                b0, _ = sp.wnfetd(cell, 0)
                _, b1 = sp.wnfetd(cell, n - 1)
                lo, hi = max(lo, b0), min(hi, b1)
    if lo >= hi:
        raise KernelError("Kernel coverage windows do not overlap")
    return lo, hi


def _load_set(kernel_dir: Path, lock: dict, verify: bool = True) -> KernelSet:
    """Furnish the kernels of `lock` from `kernel_dir`, verify them and describe the set (no caching)."""
    files = sorted(
        lock["files"],
        key=lambda f: (LOAD_ORDER + OPTIONAL_ROLES).index(f["role"])
        if f["role"] in LOAD_ORDER + OPTIONAL_ROLES else 99,
    )
    roles = {f["role"] for f in files}
    missing = [r for r in ("lsk", "spk", "lunar_pck", "lunar_fk") if r not in roles]
    if missing:
        raise KernelError(f"Kernel lock is missing required roles: {missing}")
    warnings: list[str] = []
    with SPICE_LOCK:
        sp.kclear()
        spk_paths, pck_paths = [], []
        de421 = False
        for f in files:
            path = kernel_dir / f["name"]
            if not path.exists():
                if f["role"] in OPTIONAL_ROLES:
                    continue
                raise KernelError(f"Kernel file missing: {path}")
            if verify:
                digest = sha256_of(path)
                if digest != f["sha256"]:
                    raise KernelError(
                        f"SHA-256 mismatch for {f['name']}: lock {f['sha256'][:12]}..., file {digest[:12]}..."
                    )
            sp.furnsh(str(path))
            if f["role"] == "spk":
                spk_paths.append(str(path))
            if f["role"] in ("lunar_pck",):
                pck_paths.append(str(path))
            if f["role"] in ("de421_pck", "de421_fk"):
                de421 = True
        frame = lock["body_fixed_frame"]
        if sp.namfrm(frame) == 0:
            raise KernelError(f"Frame {frame} is not defined by the loaded kernels (V-02a)")
        dim, radii = sp.bodvrd("MOON", "RADII", 3)
        radii = tuple(float(r) for r in radii)
        if any(abs(r - settings.R_MOON_M / 1000.0) > 1e-6 for r in radii):
            warnings.append(
                f"Kernel Moon radii {radii} km differ from the LOLA 1737.4 km sphere; the engine uses 1737.4 km."
            )
        et0, et1 = _coverage(spk_paths, pck_paths)
        cov_utc = (sp.et2utc(et0, "ISOC", 0), sp.et2utc(et1, "ISOC", 0))
        if de421 and sp.namfrm("MOON_ME_DE421") == 0:
            de421 = False
            warnings.append("DE421 validation kernels are listed but MOON_ME_DE421 is not defined; V-02e cannot run.")
    if lock.get("profile") != "production":
        warnings.append(
            "Sandbox test kernels are loaded. They are for automated tests only; results are not "
            "production results. Run `python -m lunaops.acquire kernels` for the pinned NAIF set."
        )
    for f in files:
        if f.get("notes"):
            warnings.append(f"{f['name']}: {f['notes']}")
    return KernelSet(
        profile=lock.get("profile", "unknown"),
        frame=frame,
        pa_frame=lock.get("pa_frame"),
        files=files,
        coverage_utc=cov_utc,
        coverage_et=(et0, et1),
        moon_radii_km=radii,
        warnings=warnings,
        de421_available=de421,
    )


def check_set(kernel_dir: Path, lock: dict | None = None) -> KernelSet:
    """Load a kernel set from any folder as a check, then unload it (used before installing a set)."""
    global _loaded
    lock = lock if lock is not None else read_lock(kernel_dir)
    try:
        return _load_set(kernel_dir, lock, verify=True)
    finally:
        with SPICE_LOCK:
            sp.kclear()
        _loaded = None


def load(verify: bool = True) -> KernelSet:
    """Load (once) the kernels listed in the active folder's lock file, verifying SHA-256."""
    global _loaded
    if _loaded is not None:
        return _loaded
    lock = read_lock()
    want = PROFILE_FOR_SET[settings.KERNEL_SET]
    got = lock.get("profile")
    if got != want:
        if settings.KERNEL_SET == "production" and got == "sandbox-test":
            raise KernelError(
                f"{settings.KERNEL_DIR} holds the sandbox TEST kernel set, not production kernels. Run "
                "`python -m lunaops.acquire kernels` (it moves the test set to data/kernels_demo first), "
                "or start with `python start.py --demo`."
            )
        raise KernelError(f"{settings.KERNEL_DIR} holds a '{got}' kernel lock; the {settings.KERNEL_SET} "
                          f"kernel set requires profile '{want}'.")
    _loaded = _load_set(settings.KERNEL_DIR, lock, verify=verify)
    return _loaded


def reset() -> None:
    """Forget loaded kernels (used by tests)."""
    global _loaded
    with SPICE_LOCK:
        sp.kclear()
    _loaded = None
