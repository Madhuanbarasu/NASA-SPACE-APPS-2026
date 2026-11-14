"""Phase 4 A3 (IB-2): lunar frame names and the DE440 / DE421 frame kernels.

moon_de440_250416.tf (DE440 frames) and moon_080317.tf (DE421 frames, V-02e only) both define the generic alias
frames MOON_PA (31000) and MOON_ME (31001). The DE421 kernel is loaded last, so in a production session the
aliases resolve to the DE421 frames, up to about 0.9 m from MOON_ME_DE440_ME421 at the surface. These tests make
sure that cannot reach a result: the engine names every frame explicitly, and its DE440 transformations are
bitwise the same whether or not the DE421 kernels are loaded. Evidence: docs/validation_evidence/ib2_2026-11-09/.
"""
from __future__ import annotations

import ast
from pathlib import Path

import numpy as np
import pytest

from conftest import needs_kernels

BACKEND = Path(__file__).resolve().parents[1]
GENERIC = {"MOON_ME", "MOON_PA"}


def test_no_generic_lunar_frame_names_in_engine_source():
    """No string in lunaops/ or validation/ is exactly a generic alias frame name (MOON_ME, MOON_PA), in any
    case; the explicit names (MOON_ME_DE440_ME421, MOON_PA_DE440, MOON_ME_DE421, ...) are what the code uses."""
    hits = []
    for root in ("lunaops", "validation"):
        for path in sorted((BACKEND / root).rglob("*.py")):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                        and node.value.strip().upper() in GENERIC:
                    hits.append(f"{path.relative_to(BACKEND)}:{node.lineno}: {node.value!r}")
    assert not hits, hits


@needs_kernels
def test_engine_frame_arguments_are_explicit(kernels, synthetic_crater, monkeypatch):
    """Every frame the engine passes to SPICE during a full analysis (Sun and Earth sampling, Earth pole, event
    detection, eclipses, series) is either J2000 or the lock's body-fixed frame; never a generic alias."""
    import spiceypy as sp
    from lunaops.engine.analysis import AnalysisRequest, analyze

    seen: list[tuple[str, str]] = []
    positions = {"sxform": (0, 1), "pxform": (0, 1), "spkcpo": (2, 7), "spkezr": (2,), "spkpos": (2,),
                 "azlcpo": (8,), "spkcvo": (2, 7)}
    for name, idx in positions.items():
        real = getattr(sp, name)

        def spy(*args, _real=real, _name=name, _idx=idx, **kw):
            for i in _idx:
                if i < len(args) and isinstance(args[i], str):
                    seen.append((_name, args[i]))
            return _real(*args, **kw)
        monkeypatch.setattr(sp, name, spy)
    analyze(AnalysisRequest(lat=-89.0, lon=45.0, start_utc="2026-11-14T00:00:00Z", end_utc="2026-11-15T00:00:00Z",
                            dte_rule="any"))
    frames = {f for _, f in seen}
    assert seen, "no SPICE frame calls were observed"
    assert frames <= {"J2000", kernels.frame}, frames
    assert not {f.upper() for f in frames} & GENERIC


@needs_kernels
def test_de440_transformations_identical_without_de421_kernels(kernels):
    """Production set only. With the DE421 PCK and FK loaded (the production session) and after unloading them,
    the J2000 -> MOON_ME_DE440_ME421 rotation and state transformation, the topocentric Sun and Earth states and
    the engine's Sun and Earth samples (az, el, radii, Earth limb extents) are bitwise identical over 1900-2050.
    Also records the alias behaviour that makes explicit names necessary."""
    import spiceypy as sp
    from lunaops.engine import kernels as K
    from lunaops.engine.ephem import Site, sample_target

    if kernels.profile != "production" or not kernels.de421_available:
        pytest.skip("needs the production DE440 kernels plus the DE421 lunar PCK/FK")
    frame = kernels.frame
    assert frame == "MOON_ME_DE440_ME421"
    ets = np.linspace(sp.str2et("1900-01-02T00:00:00"), sp.str2et("2049-12-31T00:00:00"), 400)
    site = Site(-89.463163, 222.510447, 0.0, 0.0)

    def snapshot():
        out = {"pxform": np.array([sp.pxform("J2000", frame, float(e)) for e in ets]),
               "sxform": np.array([sp.sxform("J2000", frame, float(e)) for e in ets])}
        for tgt in ("SUN", "EARTH"):
            out[tgt] = np.array([sp.spkcpo(tgt, float(e), frame, "OBSERVER", "CN+S", site.pos_km, "MOON", frame)[0]
                                 for e in ets[::4]])
        for tgt in ("sun", "earth"):
            s = sample_target(site, tgt, ets[::4])
            out[f"{tgt}_azel"] = np.stack([s.az, s.el, s.rho, s.dist_km])
            if tgt == "earth":
                out["earth_limb"] = np.stack([s.earth["rho_up"], s.earth["rho_down"], s.earth["delta_max"]])
        return out

    def alias():
        c = sp.namfrm("MOON_ME")
        return c, sp.gcpool(f"TKFRAME_{c}_RELATIVE", 0, 1)[0]

    try:
        with_de421 = snapshot()
        alias_with = alias()
        loaded = [sp.kdata(i, "ALL")[0] for i in range(sp.ktotal("ALL"))]
        de421 = [p for p in loaded if Path(p).name in ("moon_080317.tf", "moon_pa_de421_1900-2050.bpc")]
        assert len(de421) == 2, loaded
        for p in de421:
            sp.unload(p)
        assert sp.namfrm("MOON_ME_DE421") == 0                     # really unloaded
        without = snapshot()
        alias_without = alias()
    finally:
        K.reset()
        K.load()
    for key in with_de421:
        assert np.array_equal(with_de421[key], without[key]), key
    # the generic alias follows the last-loaded FK: DE421 in the production session, DE440 without it
    assert alias_with == (31001, "MOON_ME_DE421"), alias_with
    assert alias_without == (31001, "MOON_ME_DE440_ME421"), alias_without


@needs_kernels
def test_installed_frame_kernels_match_the_ib2_decision(kernels):
    """Production set only: the lock's DE440 FK is moon_de440_250416.tf with NAIF's published MD5, and the DE421
    FK is moon_080317.tf; no fallback was used."""
    if kernels.profile != "production":
        pytest.skip("checks the production lock")
    by = {f["role"]: f for f in kernels.files}
    assert by["lunar_fk"]["name"] == "moon_de440_250416.tf"
    assert by["lunar_fk"].get("naif_md5_match") is True and "notes" not in by["lunar_fk"]
    assert by["de421_fk"]["name"] == "moon_080317.tf"
