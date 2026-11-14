# IB-2: lunar frame kernel (Phase 4, A3), resolved 2026-11-09

**Decision (approved):** `moon_de440_250416.tf` is the authoritative DE440 lunar frame kernel. `moon_de440_220930.tf`
remains only as a manifest fallback, from NAIF's `a_old_versions` folder. `moon_de440_250416.tf` provides
`MOON_PA_DE440` and the engine frame `MOON_ME_DE440_ME421`. `moon_080317.tf` is retained for the DE421 frames that
V-02e compares against.

**Run conditions:**
- Production kernels as installed in A1 (`../kernels_production_2026-11-08/`).
- SpiceyPy 8.3.0 (CSPICE N0067), code at `d2c9229` (algorithm 1.5.0).
- Only small NAIF text files were fetched, on 2026-11-08/09.

## Findings

1. **What IB-2 was:** NAIF's `generic_kernels/pck/aareadme.txt` (revised 2026-10-03) names `moon_de440_220930.tf`,
   "located in the path pub/naif/generic_kernels/fk/satellites", as the frame kernel for
   `moon_pa_de440_200625.bpc`. The manifest pinned the newer `moon_de440_250416.tf`.
2. **NAIF's frame-kernel folder** (`naif/fk_satellites_listing.html`, `naif/fk_satellites_a_old_versions_listing.html`):
   - `generic_kernels/fk/satellites/` holds `moon_de440_250416.tf` (2025-04-16) and `moon_080317.tf`.
   - `moon_de440_220930.tf` (2022-09-30) is in `fk/satellites/a_old_versions/`, with `moon_de440_200625.tf`.
   - Its former URL `fk/satellites/moon_de440_220930.tf` returns HTTP 404 (rechecked 2026-11-09).
3. **NAIF's frame-kernel readme** (`naif/fk_satellites_aareadme.txt`, revised 2025-04-16) lists
   `moon_de440_250416.tf` as "DE440 version … The cited frame kernel is to be used with the binary lunar PCK
   moon_pa_de440_200625.bpc". The PCK readme's reference to 220930 is therefore out of date.
4. **Provenance of the installed file:** 19,478 bytes, MD5 `3556dde4bb7ca54a89917c301e650bbf`, matching its NAIF
   PDS4 label (`naif/moon_de440_250416_pds4_label.xml`). It was installed from `generic_kernels/fk/satellites` on
   2026-11-08, and its SHA-256 `a47c71e9…f9cf768` is pinned in the lock. Hashes of all three kernels are in
   `comparison/kernel_hashes.txt`.
5. **Definitions** (`comparison/data_sections.diff`, `comparison/moon_de440_220930_vs_250416_full.diff`):
   - The data sections of 220930 and 250416 differ **only** in the ID codes of the generic alias frames: `MOON_PA`
     and `MOON_ME` are 31010/31011 in 220930 and 31000/31001 in 250416.
   - `MOON_PA_DE440` (31008, PCK class) and `MOON_ME_DE440_ME421` (31009, angles 67.8526″, 78.6944″, 0.2785″
     about axes 3, 2, 1 from `MOON_PA_DE440`) are identical in both.
   - 250416's own notes: the alias IDs "have been reset to their respective, original values 31000, 31001 …
     These codes will remain unchanged in future revisions". The note names the previous file
     `moon_pa_de440_220930.tf`, a typo for `moon_de440_220930.tf`.
6. **The DE421 kernel is not an alternative.** `moon_080317.tf` (`comparison/moon_080317_data_section.txt`) defines
   `MOON_PA_DE421` (31006), `MOON_ME_DE421` (31007, 67.92″, 78.56″, 0.30″), `MOON_PA_DE403`, and the same generic
   aliases `MOON_PA` (31000) and `MOON_ME` (31001), pointing at the DE421 frames. It cannot provide
   `MOON_ME_DE440_ME421`.
7. **Numerical comparison** (`comparison/fk_compare.py`, `comparison/fk_compare_output.txt`), 2,001 epochs over
   1900–2050 with the same DE440 PCK:
   - The J2000 → `MOON_ME_DE440_ME421` rotation and the topocentric Sun and Earth directions at PGDA 78 Site01
     are **bitwise identical** in all four set-ups: 250416 alone, 220930 alone, and each followed by the DE421
     PCK and FK, as in the production load order.
   - With the DE421 kernels loaded last, the generic `MOON_ME` resolves to `MOON_ME_DE421`. That is up to 0.863 m
     from `MOON_ME_DE440_ME421` at the surface between 1900 and 2050.
8. **Engine:** it passes SPICE only `J2000` and the lock's frame (`MOON_ME_DE440_ME421`) and never a generic alias.
   The new tests check this.

## Effect
- No result or validation changes: transformations are bitwise identical whichever DE440 frame kernel is loaded.
- No kernel, lock, checksum, tolerance or algorithm-version change.
- V-02a to V-02e, V-03, the golden tests and the 2026-11-09 validation report are unaffected.

## Changes made for the resolution
- **`backend/lunaops/manifests/kernels.production.json`, `lunar_fk` entry:**
  - `open_issue` is replaced by `resolved_issue`;
  - the obsolete fallback URL `generic_kernels/fk/satellites/moon_de440_220930.tf` (404) is removed, leaving
    `fk/satellites/a_old_versions/moon_de440_220930.tf`;
  - the fallback reason and evidence text are updated.
- **Tests:**
  - `tests/test_phase4_frames.py`: no generic alias name anywhere in `lunaops/` or `validation/`; every frame the
    engine passes to SPICE during a full analysis is J2000 or the lock frame; production-only, DE440
    transformations and engine Sun/Earth samples bitwise identical with and without the DE421 kernels, and the
    installed frame kernels match this decision.
  - `test_kernel_setup.py::test_production_manifest_is_pinned_and_checkable`: asserts the new fallback URL list
    and the resolved issue.
- **Documentation:** README, `docs/KERNEL_SETUP_2026-11.md`, `docs/AUDIT_2026-11.md`.

## Remaining uncertainty
NAIF has not changed the PCK readme. The conclusion rests on NAIF's frame-kernel folder, its own readme and the
identical definitions, not on an explicit NAIF statement withdrawing 220930. NAIF could be told that
`pck/aareadme.txt` points to the relocated file.

## Test results (`tests/`)
- **Full backend suite, production kernels:** 319 passed, 12 skipped, exit 0. The skips are 10 tests that need the PGDA files and 2 kernel-setup tests that need the sandbox set as source.
- **Full backend suite, sandbox kernels:** 316 passed, 15 skipped, exit 0. The skips are 10 PGDA, V-02e, the two IAU_EARTH checks, and the 2 new frame tests that need the production set (the DE421 bitwise check and the installed-lock check). The source-scan and SPICE-call tests ran there and passed.
- **Installed kernels:** their SHA-256 values were identical before and after both runs.
