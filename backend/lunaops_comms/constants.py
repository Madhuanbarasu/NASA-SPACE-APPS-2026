"""Physical constants for the communication simulation, each with its source.

The lunar gravitational parameter is read as text from NAIF's gm_de440.tpc in data/comms (SHA-256 checked against
data/comms/manifest.json). The kernel is never furnished into the SPICE pool the validated engine uses.
"""
from __future__ import annotations

import hashlib
import json
import re
from functools import lru_cache

from lunaops import settings

K_BOLTZMANN = 1.380649e-23        # J/K, exact (SI 2019 definition)
C_LIGHT = 299_792_458.0           # m/s, exact (SI)
R_MOON_KM = settings.R_MOON_M / 1000.0   # LOLA reference sphere used by the engine and the DEMs (1737.4 km)


class ConstantError(RuntimeError):
    pass


def comms_dir():
    return settings.DATA_DIR / "comms"


def _manifest() -> dict:
    p = comms_dir() / "manifest.json"
    if not p.exists():
        raise ConstantError(f"{p} is missing; the lunar GM source is not installed.")
    return json.loads(p.read_text())


def parse_text_kernel_value(text: str, name: str) -> float:
    """Value of `name = ( v )` in a NAIF text kernel's \\begindata blocks (Fortran D exponents accepted)."""
    data = []
    on = False
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("\\begindata"):
            on = True
            continue
        if s.startswith("\\begintext"):
            on = False
            continue
        if on:
            data.append(line)
    m = re.search(rf"(?<![A-Z0-9_]){re.escape(name)}\s*=\s*\(\s*([-+0-9.EeDd]+)\s*\)", "\n".join(data))
    if not m:
        raise ConstantError(f"{name} not found in the kernel's data blocks.")
    return float(m.group(1).replace("D", "E").replace("d", "e"))


@lru_cache(maxsize=1)
def moon_gm() -> dict:
    """{'gm_km3_s2', 'source', 'sha256', ...} for BODY301_GM, verified against the manifest's SHA-256."""
    man = _manifest()
    e = next((f for f in man.get("files", []) if f.get("name") == "gm_de440.tpc"), None)
    if e is None:
        raise ConstantError("gm_de440.tpc is not listed in data/comms/manifest.json.")
    p = comms_dir() / e["path"]
    if not p.is_file():
        raise ConstantError(f"{p} is missing.")
    b = p.read_bytes()
    sha = hashlib.sha256(b).hexdigest()
    if sha != e.get("sha256") or len(b) != e.get("bytes"):
        raise ConstantError("gm_de440.tpc does not match the SHA-256 or size recorded in data/comms/manifest.json.")
    gm = parse_text_kernel_value(b.decode("ascii", errors="replace"), "BODY301_GM")
    return {"gm_km3_s2": gm, "name": "BODY301_GM", "file": e["name"], "sha256": sha, "source_url": e.get("source_url"),
            "citation": "DE440 (Park, Folkner, Williams and Boggs 2021, AJ 161:105, doi:10.3847/1538-3881/abd414) via NAIF gm_de440.tpc",
            "loaded_into_spice_pool": False}
