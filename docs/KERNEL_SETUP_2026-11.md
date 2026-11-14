# Production kernel setup, 2026-11-07

Starting point: the audited build (luna-ops.zip, SHA-256 `d9bff31ea18a5aacb35b497f91bcf01274b18e9b3259df6ee7f480872f39149b`). Scope: production SPICE kernels from the pinned manifest, separation of production and demo kernels, verification of files, checksums, lock.json and loading, V-02e. No terrain was downloaded and no engine algorithm was changed.

## Outcome in the build sandbox

- **The production kernels could not be downloaded here.** naif.jpl.nasa.gov does not resolve from the build sandbox; `python -m lunaops.acquire kernels` stops at the first file with "Name or service not known" and, with this build, changes nothing.
- **V-02e has not run** (it needs the production DE440 set plus the DE421 lunar PCK/FK). It stays skipped and every result stays "Pending validation".
- Everything below was tested with the demo kernel set and synthetic inputs; the PowerShell script was run with PowerShell 7.6.9 on Linux, including a mocked download to exercise its checks.

## Facts checked against NAIF (read 2026-11-07)

| Item | Value | Source |
| --- | --- | --- |
| `naif0012.tls` | 5,257 bytes, MD5 `25a2fff30b0dedb4d76c06727b1895b1` | NAIF PDS4 label, InSight SPICE archive `spice_kernels/lsk/naif0012.xml` |
| `moon_de440_250416.tf` | 19,478 bytes, MD5 `3556dde4bb7ca54a89917c301e650bbf` | NAIF PDS4 label, CLPS SPICE archive `spice_kernels/fk/moon_de440_250416.xml` |
| Companion FK of `moon_pa_de440_200625.bpc` | `moon_de440_220930.tf` in `generic_kernels/fk/satellites` | NAIF `generic_kernels/pck/aareadme.txt`, revised 2026-10-03 |
| Companion FK of `moon_pa_de440_200625.bpc` (rechecked 2026-11-09) | `moon_de440_250416.tf`; 220930 is now in `fk/satellites/a_old_versions/` and its former URL returns 404 | NAIF `generic_kernels/fk/satellites/aareadme.txt`, revised 2025-04-16, and the folder listings |
| `moon_de440_200625.tf` (first DE440 lunar FK) | does not map the `MOON_PA`/`MOON_ME` aliases | its own header (`fk/satellites/a_old_versions/`) |

Not obtained from NAIF: `aa_checksums.txt` for the planets directory (its layout is undocumented to us, so both parsers now accept any common layout), and checksums for `pck00011.tpc`, `moon_pa_de440_200625.bpc` and the DE421 files (trusted on first download, SHA-256 then pinned). The demo copy of `de440s.bsp` has MD5 `3917ee56769db332790c751e2168843d`, the value two independent projects report as NAIF's; that was not confirmed from NAIF and the file stays in the demo set.

## Changes

- **Separate kernel sets** (`settings.py`, `engine/kernels.py`, `start.py`, `tests/conftest.py`, `validation/__init__.py`). Production: `data/kernels`, profile `production`. Demo: `data/kernels_demo`, profile `sandbox-test`. `LUNAOPS_KERNEL_SET` selects one (`start.py --demo` sets `demo`). The loader refuses a lock whose profile does not belong to the selected folder. A demo set left in `data/kernels` by an earlier version is moved to `data/kernels_demo` by `start.py`, `acquire kernels` and `acquire sandbox-kernels` (nothing is deleted). Tests and validation scripts use the production set when installed, otherwise the demo set.
- **Install pipeline** (`acquire kernels`). Staging folder; published size and MD5 checks (mismatch rejects the file and tries the next URL or the fallback); NAIF `aa_checksums.txt` check for `de440s.bsp`; SPICE test load of the staged set (frames, coverage, radii); commit with `lock.json` last and the previous set kept in `superseded_<UTC>/`. Failure at any step leaves the installed set unchanged. `--from-dir` installs manually downloaded files through the same checks. The lock now records the manifest's SHA-256, per-file check results, and how each file was obtained.
- **`acquire verify-kernels`** re-checks a set (sizes, SHA-256 against the lock, NAIF-published values, test load) and reports whether V-02e can run; non-zero exit on any problem. `acquire status` lists both sets. `/api/status` reports the active set.
- **Manifest** (`kernels.production.json`). Pinned files unchanged. Added NAIF-published size/MD5 for `naif0012.tls` and `moon_de440_250416.tf`; the fallback FK `moon_de440_220930.tf` now tries `generic_kernels/fk/satellites/` (the readme's location) before `a_old_versions/`; the IB-2 conflict is recorded as `open_issue`. *(Superseded 2026-11-09: the 404 `fk/satellites/moon_de440_220930.tf` URL was removed and IB-2 is recorded as `resolved_issue`; see Open issues, item 1.)*
- **`scripts/get_production_kernels.ps1`** for Windows when Python cannot reach NAIF: downloads, checks published values, then runs `acquire kernels --from-dir` and `verify-kernels`.

## Open issues

1. **IB-2 (resolved 2026-11-09, Phase 4 A3):** `moon_de440_250416.tf` is the authoritative DE440 lunar FK. NAIF's `fk/satellites/aareadme.txt` (2025-04-16) names it; `moon_de440_220930.tf` has moved to `fk/satellites/a_old_versions/` (its former URL returns 404), so the PCK readme's reference is out of date. Both define `MOON_PA_DE440` and `MOON_ME_DE440_ME421` identically, and the transformations are bitwise identical. The manifest records `resolved_issue` and lists only the `a_old_versions` fallback URL; `scripts/get_production_kernels.ps1` matches. `moon_080317.tf` (DE421) is kept for V-02e. Evidence: `docs/validation_evidence/ib2_2026-11-09/`.
2. Four of the eight pinned kernels have no NAIF-published checksum (trust on first download).
3. V-02e, V-04, V-05, V-09 to V-13, U-04 and U-06 remain to be run with production kernels and references.
